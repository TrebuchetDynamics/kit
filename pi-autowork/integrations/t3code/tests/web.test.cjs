const { test } = require('node:test');
const assert = require('node:assert/strict');
const React = require('react');
const { act, create } = require('react-test-renderer');
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
globalThis.__t3PluginHost = { react: React, jsxRuntime: require('react/jsx-runtime') };
const subscribeRefresh = () => () => {};
async function render(api) {
  const { Panel } = await import('../dist/web.js');
  let tree;
  await act(async () => { tree = create(React.createElement(Panel, { api, subscribeRefresh })); });
  return tree;
}
const content = tree => JSON.stringify(tree.toJSON());
test('built native bundle registers its panel and palette command with real SDK exports', async () => {
  const { default: plugin } = await import('../dist/web.js');
  let panel; let command; let toast;
  plugin.activate({ injectStyles: css => assert.match(css, /focus-visible/), onDeactivate: () => {},
    rightPanel: { register: p => { panel = p; } }, commands: { register: c => { command = c; } }, toast: t => { toast = t; } });
  assert.equal(panel.name, 'overview'); assert.equal(command.id, 'refresh');
  command.run(); assert.match(toast.title, /Open Autowork/);
});
test('empty and failure states give actionable settings guidance without exposing error paths', async () => {
  const empty = await render({ rpc: { invoke: async () => [] } });
  assert.match(content(empty), /Add a repository/);
  await act(async () => empty.unmount());
  const failed = await render({ rpc: { invoke: async () => { throw new Error('/private/token=secret'); } } });
  assert.match(content(failed), /Unable to read Autowork/);
  assert.doesNotMatch(content(failed), /private/);
  assert.equal(failed.root.findByProps({ role: 'alert' }).type, 'div');
  await act(async () => failed.unmount());
});
test('repository/task selection and canonical next action render without HTML interpretation', async () => {
  const calls = [];
  const tree = await render({ rpc: { invoke: async (method, input) => {
    calls.push([method, input]);
    if (method === 'repositories') return [{ id: 'one', label: 'Project one' }, { id: 'two', label: 'Project two' }];
    return { repository: input.repository, capturedAt: '2026-01-01', state: 'Awaiting review', needs: 'Review evidence', blockers: ['review: missing check'], tasks: [{ id: 'A', title: '<script>Task</script>', state: 'Ready', why: 'Run checks' }], logs: 'Recent activity' };
  } } });
  assert.match(content(tree), /Review evidence/);
  const task = tree.root.findByProps({ className: 'aw-task' });
  await act(async () => task.props.onClick());
  assert.match(content(tree), /Run checks/);
  assert.equal(tree.root.findAllByType('script').length, 0);
  await act(async () => tree.root.findByType('select').props.onChange({ currentTarget: { value: 'two' } }));
  assert.deepEqual(calls.at(-1), ['snapshot', { repository: 'two' }]);
  await act(async () => tree.unmount());
});
test('loading state is announced and unmounted requests are ignored', async () => {
  let resolve; let calls = 0;
  const tree = await render({ rpc: { invoke: async method => {
    if (method === 'repositories') return [{ id: 'one', label: 'One' }];
    calls++; return new Promise(r => { resolve = r; });
  } } });
  assert.equal(tree.root.findByProps({ role: 'status' }).children.join(''), 'Reading repository work…');
  assert.equal(calls, 1);
  await act(async () => tree.unmount());
  await act(async () => resolve({ repository: 'one' }));
});
