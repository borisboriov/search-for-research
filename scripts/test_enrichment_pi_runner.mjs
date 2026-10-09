import assert from 'node:assert/strict';
import fs from 'node:fs';
import {mkdtempSync, rmSync, readFileSync, writeFileSync, existsSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {test} from 'node:test';
import {allowedCall, createGuardedFetch, writeOnce, main, validateConfig, assertEffectiveConfig,
  createGuardedModelStream, createSourceQueue, createSerializedTransport, assertSessionSettings} from './enrichment_pi_runner.mjs';

test('only actual source tools in collect stage; no verifier web', () => {
  assert.equal(allowedCall('zai_search', 'web_search_prime', 'collect'), true);
  assert.equal(allowedCall('zai_reader', 'webReader', 'collect'), true);
  for (const mode of ['verify', 'discover'])
    assert.equal(allowedCall('zai_search', 'web_search_prime', mode), false);
  assert.equal(allowedCall('zai_reader', 'webReader', 'verify'), false);
  assert.equal(allowedCall('zai_search', 'search', 'collect'), false);
  assert.equal(allowedCall('filesystem', 'read', 'collect'), false);
});

test('403 and 429 latch before second physical request without recording headers/query', async () => {
  for (const code of [403, 429]) {
    let calls = 0;
    const records = [];
    const fetch = createGuardedFetch(async () => {
      calls++;
      return new Response('quota unavailable', {status: code});
    }, event => records.push(event));
    const first = await fetch('https://example.org/source?credential=never-record',
      {headers: {Authorization: 'never-record'}});
    assert.equal(first.status, code);
    assert.equal(await first.text(), 'quota unavailable');
    await assert.rejects(fetch('https://other-endpoint.org/'), /Access stopped/);
    assert.equal(calls, 1);
    assert.equal(records[0].refusal_body, 'quota unavailable');
    assert.equal(JSON.stringify(records).includes('never-record'), false);
  }
});

test('raw capture immutable; importing again cannot silently overwrite', () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'sfr-pi-runner-test-'));
  try {
    const file = path.join(dir, 'response.json');
    writeOnce(file, {content: [{text: '{"nested":"raw"}'}], _meta: {original: true}});
    const before = readFileSync(file, 'utf8');
    assert.throws(() => writeOnce(file, {content: []}), /EEXIST/);
    assert.equal(readFileSync(file, 'utf8'), before);
  } finally {rmSync(dir, {recursive: true});}
});

const approved = {provider: 'zai', model: 'glm-5.3-flash', effort: 'high'};
test('missing or wrong explicit configuration rejects before SDK load or network setup', async () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'sfr-pi-config-test-'));
  const originalFetch = globalThis.fetch;
  try {
    for (const config of [undefined, {}, {...approved, effort: 'low'}, {...approved, model: 'other'},
      {...approved, provider: 'other'}, {...approved, effort: undefined}]) {
      const file = path.join(dir, 'request.json');
      const run = path.join(dir, 'run');
      writeFileSync(file, JSON.stringify({config, mode: 'verify', system_prompt: 'isolated',
        workspace_dir: dir, run_dir: run, pi_release_dir: '/nonexistent-sdk'}));
      await assert.rejects(main(file), /Explicit approved/);
      assert.equal(globalThis.fetch, originalFetch);
      assert.equal(existsSync(run), false);
    }
    assert.deepEqual(validateConfig(approved), approved);
  } finally {rmSync(dir, {recursive: true});}
});
test('session downgrade and per-request model or effort drift stop before model stream', () => {
  const model = {provider: 'zai', id: 'glm-5.3-flash'};
  assert.deepEqual(assertEffectiveConfig({model, thinkingLevel: 'high'}, approved), approved);
  assert.throws(() => assertEffectiveConfig({model, thinkingLevel: 'low'}, approved), /differs/);
  let calls = 0;
  const records = [];
  const stream = createGuardedModelStream(() => {calls++; return 'mock stream';}, approved,
    record => records.push(record));
  for (const effort of [undefined, 'low', 'medium'])
    assert.throws(() => stream(model, {}, {reasoning: effort}), /differs/);
  assert.throws(() => stream({...model, id: 'fallback'}, {}, {reasoning: 'high'}), /differs/);
  assert.equal(calls, 0);
  assert.equal(stream(model, {}, {reasoning: 'high'}), 'mock stream');
  assert.equal(calls, 1);
  assert.deepEqual(records[0], {requested: approved, effective: approved,
    backend: {provider: null, model: null, effort: null, exposed: false}});
});
function fakeTransport() {
  const messages = [], errors = [], closes = [];
  const sent = [];
  return {sent, onMessage: fn => messages.push(fn), onError: fn => errors.push(fn),
    onClose: fn => closes.push(fn), start: async () => {}, close: async () => closes.forEach(fn => fn()),
    send: async message => {sent.push(message);},
    respond: message => messages.forEach(fn => fn(message)), error: e => errors.forEach(fn => fn(e))};
}
const call = (id, name = 'web_search_prime') => ({jsonrpc: '2.0', id, method: 'tools/call',
  params: {name, arguments: {query: 'fixed mock query'}}});
const tick = () => new Promise(resolve => setImmediate(resolve));
function harness(queue, server, reserve, timeoutMs = 200) {
  const inner = fakeTransport(), log = [];
  const transport = createSerializedTransport({inner, server, mode: 'collect', queue, reserve, timeoutMs,
    persist: (kind, data) => {log.push({kind, data}); return `mock-${log.length}`;},
    emit: event => log.push({event})});
  transport.onMessage(message => log.push({delivered: message}));
  return {inner, transport, log};
}
test('concurrent tools across both servers reserve serially until raw response, while initialize bypasses lock', async () => {
  const queue = createSourceQueue(), reservations = [];
  const reserve = async request => {reservations.push(request); return {allowed: true};};
  const search = harness(queue, 'zai_search', reserve), reader = harness(queue, 'zai_reader', reserve);
  const first = search.transport.send(call(1));
  const second = reader.transport.send(call(2, 'webReader'));
  await tick();
  assert.deepEqual(reservations.map(r => r.rpc_id), [1]);
  assert.equal(reader.inner.sent.length, 0);
  await reader.transport.send({jsonrpc: '2.0', id: 10, method: 'initialize'});
  assert.equal(reader.inner.sent[0].method, 'initialize');
  search.inner.respond({jsonrpc: '2.0', id: 1, result: {content: [{type: 'text', text: 'raw'}]}});
  await first;
  await tick();
  assert.deepEqual(reservations.map(r => r.rpc_id), [1, 2]);
  const captureIndex = search.log.findIndex(e => e.kind === 'mcp-response');
  const deliveryIndex = search.log.findIndex(e => e.delivered?.id === 1);
  assert.ok(captureIndex < deliveryIndex);
  reader.inner.respond({jsonrpc: '2.0', id: 2, error: {code: -1, message: 'source error'}});
  await second;
});
test('host denial, cache, and received RPC error allow the next physical call', async () => {
  for (const outcome of ['denied', 'cached', 'rpc-error']) {
    const reservations = [];
    const reserve = async request => {
      reservations.push(request.rpc_id);
      if (request.rpc_id === 1 && outcome === 'denied') return {allowed: false, reason: 'budget'};
      if (request.rpc_id === 1 && outcome === 'cached') return {allowed: true, replacement_result: {content: []}};
      return {allowed: true};
    };
    const q = createSourceQueue(), a = harness(q, 'zai_search', reserve), b = harness(q, 'zai_reader', reserve);
    const first = a.transport.send(call(1)), second = b.transport.send(call(2, 'webReader'));
    await tick();
    if (outcome === 'rpc-error') a.inner.respond({jsonrpc: '2.0', id: 1, error: {code: -1, message: 'completed error'}});
    await first;
    await tick();
    assert.deepEqual(reservations, [1, 2], outcome);
    b.inner.respond({jsonrpc: '2.0', id: 2, result: {content: []}});
    await second;
    if (['denied', 'cached'].includes(outcome)) assert.equal(a.inner.sent.length, 0);
  }
});
test('unknown physical outcome permanently stops both servers before a second reservation, even after late response', async () => {
  for (const outcome of ['send-error', 'timeout', 'transport-error', 'close']) {
    const reservations = [];
    const reserve = async request => {reservations.push(request.rpc_id); return {allowed: true};};
    const q = createSourceQueue(), a = harness(q, 'zai_search', reserve, 15), b = harness(q, 'zai_reader', reserve);
    if (outcome === 'send-error') a.inner.send = async message => {a.inner.sent.push(message); throw new Error('send failed after dispatch');};
    const first = assert.rejects(a.transport.send(call(1)));
    const second = assert.rejects(b.transport.send(call(2, 'webReader')), /queue stopped/);
    await tick();
    if (outcome === 'transport-error') a.inner.error(new Error('transport failed'));
    if (outcome === 'close') await a.transport.close();
    await Promise.all([first, second]);
    a.inner.respond({jsonrpc: '2.0', id: 1, result: {content: []}});
    await assert.rejects(b.transport.send(call(3, 'webReader')), /queue stopped/);
    assert.deepEqual(reservations, [1], outcome);
    assert.equal(a.inner.sent.length, 1);
    assert.equal(b.inner.sent.length, 0);
  }
});
test('notification or unmatched reply does not release a physical request', async () => {
  const reservations = [];
  const q = createSourceQueue(), reserve = async request => {reservations.push(request.rpc_id); return {allowed: true};};
  const a = harness(q, 'zai_search', reserve), b = harness(q, 'zai_reader', reserve);
  const first = a.transport.send(call(1)), second = b.transport.send(call(2, 'webReader'));
  await tick();
  a.inner.respond({jsonrpc: '2.0', method: 'notifications/progress'});
  a.inner.respond({jsonrpc: '2.0', id: 99, result: {content: []}});
  await tick();
  assert.deepEqual(reservations, [1]);
  a.inner.respond({jsonrpc: '2.0', id: 1, result: {content: []}});
  await first;
  await tick();
  b.inner.respond({jsonrpc: '2.0', id: 2, result: {content: []}});
  await second;
});
test('file sync, immutable link, and directory sync finish before delivery; sync error blocks delivery and the queue', async () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'sfr-pi-durable-test-'));
  try {
    for (const failed of [false, true]) {
      const log = [], descriptors = new Map();
      const io = {...fs,
        openSync(file, ...args) {const fd = fs.openSync(file, ...args); descriptors.set(fd, file); return fd;},
        fsyncSync(fd) {
          const directory = descriptors.get(fd) === dir;
          log.push(directory ? 'directory-sync' : 'file-sync');
          if (failed && directory) throw new Error('directory sync failed');
          fs.fsyncSync(fd);
        },
        linkSync(...args) {log.push('link'); return fs.linkSync(...args);},
      };
      const q = createSourceQueue(), inner = fakeTransport();
      const t = createSerializedTransport({inner, server: 'zai_search', mode: 'collect', queue: q,
        reserve: async () => ({allowed: true}), emit: () => {},
        persist: (kind, value) => {
          if (kind === 'mcp-response') writeOnce(path.join(dir, `${failed}.json`), value, io);
          return kind;
        }});
      t.onMessage(() => log.push('delivery'));
      const pending = t.send(call(1));
      const result = failed ? assert.rejects(pending, /directory sync failed/) : pending;
      await tick();
      inner.respond({jsonrpc: '2.0', id: 1, result: {content: []}});
      await result;
      assert.deepEqual(log, failed ? ['file-sync', 'link', 'directory-sync'] : ['file-sync', 'link', 'directory-sync', 'delivery']);
      if (failed) await assert.rejects(t.send(call(2)), /queue stopped/);
    }
  } finally {rmSync(dir, {recursive: true});}
});

test('closing transport releases active call and rejects its queued calls before new reservations', async () => {
  const reservations = [];
  const a = harness(createSourceQueue(), 'zai_search', async request => {
    reservations.push(request.rpc_id); return {allowed: true};
  });
  const first = assert.rejects(a.transport.send(call(1)), /closed/);
  const second = assert.rejects(a.transport.send(call(2)), /queue stopped/);
  await tick();
  await a.transport.close();
  await Promise.all([first, second]);
  assert.deepEqual(reservations, [1]);
  assert.equal(a.inner.sent.length, 1);
});

test('session-local warming and both retry layers must be off before model runtime loads', () => {
  const mock = (cache = 'off', enabled = false, retries = 0, provider = 0) => ({
    getCacheWarmingMode: () => cache, getRetrySettings: () => ({enabled, maxRetries: retries}),
    getProviderRetrySettings: () => ({maxRetries: provider, timeoutMs: 600000}),
  });
  assert.equal(assertSessionSettings(mock()).cache_warming, 'off');
  for (const settings of [mock('streaming'), mock('off', true), mock('off', false, 1), mock('off', false, 0, 1)])
    assert.throws(() => assertSessionSettings(settings), /settings differ/);
});
