import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {test} from 'node:test';
import extension, {createModelBudget} from './enrichment_glm_extension.mjs';
import {createSourceQueue} from './enrichment_pi_runner.mjs';
import {safetyBoundary, upstreamRefusal} from './enrichment_pi_cli_extension.mjs';

test('Pi swallowing hook errors cannot send thirteenth physical request', async () => {
  const original = globalThis.fetch, previous = process.env.SFR_PI_REQUEST_PATH;
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'sfr-glm-cap-'));
  let physical = 0;
  try {
    globalThis.fetch = async () => {physical++; return new Response('{}', {status: 200});};
    const config = {provider: 'zai', model: 'glm-5.3-flash', effort: 'high'};
    const request = path.join(root, 'request.json');
    fs.writeFileSync(request, JSON.stringify({method: 'glm-public-runner-v1', mode: 'replay',
      config, run_dir: path.join(root, 'run'), max_model_requests: 12, system_prompt: 'fixed'}));
    process.env.SFR_PI_REQUEST_PATH = request;
    const hooks = {};
    const pi = {registerTool() {}, registerCommand() {}, on(name, handler) {hooks[name] = handler;},
      getThinkingLevel: () => 'high', getActiveTools: () => ['sfr_source'],
      getSettings: () => ({retry: {enabled: false, maxRetries: 0, provider: {maxRetries: 0}},
        cacheWarming: 'off', compaction: {enabled: false}})};
    await extension(pi);
    const ctx = {model: {provider: 'zai', id: 'glm-5.3-flash'}};
    hooks.before_agent_start({}, ctx);
    const payload = {messages: [], tools: []};
    for (let index = 0; index < 12; index++) {
      hooks.before_provider_request({payload}, ctx);
      await globalThis.fetch('https://api.z.ai/api/coding/paas/v4/chat/completions');
    }
    try {hooks.before_provider_request({payload}, ctx);} catch {/* Pi returns currentPayload. */}
    await assert.rejects(globalThis.fetch('https://api.z.ai/api/coding/paas/v4/chat/completions'), /stopped/i);
    assert.equal(physical, 12);
  } finally {
    globalThis.fetch = original;
    if (previous === undefined) delete process.env.SFR_PI_REQUEST_PATH;
    else process.env.SFR_PI_REQUEST_PATH = previous;
    fs.rmSync(root, {recursive: true});
  }
});

test('physical budget independently stops hidden retries and MCP semantic refusal latches', () => {
  const queue = createSourceQueue(), budget = createModelBudget(2, queue);
  budget.fetch(); budget.fetch();
  assert.throws(() => budget.fetch(), /budget/);
  assert.throws(() => budget.hook(), /stopped/i);
  for (const raw of [
    {server: 'zai_search', message: {result: {isError: true, content: [{text: '429 quota exceeded'}]}}},
    {server: 'zai_search', message: {error: {message: '403 access'}}},
  ]) {
    const stopped = createSourceQueue();
    assert.equal(upstreamRefusal(raw), true);
    try {safetyBoundary(stopped, () => {if (upstreamRefusal(raw)) throw new Error('refusal');})();} catch {}
    assert.throws(() => stopped.assertHealthy(), /stopped/i);
  }
});
