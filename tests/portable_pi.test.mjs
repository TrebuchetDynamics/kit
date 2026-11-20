import assert from 'node:assert/strict';
import test from 'node:test';
import register from '../adapters/pi.mjs';

test('Pi registers workflows and all 13 research commands; routes literal arguments', async () => {
  const commands = new Map();
  const messages = [];
  register({registerCommand: (name, handler) => commands.set(name, handler),
    sendUserMessage: (...args) => messages.push(args)});
  assert.equal(commands.size, 48);
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
  const raw = 'read-only\n$(literal); --no-push';
  await commands.get('ui-taste').handler(raw, {isIdle: () => true});
  await assertWorkflow('ui-taste');
  assert.equal(messages.at(-1)[0].endsWith(raw), true);
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
    'writing-for-agents': 'writing-for-agents',
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
  for (const raw of [
    'setup --dry-run --json\n--repo-dir "/tmp/checkout $(literal)"; no push',
    'start --dry-run --harness pi --pi-providers "/tmp/models $(literal).json" --pi-provider PUBLISHED_PROVIDER_ID --pi-model PUBLISHED_MODEL_ID',
  ]) {
    for (const idle of [true, false]) {
      await commands.get('orbi').handler(raw, {isIdle: () => idle});
      const [message, delivery] = messages.at(-1);
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


test('Push loads its repo-wide default and preserves narrower requests', async () => {
  const commands = new Map();
  const messages = [];
  register({registerCommand: (name, handler) => commands.set(name, handler),
    sendUserMessage: (...args) => messages.push(args)});
  await commands.get('push').handler('', {isIdle: () => true});
  assert.match(messages[0][0], /host-neutral Push workflow/);
  assert.match(commands.get('push').description, /pull main/);
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
  for (const name of ['autowork', 'work', 'pending', 'blockers'])
    for (const root of ['skills', 'adapters/skills'])
      assert.equal([...paths].some(p => p.startsWith(`${root}/${name}/`)), false);
  assert.equal(paths.has('adapters/skills/grill-me/SKILL.md'), false);
  assert.equal(paths.has('adapters/skills/grill-me/PROTOCOL.md'), true);
  assert.equal([...paths].some(p => p.includes('__pycache__') || p.endsWith('.pyc')), false);
  assert.equal([...paths].some(p => p.startsWith('pi-autowork/') || p.startsWith('src/')), false);
  assert.equal(paths.has('paseo-plugin.json'), false);
  assert.equal([...paths].some(p => p.startsWith('Src/')), false);
  for (const path of ['adapters/pi.mjs', 'adapters/skills/COMMON.md',
    'skills/docs-sync/scripts/docs.py', 'skills/autoresearch/upstream/plan.md', 'skills/impeccable/LICENSE',
    'skills/test-optimizer/SKILL.md', 'skills/engineering/local/test-suite-optimization/PROTOCOL.md',
    'skills/apk-get/SKILL.md', 'skills/apk-get/BUILD.md', 'skills/apk-get/scripts/verify_apk.py',
    'skills/state-machine/SKILL.md', 'skills/state-machine/PROTOCOL.md',
    'skills/state-machine/references/sources-and-example.md',
    'adapters/skills/state-machine/SKILL.md', 'adapters/skills/state-machine/agents/openai.yaml',
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
  const {execFileSync} = await import('node:child_process');
  const {cp, mkdir, mkdtemp, readdir, readFile, rm, stat, writeFile} = await import('node:fs/promises');
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
    await mkdir(join(source, 'pi-autowork/pi_autowork'), {recursive: true});
    await writeFile(join(source, 'pi-autowork/pi_autowork/fixture.py'), 'raise RuntimeError("retired executor")\n');
    await mkdir(join(source, 'src/kit_runtime'), {recursive: true});
    await writeFile(join(source, 'src/kit_runtime/private.py'), 'raise RuntimeError("native payload")\n');
    const archive = JSON.parse(execFileSync('npm', ['pack', '--ignore-scripts', '--offline', '--json', '--pack-destination', scratch],
      {cwd: source, encoding: 'utf8'}))[0];
    assert.equal(archive.files.some(f => f.path.startsWith('pi-autowork/') || f.path.startsWith('src/')), false);
    execFileSync('tar', ['-xzf', join(scratch, archive.filename), '-C', scratch]);
    const installed = join(scratch, 'package');
    const foreign = join(scratch, 'unrelated cwd');
    await mkdir(foreign);
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
    assert.equal(skillCount, 35);
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
    assert.equal(commands.size, 48);
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
    await readFile(join(installed, 'skills/orbi/references/lifecycle.md'));
    await readFile(join(installed, 'skills/orbi/scripts/orbi_control.py'));
    assert.match(canonicalOrbi, /<this-skill>\/scripts\/orbi_control\.py/);
    // Loading the extension and dispatching every command installs nothing.
    assert.deepEqual(await listing(installed), beforeLoad);
  } finally {
    await rm(scratch, {recursive: true, force: true});
  }
});

test('removed skills are neither commands nor discoverable resources; blockers is literal planning input', async () => {
  const commands = new Map(), messages = [];
  register({registerCommand: (name, handler) => commands.set(name, handler),
    sendUserMessage: (...args) => messages.push(args)});
  const {existsSync} = await import('node:fs');
  for (const name of ['autowork', 'work', 'pending', 'blockers']) {
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
