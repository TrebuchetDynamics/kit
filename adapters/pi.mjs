import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const skillsRoot = new URL('./skills/', import.meta.url);
const protocols = JSON.parse(await readFile(new URL('../skills/autoresearch/UPSTREAM.json', import.meta.url), 'utf8')).commands;
const workflows = {
  'plan-with-me': ['plan-with-me', 'Ask questions and plan together'],
  'plan-for-me': ['plan-for-me', 'Investigate, decide and save the plan'],
  unslop: ['unslop', 'Turn a UI design audit into GitHub issues for Orbi'],
  'docs-sync': ['docs-sync', 'Maintain documentation and GitHub issue handoffs'],
  orbi: ['orbi', 'Prepare, update, start, inspect or stop one Orbi deployment'],
  'update-kit': ['update-kit', 'Refresh upstream Kit and reinstall the suite'],
  autoresearch: ['autoresearch', 'Run bounded research or experiments'],
  'apk-get': ['apk-get', 'Find the app, build an ARM64 release APK and upload with s3upload'],
  'test-optimizer': ['test-optimizer', 'Reduce redundant tests while preserving real regression protection'],
  graphify: ['graphify', 'Query a local Graphify code graph before wide reading'],
  'writing-for-agents': ['writing-for-agents', 'Write and prune skills, AGENTS.md and agent docs'],
  'agents-md-generator': ['agents-md-generator', 'Reconcile repository instructions against evidence'],
  'ask-kit': ['ask-kit', 'Find the skill that fits the situation'],
  'responsive-screenshots': ['responsive-screenshots', 'Capture pages at breakpoints and check overflow'],
  grilling: ['grilling', 'Stress-test a plan or idea with rounds of questions'],
  'grill-with-docs': ['grill-with-docs', 'Grill a plan and record decisions as ADRs and terms'],
  'improve-codebase-architecture': ['improve-codebase-architecture', 'Find deepening opportunities and report them visually'],
  'bug-harvest': ['bug-harvest', 'Hunt evidence-backed bugs within scope and limits'],
  'autonomous-codebase-improver': ['autonomous-codebase-improver', 'Improve a repository through reviewed bounded slices'],
  'split-folder': ['split-folder', 'Split one named folder without changing behavior'],
  'unused-code': ['unused-code', 'Publish proven dead-code cleanup issues'],
  ponytail: ['ponytail', 'Choose Ponytail simplicity guidance or level'],
  'ponytail-review': ['ponytail-review', 'Review a change and connected code'],
  'ponytail-audit': ['ponytail-audit', 'Audit a repository or folder'],
  'ponytail-debt': ['ponytail-debt', 'Publish issues for triggered shortcut debt'],
  'ponytail-gain': ['ponytail-gain', 'Show upstream Ponytail benchmark results'],
  'ponytail-help': ['ponytail-help', 'Explain bundled Ponytail commands'],
  impeccable: ['impeccable', 'Improve interface design'],
  'ui-taste': ['ui-taste', 'Improve UI taste with Uizze playbooks'],
  'forever-components': ['forever-components', 'Find and adapt selected Forever components.'],
  'procedural-drawing': ['procedural-drawing', 'Draw CPU-rendered illustrations from scene code'],
  genart: ['genart', 'Create and verify seeded generative art'],
  tastemaker: ['tastemaker', 'Study visual references, audit UI or brief comps'],
  dembrandt: ['dembrandt', 'Apply an existing design language or measure site tokens'],
  genjutsu: ['genjutsu', 'Design interaction motion for an interface'],
  'motion-graphics': ['motion-graphics', 'Build and render seekable motion graphics'],
  'brand-identity': ['brand-identity', 'Compare brand directions and build the selected kit'],
  styleseed: ['styleseed', 'Create and maintain a project design system'],
  sakurai: ['sakurai', "Find Sakurai's game-design guidance upstream"],
  'beautify-github-readme': ['beautify-github-readme', 'Redesign or audit a GitHub README'],
  'grill-me': ['plan-with-me', 'Plan With Me challenge mode (compatibility)', 'challenge'],
  lgtm: ['lgtm', 'Continue the last approved action'],
  goal: ['goal', 'Keep one objective alive until evidence proves it done'],
  unblock: ['unblock', 'Resolve blocked GitHub work without releasing pauses'],
  'git-commit-push': ['git-commit-push', 'Commit current branch, sync and push its upstream.'],
  push: ['push', 'Save this checkout, pull and deliver to main.'],
};

/** Native Pi command adapter. No subprocess, permission changes or install hooks. */
export default function register(pi) {
  const entries = Object.entries(workflows).map(([command, [skill, description, mode]]) => ({command, skill, description, mode}));
  for (const protocol of protocols) {
    entries.push({command: `autoresearch-${protocol}`, skill: 'autoresearch',
      description: `Autoresearch ${protocol}`, protocol});
  }
  for (const {command, skill, description, protocol, mode} of entries) {
    pi.registerCommand(command, {
      description,
      handler: async (args, ctx) => {
        const [first] = (args || '').trim().split(/\s+/);
        const target = skill;
        const file = new URL(`${target}/SKILL.md`, skillsRoot);
        const body = await readFile(file, 'utf8');
        const planning = ['plan-for-me', 'plan-with-me', 'unslop'].includes(target)
          || (target === 'autoresearch' && (protocol === 'plan' || (!protocol && first === 'plan')));
        const contract = new URL('../skills/shared/RESEARCH-PLAN.md', import.meta.url);
        const boundary = planning
          ? `Planning contract. Source: ${fileURLToPath(contract)}\n`
            + `Resolve its references from that directory.\n\n${await readFile(contract, 'utf8')}\n\n`
          : '';
        // Supply Orbi's common path up front; the host still interprets and invokes tools.
        let supplied = '';
        if (target === 'orbi') {
          for (const source of [new URL('./skills/COMMON.md', import.meta.url),
            new URL('../skills/orbi/SKILL.md', import.meta.url)]) {
            supplied += `Source: ${fileURLToPath(source)}\n`
              + `Resolve its references from ${fileURLToPath(new URL('./', source))}.\n\n`
              + `${await readFile(source, 'utf8')}\n\n`;
          }
        }
        const message = `Use this portable Kit workflow. Source: ${fileURLToPath(file)}\n`
          + boundary + supplied
          + `Resolve the workflow references from ${fileURLToPath(new URL('./', file))}.\n\n${body}\n\n`
          + (protocol ? `Selected subcommand: ${protocol}\n\n` : '')
          + (mode ? `Selected mode: ${mode}\n\n` : '')
          + `User request (preserve scope and restrictions):\n${args}`;
        pi.sendUserMessage(message, ctx.isIdle() ? undefined : {deliverAs: 'followUp'});
      },
    });
  }
}
