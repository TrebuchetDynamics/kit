// Constant source, not a runtime asset: the official plugin compiler bundles this string.
// This is only a transport/ownership adapter. Planning policy and persistence stay upstream.
export const PLANNING_BRIDGE = String.raw`
import importlib.util
import inspect
import json
import os
from pathlib import Path
import sys

MAX_REQUEST = 256 * 1024
MAX_RESPONSE = 4 * 1024 * 1024
MAX_TEXT = 64000
MAX_SESSIONS = 32
protocol = sys.stdout.buffer
# Controller diagnostics must never become protocol records (or frontend errors).
sys.stdout = sys.stderr

class Refusal(Exception):
    pass

def require(condition, message):
    if not condition:
        raise Refusal(message)

def text(value, limit=65536):
    require(isinstance(value, str) and len(value.encode('utf-8')) <= limit,
            'planning text exceeds limit or is invalid')
    return value

def main():
    source, state = (Path(p) for p in sys.argv[1:3])
    require(source.is_absolute() and state.is_absolute(), 'absolute runtime paths required')
    source = source.resolve(strict=True)
    require(not state.is_relative_to(source), 'planning state overlaps source')
    spec = importlib.util.spec_from_file_location('_paseo_autowork_bootstrap', source / 'scripts/autowork_bootstrap.py')
    bootstrap = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = bootstrap
    spec.loader.exec_module(bootstrap)
    planning = bootstrap.load(source, 'pi_autowork.planning')
    hubs = bootstrap.load(source, 'pi_autowork.planning_hub')
    for module, name in ((planning, 'planning'), (hubs, 'planning_hub')):
        require(Path(module.__file__).resolve() == (source / 'pi-autowork/pi_autowork' / (name + '.py')).resolve(),
                'controller source mismatch')
    hub = hubs.PlanningHub(max_text=MAX_TEXT)
    owned = {}
    applied = set()

    def snapshot(repo, sid):
        value = hub.snapshot(repo, sid)
        require(isinstance(value, dict), 'owned planning turn unavailable')
        status = value.get('status')
        if status == 'failed':
            return dict(status='failed', text='Planning turn failed; inspect retained planning records.')
        result = dict(value.get('result') or {})
        if 'text' in result:
            result['text'] = str(result['text'])[-MAX_TEXT:]
        return dict(status='applied' if sid in applied else status,
                    text=str(value.get('text', ''))[-MAX_TEXT:], result=result)

    def dispatch(request):
        require(isinstance(request, dict), 'invalid planning request')
        method = request.get('method')
        fields = {
            'start': {'repo', 'objective', 'mode', 'task', 'model'}, 'send': {'repo', 'sessionId', 'message'},
            'state': {'repo', 'sessionId'}, 'preview': {'repo', 'sessionId'},
            'history': {'repo', 'sessionId'}, 'roadmap': {'repo', 'sessionId'},
            'apply': {'repo', 'sessionId', 'revision'}, 'steer': {'repo', 'sessionId', 'message'},
            'cancel': {'repo', 'sessionId'},
        }
        require(isinstance(method, str) and method in fields, 'unknown planning method')
        require(set(request) == fields[method] | {'id', 'method'}, 'invalid planning request fields')
        repo = text(request['repo'], 16384)
        require(Path(repo).is_absolute() and str(Path(repo).resolve(strict=True)) == repo,
                'canonical repository required')
        require(not state.is_relative_to(Path(repo)) and not Path(repo).is_relative_to(state),
                'planning state overlaps repository')
        if method == 'start':
            objective = text(request['objective'])
            require(len(owned) < MAX_SESSIONS, 'planning session limit reached; reload after closing')
            require(sum(snapshot(r, s)['status'] == 'running' for s, (r, _) in owned.items()) < 4,
                    'four planning turns are running; cancel or wait for one')
            mode = text(request['mode'], 32)
            require(mode in ('plan', 'discuss', 'investigate'), 'planning mode must be plan, discuss or investigate')
            task = text(request['task'], 160) or None
            model = text(request['model'], 200) or None
            require(task is None or (task.isprintable() and not task.isspace()), 'invalid task scope')
            require(model is None or (model.isprintable() and not any(c.isspace() for c in model)), 'invalid model')
            controller = hub.controller(repo, lambda r: planning.Planner(r, state_root=state,
                                                        pi=sys.argv[3] if len(sys.argv) > 3 else 'pi'))
            require(str(Path(controller.repo).resolve()) == repo, 'canonical main repository required')
            accepted = inspect.signature(controller.create).parameters
            require(model is None or 'model' in accepted, 'installed Autowork cannot pin a planning model')
            options = {'objective': objective}
            if task is not None or 'task' in accepted:
                options['task'] = task
            if mode != 'plan' or 'mode' in accepted:
                options['mode'] = mode
            if model is not None:
                options['model'] = model
            meta = controller.create(**options)
            sid = meta['id']
            require(isinstance(sid, str) and len(sid) == 32 and all(c in '0123456789abcdef' for c in sid)
                    and sid not in owned, 'invalid new planning session')
            owned[sid] = (repo, controller)
            hub.start(repo, controller, sid, objective)
            return dict(id=sid, status='running')
        sid = request['sessionId']
        require(isinstance(sid, str) and sid in owned, 'unknown owned planning session')
        registered, controller = owned[sid]
        require(registered == repo, 'planning session repository mismatch')
        if method == 'state':
            return snapshot(repo, sid)
        if method == 'cancel':
            hub.cancel(repo, sid)
            return dict(id=sid, status='cancellation-requested')
        if method == 'steer':
            message = text(request['message'])
            require(bool(message), 'steering message required')
            return controller.steer(sid, message)
        if method == 'history':
            return controller.history(sid)
        require(snapshot(repo, sid)['status'] != 'running',
                'planning session is running; use state, steer or cancel')
        if method == 'send':
            require(sid not in applied, 'applied planning session is read-only')
            message = text(request['message'])
            require(bool(message), 'follow-up message required')
            hub.start(repo, controller, sid, message)
            return dict(id=sid, status='running')
        if method == 'apply':
            revision = text(request['revision'], 4096)
            require(bool(revision), 'review revision required')
            result = controller.apply(sid, revision)
            applied.add(sid)
            return result
        # Fixed method allowlist above; never dispatch a caller-selected attribute.
        if method == 'preview':
            return controller.preview(sid)
        return controller.roadmap(sid)

    try:
        while True:
            line = sys.stdin.buffer.readline(MAX_REQUEST + 1)
            if not line:
                break
            if len(line) > MAX_REQUEST or not line.endswith(b'\n'):
                return 1
            ident = None
            try:
                request = json.loads(line.decode('utf-8'))
                require(isinstance(request, dict), 'invalid planning request')
                ident = request.get('id')
                require(isinstance(ident, str) and ident.isascii() and ident.isdigit() and len(ident) <= 16,
                        'invalid planning request id')
                response = dict(id=ident, result=dispatch(request))
            except Refusal as error:
                response = dict(id=ident, error=str(error))
            except Exception:
                response = dict(id=ident, error='Planning operation failed; inspect retained planning records.')
            encoded = json.dumps(response, ensure_ascii=False, separators=(',', ':')).encode('utf-8') + b'\n'
            if len(encoded) > MAX_RESPONSE:
                encoded = (json.dumps(dict(id=ident, error='Planning response exceeds output limit.')) + '\n').encode()
            protocol.write(encoded)
            protocol.flush()
    finally:
        # Upstream close sets every owned cancellation event and joins its turn pool.
        # The host bounds this wait and reports uncertainty if termination is needed.
        hub.close()
    return 0

try:
    code = main()
except BaseException:
    code = 1
sys.exit(code)
`;
