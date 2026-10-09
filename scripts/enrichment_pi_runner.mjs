#!/usr/bin/env node
/** Isolated Pi 1.1.0 SDK runner. Host grants every MCP source invocation first. */
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import readline from 'node:readline';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';

export const SOURCE_TOOLS = Object.freeze({zai_search: 'web_search_prime', zai_reader: 'webReader'});
export function writeOnce(file, value, io = fs) {
  const temporary = `${file}.tmp-${process.pid}-${Math.random().toString(16).slice(2)}`;
  try {
    io.writeFileSync(temporary, JSON.stringify(value, null, 2) + '\n', {flag: 'wx', mode: 0o600});
    const descriptor = io.openSync(temporary, 'r');
    try {io.fsyncSync(descriptor);} finally {io.closeSync(descriptor);}
    io.linkSync(temporary, file);
    io.unlinkSync(temporary);
    // A synced file alone does not make its new directory entry durable.
    const directory = io.openSync(path.dirname(file), 'r');
    try {io.fsyncSync(directory);} finally {io.closeSync(directory);}
  } finally {if (io.existsSync(temporary)) io.unlinkSync(temporary);}
}
export function allowedCall(server, name, mode) {
  return mode === 'collect' && SOURCE_TOOLS[server] === name;
}
export function readerView(message) {
  if (!message.result?.content) return message;
  const content = message.result.content.map(block => {
    if (block.type !== 'text') return block;
    let decoded = block.text;
    for (let n = 0; n < 8 && typeof decoded === 'string'; n++) {
      try {decoded = JSON.parse(decoded);} catch {break;}
    }
    if (!decoded || typeof decoded !== 'object' || typeof decoded.content !== 'string') return block;
    const body = decoded.content;
    const view = body.length <= 20000 ? body : body.slice(0, 12000) +
      '\n[MODEL VIEW TRUNCATED; FULL SOURCE SAVED OUTSIDE CONTEXT]\n' + body.slice(-8000);
    return {...block, text: JSON.stringify({url: decoded.url, title: decoded.title,
      description: decoded.description, metadata: decoded.metadata, content: view,
      model_view_truncated: body.length > 20000})};
  });
  return {...message, result: {...message.result, content}};
}
export function createGuardedFetch(realFetch, record, isAllowed = () => true) {
  let stopped = false;
  return async (...args) => {
    if (stopped) throw new Error('Access stopped after HTTP quota/access refusal');
    const rawUrl = args[0] instanceof Request ? args[0].url : String(args[0]);
    const url = new URL(rawUrl);
    if (!isAllowed(url)) throw new Error('Unapproved network endpoint');
    const started = new Date().toISOString();
    const response = await realFetch(args[0], {...args[1], redirect: 'error'});
    const info = {started, finished: new Date().toISOString(), origin: url.origin,
      pathname: url.pathname, status: response.status}; // Never capture headers/query/auth.
    if (response.status === 403 || response.status === 429) {
      stopped = true;
      info.refusal_body = await response.clone().text();
    }
    record(info);
    return response;
  };
}

export const REQUIRED_CONFIG = Object.freeze({provider: 'zai', model: 'glm-5.3-flash', effort: 'high'});
export function validateConfig(config) {
  if (!config || Object.entries(REQUIRED_CONFIG).some(([key, value]) => config[key] !== value))
    throw new Error('Explicit approved provider/model/effort configuration required');
  return {...REQUIRED_CONFIG};
}
export function effectiveConfig(session) {
  return {provider: session.model?.provider ?? null, model: session.model?.id ?? null,
    effort: session.thinkingLevel ?? null};
}
export function assertEffectiveConfig(session, requested) {
  const effective = effectiveConfig(session);
  if (Object.keys(requested).some(key => effective[key] !== requested[key]))
    throw new Error('Runtime configuration differs from requested configuration');
  return effective;
}
export function verifierContext(context, instruction, userPrompt) {
  const users = context.messages.filter(message => message.role !== 'system');
  if (context.tools?.length || context.messages.some(message => message.toolsAdded?.length) ||
      users.length !== 1 || users[0].role !== 'user' || users[0].content.length !== 1 ||
      users[0].content[0].type !== 'text' || users[0].content[0].text !== userPrompt)
    throw new Error('Cache verifier context differs from the frozen input');
  // Pi normally appends its cwd section. Project exactly the shared instruction at this public API boundary.
  return {messages: [{role: 'system', content: instruction, timestamp: 0}, users[0]], tools: []};
}
export function createGuardedModelStream(stream, requested, record, assertHealthy = () => {}, input = null) {
  return (model, context, options) => {
    assertHealthy(); // SDK can swallow tool errors; never allow another physical model request.
    const effective = {provider: model?.provider ?? null, model: model?.id ?? null,
      effort: options?.reasoning ?? null};
    if (Object.keys(requested).some(key => effective[key] !== requested[key]))
      throw new Error('Model request differs from explicit configuration');
    const projected = input ? verifierContext(context, input.instruction, input.userPrompt) : context;
    const hash = value => createHash('sha256').update(value).digest('hex');
    record({requested, effective, backend: {provider: null, model: null, effort: null, exposed: false},
      ...(input ? {instruction_sha256: hash(input.instruction), user_prompt_sha256: hash(input.userPrompt), tools: []} : {})});
    return stream(model, projected, options);
  };
}
export function assertSessionSettings(settings) {
  const retry = settings.getRetrySettings();
  const provider = settings.getProviderRetrySettings();
  const effective = {cache_warming: settings.getCacheWarmingMode(), automatic_llm_retries: retry.maxRetries,
    retry_enabled: retry.enabled, provider_retries: provider.maxRetries, timeout_ms: provider.timeoutMs};
  if (effective.cache_warming !== 'off' || effective.retry_enabled !== false ||
      effective.automatic_llm_retries !== 0 || effective.provider_retries !== 0 || effective.timeout_ms !== 600000)
    throw new Error('Session retry/cache-warming settings differ from approved limits');
  return effective;
}
// One queue shared by both source servers; protocol discovery bypasses it.
export function createSourceQueue() {
  let tail = Promise.resolve();
  let stopped;
  const assertHealthy = () => {
    if (stopped) throw new Error('Source queue stopped after terminal transport/capture failure', {cause: stopped});
  };
  return {
    stop(error) {stopped ??= error;},
    assertHealthy,
    run(operation) {
      const task = tail.then(() => {
        assertHealthy();
        return operation();
      });
      tail = task.catch(() => {});
      return task;
    },
  };
}
export function createSerializedTransport({inner, server, mode, queue, reserve, persist, emit,
  timeoutMs = 600000}) {
  const listeners = new Set();
  const active = new Map();
  let closed = false;
  const deliver = message => {for (const listener of listeners) listener(message);};
  const failActive = error => {
    if (active.size) queue.stop(error);
    for (const pending of active.values()) pending.reject(error);
  };
  // Every capture is a safety boundary, including protocol, reservations and synthetic replies.
  const capture = (kind, value) => {
    try {return persist(kind, value);}
    catch (error) {queue.stop(error); failActive(error); throw error;}
  };
  inner.onError(failActive);
  const closePending = () => {closed = true; failActive(new Error('Source transport closed'));};
  inner.onClose(closePending);
  inner.onMessage(message => {
    const pending = active.get(message.id);
    const completed = Object.hasOwn(message, 'id') &&
      (Object.hasOwn(message, 'result') || Object.hasOwn(message, 'error'));
    try {
      const file = capture('mcp-response', {server, message});
      emit({type: 'mcp_result', server, rpc_id: message.id ?? null, file});
      // Save durable raw before delivery and before granting the next call.
      if (pending && completed) pending.received = true;
      deliver(server === 'zai_reader' ? readerView(message) : message);
      if (completed) pending?.resolve();
    } catch (error) {
      queue.stop(error); // Failed persistence must never permit delivery or another request.
      failActive(error);
    }
  });
  const synthetic = (message, result, kind, extra = {}) => {
    const response = {jsonrpc: '2.0', id: message.id, result};
    const file = capture(kind, {server, message: response});
    emit({type: 'mcp_result', server, rpc_id: message.id, file, performed: false, ...extra});
    deliver(response);
  };
  return {
    start: () => inner.start(),
    close: () => {closePending(); return inner.close();},
    onMessage: listener => {listeners.add(listener); return () => listeners.delete(listener);},
    onError: listener => inner.onError(listener), onClose: listener => inner.onClose(listener),
    setProtocolVersion: version => inner.setProtocolVersion?.(version),
    send: async message => {
      if (closed) throw new Error('Source transport closed');
      if (message.method !== 'tools/call') {
        capture('mcp-request', {server, message});
        return inner.send(message);
      }
      if (!allowedCall(server, message.params?.name, mode)) throw new Error('Unapproved source tool');
      return queue.run(async () => {
        if (closed) throw new Error('Source transport closed');
        const name = message.params.name;
        const permission = await reserve({server, tool: name,
          arguments: message.params.arguments, rpc_id: message.id});
        capture('reservation', {server, name, rpc_id: message.id, permission});
        if (closed) throw new Error('Source transport closed');
        if (!permission.allowed) {
          synthetic(message, {isError: true, content: [{type: 'text',
            text: `Access not performed: ${permission.reason || 'host denied'}`}]}, 'denied-mcp-response');
          return;
        }
        if (permission.replacement_result) {
          synthetic(message, permission.replacement_result, 'cached-mcp-response', {cached: true});
          return;
        }
        let timer;
        let pending;
        const response = new Promise((resolve, reject) => {
          pending = {resolve, reject, received: false};
          active.set(message.id, pending);
          timer = setTimeout(() => {
            const error = new Error('Source response timeout');
            queue.stop(error);
            reject(error);
          }, timeoutMs);
        });
        response.catch(() => {});
        try {
          capture('mcp-request', {server, message});
          await Promise.all([inner.send(message), response]);
        } catch (error) {
          if (!pending.received) queue.stop(error);
          throw error;
        } finally {clearTimeout(timer); active.delete(message.id);}
      });
    },
  };
}

export async function main(requestPath) {
  const request = JSON.parse(fs.readFileSync(requestPath, 'utf8'));
  const requested = validateConfig(request.config); // Before SDK load or network setup.
  if (!['discover', 'collect', 'verify'].includes(request.mode)) throw new Error('Invalid mode');
  if (typeof request.system_prompt !== 'string' || !request.workspace_dir || !request.run_dir)
    throw new Error('Missing isolated input');
  const runDir = path.resolve(request.run_dir);
  fs.mkdirSync(runDir, {recursive: true, mode: 0o700});
  writeOnce(path.join(runDir, 'runner-started.json'), {at: new Date().toISOString(), mode: request.mode, requested});
  let seq = 0;
  const persist = (kind, data) => {
    const file = `${String(++seq).padStart(6, '0')}-${kind}.json`;
    writeOnce(path.join(runDir, file), data);
    return file;
  };
  const emit = value => process.stdout.write(JSON.stringify(value) + '\n');
  const pending = new Map();
  const lines = readline.createInterface({input: process.stdin});
  lines.on('line', line => {
    let response;
    try {response = JSON.parse(line);} catch {return;}
    const waiter = pending.get(response.id);
    if (waiter) {pending.delete(response.id); clearTimeout(waiter.timer); waiter.resolve(response);}
  });
  const reserve = async data => {
    const id = `reservation-${++seq}`;
    const response = new Promise((resolve, reject) => {
      const timer = setTimeout(() => {pending.delete(id); reject(new Error('Host reservation timeout'));}, 30000);
      pending.set(id, {resolve, reject, timer});
    });
    emit({type: 'reserve', id, ...data});
    return response;
  };
  globalThis.fetch = createGuardedFetch(globalThis.fetch, info => {
    const file = persist('http', info);
    emit({type: 'http', file, status: info.status, origin: info.origin, pathname: info.pathname});
  }, url => url.origin === 'https://api.z.ai' &&
    (url.pathname.startsWith('/api/coding/paas/v4/') ||
     ['/api/mcp/web_search_prime/mcp', '/api/mcp/web_reader/mcp'].includes(url.pathname)));
  const release = request.pi_release_dir || path.join(os.homedir(), '.pi/agent/install/releases/1.1.0');
  const pkg = path.join(release, 'node_modules/@earendil-works/pi-coding-agent/dist');
  const sdk = await import(pathToFileURL(path.join(pkg, 'index.js')).href);
  const {loadMcpConfig} = await import(pathToFileURL(path.join(pkg, 'extensions/mcp/config.js')).href);
  const {createDefaultTransport} = await import(pathToFileURL(path.join(pkg, 'extensions/mcp/runtime.js')).href);
  const agentDir = sdk.getAgentDir();
  const settings = sdk.SettingsManager.inMemory({retry: {enabled: false, maxRetries: 0,
    provider: {maxRetries: 0, timeoutMs: 600000}}, compaction: {enabled: false}, cacheWarming: 'off'});
  const sessionSettings = assertSessionSettings(settings);
  persist('runtime-settings', sessionSettings);
  const modelRuntime = await sdk.ModelRuntime.create({allowModelNetwork: false, refreshOnCreate: false});
  const model = modelRuntime.getModel(requested.provider, requested.model);
  if (!model || model.provider !== requested.provider || model.id !== requested.model)
    throw new Error('Required configured model unavailable');
  const {getSupportedThinkingLevels} = await import(pathToFileURL(path.join(release,
    'node_modules/@earendil-works/pi-ai/dist/models.js')).href);
  if (!getSupportedThinkingLevels(model).includes(requested.effort))
    throw new Error('Required thinking effort unavailable; downgrade forbidden');
  const queue = createSourceQueue();
  modelRuntime.streamSimple = createGuardedModelStream(modelRuntime.streamSimple.bind(modelRuntime),
    requested, data => persist('model-request-config', data), queue.assertHealthy,
    request.method === 'cache-verifier-v1' ? {instruction: request.system_prompt,
      userPrompt: JSON.stringify({task: request.task, output_json_schema: request.output_schema})} : null);
  const mcp = request.mode === 'verify' ? null : sdk.createMcpExtension({
    logPath: path.join(runDir, 'mcp.log'),
    loadConfig: () => {
      const config = loadMcpConfig({agentDir, cwd: request.workspace_dir, projectTrusted: false});
      if (config.errors.length) throw new Error('Native MCP configuration error');
      const servers = config.servers.filter(entry => Object.hasOwn(SOURCE_TOOLS, entry.name));
      if (servers.length !== 2) throw new Error('Required native MCP servers missing');
      // Session-local exposure only. Saved auth and endpoints remain native and unchanged.
      return {servers: servers.map(entry => ({...entry, config: {...entry.config,
        exposure: 'direct', toolExposure: {}, enabled: true}})), errors: [], autoEnableCodemode: false};
    },
    createTransport: (entry, cwd, auth) => createSerializedTransport({
      inner: createDefaultTransport(entry, cwd, auth), server: entry.name,
      mode: request.mode, queue, reserve, persist, emit}),
  });
  const loader = new sdk.DefaultResourceLoader({cwd: request.workspace_dir, agentDir,
    settingsManager: settings, noExtensions: true, noSkills: true, noPromptTemplates: true,
    noThemes: true, noContextFiles: true, systemPrompt: request.system_prompt,
    appendSystemPrompt: [], extensionFactories: request.mode === 'verify' ? [] : [mcp]});
  await loader.reload();
  if (loader.getAgentsFiles().agentsFiles.length || loader.getSkills().skills.length ||
      loader.getPrompts().prompts.length || loader.getAppendSystemPrompt().length)
    throw new Error('Unexpected context resources');
  const {session} = await sdk.createAgentSession({cwd: request.workspace_dir, agentDir,
    resourceLoader: loader, settingsManager: settings, sessionManager: sdk.SessionManager.inMemory(),
    modelRuntime, model, thinkingLevel: requested.effort, noTools: 'builtin',
    tools: request.mode === 'verify' ? [] : Object.entries(SOURCE_TOOLS).map(([s,t]) => `mcp__${s}__${t}`)});
  if (request.mode === 'verify' &&
      (session.getActiveToolNames().length || session.getCallableToolNames().length))
    throw new Error('Cache verifier unexpectedly exposes tools');
  if (request.mode === 'verify') persist('tool-inventory', {mode: request.mode,
    tools: session.getActiveToolNames(), callable_tools: session.getCallableToolNames()});
  let timeout;
  let timedOut = false;
  let assistantFailure = false;
  try {
    assertEffectiveConfig(session, requested); // Check SDK clamp before MCP discovery or prompt.
    persist('runtime-config', {requested, effective: effectiveConfig(session),
      backend: {provider: null, model: null, effort: null, exposed: false}, pi_version: sdk.VERSION});
    await session.bindExtensions({});
    if (request.mode !== 'verify') {
      const until = Date.now() + 30000;
      while (Date.now() < until && session.getAllTools().filter(tool => tool.name.startsWith('mcp__')).length < 2)
        await new Promise(resolve => setTimeout(resolve, 100));
      const tools = session.getAllTools().filter(tool => tool.name.startsWith('mcp__'));
      if (tools.length !== 2) throw new Error('MCP discovery incomplete');
      const file = persist('tool-schemas', tools);
      emit({type: 'schemas', file, names: tools.map(tool => tool.name)});
    }
    if (request.mode === 'discover') {queue.assertHealthy(); emit({type: 'done', mode: 'discover'}); return;}
    session.subscribe(event => {
      if (event.type === 'message_end' && event.message?.role === 'assistant' &&
          ['error', 'aborted'].includes(event.message.stopReason)) assistantFailure = true;
      const file = persist('session-event', event);
      emit({type: 'event', event_type: event.type, file});
    });
    timeout = setTimeout(() => {timedOut = true; session.abort();}, 600000);
    const publicInput = request.output_schema ? {task: request.task, output_json_schema: request.output_schema} : request.task;
    assertEffectiveConfig(session, requested);
    queue.assertHealthy();
    await session.prompt(JSON.stringify(publicInput), {expandPromptTemplates: false});
    // A normal assistant completion cannot erase a source/capture failure swallowed by Pi SDK.
    queue.assertHealthy();
    if (timedOut || assistantFailure) throw new Error('Agent did not complete normally');
    const stats = session.getSessionStats();
    const effective = assertEffectiveConfig(session, requested);
    const runtime = {...effective, requested, effective,
      backend: {provider: null, model: null, effort: null, exposed: false}, routed_model: session.routedModel?.model?.id ?? null,
      pi_version: sdk.VERSION, settings: sessionSettings, stats, catalog_cost_is_subscription_charge: false};
    const file = persist('runtime', runtime);
    writeOnce(path.join(runDir, 'runner-finished.json'), {at: new Date().toISOString(), runtime_file: file});
    emit({type: 'done', mode: request.mode, runtime_file: file});
  } catch (error) {
    const file = persist('runner-error', {name: error.name, message: error.message,
      at: new Date().toISOString(), timed_out: timedOut, assistant_failure: assistantFailure});
    emit({type: 'failure', file});
    throw error;
  } finally {
    clearTimeout(timeout);
    session.dispose();
    for (const waiter of pending.values()) {clearTimeout(waiter.timer); waiter.reject(new Error('Runner closed'));}
    pending.clear();
    lines.close();
  }
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const index = process.argv.indexOf('--request');
  if (index < 0 || !process.argv[index + 1]) {process.stderr.write('Usage: --request private.json\n'); process.exitCode = 2;}
  else main(process.argv[index + 1]).catch(error => {
    process.stdout.write(JSON.stringify({type: 'error', name: error.name}) + '\n', () => process.exit(1));
  });
}
