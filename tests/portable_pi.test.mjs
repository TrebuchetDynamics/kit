import assert from 'node:assert/strict';
import test from 'node:test';
import register from '../adapters/pi.mjs';

test('Pi registers workflows and all 13 research commands; routes literal arguments', async () => {
  const commands = new Map();
  const messages = [];
  register({registerCommand: (name, handler) => commands.set(name, handler),
    sendUserMessage: (...args) => messages.push(args)});
  assert.equal(commands.size, 52);
  assert.equal(commands.has('orbi'), true);
  assert.equal(commands.has('push'), true);
  assert.equal(commands.has('unblock'), true);
  assert.equal(commands.has('apk-get'), true);
  assert.equal(commands.has('engineering'), false);
  assert.equal(commands.has('goal'), true);
  assert.equal(commands.has('autogoal'), false);
  for (const name of commands.keys()) assert.match(name, /^[a-z0-9]+(?:-[a-z0-9]+)*$/, name);
  const {readFile} = await import('node:fs/promises');
  const {fileURLToPath} = await import('node:url');
  const assertWorkflow = async (skill) => {
    const source = new URL(`../adapters/skills/${skill}/SKILL.md`, import.meta.url);
    const message = messages.at(-1)[0];
    assert.equal(message.includes(`Source: ${fileURLToPath(source)}\n`), true, skill);
    assert.equal(message.includes(await readFile(source, 'utf8')), true, skill);
    assert.equal(message.includes('(../COMMON.md)'), true, skill);
  };
  // Bare full-write, explicit audit, scoped update and read-only precedence
  // remain model inputs, not a shell mode parser or a deterministic editor.
  assert.equal(commands.has('agents-md-generator'), true);
  assert.equal(commands.has('agents_md_generator'), false);
  for (const args of ['', 'audit /tmp/target repo; no writes',
    'update only src/AGENTS.md; preserve human release approval',
    'read-only: revamp both AGENTS.md and CLAUDE.md']) {
    for (const idle of [true, false]) {
      await commands.get('agents-md-generator').handler(args, {isIdle: () => idle});
      await assertWorkflow('agents-md-generator');
      assert.equal(messages.at(-1)[0].endsWith(`User request (preserve scope and restrictions):\n${args}`), true);
      assert.deepEqual(messages.at(-1)[1], idle ? undefined : {deliverAs: 'followUp'});
    }
  }
  const raw = 'read-only\n$(literal); --no-push';
  assert.equal(commands.get('ponytail-debt').description, 'Publish issues for triggered shortcut debt');
  for (const args of ['', raw]) {
    await commands.get('ponytail-debt').handler(args, {isIdle: () => true});
    await assertWorkflow('ponytail-debt');
    assert.equal(messages.at(-1)[0].includes('trigger analysis and issue handoff'), true);
    assert.equal(messages.at(-1)[0].endsWith(`User request (preserve scope and restrictions):\n${args}`), true);
  }
  await commands.get('sakurai').handler(raw, {isIdle: () => true});
  await assertWorkflow('sakurai');
  assert.equal(messages.at(-1)[0].endsWith(raw), true);
  await commands.get('ui-taste').handler(raw, {isIdle: () => true});
  await assertWorkflow('ui-taste');
  assert.equal(messages.at(-1)[0].endsWith(raw), true);
  for (const name of ['brand-identity', 'styleseed']) {
    await commands.get(name).handler(raw, {isIdle: () => false});
    await assertWorkflow(name);
    assert.match(messages.at(-1)[0], new RegExp(`skills/${name}/SKILL\\.md`));
    assert.doesNotMatch(messages.at(-1)[0], /upstream\/|WORKFLOW\.md/);
    assert.equal(messages.at(-1)[0].endsWith(`User request (preserve scope and restrictions):\n${raw}`), true);
    assert.deepEqual(messages.at(-1)[1], {deliverAs: 'followUp'});
  }
  messages.length = 0;
  await commands.get('plan-with-me').handler(raw, {isIdle: () => true});
  await assertWorkflow('plan-with-me');
  assert.equal(messages[0][0].endsWith(raw), true);
  assert.equal(messages[0][1], undefined);
  messages.length = 0;
  const planningContract = await readFile(new URL('../skills/shared/RESEARCH-PLAN.md', import.meta.url), 'utf8');
  // Dispatch cannot know whether prior conversation supplies a concrete finding.
  // The loaded canonical workflow owns that decision; this is not a model test.
  for (const args of ['', ' \t\n ', 'implement offline support', `read-only: plan offline support\n${raw}`]) {
    for (const idle of [true, false]) {
      await commands.get('plan-for-me').handler(args, {isIdle: () => idle});
      await assertWorkflow('plan-for-me');
      const [message, delivery] = messages.at(-1);
      assert.equal(message.includes('../../../skills/plan-for-me/SKILL.md'), true);
      assert.equal(message.includes('Use the current host conversation as input'), true);
      assert.equal(message.includes(planningContract), true);
      assert.doesNotMatch(message, /Selected route:|No user objective was supplied/);
      assert.equal(message.endsWith(`User request (preserve scope and restrictions):\n${args}`), true);
      assert.deepEqual(delivery, idle ? undefined : {deliverAs: 'followUp'});
    }
  }
  messages.length = 0;
  await commands.get('autoresearch-debug').handler(raw, {isIdle: () => false});
  assert.match(messages[0][0], /Selected subcommand: debug/);
  assert.deepEqual(messages[0][1], {deliverAs: 'followUp'});
  // The actual shared boundary is loaded, not just command registration/skill metadata.
  const boundary = await readFile(new URL('../skills/shared/RESEARCH-PLAN.md', import.meta.url), 'utf8');
  for (const name of ['plan-with-me', 'plan-for-me', 'unslop', 'grill-me', 'autoresearch-plan']) {
    await commands.get(name).handler(raw, {isIdle: () => true});
    assert.equal(messages.at(-1)[0].includes(boundary), true, name);
    assert.equal(messages.at(-1)[0].endsWith(raw), true, name);
  }
  await commands.get('autoresearch').handler(`plan ${raw}`, {isIdle: () => true});
  assert.equal(messages.at(-1)[0].includes(boundary), true);
  assert.equal(messages.at(-1)[0].endsWith(`plan ${raw}`), true);
  await commands.get('grill-me').handler(raw, {isIdle: () => false});
  await assertWorkflow('plan-with-me');
  assert.match(messages.at(-1)[0], /Selected mode: challenge/);
  assert.equal(messages.at(-1)[0].endsWith(raw), true);
  assert.deepEqual(messages.at(-1)[1], {deliverAs: 'followUp'});
  const selectors = JSON.parse(await readFile(new URL('../skills/autoresearch/UPSTREAM.json', import.meta.url))).commands;
  assert.equal(selectors.length, 13);
  for (const selector of selectors) {
    await commands.get(`autoresearch-${selector}`).handler(raw, {isIdle: () => false});
    assert.match(messages.at(-1)[0], new RegExp(`Selected subcommand: ${selector}`));
    assert.equal(messages.at(-1)[0].endsWith(raw), true);
    assert.deepEqual(messages.at(-1)[1], {deliverAs: 'followUp'});
    await readFile(new URL(`../skills/autoresearch/upstream/${selector}.md`, import.meta.url));
  }
  for (const [name, skill] of Object.entries({
    'plan-with-me': 'plan-with-me', 'plan-for-me': 'plan-for-me', 'docs-sync': 'docs-sync',
    orbi: 'orbi', 'update-kit': 'update-kit', autoresearch: 'autoresearch',
    impeccable: 'impeccable', 'ui-taste': 'ui-taste', unslop: 'unslop',
    'beautify-github-readme': 'beautify-github-readme', 'grill-me': 'plan-with-me',
    lgtm: 'lgtm', goal: 'goal', unblock: 'unblock',
    'git-commit-push': 'git-commit-push', push: 'push',
    ponytail: 'ponytail', 'ponytail-review': 'ponytail-review', 'ponytail-audit': 'ponytail-audit',
    'ponytail-debt': 'ponytail-debt', 'ponytail-gain': 'ponytail-gain', 'ponytail-help': 'ponytail-help',
    'bug-harvest': 'bug-harvest', 'autonomous-codebase-improver': 'autonomous-codebase-improver',
    'split-folder': 'split-folder', 'unused-code': 'unused-code',
    'test-optimizer': 'test-optimizer', 'apk-get': 'apk-get', graphify: 'graphify',
    'writing-for-agents': 'writing-for-agents', 'agents-md-generator': 'agents-md-generator',
    grilling: 'grilling', 'grill-with-docs': 'grill-with-docs',
    'improve-codebase-architecture': 'improve-codebase-architecture',
    'ask-kit': 'ask-kit',
    'responsive-screenshots': 'responsive-screenshots',
    ...Object.fromEntries(selectors.map(selector => [`autoresearch-${selector}`, 'autoresearch'])),
  })) {
    await commands.get(name).handler('questions only', {isIdle: () => true});
    await assertWorkflow(skill);
  }
});

test('delivery help distinguishes current branch/upstream from main and preserves restrictions', async () => {
  const commands = new Map(), messages = [];
  register({registerCommand: (name, handler) => commands.set(name, handler),
    sendUserMessage: (...args) => messages.push(args)});
  assert.equal(messages.length, 0); // Registration never invokes delivery.
  assert.equal(commands.get('git-commit-push').description,
    'Commit current branch, sync and push its upstream.');
  assert.equal(commands.get('push').description,
    'Save this checkout, pull and deliver to main.');
  for (const name of ['git-commit-push', 'push']) {
    assert.ok(commands.get(name).description.length <= 60);
    for (const args of ['src/parser.py', 'src/parser.py; no push', 'audit; no writes']) {
      await commands.get(name).handler(args, {isIdle: () => true});
      assert.equal(messages.at(-1)[0].endsWith(
        `User request (preserve scope and restrictions):\n${args}`), true);
      assert.match(messages.at(-1)[0], new RegExp(`skills/${name}/SKILL\\.md`));
    }
  }
  for (const args of ['pull', 'sync', 'merge topic; no push', 'all']) {
    await commands.get('git-commit-push').handler(args, {isIdle: () => false});
    assert.equal(messages.at(-1)[0].endsWith(args), true);
    assert.deepEqual(messages.at(-1)[1], {deliverAs: 'followUp'});
  }
});

test('planning messages disclose interview detail only through the interactive owner', async () => {
  const {readFile} = await import('node:fs/promises');
  const {fileURLToPath} = await import('node:url');
  const root = fileURLToPath(new URL('../', import.meta.url)).replace(/\/$/, '');
  const commands = new Map(), messages = [];
  register({registerCommand: (name, handler) => commands.set(name, handler),
    sendUserMessage: (...args) => messages.push(args)});
  const boundary = await readFile(new URL('../skills/shared/RESEARCH-PLAN.md', import.meta.url), 'utf8');
  const raw = 'Plan offline support; read-only\n$(literal); --no-push';
  // Captured at 14e84eaf, identical request/idle state. Normalize only checkout
  // roots to <kit> so these UTF-8 initial-message comparisons travel with npm.
  // These are message bytes, NOT model latency or the total bytes read later.
  for (const [name, baseline] of Object.entries({
    'plan-for-me': 18423, 'plan-with-me': 18430, 'grill-me': 18456,
    unslop: 17783, 'autoresearch-plan': 19350, autoresearch: 19328,
  })) {
    const args = name === 'autoresearch' ? `plan ${raw}` : raw;
    for (const idle of [true, false]) {
      await commands.get(name).handler(args, {isIdle: () => idle});
      const [message, delivery] = messages.at(-1);
      const skill = name === 'grill-me' ? 'plan-with-me' : name.startsWith('autoresearch') ? 'autoresearch' : name;
      const workflow = await readFile(new URL(`../adapters/skills/${skill}/SKILL.md`, import.meta.url), 'utf8');
      assert.equal(message.split(boundary).length - 1, 1, name);
      assert.ok(message.indexOf(boundary) < message.indexOf(workflow), name);
      assert.ok(Buffer.byteLength(message.replaceAll(root, '<kit>'), 'utf8') < baseline, name);
      assert.doesNotMatch(message, /Turn the initial prompt into a concise working brief|Ask the highest-impact ready question|Stop questioning once/);
      assert.equal(message.endsWith(`User request (preserve scope and restrictions):\n${args}`), true);
      assert.deepEqual(delivery, idle ? undefined : {deliverAs: 'followUp'});
      if (name === 'grill-me') assert.match(message, /Selected mode: challenge/);
      if (name === 'autoresearch-plan') assert.match(message, /Selected subcommand: plan/);
    }
  }
  for (const [name, args] of [['docs-sync', raw], ['autoresearch-debug', raw],
    ['autoresearch', `debug ${raw}`], ['autoresearch', `planning ${raw}`]]) {
    await commands.get(name).handler(args, {isIdle: () => true});
    assert.equal(messages.at(-1)[0].includes(boundary), false, name);
  }
});

test('Update Kit dispatch is explicit-only, literal and queues while busy', async () => {
  const commands = new Map(), messages = [];
  register({registerCommand: (name, handler) => commands.set(name, handler),
    sendUserMessage: (...args) => messages.push(args)});
  const raw = '--only pi --hermes-home "space $(literal); home"\nno restarts';
  for (const idle of [true, false]) {
    await commands.get('update-kit').handler(raw, {isIdle: () => idle});
    const [message, delivery] = messages.at(-1);
    assert.match(message, /disable-model-invocation: true/);
    assert.equal(message.includes('../../../skills/update-kit/SKILL.md'), true);
    assert.equal(message.endsWith(raw), true);
    assert.deepEqual(delivery, idle ? undefined : {deliverAs: 'followUp'});
  }
});

test('Orbi dispatch forwards lifecycle arguments and queues in a busy session', async () => {
  const commands = new Map(), messages = [];
  register({registerCommand: (name, handler) => commands.set(name, handler),
    sendUserMessage: (...args) => messages.push(args)});
  const {readFile} = await import('node:fs/promises');
  const {fileURLToPath} = await import('node:url');
  const adapterFile = new URL('../adapters/skills/orbi/SKILL.md', import.meta.url);
  const adapter = await readFile(adapterFile, 'utf8');
  const workflowFile = new URL('../skills/orbi/SKILL.md', import.meta.url);
  const workflow = await readFile(workflowFile, 'utf8');
  const hostFile = new URL('../adapters/skills/COMMON.md', import.meta.url);
  const host = await readFile(hostFile, 'utf8');
  for (const raw of [
    '', 'status', 'status all', 'status all --json', 'status all --verbose', 'status all --work --json',
    'help', 'setup', 'setup --dry-run', 'start --dry-run',
    'setup --prepare-only', 'setup --prepare-only --dry-run',
    'setup --resume-setup --config "/tmp/literal $(config).toml"',
    'setup --prepare-only --resume-setup --config "/tmp/literal $(config).toml"',
    'setup --harness pi --pi-providers "/tmp/models $(literal).json" --pi-provider openai-codex --pi-model gpt-6.2-sol',
    'stop --dry-run', 'update --dry-run',
    'update --config "/missing literal $(file).toml"', 'start or stop?',
    'setup --dry-run --json\n--repo-dir "/tmp/checkout $(literal)"; no push',
    'start --dry-run --harness pi --pi-providers "/tmp/models $(literal).json" --pi-provider PUBLISHED_PROVIDER_ID --pi-model PUBLISHED_MODEL_ID',
  ]) {
    for (const idle of [true, false]) {
      const before = messages.length;
      await commands.get('orbi').handler(raw, {isIdle: () => idle});
      const [message, delivery] = messages.at(-1);
      // One dispatch is NOT a measured model request. The real host owns inference.
      assert.equal(messages.length - before, 1);
      for (const [body, source] of [[workflow, workflowFile], [host, hostFile]]) {
        assert.equal(message.split(body).length - 1, 1, `supplied once: ${source}`);
        assert.equal(message.includes(`Source: ${fileURLToPath(source)}\n`), true);
        assert.equal(message.includes(`Resolve its references from ${fileURLToPath(new URL('./', source))}.`), true);
      }
      assert.equal(message.includes(adapter), true);
      assert.equal(message.includes('../../../skills/orbi/SKILL.md'), true);
      assert.equal(message.includes(`Resolve the workflow references from ${fileURLToPath(new URL('./', adapterFile))}.`), true);
      assert.equal(message.endsWith('User request (preserve scope and restrictions):\n' + raw), true);
      assert.deepEqual(delivery, idle ? undefined : {deliverAs: 'followUp'});
    }
  }
  // The extension callback is dispatch only: it never shells out to a lifecycle command.
  const source = await readFile(new URL('../adapters/pi.mjs', import.meta.url), 'utf8');
  for (const forbidden of ['node:child_process', 'spawn(', 'execFile(', 'systemctl',
    'uv tool install', 'orbi_control']) {
    assert.equal(source.includes(forbidden), false, forbidden);
  }
});


test('Push loads its invoking-checkout main default and preserves narrower requests', async () => {
  const commands = new Map();
  const messages = [];
  register({registerCommand: (name, handler) => commands.set(name, handler),
    sendUserMessage: (...args) => messages.push(args)});
  await commands.get('push').handler('', {isIdle: () => true});
  assert.match(messages[0][0], /host-neutral Push workflow/);
  assert.match(commands.get('push').description, /pull and deliver to main/);
  assert.equal(messages[0][0].endsWith('User request (preserve scope and restrictions):\n'), true);
  assert.equal(messages[0][1], undefined);
  const restricted = 'dry run; no fetch; no sync; no commit; no push; only docs/';
  await commands.get('push').handler(restricted, {isIdle: () => false});
  assert.equal(messages[1][0].endsWith(restricted), true);
  assert.deepEqual(messages[1][1], {deliverAs: 'followUp'});
});

test('APK Get accepts a bare invocation without requiring an app path', async () => {
  const commands = new Map();
  const messages = [];
  register({registerCommand: (name, handler) => commands.set(name, handler),
    sendUserMessage: message => messages.push(message)});
  await commands.get('apk-get').handler('', {isIdle: () => true});
  assert.equal(messages.length, 1);
  assert.equal(messages[0].endsWith('User request (preserve scope and restrictions):\n'), true);
  const {readFile} = await import('node:fs/promises');
  const adapter = await readFile(new URL('../adapters/skills/apk-get/SKILL.md', import.meta.url), 'utf8');
  assert.equal(messages[0].includes(adapter), true);
});

test('npm package excludes local bytecode and keeps portable support files', async () => {
  const {execFileSync} = await import('node:child_process');
  const {fileURLToPath} = await import('node:url');
  const {cp, mkdir, mkdtemp, readFile, rm} = await import('node:fs/promises');
  const {tmpdir} = await import('node:os');
  const {join} = await import('node:path');
  const root = fileURLToPath(new URL('../', import.meta.url));
  const source = await mkdtemp(join(tmpdir(), 'portable inventory '));
  let packed;
  try {
    const manifest = JSON.parse(await readFile(join(root, 'package.json'), 'utf8'));
    for (const entry of ['package.json', ...manifest.files.filter(p => !p.startsWith('!'))]) {
      const target = join(source, entry);
      await mkdir(join(target, '..'), {recursive: true});
      try { await cp(join(root, entry), target, {recursive: true, filter: p => !p.includes('node_modules')}); }
      catch (error) { if (error.code !== 'ENOENT') throw error; }
    }
    packed = JSON.parse(execFileSync('npm', ['pack', '--ignore-scripts', '--offline', '--dry-run', '--json'], {cwd: source, encoding: 'utf8'}))[0];
  } finally {
    await rm(source, {recursive: true, force: true});
  }
  const paths = new Set(packed.files.map(f => f.path));
  for (const name of ['work', 'pending', 'blockers'])
    for (const root of ['skills', 'adapters/skills'])
      assert.equal([...paths].some(p => p.startsWith(`${root}/${name}/`)), false);
  assert.equal(paths.has('adapters/skills/grill-me/SKILL.md'), false);
  assert.equal(paths.has('adapters/skills/grill-me/PROTOCOL.md'), true);
  assert.equal([...paths].some(p => p.includes('__pycache__') || p.endsWith('.pyc')), false);
  assert.equal([...paths].some(p => p.startsWith('src/')), false);
  assert.equal(paths.has('paseo-plugin.json'), false);
  assert.deepEqual([...paths].filter(p => p.startsWith('skills/agents-md-generator/') && p.endsWith('/SKILL.md')),
    ['skills/agents-md-generator/SKILL.md']);
  assert.equal([...paths].some(p => p.startsWith('Src/')), false);
  for (const path of ['adapters/pi.mjs', 'adapters/skills/COMMON.md',
    'skills/docs-sync/scripts/docs.py', 'skills/autoresearch/upstream/plan.md', 'skills/impeccable/LICENSE',
    'skills/test-optimizer/SKILL.md', 'skills/engineering/local/test-suite-optimization/PROTOCOL.md',
    'skills/apk-get/SKILL.md', 'skills/apk-get/BUILD.md', 'skills/apk-get/scripts/verify_apk.py',
    'skills/state-machine/SKILL.md', 'skills/state-machine/PROTOCOL.md',
    'skills/state-machine/references/sources-and-example.md',
    'adapters/skills/state-machine/SKILL.md', 'adapters/skills/state-machine/agents/openai.yaml',
    'skills/agents-md-generator/SKILL.md', 'skills/agents-md-generator/UPSTREAM.json',
    'skills/agents-md-generator/upstream/PROTOCOL.md', 'skills/agents-md-generator/upstream/LICENSE',
    'skills/agents-md-generator/upstream/agents/openai.yaml',
    ...['discovery', 'merge-and-verify', 'output-template', 'tool-compatibility'].map(name =>
      `skills/agents-md-generator/upstream/references/${name}.md`),
    ...['', '.cmd', '.ps1', '.py', '.sh'].map(ext =>
      `skills/agents-md-generator/upstream/scripts/detect-agent-context${ext}`),
    'adapters/skills/agents-md-generator/SKILL.md', 'adapters/skills/agents-md-generator/agents/openai.yaml',
    'skills/shared/AGENT-INSTRUCTIONS.md',
    'skills/shared/COMMUNICATION.md', 'skills/unslop/SKILL.md',
    'adapters/skills/unslop/SKILL.md', 'adapters/skills/unslop/agents/openai.yaml',
    'skills/orbi/SKILL.md', 'skills/orbi/references/lifecycle.md',
    'skills/orbi/scripts/orbi_control.py',
    'skills/update-kit/SKILL.md', 'skills/update-kit/scripts/update_kit.py',
    'adapters/skills/update-kit/SKILL.md', 'adapters/skills/update-kit/agents/openai.yaml',
    'adapters/skills/orbi/SKILL.md', 'adapters/skills/orbi/agents/openai.yaml',
    'scripts/github_issues.py', 'scripts/worktree_paths.py', 'scripts/checkout_lock.py',
    'docs/github-native.md']) {
    assert.equal(paths.has(path), true, path);
  }
});

test('installed archive resolves portable references and commands without checkout files', async () => {
  const {execFileSync, spawnSync} = await import('node:child_process');
  const {cp, mkdir, mkdtemp, readdir, readFile, rename, rm, stat, writeFile} = await import('node:fs/promises');
  const {tmpdir} = await import('node:os');
  const {join} = await import('node:path');
  const {fileURLToPath, pathToFileURL} = await import('node:url');
  const scratch = await mkdtemp(join(tmpdir(), 'portable package '));
  try {
    const root = fileURLToPath(new URL('../', import.meta.url));
    // A private release fixture, not an install: include the declared resources and
    // sentinel future owners without redirecting any production public entry.
    const source = join(scratch, 'source');
    await mkdir(source);
    const manifest = JSON.parse(await readFile(join(root, 'package.json'), 'utf8'));
    for (const entry of ['package.json', ...manifest.files.filter(p => !p.startsWith('!'))]) {
      const target = join(source, entry);
      await mkdir(join(target, '..'), {recursive: true});
      // npm's include list may retain optional paths absent in this release.
      try { await cp(join(root, entry), target, {recursive: true, filter: p => !p.includes('node_modules')}); }
      catch (error) { if (error.code !== 'ENOENT') throw error; }
    }
    // Even accidental executor/native files in a source checkout must stay out of npm.
    await mkdir(join(source, 'src/kit_runtime'), {recursive: true});
    await writeFile(join(source, 'src/kit_runtime/private.py'), 'raise RuntimeError("native payload")\n');
    const archive = JSON.parse(execFileSync('npm', ['pack', '--ignore-scripts', '--offline', '--json', '--pack-destination', scratch],
      {cwd: source, encoding: 'utf8'}))[0];
    assert.equal(archive.files.some(f => f.path.startsWith('src/')), false);
    execFileSync('tar', ['-xzf', join(scratch, archive.filename), '-C', scratch]);
    const installed = join(scratch, 'package');
    const foreign = join(scratch, 'unrelated cwd');
    await mkdir(foreign);
    const openCodeInstaller = join(installed, 'adapters/opencode/install.py');
    const configHome = join(scratch, 'user config');
    const openCodeOptions = {
      cwd: foreign, encoding: 'utf8', env: {...process.env, XDG_CONFIG_HOME: configHome},
    };
    const unsafe = join(scratch, 'package-$1');
    await rename(installed, unsafe);
    try {
      const result = spawnSync('python3', [join(unsafe, 'adapters/opencode/install.py')], openCodeOptions);
      assert.equal(result.status, 1);
      assert.match(result.stderr, /Unsupported character in Kit checkout path/);
      await assert.rejects(stat(configHome), {code: 'ENOENT'});
    } finally {
      await rename(unsafe, installed);
    }
    const invalidHome = spawnSync('python3', [openCodeInstaller], {
      ...openCodeOptions, env: {...openCodeOptions.env, XDG_CONFIG_HOME: 'relative'},
    });
    assert.equal(invalidHome.status, 1);
    assert.match(invalidHome.stderr, /absolute path/);
    await assert.rejects(stat(join(foreign, 'relative')), {code: 'ENOENT'});
    for (let run = 0; run < 2; run++) {
      execFileSync('python3', [openCodeInstaller], openCodeOptions);
    }
    const commandsDir = join(configHome, 'opencode/commands');
    assert.deepEqual((await readdir(commandsDir)).sort(), ['plan-for-me.md', 'plan-with-me.md']);
    for (const name of ['plan-for-me', 'plan-with-me']) {
      const adapter = join(installed, 'adapters/skills', name, 'SKILL.md');
      const command = await readFile(join(commandsDir, `${name}.md`), 'utf8');
      assert.ok(command.includes(JSON.stringify(adapter)));
      assert.ok((await stat(adapter)).isFile());
    }
    const customCommand = join(commandsDir, 'plan-for-me.md');
    await writeFile(customCommand, 'Custom command\n');
    const conflict = spawnSync('python3', [openCodeInstaller], openCodeOptions);
    assert.equal(conflict.status, 1);
    assert.match(conflict.stderr, /Existing OpenCode command differs/);
    assert.equal(await readFile(customCommand, 'utf8'), 'Custom command\n');

    const batch = {issues: [{key: 'example', title: 'Example task',
      outcome: 'Bounded outcome', scope: 'Docs only', exclusions: 'No deployment',
      acceptance: 'Guide explains the contract', verification: 'Run focused tests', sources: 'Accepted request'}]};
    await writeFile(join(foreign, 'batch.json'), JSON.stringify(batch));
    const preview = JSON.parse(execFileSync('python3', [join(installed, 'scripts/github_issues.py'),
      '--repo', 'example/project', '--batch', join(foreign, 'batch.json')], {cwd: foreign, encoding: 'utf8'}));
    assert.equal(preview.preview, true);
    assert.equal(preview.remote_checked, false);
    assert.equal(preview.issues[0].key, 'example');
    let skillCount = 0;
    const walk = async (dir) => {
      for (const entry of await readdir(dir, {withFileTypes: true})) {
        const path = join(dir, entry.name);
        if (entry.isDirectory()) await walk(path);
        else if (entry.name.endsWith('.md')) {
          if (entry.name === 'SKILL.md') skillCount++;
          const text = await readFile(path, 'utf8');
          for (const match of text.matchAll(/\[[^\]]*\]\(([^)]+)\)/g)) {
            if (!match[1].includes('://') && !match[1].startsWith('#')) {
              await stat(fileURLToPath(new URL(match[1].split('#')[0], pathToFileURL(path))));
            }
          }
        }
      }
    };
    await walk(join(installed, 'adapters/skills'));
    // Follow moved interview links from the released payload, not the checkout.
    for (const relative of ['skills/shared/RESEARCH-PLAN.md', 'skills/plan-with-me/SKILL.md']) {
      const path = join(installed, relative);
      const text = await readFile(path, 'utf8');
      for (const match of text.matchAll(/\[[^\]]*\]\(([^)#]+)(?:#[^)]*)?\)/g)) {
        if (!match[1].includes('://')) await stat(fileURLToPath(new URL(match[1], pathToFileURL(path))));
      }
    }
    assert.equal(skillCount, 39);
    const sakurai = join(installed, 'skills/sakurai');
    assert.deepEqual((await readdir(sakurai)).sort(), ['SKILL.md', 'UPSTREAM.json']);
    assert.equal(await readFile(join(sakurai, 'SKILL.md'), 'utf8'),
      await readFile(join(root, 'skills/sakurai/SKILL.md'), 'utf8'));
    const sakuraiSource = JSON.parse(await readFile(join(sakurai, 'UPSTREAM.json'), 'utf8'));
    assert.equal(sakuraiSource.distribution, 'pointer-only');
    assert.deepEqual(sakuraiSource.files, {});
    const publicEntries = (await readdir(join(installed, 'adapters/skills'), {withFileTypes: true}))
      .filter(e => e.isDirectory()).map(e => e.name);
    assert.equal(publicEntries.includes('agents-md-generator'), true);
    assert.equal(publicEntries.includes('detect-agent-context'), false);
    const generator = join(installed, 'skills/agents-md-generator');
    const generatorText = await readFile(join(generator, 'SKILL.md'), 'utf8');
    const adapterText = await readFile(join(installed, 'adapters/skills/agents-md-generator/SKILL.md'), 'utf8');
    assert.match(adapterText, /disable-model-invocation: true/);
    assert.match(adapterText, /\.\.\/\.\.\/\.\.\/skills\/agents-md-generator\/SKILL\.md/);
    assert.match(await readFile(join(installed, 'adapters/skills/agents-md-generator/agents/openai.yaml'), 'utf8'),
      /allow_implicit_invocation: false/);
    // Walk the actual canonical guide's resource links in the released payload.
    for (const match of generatorText.matchAll(/\[[^\]]*\]\(([^)#]+)(?:#[^)]*)?\)/g)) {
      if (!match[1].includes('://')) await stat(join(generator, match[1]));
    }
    const target = join(foreign, 'target repo');
    await mkdir(join(target, 'src'), {recursive: true});
    await writeFile(join(target, 'AGENTS.md'), 'Use npm run stale. Human release approval required.\n');
    await writeFile(join(target, 'CLAUDE.md'), 'Read AGENTS.md. Use EnterWorktree. Use npm run stale.\n');
    await writeFile(join(target, 'src/AGENTS.md'), 'Schema source only.\n');
    await writeFile(join(target, 'src/AGENTS.override.md'), 'Scoped override.\n');
    const {symlink, lstat, readlink} = await import('node:fs/promises');
    await symlink('AGENTS.md', join(target, 'GEMINI.md'));
    await writeFile(join(target, 'untracked.txt'), 'unrelated content\n');
    const filesystem = async dir => {
      const result = [];
      const visit = async folder => {
        for (const name of (await readdir(folder)).sort()) {
          const path = join(folder, name), info = await lstat(path);
          result.push([path, info.mode, info.isSymbolicLink() ? await readlink(path) :
            info.isDirectory() ? 'directory' : (await readFile(path)).toString('base64')]);
          if (info.isDirectory()) await visit(path);
        }
      };
      await visit(dir);
      return result;
    };
    const beforeDetection = await filesystem(foreign);
    const detector = join(generator, 'upstream/scripts/detect-agent-context');
    const detected = JSON.parse(execFileSync(detector, ['--root', target, '--format', 'json'],
      {cwd: installed, encoding: 'utf8', timeout: 15000}));
    assert.equal(detected.root, target);
    assert.deepEqual(detected.instruction_sources.map(e => e.path),
      ['AGENTS.md', 'CLAUDE.md', 'GEMINI.md', 'src/AGENTS.md', 'src/AGENTS.override.md']);
    assert.equal(detected.warnings.some(w => w.includes('shadows src/AGENTS.md')), true);
    assert.deepEqual(await filesystem(foreign), beforeDetection);

    // Execute the packaged CommonJS helper under Kit's ESM package boundary.
    const mapScript = join(installed, 'skills/ponytail/upstream/scripts/ponytail-map.cjs');
    const map = execFileSync('node', [mapScript, installed], {encoding: 'utf8'});
    assert.match(map, /Codebase map/);
    for (const skill of ['ponytail', 'bug-harvest', 'autonomous-codebase-improver',
      'split-folder', 'unused-code']) {
      const pin = JSON.parse(await readFile(join(installed, `skills/${skill}/UPSTREAM.json`)));
      for (const resource of Object.values(pin.files)) {
        await stat(join(installed, `skills/${skill}`, resource.path));
      }
    }
    const listing = async dir => {
      const entries = [];
      const walkAll = async folder => {
        for (const entry of await readdir(folder, {withFileTypes: true})) {
          const path = join(folder, entry.name);
          entries.push(path);
          if (entry.isDirectory()) await walkAll(path);
        }
      };
      await walkAll(dir);
      return entries.sort();
    };
    const beforeLoad = await listing(installed);
    const commands = new Map();
    const messages = [];
    const {default: installedRegister} = await import(pathToFileURL(join(installed, 'adapters/pi.mjs')));
    installedRegister({registerCommand: (name, handler) => commands.set(name, handler),
      sendUserMessage: (...args) => messages.push(args)});
    assert.equal(commands.size, 52);
    assert.equal(commands.has('orbi'), true);
    assert.equal(commands.has('apk-get'), true);
    for (const [name, handler] of commands) {
      assert.match(name, /^[a-z0-9]+(?:-[a-z0-9]+)*$/, name);
      await handler.handler('read-only; $(literal)\nno push', {isIdle: () => false});
      assert.equal(messages.at(-1)[0].endsWith('read-only; $(literal)\nno push'), true, name);
      assert.deepEqual(messages.at(-1)[1], {deliverAs: 'followUp'});
    }
    for (const selector of JSON.parse(await readFile(join(installed, 'skills/autoresearch/UPSTREAM.json'))).commands) {
      await readFile(join(installed, `skills/autoresearch/upstream/${selector}.md`));
    }
    // The archive carries the adapter, canonical skill, helper and reference, and
    // loading the extension resolves them without shelling out to a lifecycle command.
    const installedAdapter = await readFile(join(installed, 'adapters/pi.mjs'), 'utf8');
    for (const forbidden of ['node:child_process', 'spawn(', 'execFile(', 'systemctl',
      'uv tool install', 'orbi_control']) {
      assert.equal(installedAdapter.includes(forbidden), false, forbidden);
    }
    const canonicalOrbi = await readFile(join(installed, 'skills/orbi/SKILL.md'), 'utf8');
    await commands.get('orbi').handler('update --dry-run', {isIdle: () => true});
    assert.equal(messages.at(-1)[0].includes(canonicalOrbi), true);
    assert.equal(messages.at(-1)[0].includes(await readFile(join(installed, 'adapters/skills/COMMON.md'), 'utf8')), true);
    assert.equal(messages.at(-1)[0].includes(`Source: ${join(installed, 'skills/orbi/SKILL.md')}\n`), true);
    await readFile(join(installed, 'skills/orbi/references/lifecycle.md'));
    await readFile(join(installed, 'skills/orbi/scripts/orbi_control.py'));
    assert.match(canonicalOrbi, /<this-skill>\/scripts\/orbi_control\.py/);
    // Loading the extension and dispatching every command installs nothing.
    assert.deepEqual(await listing(installed), beforeLoad);
    // Dispatch only loads text; no target rewrites on registration or any mode.
    for (const request of ['', `audit ${target}`, `update ${target} only src/AGENTS.md`,
      `read-only: revamp ${target}`]) {
      await commands.get('agents-md-generator').handler(request, {isIdle: () => true});
      assert.equal(messages.at(-1)[0].includes(adapterText), true);
      assert.equal(messages.at(-1)[0].includes(join(installed, 'adapters/skills/agents-md-generator')), true);
      assert.equal(messages.at(-1)[0].endsWith(`User request (preserve scope and restrictions):\n${request}`), true);
    }
    assert.deepEqual(await filesystem(foreign), beforeDetection);

    // Missing authority must surface the concrete package error, not send a
    // weakened/path-only planning prompt. Restore the fixture before cleanup.
    const contract = join(installed, 'skills/shared/RESEARCH-PLAN.md');
    await rename(contract, contract + '.missing');
    const sent = messages.length;
    try {
      await assert.rejects(commands.get('plan-for-me').handler('read-only', {isIdle: () => true}),
        error => error.code === 'ENOENT' && error.path === contract);
      assert.equal(messages.length, sent);
    } finally {
      await rename(contract + '.missing', contract);
    }

  } finally {
    await rm(scratch, {recursive: true, force: true});
  }
});

test('removed skills are neither commands nor discoverable resources; blockers is literal planning input', async () => {
  const commands = new Map(), messages = [];
  register({registerCommand: (name, handler) => commands.set(name, handler),
    sendUserMessage: (...args) => messages.push(args)});
  const {existsSync} = await import('node:fs');
  for (const name of ['work', 'pending', 'blockers']) {
    assert.equal(commands.has(name), false, name);
    for (const root of ['skills', 'adapters/skills'])
      assert.equal(existsSync(new URL(`../${root}/${name}/`, import.meta.url)), false, `${root}/${name}`);
  }
  for (const idle of [true, false]) {
    const raw = 'blockers ./repo --no-write\n$(literal)';
    await commands.get('plan-with-me').handler(raw, {isIdle: () => idle});
    assert.match(messages.at(-1)[0], /adapters\/skills\/plan-with-me\/SKILL.md/);
    assert.equal(messages.at(-1)[0].endsWith(raw), true);
    assert.deepEqual(messages.at(-1)[1], idle ? undefined : {deliverAs: 'followUp'});
  }
});
