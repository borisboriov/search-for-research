import assert from 'node:assert/strict';
import {test} from 'node:test';
import {boundedPayload, recordEvent, safetyBoundary} from './enrichment_pi_cli_extension.mjs';
import {createSourceQueue, createGuardedFetch} from './enrichment_pi_runner.mjs';

test('latest exact host budget reaches each request and finalization removes tools', () => {
  const original = {messages: [{role: 'user', content: 'frozen task'}], tools: [{type: 'function'}]};
  const budget = {search_remaining: 1, resources_remaining_including_robots: 0, host_robots: 5, source_reads: 3};
  const result = boundedPayload(original, budget, true);
  assert.equal(result.tools, undefined);
  assert.deepEqual(original.messages, [{role: 'user', content: 'frozen task'}]);
  assert.match(result.messages.at(-1).content, /"host_robots":5/);
  assert.match(result.messages.at(-1).content, /Source tools are closed/);
  assert.equal(boundedPayload(original, budget, false).tools, original.tools);
});
test('a swallowed synchronous or async extension failure blocks the next physical fetch', async () => {
  for (const asynchronous of [true, false]) {
    const queue = createSourceQueue();
    const handler = safetyBoundary(queue, asynchronous ? async () => {throw new Error('disk');} :
      () => {throw new Error('disk');});
    try {await handler();} catch {} // Native Pi catches extension errors.
    let calls = 0;
    const fetch = createGuardedFetch(async () => {calls++; return new Response('ok');}, () => {},
      () => {queue.assertHealthy(); return true;});
    await assert.rejects(fetch('https://api.z.ai/api/coding/paas/v4/chat/completions'), /queue stopped/);
    assert.equal(calls, 0);
  }
});
test('only final authoritative messages and necessary lifecycle records are saved', () => {
  assert.equal(recordEvent({type: 'message_end'}), true);
  assert.equal(recordEvent({type: 'message_update', assistantMessageEvent: {type: 'text_delta'}}), false);
});
