#!/usr/bin/env node
// Kit's local capability check: no remote version lookup, install or project writes.
import { mkdtempSync, rmSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { readKitCatalog, requireVerifiedDistribution } from './workflows/ss-resolve/scripts/distribution-integrity.mjs';

try {
  const {values} = parseArgs({options: {
    help: {type: 'boolean'}, render: {type: 'boolean'}, browser: {type: 'string'},
    record: {type: 'boolean'},
  }});
  if (values.help) {
    console.log('Usage: node preflight.mjs [--render] [--browser PATH] [--record]\nChecks the local payload, existing Playwright Chromium for rendering, and its encoder only for recording.');
  } else {
    if (Number(process.versions.node.split('.')[0]) < 22) {
      throw new Error('Select Node.js 22 or later and retry.');
    }
    const catalog = readKitCatalog();
    const receipt = requireVerifiedDistribution({catalog, scriptPath: fileURLToPath(import.meta.url)});
    console.log(`StyleSeed distribution verified: ${receipt.computedRevision}`);
    if (values.render || values.record || values.browser !== undefined) {
      const {loadBrowser} = await import('./workflows/ss-reference/scripts/measure-reference.mjs');
      let browser;
      let recordingDir;
      try {
        const {chromium} = await loadBrowser(values.browser ?? process.env.STYLESEED_BROWSER_MODULE);
        browser = await chromium.launch({headless: true, timeout: 10000});
        if (values.record) {
          // A blank page exercises Playwright's own FFmpeg, not a different binary on PATH.
          recordingDir = mkdtempSync(join(tmpdir(), 'styleseed-record-'));
          const context = await browser.newContext({recordVideo: {dir: recordingDir}, viewport: {width: 320, height: 240}});
          const page = await context.newPage();
          await page.setContent('<p>StyleSeed encoder check</p>', {timeout: 5000});
          await page.waitForFunction(() => {
            // Update the blank page for several frames to exercise the recorder.
            document.body.dataset.frames = Number(document.body.dataset.frames ?? 0) + 1;
            document.querySelector('p').textContent = `StyleSeed encoder check — frame ${document.body.dataset.frames}`;
            return Number(document.body.dataset.frames) >= 20;
          }, undefined, {timeout: 5000});
          await context.close();
          if (!statSync(await page.video().path()).size) throw new Error('Playwright produced an empty recording');
        }
      } catch (error) {
        const capability = values.record ? 'Playwright Chromium or its recording encoder' : 'Playwright Chromium';
        throw new Error(`${capability} unavailable: ${error.message}\nPrepare the required runtime explicitly or point --browser at an existing Playwright module, then retry.`);
      } finally {
        try { await browser?.close(); }
        finally { if (recordingDir) rmSync(recordingDir, {recursive: true, force: true}); }
      }
      console.log(`Playwright Chromium ${values.record ? 'recorded a local test page' : 'started'} (no project page rendered).`);
    }
  }
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
