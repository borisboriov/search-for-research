import assert from 'node:assert/strict';
import {test} from 'node:test';
import {boundedPayload, recordEvent, safetyBoundary, upstreamRefusal, createReadPlan, substantiveBody} from './enrichment_pi_cli_extension.mjs';
import {createSourceQueue, createGuardedFetch, createSerializedTransport} from './enrichment_pi_runner.mjs';

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

test('site-root search links cannot be replaced by a catalog/snippet ORCID path', () => {
  const catalog = 'https://orcid.org/0000-0000-0000-0001';
  const plan = createReadPlan({profile: {orcid: catalog}});
  plan.observe({server: 'zai_search', message: {result: {content: [{text: JSON.stringify(JSON.stringify([
    {title: 'Person', link: 'https://orcid.org', content: catalog},
    {title: 'Publication', link: 'https://journal.example/article'}]))}]}}});
  const denial = plan.allow({server: 'zai_reader', arguments: {url: catalog}}, 3);
  assert.match(denial, /Allowed exact URLs/);
  assert.deepEqual(JSON.parse(denial.split('Allowed exact URLs: ')[1]), plan.snapshot().available_discovered_urls);
  assert.equal(plan.snapshot().reader_attempts, 0);
  // Neither an unauthorized path nor a representation change spends a source read.
  for (const url of ['https://orcid.org/', 'http://orcid.org', 'https://orcid.org/robots.txt'])
    assert.match(plan.allow({server: 'zai_reader', arguments: {url}}, 3), /exact link/);
  assert.equal(plan.allow({server: 'zai_reader', arguments: {url: 'https://journal.example/article'}}, 4), null);
  assert.equal(plan.snapshot().reader_attempts, 1);
});

test('native reader schema offers exact unused URLs, preserves budgets and closes on finalization', () => {
  const original = {messages: [], tools: [
    {type: 'function', function: {name: 'mcp__zai_search__web_search_prime', parameters: {}}},
    {type: 'function', function: {name: 'mcp__zai_reader__webReader', parameters: {
      type: 'object', required: ['url'], properties: {url: {type: 'string'}, retain_images: {type: 'boolean'}}}}}]};
  const budget = {available_discovered_urls: ['https://orcid.org', 'https://journal.example/article'],
    substantive_reader_bodies: 0, search_remaining: 3, resources_remaining_including_robots: 8,
    model_requests: 3, seconds_remaining: 540};
  const frozen = structuredClone(original), snapshot = structuredClone(budget);
  const result = boundedPayload(original, budget, false);
  assert.equal(result.tools.length, 1);
  assert.deepEqual(result.tools[0].function.parameters.properties.url.enum, budget.available_discovered_urls);
  assert.deepEqual(result.tools[0].function.parameters.required, ['url']);
  assert.deepEqual(original, frozen);
  assert.deepEqual(budget, snapshot);
  assert.match(result.messages.at(-1).content, /Catalog ORCID.*not registered reader links/);
  assert.equal(boundedPayload(original, {...budget, substantive_reader_bodies: 1}, false).tools.length, 2);
  assert.equal(boundedPayload(original, budget, true).tools, undefined);
  assert.throws(() => boundedPayload({messages: [], tools: []}, budget, false), /reader missing/);
  const changed = structuredClone(original);
  changed.tools[1].function.parameters.properties.url.type = 'number';
  assert.throws(() => boundedPayload(changed, budget, false), /Unknown native reader/);
});

test('a denied URL leaves host resources for an exact read; STOP blocks the next transport call', async () => {
  const plan = createReadPlan({discovered_urls: ['https://journal.example/article']});
  const queue = createSourceQueue();
  let receiver, physical = 0, hostReservations = 0;
  const inner = {start() {}, close() {}, onError() {}, onClose() {},
    onMessage(handler) {receiver = handler;},
    async send(message) {
      physical++;
      receiver({jsonrpc: '2.0', id: message.id, result: {content: [{type: 'text', text: '{}'}]}});
    }};
  const seen = [];
  const transport = createSerializedTransport({inner, server: 'zai_reader', mode: 'collect', queue,
    reserve: async data => {
      const reason = plan.allow(data, 3);
      if (reason) return {allowed: false, reason};
      hostReservations++;
      return {allowed: true};
    }, persist: () => 'offline', emit() {}});
  transport.onMessage(message => seen.push(message));
  const call = (id, url) => ({jsonrpc: '2.0', id, method: 'tools/call',
    params: {name: 'webReader', arguments: {url}}});
  await transport.send(call(1, 'https://catalog.example/person'));
  assert.equal(physical, 0);
  assert.equal(hostReservations, 0);
  assert.match(seen[0].result.content[0].text, /Allowed exact URLs/);
  await transport.send(call(2, 'https://journal.example/article'));
  assert.equal(physical, 1);
  assert.equal(hostReservations, 1);
  queue.stop(new Error('STOP'));
  await assert.rejects(transport.send(call(3, 'https://journal.example/article')), /queue stopped/);
  assert.equal(physical, 1);
});
