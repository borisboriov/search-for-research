#!/usr/bin/env node
/** Isolated Pi 1.1.0 SDK runner. Host grants every MCP source invocation first. */
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import readline from 'node:readline';
import { pathToFileURL } from 'node:url';

export const SOURCE_TOOLS = Object.freeze({zai_search: 'web_search_prime', zai_reader: 'webReader'});
export function writeOnce(file, value) {
  const temporary = `${file}.tmp-${process.pid}-${Math.random().toString(16).slice(2)}`;
  try {
    fs.writeFileSync(temporary, JSON.stringify(value, null, 2) + '\n', {flag: 'wx', mode: 0o600});
    const descriptor = fs.openSync(temporary, 'r');
    try {fs.fsyncSync(descriptor);} finally {fs.closeSync(descriptor);}
    fs.linkSync(temporary, file);
  } finally {if (fs.existsSync(temporary)) fs.unlinkSync(temporary);}
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

export async function main(requestPath) {
  const request = JSON.parse(fs.readFileSync(requestPath, 'utf8'));
  if (!['discover', 'collect', 'verify'].includes(request.mode)) throw new Error('Invalid mode');
  if (typeof request.system_prompt !== 'string' || !request.workspace_dir || !request.run_dir)
    throw new Error('Missing isolated input');
  const runDir = path.resolve(request.run_dir);
  fs.mkdirSync(runDir, {recursive: true, mode: 0o700});
  writeOnce(path.join(runDir, 'runner-started.json'), {at: new Date().toISOString(), mode: request.mode});
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
    if (waiter) {pending.delete(response.id); waiter(response);}
  });
  const reserve = async data => {
    const id = `reservation-${++seq}`;
    const response = new Promise(resolve => pending.set(id, resolve));
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
    provider: {maxRetries: 0, timeoutMs: 600000}}, compaction: {enabled: false}});
  const modelRuntime = await sdk.ModelRuntime.create({allowModelNetwork: false, refreshOnCreate: false});
  const model = modelRuntime.getModel('zai', 'glm-5.3-flash');
  if (!model) throw new Error('Required configured model unavailable');
  const mcp = sdk.createMcpExtension({
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
    createTransport: (entry, cwd, auth) => {
      const inner = createDefaultTransport(entry, cwd, auth);
      const listeners = new Set();
      const deliver = message => {for (const listener of listeners) listener(message);};
      inner.onMessage(message => {
        const file = persist('mcp-response', {server: entry.name, message});
        emit({type: 'mcp_result', server: entry.name, rpc_id: message.id ?? null, file});
        deliver(entry.name === 'zai_reader' ? readerView(message) : message);
        // Full result has been saved before bounded text is delivered to model.
      });
      return {
        start: () => inner.start(), close: () => inner.close(),
        onMessage: listener => {listeners.add(listener); return () => listeners.delete(listener);},
        onError: listener => inner.onError(listener), onClose: listener => inner.onClose(listener),
        setProtocolVersion: version => inner.setProtocolVersion?.(version),
        send: async message => {
          if (message.method === 'tools/call') {
            const name = message.params?.name;
            if (!allowedCall(entry.name, name, request.mode)) throw new Error('Unapproved source tool');
            const permission = await reserve({server: entry.name, tool: name,
              arguments: message.params.arguments, rpc_id: message.id});
            persist('reservation', {server: entry.name, name, rpc_id: message.id, permission});
            if (!permission.allowed) {
              const denied = {jsonrpc: '2.0', id: message.id, result: {isError: true,
                content: [{type: 'text', text: `Access not performed: ${permission.reason || 'host denied'}`} ]}};
              const file = persist('denied-mcp-response', {server: entry.name, message: denied});
              emit({type: 'mcp_result', server: entry.name, rpc_id: message.id, file, performed: false});
              deliver(denied);
              return;
            }
            if (permission.replacement_result) {
              const cached = {jsonrpc: '2.0', id: message.id, result: permission.replacement_result};
              const file = persist('cached-mcp-response', {server: entry.name, message: cached});
              emit({type: 'mcp_result', server: entry.name, rpc_id: message.id, file, performed: false, cached: true});
              deliver(cached);
              return;
            }
          }
          persist('mcp-request', {server: entry.name, message});
          await inner.send(message);
        },
      };
    },
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
    modelRuntime, model, thinkingLevel: 'low', noTools: 'builtin',
    tools: request.mode === 'verify' ? [] : Object.entries(SOURCE_TOOLS).map(([s,t]) => `mcp__${s}__${t}`)});
  let timeout;
  let timedOut = false;
  let assistantFailure = false;
  try {
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
    if (request.mode === 'discover') {emit({type: 'done', mode: 'discover'}); return;}
    session.subscribe(event => {
      if (event.type === 'message_end' && event.message?.role === 'assistant' &&
          ['error', 'aborted'].includes(event.message.stopReason)) assistantFailure = true;
      const file = persist('session-event', event);
      emit({type: 'event', event_type: event.type, file});
    });
    timeout = setTimeout(() => {timedOut = true; session.abort();}, 600000);
    const publicInput = request.output_schema ? {task: request.task, output_json_schema: request.output_schema} : request.task;
    await session.prompt(JSON.stringify(publicInput), {expandPromptTemplates: false});
    if (timedOut || assistantFailure) throw new Error('Agent did not complete normally');
    const stats = session.getSessionStats();
    const runtime = {provider: session.model?.provider ?? null, model: session.model?.id ?? null,
      effort: session.thinkingLevel, routed_model: session.routedModel?.model?.id ?? null,
      pi_version: sdk.VERSION, stats, catalog_cost_is_subscription_charge: false};
    const file = persist('runtime', runtime);
    writeOnce(path.join(runDir, 'runner-finished.json'), {at: new Date().toISOString(), runtime_file: file});
    emit({type: 'done', mode: request.mode, runtime_file: file});
  } catch (error) {
    const file = persist('runner-error', {name: error.name, message: error.message,
      at: new Date().toISOString(), timed_out: timedOut, assistant_failure: assistantFailure});
    emit({type: 'failure', file});
    throw error;
  } finally {clearTimeout(timeout); session.dispose(); lines.close();}
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const index = process.argv.indexOf('--request');
  if (index < 0 || !process.argv[index + 1]) {process.stderr.write('Usage: --request private.json\n'); process.exitCode = 2;}
  else main(process.argv[index + 1]).catch(error => {
    process.stdout.write(JSON.stringify({type: 'error', name: error.name}) + '\n', () => process.exit(1));
  });
}
