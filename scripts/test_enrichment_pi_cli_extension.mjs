import assert from 'node:assert/strict';
import {test} from 'node:test';
import {boundedPayload, recordEvent, safetyBoundary, upstreamRefusal, createReadPlan, substantiveBody} from './enrichment_pi_cli_extension.mjs';
import {createSourceQueue, createGuardedFetch} from './enrichment_pi_runner.mjs';

test('latest exact host budget reaches each request and finalization removes tools', () => {
  const original = {messages: [{role: 'user', content: 'frozen task'}], tools: [{type: 'function'}]};
  const budget = {search_remaining: 1, resources_remaining_including_robots: 0, host_robots: 5, source_reads: 3};
  const result = boundedPayload(original, budget, true);
  assert.equal(result.tools, undefined);
  assert.equal(result.messages.at(-1).role, 'user');
  assert.match(result.messages.at(-1).content, /complete final JSON/);
  assert.match(result.messages.at(-1).content, /No acknowledgement/);
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

test('quota errors inside HTTP200 are refused; ordinary source403 only blocks that source', () => {
  assert.equal(upstreamRefusal({server: 'zai_reader', message: {result: {isError: true, content: [{text: '429 quota exceeded'}]}}}), true);
  assert.equal(upstreamRefusal({server: 'zai_search', message: {error: {message: '403 access'}}}), true);
  assert.equal(upstreamRefusal({server: 'zai_reader', message: {result: {isError: true, content: [{text: '403 source access'}]}}}), false);
  assert.equal(upstreamRefusal({server: 'zai_search', message: {result: {content: [{text: 'publication429'}]}}}), false);
});

test('a discovered URL is read early; refusal/shell leads to a different exact link', () => {
  for (const content of ['ORCID', null]) {
    const plan = createReadPlan();
    const urls = ['https://example.org/person', 'https://example.org/publication'];
    plan.observe({server: 'zai_search', message: {result: {content: [{text: JSON.stringify(JSON.stringify(
      urls.map(link => ({title: 'Researcher', link, content: 'snippet only'}))))}]}}});
    const search = {server: 'zai_search', arguments: {search_query: 'subject anchor'}};
    assert.match(plan.allow(search, 3), /Read a discovered URL/);
    assert.equal(plan.allow({server: 'zai_reader', arguments: {url: urls[0]}}, 2), null);
    plan.observe({server: 'zai_reader', message: {result: content === null ? {isError: true} :
      {content: [{text: JSON.stringify({url: urls[0], content})}]}}});
    assert.equal(plan.snapshot().substantive_reader_bodies, 0);
    assert.match(plan.allow(search, 4), /alternative/);
    assert.match(plan.allow({server: 'zai_reader', arguments: {url: 'https://101.example.org'}}, 4), /never invent/);
    assert.equal(plan.allow({server: 'zai_reader', arguments: {url: urls[1]}}, 4), null);
    plan.observe({server: 'zai_reader', message: {result: {content: [{text: JSON.stringify(
      {url: urls[1], content: 'Researcher publication and official affiliation. '.repeat(10)})}]}}});
    assert.equal(plan.snapshot().substantive_reader_bodies, 1);
    assert.match(plan.allow({server: 'zai_reader', arguments: {url: urls[0]}}, 4), /already attempted/);
  }
  assert.equal(substantiveBody('ORCID'), false);
  assert.equal(substantiveBody('x'.repeat(500)), false);
});
