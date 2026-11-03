import { mkdtemp, writeFile, chmod, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const temps: string[] = [];
export async function cleanupFixtures() { for (const p of temps.splice(0)) await rm(p, { recursive: true, force: true }); }
export async function fixture() {
  const root = await mkdtemp(path.join(tmpdir(), 'paseo-aw-')); temps.push(root);
  const repo = path.join(root, 'repo');
  execFileSync('git', ['init', '-q', '-b', 'main', repo]);
  execFileSync('git', ['-C', repo, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@localhost', 'commit', '--allow-empty', '-qm', 'base']);
  const log = path.join(root, 'calls.jsonl'); const exe = path.join(root, 'autowork');
  const runner = { name: 'example', repo, state: 'stalled', service: 'running', running: 0, waiting: 2, push: false,
    questions: [{ id: 'T-1', effort: 'decision', unblocks: 1, needs: 'Choose scope', answer: 'Record decision', kind: 'outside' }],
    lanes: [{ task: 'T-OLD', phase: 'paused', attempt: 2 }], main_check: { state: 'red' } };
  const task = { id: 'T-1', title: 'Choose scope', short: 'Scope', section: 'Needs decision', status: 'open', goal: 'G', rank: 1000,
    closure: null, depends_on: [], verified_depends_on: [], touches: ['src/'], resources: [], kind: 'implementation',
    ownership: 'owner', live: 'denied', scope: 'Bounded', acceptance: ['a'], checks: ['test'], exclusions: [],
    contract_hash: 'contract-v1', record_revision: 'record-v1', path: 'tasks/items/T-1.md', rev: 'fixture-revision', notes: '', draft: false, missing_fields: [] };
  const source = `#!/usr/bin/env node\nconst fs=require('node:fs'); const args=process.argv.slice(2); fs.appendFileSync(${JSON.stringify(log)},JSON.stringify(args)+'\\n');
if(args[0]==='capabilities') console.log(JSON.stringify({tool:'autowork',release:'fixture-release',prepare_api:4,commands:['ls','tasks','plan','logs','start','pause','resume','stop','restart'],tasks:['list','show','decide']}));
else if(args[0]==='ls') console.log(JSON.stringify({runners:[${JSON.stringify(runner)}]}));
else if(args[0]==='tasks'&&args[1]==='list') console.log('[]');
else if(args[0]==='tasks'&&args[1]==='show') console.log(JSON.stringify(${JSON.stringify(task)}));
else if(args[0]==='logs') console.log('safe log');
else if(args[0]==='unicode'){const b=Buffer.from('"é"');process.stdout.write(b.subarray(0,2));setTimeout(()=>process.stdout.write(b.subarray(2)),20);}
else if(args[0]==='invalid') console.log('not json');
else if(args[0]==='large') console.log('x'.repeat(10000));
else if(args[0]==='hang') setTimeout(()=>{},30000);
else if(args[0]==='ignore'){process.on('SIGINT',()=>{});process.on('SIGTERM',()=>{});process.stderr.write('ready\\n');setTimeout(()=>{},30000);}
else if(args[0]==='fail'){process.stderr.write('SECRET_TOKEN=do-not-leak');process.exitCode=2;}
else console.log(JSON.stringify({status:'ready',id:'session-1',text:'proposal'}));\n`;
  await writeFile(exe, source); await chmod(exe, 0o700);
  return { root, repo, log, exe, runner };
}
