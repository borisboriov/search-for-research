import assert from 'node:assert/strict';
import fs from 'node:fs';
import readline from 'node:readline';
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

test('denial, cache, and reservation fsync failures stop queued second-server calls before reserve or send', async () => {
  for (const outcome of ['denied', 'cached', 'reservation']) {
    const dir = mkdtempSync(path.join(tmpdir(), 'sfr-pi-synthetic-durable-'));
    try {
      const failedKind = {denied: 'denied-mcp-response', cached: 'cached-mcp-response', reservation: 'reservation'}[outcome];
      const descriptors = new Map(), reservations = [], deliveries = [], captures = [];
      const io = {...fs,
        openSync(file, ...args) {const fd = fs.openSync(file, ...args); descriptors.set(fd, file); return fd;},
        fsyncSync(fd) {
          if (descriptors.get(fd) === dir) throw new Error('directory fsync failed');
          fs.fsyncSync(fd);
        },
      };
      const q = createSourceQueue(), inner = fakeTransport();
      const reserve = async request => {
        reservations.push(request.rpc_id);
        if (request.rpc_id === 1 && outcome === 'denied') return {allowed: false, reason: 'host policy'};
        if (request.rpc_id === 1 && outcome === 'cached') return {allowed: true, replacement_result: {content: []}};
        return {allowed: true};
      };
      const firstTransport = createSerializedTransport({inner, server: 'zai_search', mode: 'collect', queue: q,
        reserve, emit: () => {}, persist: (kind, value) => {
          captures.push(kind);
          if (kind === failedKind) writeOnce(path.join(dir, `${kind}.json`), value, io);
          return kind;
        }});
      firstTransport.onMessage(message => deliveries.push(message));
      const second = harness(q, 'zai_reader', reserve);
      const firstResult = assert.rejects(firstTransport.send(call(1)), /directory fsync failed/);
      const secondResult = assert.rejects(second.transport.send(call(2, 'webReader')), /queue stopped/);
      await Promise.all([firstResult, secondResult]);
      await assert.rejects(second.transport.send(call(3, 'webReader')), /queue stopped/);
      assert.deepEqual(reservations, [1], outcome);
      assert.ok(captures.includes(failedKind), outcome);
      assert.equal(deliveries.length, 0, outcome);
      assert.equal(inner.sent.length, 0, outcome);
      assert.equal(second.inner.sent.length, 0, outcome);
    } finally {rmSync(dir, {recursive: true});}
  }
});
test('protocol capture failure also stops the shared queue and active physical request', async () => {
  for (const failedKind of ['mcp-request', 'mcp-response']) {
    const q = createSourceQueue(), inner = fakeTransport(), reservations = [], deliveries = [];
    let fail = false;
    const reserve = async request => {reservations.push(request.rpc_id); return {allowed: true};};
    const firstTransport = createSerializedTransport({inner, server: 'zai_search', mode: 'collect', queue: q,
      reserve, emit: () => {}, persist: kind => {
        if (fail && kind === failedKind) throw new Error('protocol capture failed');
        return kind;
      }});
    firstTransport.onMessage(message => deliveries.push(message));
    const second = harness(q, 'zai_reader', reserve);
    const firstResult = assert.rejects(firstTransport.send(call(1)), /protocol capture failed/);
    const secondResult = assert.rejects(second.transport.send(call(2, 'webReader')), /queue stopped/);
    await tick();
    fail = true;
    if (failedKind === 'mcp-request')
      await assert.rejects(firstTransport.send({jsonrpc: '2.0', id: 10, method: 'initialize'}), /protocol capture failed/);
    else inner.respond({jsonrpc: '2.0', id: 10, result: {protocolVersion: 'test'}});
    await Promise.all([firstResult, secondResult]);
    assert.deepEqual(reservations, [1]);
    assert.equal(inner.sent.length, 1);
    assert.equal(second.inner.sent.length, 0);
    assert.equal(deliveries.length, 0);
  }
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

test('terminal queue state rejects another physical model request after a swallowed tool error', async () => {
  const queue = createSourceQueue();
  let modelCalls = 0;
  const stream = createGuardedModelStream(() => {modelCalls++;}, approved, () => {}, queue.assertHealthy);
  const swallowed = await queue.run(() => {
    const error = new Error('capture fsync failed');
    queue.stop(error);
    throw error;
  }).catch(error => ({isError: true, content: [{type: 'text', text: error.message}]}));
  assert.equal(swallowed.isError, true);
  assert.throws(() => stream({provider: 'zai', id: 'glm-5.3-flash'}, {}, {reasoning: 'high'}), /queue stopped/);
  assert.throws(queue.assertHealthy, /queue stopped/);
  assert.equal(modelCalls, 0);
});

test('main rejects swallowed capture failure despite normal empty collector JSON; no runtime/done or downstream jobs', async () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'sfr-pi-terminal-sdk-'));
  const originalFetch = globalThis.fetch, originalSync = fs.fsyncSync, originalOpen = fs.openSync;
  const originalWrite = process.stdout.write, originalReadline = readline.createInterface;
  const emitted = [], descriptors = new Map();
  let hostLine;
  globalThis.__sfrTerminalFixture = {failCapture: false, swallowed: false, modelCalls: 0, disposed: false};
  try {
    const release = path.join(dir, 'release');
    const pkg = path.join(release, 'node_modules/@earendil-works/pi-coding-agent');
    const ai = path.join(release, 'node_modules/@earendil-works/pi-ai');
    fs.mkdirSync(path.join(pkg, 'dist/extensions/mcp'), {recursive: true});
    fs.mkdirSync(path.join(ai, 'dist'), {recursive: true});
    writeFileSync(path.join(pkg, 'package.json'), '{"type":"module"}');
    writeFileSync(path.join(ai, 'package.json'), '{"type":"module"}');
    writeFileSync(path.join(ai, 'dist/models.js'), 'export const getSupportedThinkingLevels = () => ["high"];');
    writeFileSync(path.join(pkg, 'dist/extensions/mcp/config.js'), 'export const loadMcpConfig = () => ({servers: [], errors: []});');
    writeFileSync(path.join(pkg, 'dist/extensions/mcp/runtime.js'), `
      export const createDefaultTransport = () => ({
        onError() {}, onClose() {}, onMessage() {}, start: async () => {}, close: async () => {},
        send: async () => { throw new Error('Physical request must not be reached after capture failure'); },
      });
    `);
    writeFileSync(path.join(pkg, 'dist/index.js'), `
      export const VERSION = 'offline-fixture';
      export const getAgentDir = () => '/unused-no-auth';
      export const SettingsManager = {inMemory: () => ({
        getCacheWarmingMode: () => 'off', getRetrySettings: () => ({enabled: false, maxRetries: 0}),
        getProviderRetrySettings: () => ({maxRetries: 0, timeoutMs: 600000}),
      })};
      export const ModelRuntime = {create: async () => ({
        getModel: () => ({provider: 'zai', id: 'glm-5.3-flash'}),
        streamSimple: () => {globalThis.__sfrTerminalFixture.modelCalls++; return 'mock';},
      })};
      export const SessionManager = {inMemory: () => ({})};
      export const createMcpExtension = options => options;
      export class DefaultResourceLoader {
        constructor(options) {this.options = options;}
        async reload() {}
        getAgentsFiles() {return {agentsFiles: []};}
        getSkills() {return {skills: []};}
        getPrompts() {return {prompts: []};}
        getAppendSystemPrompt() {return [];}
      }
      export async function createAgentSession({resourceLoader, model, thinkingLevel, modelRuntime}) {
        const transport = resourceLoader.options.extensionFactories[0].createTransport({name: 'zai_search'});
        let listener;
        return {session: {
          model, thinkingLevel, bindExtensions: async () => {},
          getAllTools: () => [{name: 'mcp__zai_search__web_search_prime'}, {name: 'mcp__zai_reader__webReader'}],
          subscribe: callback => {listener = callback;},
          prompt: async input => {
            const task = JSON.parse(input);
            const hooks = globalThis.__sfrTerminalFixture;
            modelRuntime.streamSimple(model, {}, {reasoning: 'high'});
            hooks.failCapture = true;
            try {await transport.send({jsonrpc: '2.0', id: 10, method: 'tools/call', params: {name: 'web_search_prime', arguments: {search_query: 'offline fixture'}}});}
            catch (error) {hooks.swallowed = {isError: true, content: [{type: 'text', text: error.message}]};}
            listener({type: 'message_end', message: {role: 'assistant', stopReason: 'stop',
              content: [{type: 'text', text: JSON.stringify({
                author_id: task.author_id, batch_ticket_id: task.batch_ticket_id,
                batch_input_sha256: task.batch_input_sha256, items: [], evidence_pool: {},
                profile_evidence: {identity: [], current_affiliation: []},
                field_statuses: Object.fromEntries(['personal_contact', 'coordinator_contact', 'supervision_history',
                  'published_recruitment', 'direct_willingness', 'topic', 'supervisor_role', 'student_level',
                  'student_year', 'required_skills', 'external_students', 'thesis_possible', 'city',
                  'work_format', 'workload', 'payment', 'deadline', 'response_method'].map(field => [field, 'not_checked'])),
              })}]}});
          },
          getSessionStats: () => ({}), abort() {},
          dispose() {globalThis.__sfrTerminalFixture.disposed = true;},
        }};
      }
    `);
    fs.openSync = (file, ...args) => {
      const descriptor = originalOpen(file, ...args);
      descriptors.set(descriptor, String(file));
      return descriptor;
    };
    fs.fsyncSync = descriptor => {
      if (globalThis.__sfrTerminalFixture.failCapture && descriptors.get(descriptor)?.includes('denied-mcp-response')) {
        globalThis.__sfrTerminalFixture.failCapture = false;
        throw new Error('fixture capture fsync failed');
      }
      return originalSync(descriptor);
    };
    readline.createInterface = () => ({on(event, handler) {if (event === 'line') hostLine = handler;}, close() {}});
    process.stdout.write = chunk => {
      const event = JSON.parse(String(chunk));
      emitted.push(event);
      if (event.type === 'reserve') hostLine(JSON.stringify({id: event.id, allowed: false, reason: 'offline host denial'}));
      return true;
    };
    const runDir = path.join(dir, 'run'), request = path.join(dir, 'request.json');
    writeFileSync(request, JSON.stringify({config: approved, mode: 'collect', system_prompt: 'offline',
      workspace_dir: dir, run_dir: runDir, pi_release_dir: release, task: {author_id: 'A1', batch_ticket_id: 'A1-collect', batch_input_sha256: 'a'.repeat(64)}}));
    let downstreamJobs = 0;
    await assert.rejects((async () => {
      await main(request);
      downstreamJobs++; // Native verifier and following profile can only follow successful completion.
    })(), /queue stopped/);
    assert.equal(globalThis.__sfrTerminalFixture.swallowed.isError, true);
    assert.equal(globalThis.__sfrTerminalFixture.modelCalls, 1);
    assert.equal(globalThis.__sfrTerminalFixture.disposed, true);
    assert.equal(downstreamJobs, 0);
    assert.ok(emitted.some(event => event.type === 'failure'));
    assert.equal(emitted.some(event => event.type === 'done'), false);
    assert.equal(existsSync(path.join(runDir, 'runner-finished.json')), false);
    assert.equal(fs.readdirSync(runDir).some(file => file.endsWith('-runtime.json')), false);
    const saved = fs.readdirSync(runDir).filter(file => file.endsWith('-session-event.json'));
    assert.equal(saved.length, 1);
    const empty = JSON.parse(JSON.parse(readFileSync(path.join(runDir, saved[0]), 'utf8')).message.content[0].text);
    assert.deepEqual(empty.items, []);
    assert.equal(Object.keys(empty.field_statuses).length, 18);
    assert.equal(empty.batch_ticket_id, 'A1-collect');
    assert.deepEqual(empty.profile_evidence, {identity: [], current_affiliation: []});
  } finally {
    globalThis.fetch = originalFetch;
    fs.fsyncSync = originalSync;
    fs.openSync = originalOpen;
    readline.createInterface = originalReadline;
    process.stdout.write = originalWrite;
    delete globalThis.__sfrTerminalFixture;
    rmSync(dir, {recursive: true});
  }
});
