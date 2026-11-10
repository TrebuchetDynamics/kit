"""Task, decision and edit screens hosted by the fleet application's callbacks."""
import json
import re
import subprocess
import time

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Header, Input, Label, OptionList, Select, Static, TextArea

from pi_autowork import fleet_view, task_status
from pi_autowork.planning_ui import DecisionPrompt
from pi_autowork.tui_common import REFRESH, MenuBar, ReadScreen, action_text, read_input
from pi_autowork.tui_dialogs import Confirm


class DecisionScreen(ReadScreen, DecisionPrompt):
    """Read the current record off-thread; save through the CLI with its exact revision."""
    def __init__(self, runner, task, question=None):
        context = (f'Question (displayed inventory): {question.needs}\n'
                   f'Unblocks {question.unblocks} task(s). Suggested answer: {question.answer or "None supplied"}'
                   if question else 'Owner direction for this task.')
        store = runner.snapshot.store if runner.snapshot is not None else None
        dependents = sorted(t.id for t in store.tasks.values() if t.status == 'open' and task in t.depends_on) if store else []
        if runner.triage_failures:
            context += '\n\n' + fleet_view.recovery_detail(runner)
        context += '\nDependent tasks (committed snapshot): ' + (
            ', '.join(dependents) if dependents else ('None' if store else 'unavailable'))
        super().__init__(task, context, loading=True)
        self.runner_name, self.repo = runner.name, runner.repo
        self.owner_action_question = bool(question and (
            question.kind == 'owner_action' or (
                question.kind == 'outside' and question.needs == (
                    f'{task} requires owner action or recorded live authorization; '
                    'an unattended runner cannot run it.'))))
        self.record = None

    def on_mount(self):
        super().on_mount()
        self.refresh_record()

    def refresh_record(self):
        # Never rebind an edited draft to newer bytes; only replace an invalidated initial read.
        if self.record is not None or self.saving:
            return
        command, run, repo, task = self.app.command, self.app.runner_cmd, self.repo, self.task_id
        def load():
            result = run([command, 'tasks', 'show', task, '--worktree', repo],
                         capture_output=True, text=True, timeout=30)
            if result.returncode:
                raise ValueError((result.stderr or result.stdout or 'Task unavailable').strip())
            return json.loads(result.stdout)
        self.read('answer', (repo, task), load, self.loaded_record, self.load_failed)

    def load_failed(self, error):
        self.ready = False
        self.query_one('#decision-save', Button).disabled = True
        self.query_one('#decision-status', Static).update(f'Cannot answer: {error}. Close and reopen after refreshing.')

    def loaded_record(self, record):
        revision = record.get('record_revision') if isinstance(record, dict) else None
        if (not isinstance(revision, str) or len(revision) != 64
                or any(c not in '0123456789abcdef' for c in revision)
                or record.get('id') != self.task_id or record.get('status') != 'open'):
            self.load_failed('task is closed, missing, or its revision is unavailable')
            return
        self.record, self.ready = record, True
        previous = '\n'.join(line for line in record.get('notes', '').splitlines()
                             if line.startswith('- Owner decision:'))
        saved = previous.splitlines()[-1].partition(':')[2].strip() if previous else ''
        owner_action = record.get('ownership') == 'owner' and self.owner_action_question
        remaining = ('Owner-performed action remains; this runner must not execute it. '
                     'Another approval is not required. Record actual completion evidence or defer/cancel.'
                     if owner_action else '')
        self.query_one('#decision-context', TextArea).load_text(
            (f'Saved answer (working record): {saved}\n' if saved else '')
            + (remaining + '\n' if remaining else '')
            + f'{self.task_id}: {record.get("title", "")}\n'
            f'Current working record: {record.get("section", "unknown")} · '
            f'ownership {record.get("ownership", "unknown")} · live {record.get("live", "denied")}\n'
            + record.get('scope', '') + '\n\n' + self.context)
        if saved:
            # Restore the owner's actual saved direction, never the runner's suggestion.
            editor = self.query_one('#decision-text', TextArea)
            if not editor.text:
                editor.load_text(saved)
            self.query_one('#decision-title', Label).update(
                f'{"Owner action" if owner_action else "Update answer"} {self.task_id} · Saved answer in record')
        # A task in Needs decision is waiting for this answer. Default the save to move it
        # back to Now so the decision count falls and the runner can select it; the owner
        # can still choose keep-current or defer explicitly.
        if record.get('section') == 'Needs decision':
            self.query_one('#decision-section', Select).value = 'Now'
        self.query_one('#decision-save', Button).disabled = False
        self.query_one('#decision-text', TextArea).focus()
        self.query_one('#decision-status', Static).update(
            'Answer already saved; owner-performed action still outstanding. '
            'Save updates direction, not execution or completion.' if saved and owner_action else
            'Save commits this answer and the selected section locally, not unrelated edits. '
            'No push, live permission, hold release or verification.')

    def submit(self, value):
        runner = next((r for r in self.app.runners if (r.name, r.repo) == (self.runner_name, self.repo)), None)
        if self.app.view_only or runner is None or self.app.deletion_pending(runner, self.task_id):
            self.load_failed('task actions are no longer available')
            return
        argv = [self.app.command, 'tasks', 'decide', self.task_id, value['text'], self.repo,
                '--expect', self.record['record_revision'], '--commit']
        if value['section']:
            argv += ['--section', value['section']]
        self.saving = True
        self.query_one('#decision-text', TextArea).disabled = True
        self.query_one('#decision-section', Select).disabled = True
        self.query_one('#decision-save', Button).disabled = True
        self.query_one('#decision-cancel', Button).disabled = True
        self.query_one('#decision-status', Static).update('Saving and committing this answer… wait for the result.')
        self.app.execute(fleet_view.Action('e', f'Answer {self.task_id}', argv), on_complete=self.saved)

    def saved(self, ok, message):
        if not self.is_mounted:
            return
        self.saving = False
        if ok:
            self.dismiss(None)
        else:
            self.query_one('#decision-text', TextArea).disabled = False
            self.query_one('#decision-section', Select).disabled = False
            self.query_one('#decision-save', Button).disabled = False
            self.query_one('#decision-cancel', Button).disabled = False
            self.query_one('#decision-text', TextArea).focus()
            self.query_one('#decision-status', Static).update(
                f'Save failed: {message}. Draft kept; close and reopen if the record changed.')


class TextPrompt(ModalScreen[str]):
    """One line of the owner's words; Enter saves, Escape cancels."""
    BINDINGS = [Binding('escape', 'cancel', 'cancel')]
    DEFAULT_CSS = '''
    TextPrompt { align: center middle; }
    TextPrompt > Vertical { width: 80; height: auto; border: thick $accent; background: $surface; padding: 1 2; }
    '''

    def __init__(self, title, hint):
        super().__init__()
        self.title_text, self.hint = title, hint

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(Text(self.title_text, style='bold'))
            yield Label(Text(self.hint, style='dim'))
            yield Input(placeholder='Enter saves, Esc cancels', id='words')

    def on_input_submitted(self, event):
        self.dismiss(' '.join(event.value.split()) or None)

    def action_cancel(self):
        self.dismiss(None)


class PickSection(ModalScreen[str]):
    """Now, Next or Needs decision."""
    BINDINGS = [Binding('escape', 'cancel', 'cancel')]
    DEFAULT_CSS = '''
    PickSection { align: center middle; }
    PickSection > Vertical { width: 50; height: auto; border: thick $accent; background: $surface; padding: 1 2; }
    '''
    SECTIONS = ('Now', 'Next', 'Needs decision')

    def __init__(self, task):
        super().__init__()
        self.task_id = task

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f'Move {self.task_id} to:')
            yield OptionList(*self.SECTIONS)

    def on_option_list_option_selected(self, event):
        self.dismiss(self.SECTIONS[event.option_index])

    def action_cancel(self):
        self.dismiss(None)


class NewTask(ReadScreen, ModalScreen[dict]):
    """Simple task authoring; grouping and list labels are optional."""
    BINDINGS = [Binding('escape', 'cancel', 'cancel')]
    DEFAULT_CSS = '''
    NewTask { align: center middle; }
    NewTask > Vertical { width: 90; max-width: 100%; height: auto; max-height: 90%; border: thick $accent; background: $surface; padding: 1 2; }
    #new-task-fields { height: 1fr; }
    NewTask Input, NewTask Select { margin-bottom: 1; }
    NewTask Horizontal { height: auto; align-horizontal: right; }
    NewTask Button { margin-left: 2; }
    '''

    def __init__(self, goals, runner=None):
        super().__init__()
        self.goals, self.goal_runner = goals, read_input(runner)

    def on_mount(self):
        if self.goal_runner:
            runner = self.goal_runner
            self.read('goals', runner.repo, lambda: fleet_view.open_goals(runner), self.loaded_goals)

    def loaded_goals(self, goals):
        self.goals = goals
        self.query_one('#goal', Select).set_options([(f'{gid}  {title}'[:70], gid) for gid, title in goals])

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(Text('New task', style='bold'))
            with VerticalScroll(id='new-task-fields'):
                yield Input(placeholder='Title: the outcome, in a sentence', id='title')
                yield Input(placeholder='Short title (optional; derived from title)', id='short', max_length=40)
                yield Select([(f'{gid}  {title}'[:70], gid) for gid, title in self.goals], prompt='Goal (optional)', id='goal')
                yield Select([(name, name) for name in PickSection.SECTIONS], value='Next', allow_blank=False, id='section')
                yield Input(placeholder='Scope: the bounded change', id='scope')
                yield Input(placeholder='Acceptance: the test that proves it', id='acceptance')
                yield Input(placeholder='Checks: the exact verification command', id='checks')
                yield Input(placeholder='Touches (optional): leave blank to save a draft', id='touches')
            with Horizontal():
                yield Button('Add', variant='primary', id='add')
                yield Button('Cancel', id='cancel')

    def on_button_pressed(self, event):
        if event.button.id == 'cancel':
            self.dismiss(None)
            return
        value = {key: str(self.query_one(f'#{key}').value or '').strip()
                 for key in ('title', 'short', 'scope', 'acceptance', 'checks', 'touches')}
        goal = self.query_one('#goal', Select).value
        if not all(value[key] for key in ('title', 'scope', 'acceptance', 'checks')):
            self.notify('A new task needs title, scope, acceptance and checks.', severity='warning')
            return
        self.dismiss(dict(value, goal=goal if isinstance(goal, str) and goal else None, section=self.query_one('#section', Select).value))

    def action_cancel(self):
        self.dismiss(None)


def pending_edits(runner_cmd, command, repo):
    """Saved-edit snapshot through the CLI dry run: files and lifecycle, or unknown (None)."""
    try:
        result = runner_cmd([command, 'tasks', 'commit', '--dry-run', repo],
                            capture_output=True, text=True, timeout=30)
        if result.returncode:
            return None
        data = json.loads(result.stdout)
        files = data.get('files') if isinstance(data, dict) else None
        return data if isinstance(files, list) else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


class CommitEdits(ReadScreen, ModalScreen[dict]):
    """Commit the saved task edits that the runner cannot read yet. Only tasks/ paths move."""
    BINDINGS = [Binding('escape', 'cancel', 'cancel')]
    DEFAULT_CSS = '''
    CommitEdits { align: center middle; }
    CommitEdits > Vertical { width: 80; max-width: 100%; height: 90%; border: thick $accent; background: $surface; padding: 1 2; }
    #commit-body { height: 1fr; }
    #commit-diff { height: 8; }
    CommitEdits Input { margin: 1 0; }
    CommitEdits Horizontal { height: auto; align-horizontal: right; }
    CommitEdits Button { margin-left: 2; }
    '''

    def __init__(self, count, example, revision, diff):
        super().__init__()
        self.count, self.example = count, example
        self.revision, self.diff = revision, diff

    def compose(self) -> ComposeResult:
        with Vertical():
            with VerticalScroll(id='commit-body'):
                yield Label(Text('Commit saved answers', style='bold'))
                yield Static(Text(
                    f'{self.count} saved edit(s). Review this exact tasks/ diff; changed edits refuse the commit. '
                    'Other dirty files stay. No push or new live authorization. '
                    'An existing runner can select committed tasks.'))
                yield TextArea(self.diff, read_only=True, id='commit-diff')
                yield Input(value=self.example, id='commit-message', placeholder='Commit message')
            with Horizontal():
                yield Button('Commit', variant='primary', id='commit-save')
                yield Button('Cancel', id='commit-cancel')

    def on_mount(self):
        self.query_one('#commit-message', Input).focus()

    def on_button_pressed(self, event):
        if event.button.id == 'commit-cancel':
            self.dismiss(None)
            return
        message = ' '.join(str(self.query_one('#commit-message', Input).value or '').split())
        if not message:
            self.notify('A commit message is required.', severity='warning')
            return
        self.dismiss({'message': message, 'revision': self.revision})

    def action_cancel(self):
        self.dismiss(None)


class TasksScreen(ReadScreen, Screen):
    """One runner's open tasks in priority (section, then rank) order: filter them, re-sort them, clear or
    set aside a hold, answer the owner's questions, commit those answers. Refreshed like the main screen."""
    VIEW_NAMES = {'all': 'Open', 'working': 'Active', 'held': 'Blocker', 'waiting': 'Waiting',
                  'questions': 'Questions', 'decisions': 'Decisions', 'closed': 'Closed'}
    BINDINGS = [Binding('escape,q', 'app.pop_screen', 'Back', show=False),
                Binding('tab', 'step_view(1)', 'next view', show=False),
                Binding('shift+tab', 'step_view(-1)', 'previous view', show=False),
                *[Binding(str(n + 1), f'show_view("{view}")', view, show=False)
                  for n, view in enumerate(fleet_view.TASK_VIEWS)],
                *[Binding(key, f'task("{key}")', key, show=False) for key in 'udcabs'],
                Binding('n', 'new_task', 'New', show=False),
                Binding('x,delete', 'task("x")', 'Delete', show=False),
                Binding('g', 'plan("discuss")', 'Discuss', show=False),
                Binding('v', 'plan("investigate")', 'Investigate', show=False),
                Binding('e', 'decide', 'Decide', show=False),
                Binding('C', 'commit_tasks', 'Commit', show=False),
                Binding('i', 'snapshot_info', 'Snapshot info', show=False, priority=True)]
    DEFAULT_CSS = '''
    #task-views { height: auto; max-height: 3; padding: 0 1; }
    #task-freshness { height: auto; padding: 0 1; }
    #task-pending { height: auto; padding: 0 1; }
    #task-provenance { display: none; height: 3; border: none; padding: 0 1; }
    #tasks { height: 1fr; }
    #task-detail { height: auto; max-height: 7; padding: 0 1; border-top: solid $panel; }
    '''
    # State and Why are cut to what the terminal has left; Why goes first on a narrow one.
    FIXED, TEXT = ('#', 'Task'), ('State', 'Why')

    def __init__(self, runner_name, view='all'):
        super().__init__()
        # opener: the blockers report routes here, so its recorded questions can be answered.
        self.runner_name, self.view, self.rows, self.shown = runner_name, view, [], []
        self.history = []
        self.pending = None  # None: not read yet; []: nothing to commit

    def compose(self) -> ComposeResult:
        yield Header()
        yield MenuBar(id='menubar')
        yield Static(id='task-views')
        yield Static(id='task-freshness')
        yield Static(id='task-pending')
        yield TextArea(read_only=True, show_cursor=False, id='task-provenance')
        yield DataTable(id='tasks', cursor_type='row', zebra_stripes=True)
        yield Static(id='task-detail')

    def on_mount(self):
        self.title = f'{self.runner_name}: tasks'
        self.query_one('#tasks', DataTable).add_columns(*self.FIXED, *self.TEXT)
        self.refresh_tasks()
        self.read_pending()
        self.query_one('#tasks', DataTable).focus()
        self.set_interval(REFRESH, self.refresh_tasks)

    def on_resize(self, event):
        if self.is_mounted:
            self.call_after_refresh(self.refresh_tasks)  # cached rows only, at the new width

    def runner(self):
        return next((r for r in self.app.runners if r.name == self.runner_name), None)

    def view_rows(self, view):
        return self.history if view == 'closed' else fleet_view.task_view(self.rows, view)

    def on_screen_resume(self):
        # Coming back from the decision form is exactly when a new answer waits to be committed.
        if self.is_mounted:
            self.refresh_tasks()
            self.read_pending()

    def read_pending(self):
        """An answer is a record edit; the runner reads committed records, so say when one waits."""
        runner = self.runner()
        if runner is None or not runner.repo:
            return
        self.read('pending', (self.runner_name, runner.repo),
                  lambda: pending_edits(self.app.runner_cmd, self.app.command, runner.repo),
                  self.loaded_pending)

    def loaded_pending(self, files):
        # None is unknown (the dry run did not answer), not "nothing waits".
        self.pending = None if files is None else list(files['files'])
        self.pending_feedback = files.get('lifecycle') if files else None
        self.pending_snapshot = files
        self.show_pending()

    def show_pending(self):
        # A read can land while this screen is composing or leaving; a missing line is not an error.
        found = self.query('#task-pending')
        if not found:
            return
        line = found.first()
        files = self.pending
        if files is None:
            # Unknown is not clean: say the state is unread, do not imply nothing waits.
            line.display = True
            line.update(Text('Saved-edit state unknown; tasks commit --dry-run did not answer.', style='dim'))
            return
        if not files:
            line.update(Text(''))
            line.display = False
            return
        line.display = True
        feedback = getattr(self, 'pending_feedback', None) or task_status.edit_lifecycle('pending_commit')
        message = f"{len(files)} saved edit(s) not committed — {feedback['message']}  "
        body = Text(message, style='yellow')
        if self.app.view_only:
            body.append('View only: commit in a writable session.', style='yellow')
        else:
            body.append('C Commit', style='bold yellow')
        line.update(body)

    def action_commit_tasks(self):
        runner = self.runner()
        if runner is None or self.app.view_only or not self.pending:
            return
        snapshot = getattr(self, 'pending_snapshot', None) or {}
        revision = snapshot.get('pending_revision', '')
        if not re.fullmatch(r'[a-f0-9]{64}', revision):
            self.notify('Refresh pending edits; update Autowork if snapshot protection is unavailable.', severity='warning')
            return
        self.app.push_screen(CommitEdits(len(self.pending), 'tasks: record owner answers',
                                         revision, snapshot.get('diff', '')), self.commit_edits)

    def commit_edits(self, result):
        runner = self.runner()
        if not result or runner is None or self.app.view_only:
            return
        self.app.execute(
            fleet_view.Action('C', 'Commit task edits',
                              [self.app.command, 'tasks', 'commit', '--expect-pending', result['revision'],
                               '-m', result['message'], runner.repo]),
            on_complete=lambda _ok, _message: self.read_pending())

    def action_snapshot_info(self):
        info = self.query_one('#task-provenance', TextArea)
        info.display = not info.display
        (info if info.display else self.query_one('#tasks', DataTable)).focus()

    def refresh_tasks(self, follow=None):
        """``follow``: keep the cursor on this task wherever it moved (after a re-sort)."""
        runner = self.runner()
        self.rows = fleet_view.task_rows(runner, include_closed=True) if runner else []
        self.history = fleet_view.closed_task_rows(runner) if runner else []
        snapshot = fleet_view.snapshot_for(runner) if runner else None
        available = snapshot is not None and snapshot.counts is not None
        views = Text()
        for number, view in enumerate(fleet_view.TASK_VIEWS):
            count = len(self.view_rows(view)) if available else '?'
            label = f'{number + 1} {self.VIEW_NAMES[view]} {count}'
            views.append(('  ' if number else '') + label, style='bold reverse' if view == self.view else 'dim')
        views.append('   tab next view', style='dim')
        self.query_one('#task-views', Static).update(views)
        freshness = Text('Inventory ' + (snapshot.freshness if snapshot else 'unavailable'), style='bold')
        if snapshot:
            freshness.append(f' · execution {snapshot.engine_freshness}',
                             style='dim' if snapshot.engine_freshness == 'fresh' else 'yellow')
            if snapshot.freshness != 'fresh':
                freshness.append(' · captured ' + fleet_view.ago(max(0, int(time.time() - snapshot.captured_at))),
                                 style='yellow')
            if snapshot.errors:
                freshness.append(' · ' + ' '.join(snapshot.errors[0].split())[:100] + ' (i Info)', style='yellow')
        if runner and runner.display_deleted:
            freshness.append(f'\nDeletion pending commit: {len(runner.display_deleted)} record(s) (display only)', style='yellow')
        if runner and runner.display_recreated:
            freshness.append(f'\nRestored/recreated pending record(s): {len(runner.display_recreated)} (not committed inventory)',
                             style='yellow')
        self.query_one('#task-freshness', Static).update(freshness)
        table = self.query_one('#tasks', DataTable)
        previous_row = table.cursor_row
        current = follow or (self.current().task if self.current() else None)
        self.shown = self.view_rows(self.view)
        position = {row.task: number + 1 for number, row in enumerate(self.rows)}
        cells = [{'#': (str(position[row.task]), 'dim'), 'Task': (row.short, 'bold'),
                  'State': (row.state, fleet_view.state_style(row)),
                  'Why': (row.why, 'yellow' if row.question else 'dim')} for row in self.shown]
        # Names get the space previously spent on opaque IDs; IDs remain in details
        # and self.shown for selection/actions, including tasks with identical names.
        name_room = max(1, self.size.width - len(str(max(position.values(), default=0))) - 8)
        self.app.fill(table, cells, self.FIXED, self.TEXT, minimum=10, limits={'Task': name_room})
        tasks = [row.task for row in self.shown]
        target = tasks.index(current) if current in tasks else min(previous_row, len(tasks) - 1)
        if target >= 0 and table.cursor_row != target:
            table.move_cursor(row=target)
        self.show_task()

    def current(self):
        table = self.query_one('#tasks', DataTable)
        return self.shown[table.cursor_row] if 0 <= table.cursor_row < len(self.shown) else None

    def actions(self, row):
        runner = self.runner()
        if runner is None or row is None or self.app.view_only:
            return []
        return fleet_view.task_actions(runner, row, command=self.app.command, script=self.app.script,
                                       agent=self.app.agent)

    def show_task(self):
        row = self.current()
        text = Text()
        if row is None:
            runner = self.runner()
            snapshot = fleet_view.snapshot_for(runner) if runner else None
            if snapshot is None or snapshot.counts is None:
                text.append('Task inventory unavailable; task counts are unknown.\n', style='yellow')
            else:
                text.append('No task in this view.\n', style='dim')
        else:
            text.append(row.task, style='bold')
            text.append(f'  {row.short}\n')
            runner = self.runner()
            question = next((q for q in runner.questions if q.id == row.task), None) if runner else None
            snapshot = fleet_view.snapshot_for(runner) if runner else None
            record = snapshot.store.tasks.get(row.task) if snapshot and snapshot.store else None
            if question and question.kind == 'owner_action':
                action = record.scope if record and record.scope else 'Exact action not recorded; Enter opens the task.'
                text.append('You: ' + fleet_view.short(' '.join(action.split()), max(20, self.size.width - 8))
                            + '\n', style='bold yellow')
                result = '; '.join(record.acceptance) if record and record.acceptance else 'Required result not recorded.'
                text.append('Needed result: ' + fleet_view.short(' '.join(result.split()), max(20, self.size.width - 18))
                            + '\n')
                text.append('Approval is not completion. Enter: full task.\n', style='dim')
            elif question:
                text.append('Next: ' + (question.answer or question.needs) + '\n', style='yellow')
            elif row.why:
                text.append(('' if row.kind == 'closed' else 'Next: ') + row.why + '\n')
            text.append(f'{row.section} · {row.state}\n', style=fleet_view.state_style(row) or 'dim')
        keys = [(a.key, a.label) for a in self.actions(row)]
        if not self.app.view_only:
            keys.append(('n', 'New'))
            if row:
                keys = ([('e', 'Decide')] if row.kind != 'closed' else []) + [('g', 'Discuss'), ('v', 'Investigate')] + keys
        controls = ([('enter', 'Open')] if row else []) + keys + [('i', 'Info/Help'), ('esc', 'Back')]
        runner = self.runner()
        provenance = fleet_view.freshness(runner, detailed=True) if runner else 'Runner unavailable.'
        if row and row.why:
            provenance = row.why + '\n\n' + provenance
        provenance = 'Keys: ' + ' · '.join(f'{key} {label}' for key, label in controls) + '\n\n' + provenance
        info = self.query_one('#task-provenance', TextArea)
        if info.text != provenance:
            info.load_text(provenance)
        essential = ([('enter', 'Open')] if row else [])
        if row and row.kind != 'closed' and not self.app.view_only:
            essential.append(('e', 'Decide'))
        if self.pending and not self.app.view_only:
            essential.append(('C', 'Commit'))
        self.query_one('#menubar', MenuBar).show(essential + [('i', 'Info/Help'), ('esc', 'Back')])
        self.query_one('#task-detail', Static).update(text)

    def on_data_table_row_selected(self, event):
        row = self.current()
        if row is not None:
            self.app.push_screen(TaskScreen(self.runner_name, row.task, read_only=self.view == 'closed'))

    def action_plan(self, mode):
        runner, row = self.runner(), self.current()
        if runner and row and not self.app.view_only:
            self.app.open_plan(runner.repo, task=row.task, mode=mode)

    def action_decide(self):
        runner, row = self.runner(), self.current()
        if runner and row and row.kind != 'closed' and not self.app.view_only:
            self.app.decide_task(runner, row.task)

    def action_new_task(self):
        runner = self.runner()
        if runner is None or self.app.view_only:
            return

        def add(task):
            if not task:
                return
            argv = [self.app.command, 'tasks', 'add', '--title', task['title'], '--section', task['section']]
            for key in ('short', 'goal', 'scope', 'acceptance', 'checks', 'touches'):
                if task[key]:
                    argv += [f'--{key}', task[key]]
            self.app.execute(fleet_view.Action('n', f'New task in {runner.name}', argv + [runner.name]))
        self.app.push_screen(NewTask([], runner=runner), add)

    def on_data_table_row_highlighted(self, event):
        self.show_task()

    def action_show_view(self, view):
        self.view = view
        self.refresh_tasks()

    def action_step_view(self, step):
        views = fleet_view.TASK_VIEWS
        self.action_show_view(views[(views.index(self.view) + step) % len(views)])

    def action_task(self, key):
        row = self.current()
        if row is None:
            return
        action = next((a for a in self.actions(row) if a.key == key), None)
        if action is None:
            if key == 'a' and row.kind != 'closed':  # Answer, as on the fleet: no hold to set aside
                self.action_decide()
            return
        self.follow = row.task
        if key == 's':
            runner = self.runner()
            self.app.push_screen(PickSection(row.task), lambda section: section and self.app.execute(
                fleet_view.Action('s', f'Section {row.task}', [self.app.command, 'tasks', 'place', row.task, section, runner.name])))
            return
        if action.confirm:
            self.app.push_screen(Confirm(action.confirm), lambda yes: yes and self.app.execute(action))
        else:
            self.app.execute(action)


class TaskScreen(ReadScreen, Screen):
    """One task: its question and the runner's suggested answer, its whole task record and
    its worker's last actions. Answer it here; refreshed like the main screen."""
    BINDINGS = [Binding('escape,q', 'app.pop_screen', 'Back', show=False),
                Binding('s', 'section', 'Section', show=False),
                Binding('e', 'decide', 'Decide', show=False),
                Binding('g', 'plan("discuss")', 'Discuss', show=False),
                Binding('v', 'plan("investigate")', 'Investigate', show=False),
                *[Binding(key, f'answer("{key}")', key, show=False) for key in 'ohrwd']]
    DEFAULT_CSS = '''
    #task-scroll { height: 1fr; padding: 0 1; }
    #task-answers { height: auto; padding: 0 1; border-top: solid $panel; }
    '''

    def __init__(self, runner_name, task, *, read_only=False):
        super().__init__()
        self.runner_name, self.task_id = runner_name, task
        self.read_only, self.closed = read_only, False
        self.entry, self.recent = '', []

    def compose(self) -> ComposeResult:
        yield Header()
        yield MenuBar(id='menubar')
        with VerticalScroll(id='task-scroll'):
            yield Static(id='task-body')
        yield Static(id='task-answers')

    def on_mount(self):
        self.title = f'{self.runner_name}: {self.task_id}'
        self.refresh_tasks()
        self.set_interval(REFRESH, self.refresh_tasks)

    def runner(self):
        return next((r for r in self.app.runners if r.name == self.runner_name), None)

    def question(self):
        runner = self.runner()
        return next((q for q in runner.questions if q.id == self.task_id), None) if runner else None

    def answers(self):
        runner, question = self.runner(), self.question()
        if (runner is None or question is None or self.app.view_only or self.read_only
                or self.app.deletion_pending(runner, self.task_id)):
            return []
        return fleet_view.answers(runner, question, command=self.app.command)

    def refresh_tasks(self, follow=None):
        runner = read_input(self.runner())
        task = self.task_id
        if self.app.deletion_pending(runner, task):
            self.invalidate_read()
            self.entry, self.recent = '', []
            self.show_task()
            return
        self.show_task()
        if runner:
            return self.read('task-detail', (runner.repo, task),
                             lambda: (fleet_view.task_entry(runner, task), fleet_view.recent_actions(runner, task)),
                             self.loaded_task)

    def loaded_task(self, value):
        if not self.app.deletion_pending(self.runner(), self.task_id):
            self.entry, self.recent = value
        self.show_task()

    def show_task(self):
        runner, question = self.runner(), self.question()
        closed_row = next((r for r in fleet_view.closed_task_rows(runner) if r.task == self.task_id), None) if runner else None
        self.closed = closed_row is not None
        row = closed_row or (next((r for r in fleet_view.task_rows(runner, include_closed=True)
                                   if r.task == self.task_id), None) if runner else None)
        text = Text()
        text.append(self.task_id, style='bold')
        if row:
            text.append(f'  {row.short}\n')
            text.append(f'{row.section} · {row.state}\n', style=fleet_view.state_style(row) or 'dim')
        else:
            text.append('  (closed, or not in tasks/ now)\n', style='dim')
        if self.closed and row is not None and row.why:
            text.append(row.why + '\n')
        if question:
            text.append(f'\nQuestion for you ({question.effort}, unblocks {question.unblocks})\n', style='bold yellow')
            text.append(question.needs + '\n', style='yellow')
            if question.answer:
                text.append('The runner suggests: ', style='bold')
                text.append(question.answer + '\n', style='dim')
        elif row and row.why and not self.closed:
            text.append(row.why + '\n')
        pending_delete = self.app.deletion_pending(runner, self.task_id)
        if pending_delete:
            text.append('\nDeletion pending commit; task record/actions unavailable.\n', style='yellow')
        entry = '' if pending_delete else self.entry
        if entry:
            text.append('\nTask record (working tree; independent of committed inventory)\n', style='bold')
            text.append(entry + '\n')
        actions = [] if pending_delete else self.recent
        if actions:
            text.append('\nLast actions\n', style='bold')
            for line, age in actions:
                text.append(f'{fleet_view.ago(age):>9}  ', style='dim')
                text.append_text(action_text(line, max(20, self.size.width - 15)))
                text.append('\n')
        self.query_one('#task-body', Static).update(text)
        answers = self.answers()
        self.query_one('#menubar', MenuBar).show([(a.key, a.label) for a in answers]
                                                 + ([] if self.app.view_only or self.read_only or self.closed or pending_delete or row is None
                                                    else [('s', 'Section'), ('e', 'Decide')])
                                                 + ([] if self.app.view_only or pending_delete or row is None
                                                    else [('g', 'Discuss'), ('v', 'Investigate')])
                                                 + [('esc', 'Back')])
        explained = Text()  # what each answer does, under the task; the keys are in the menu bar
        for answer in answers:
            explained.append(f' {answer.label:<11}', style='bold')
            explained.append(f'{answer.explain}\n', style='dim')
        self.query_one('#task-answers', Static).update(explained)

    def action_answer(self, key):
        answer = next((a for a in self.answers() if a.key == key), None)
        if answer is None:
            return

        def run(words):
            if answer.needs_text and not words:
                return
            argv = [part.replace('{text}', words or '') for part in answer.argv]
            self.app.execute(fleet_view.Action(answer.key, f'{answer.label} {self.task_id}', argv))
        if answer.needs_text:
            self.app.push_screen(TextPrompt(f'{answer.label}: {self.task_id}', answer.explain), run)
        else:
            self.app.push_screen(Confirm(f'{answer.label} {self.task_id}: {answer.explain}?'), lambda yes: yes and run(''))

    def action_plan(self, mode):
        runner = self.runner()
        if (runner and not self.app.view_only and not self.app.deletion_pending(runner, self.task_id)
                and any(row.task == self.task_id for row in fleet_view.task_rows(runner, include_closed=True))):
            self.app.open_plan(runner.repo, task=self.task_id, mode=mode)

    def action_decide(self):
        runner = self.runner()
        if (runner and not self.app.view_only and not self.read_only and not self.closed
                and not self.app.deletion_pending(runner, self.task_id)
                and any(row.task == self.task_id for row in fleet_view.task_rows(runner))):
            self.app.decide_task(runner, self.task_id)

    def action_section(self):
        runner = self.runner()
        if (runner is None or self.app.view_only or self.read_only or self.closed
                or self.app.deletion_pending(runner, self.task_id)
                or not any(row.task == self.task_id for row in fleet_view.task_rows(runner))):
            return
        self.app.push_screen(PickSection(self.task_id), lambda section: section and self.app.execute(
            fleet_view.Action('s', f'Section {self.task_id}',
                              [self.app.command, 'tasks', 'place', self.task_id, section, runner.name])))
