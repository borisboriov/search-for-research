/** Session-local extension for the supported Pi CLI. Never calls a model API. */
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {SOURCE_TOOLS, writeOnce, createGuardedFetch, createSourceQueue,
  createSerializedTransport, validateConfig} from './enrichment_pi_runner.mjs';

export const CLI_METHOD = 'enrichment-cli-bounded-v1';
export function boundedPayload(payload, budget, finalizing) {
  if (!Array.isArray(payload.messages)) throw new Error('Unknown provider payload');
  const directive = 'HOST CONTROL (not source prose): ' + JSON.stringify(budget) +
    (finalizing ? '. Source tools are closed. Return final JSON now using saved evidence; unknown stays unknown.' :
      '. Robots are checked only by host. Do not request robots.txt. Caps are not targets.');
  return {...payload, messages: [...payload.messages, {role: 'system', content: directive}],
    ...(finalizing ? {tools: undefined, tool_choice: undefined} : {})};
}
export function recordEvent(event) {
  return ['message_end', 'tool_execution_start', 'tool_execution_end', 'agent_settled'].includes(event.type);
}
export function safetyBoundary(queue, handler) {
  return (...args) => {
    try {
      const result = handler(...args);
      if (result?.then) return result.catch(error => {queue.stop(error); throw error;});
      return result;
    } catch (error) {queue.stop(error); throw error;}
  };
}

export default async function extension(pi) {
  const queue = createSourceQueue();
  const nativeFetch = globalThis.fetch;
  // Pi reports extension errors and can continue. Latch BEFORE loading/configuring
  // the extension so even swallowed errors stop all subsequent physical requests.
  globalThis.fetch = (...args) => {queue.assertHealthy(); return nativeFetch(...args);};
  try {
  const requestPath = process.env.SFR_PI_REQUEST_PATH;
  if (!requestPath) throw new Error('Explicit host request required');
  const request = JSON.parse(fs.readFileSync(requestPath, 'utf8'));
  const config = validateConfig(request.config);
  if (request.method !== CLI_METHOD || request.mode !== 'collect') throw new Error('Unapproved CLI method');
  const runDir = path.resolve(request.run_dir);
  fs.mkdirSync(runDir, {recursive: true, mode: 0o700});
  let seq = 0, started = Date.now(), modelRequests = 0, finalizing = false, failed = false;
  let budget = {search_remaining: 4, resources_remaining_including_robots: 8, host_robots: 0, source_reads: 0};
  const persist = safetyBoundary(queue, (kind, value) => {
    const file = `${String(++seq).padStart(6, '0')}-${kind}.json`;
    writeOnce(path.join(runDir, file), value);
    return file;
  });
  // Protocol records consumed by the host, not diagnostic output or model context.
  const emit = value => process.stdout.write(JSON.stringify({sfr_host: true, ...value}) + '\n');
  const reserve = async data => {
    const id = `reservation-${++seq}`;
    emit({type: 'reserve', id, ...data});
    const permission = path.join(runDir, `${id}.permission.json`);
    const until = Date.now() + 30000;
    while (!fs.existsSync(permission) && Date.now() < until) await new Promise(resolve => setTimeout(resolve, 50));
    if (!fs.existsSync(permission)) {queue.stop(new Error('Host permission timeout')); queue.assertHealthy();}
    const value = JSON.parse(fs.readFileSync(permission, 'utf8'));
    if (value.id !== id || !value.budget) throw new Error('Invalid host permission');
    budget = value.budget;
    return value;
  };
  globalThis.fetch = createGuardedFetch(globalThis.fetch, info => {
    const file = persist('http', info);
    emit({type: 'http', file, status: info.status, origin: info.origin, pathname: info.pathname});
  }, url => {queue.assertHealthy(); return url.origin === 'https://api.z.ai' &&
    (url.pathname.startsWith('/api/coding/paas/v4/') ||
     ['/api/mcp/web_search_prime/mcp', '/api/mcp/web_reader/mcp'].includes(url.pathname));});
  // Pi's documented extension factory: only its native MCP transport is customized.
  // CLI owns authentication, sessions and all model execution.
  const pkg = path.join(os.homedir(), '.pi/agent/install/releases/1.1.0/node_modules/@earendil-works/pi-coding-agent/dist');
  const {createMcpExtension} = await import(pathToFileURL(path.join(pkg, 'extensions/mcp/index.js')).href);
  const {loadMcpConfig} = await import(pathToFileURL(path.join(pkg, 'extensions/mcp/config.js')).href);
  const {createDefaultTransport} = await import(pathToFileURL(path.join(pkg, 'extensions/mcp/runtime.js')).href);
  await createMcpExtension({
    logPath: path.join(runDir, 'mcp.log'), startupWaitMs: 30000,
    loadConfig: () => {
      const loaded = loadMcpConfig({agentDir: path.join(os.homedir(), '.pi/agent'), cwd: request.workspace_dir, projectTrusted: false});
      if (loaded.errors.length) throw new Error('Invalid native MCP configuration');
      const servers = loaded.servers.filter(entry => Object.hasOwn(SOURCE_TOOLS, entry.name));
      if (servers.length !== 2) throw new Error('Missing approved source servers');
      return {servers: servers.map(entry => ({...entry, config: {...entry.config,
        exposure: 'direct', toolExposure: {}, enabled: true}})), errors: [], autoEnableCodemode: false};
    },
    createTransport: (entry, cwd, auth) => createSerializedTransport({
      inner: createDefaultTransport(entry, cwd, auth), server: entry.name, mode: 'collect', queue,
      reserve, persist, emit, timeoutMs: 45000}),
  })(pi);
  const effective = ctx => {
    const result = {provider: ctx.model?.provider, model: ctx.model?.id, effort: pi.getThinkingLevel()};
    if (Object.keys(config).some(key => result[key] !== config[key])) throw new Error('CLI configuration mismatch');
    return result;
  };
  const checkRuntime = ctx => {
    const settings = pi.getSettings();
    if (settings.retry?.enabled !== false || settings.retry?.maxRetries !== 0 ||
        settings.retry?.provider?.maxRetries !== 0 || settings.cacheWarming !== 'off' ||
        settings.compaction?.enabled !== false) throw new Error('CLI retry/cache configuration mismatch');
    const names = pi.getActiveTools();
    const approved = Object.entries(SOURCE_TOOLS).map(([server, tool]) => `mcp__${server}__${tool}`);
    if (names.length !== 2 || names.some(name => !approved.includes(name))) throw new Error('Unexpected CLI tools');
    return {requested: config, effective: effective(ctx), backend: null,
      tools: names, cli: 'pi', version: '1.1.0', settings: {retry: settings.retry, cacheWarming: settings.cacheWarming,
        compaction: settings.compaction}};
  };
  pi.registerCommand('sfr-preflight', {description: 'Inspect isolated runtime without any model request',
    handler: safetyBoundary(queue, async (args, ctx) => {
      const until = Date.now() + 30000;
      while (pi.getActiveTools().length < 2 && Date.now() < until)
        await new Promise(resolve => setTimeout(resolve, 50));
      const runtime = checkRuntime(ctx);
      persist('cli-preflight', {...runtime, model_requests: modelRequests, succeeded: modelRequests === 0});
      ctx.shutdown();
    }),
  });
  pi.on('before_agent_start', safetyBoundary(queue, (event, ctx) => {
    started = Date.now();
    persist('runtime-config', checkRuntime(ctx));
    return {systemPrompt: request.system_prompt};
  }));
  pi.on('before_provider_request', safetyBoundary(queue, (event, ctx) => {
    queue.assertHealthy();
    effective(ctx);
    if (failed || modelRequests >= 6) throw new Error('Bounded model request limit');
    modelRequests++;
    const seconds = (Date.now() - started) / 1000;
    finalizing ||= seconds >= 360 || budget.resources_remaining_including_robots <= 0 || modelRequests >= 6;
    if (finalizing) pi.setActiveTools([]);
    const live = {...budget, elapsed_seconds: seconds, seconds_remaining: Math.max(0, 590 - seconds),
      model_requests_including_this: modelRequests, finalizing};
    const payload = boundedPayload(event.payload, live, finalizing);
    persist('model-request-config', {requested: config, effective: effective(ctx), backend: null, budget: live,
      instruction_sha256: createHash('sha256').update(request.system_prompt).digest('hex')});
    return payload;
  }));
  pi.on('tool_call', safetyBoundary(queue, event => {
    queue.assertHealthy();
    if (finalizing) return {block: true, reason: 'Source phase closed; return final JSON'};
    if (event.toolName === 'mcp__zai_reader__webReader' && new URL(event.input.url).pathname === '/robots.txt')
      return {block: true, reason: 'Host-only robots policy; do not repeat robots reads'};
  }));
  pi.on('message_end', event => {
    if (event.message.role === 'assistant' && ['error', 'aborted'].includes(event.message.stopReason)) failed = true;
  });
  pi.on('agent_settled', safetyBoundary(queue, (event, ctx) => {
    queue.assertHealthy();
    if (event.aborted || failed) throw new Error('CLI agent failed or aborted');
    const file = persist('runtime', {requested: config, effective: effective(ctx), backend: null, model_requests: modelRequests});
    emit({type: 'done', runtime_file: file});
  }));
  } catch (error) {queue.stop(error); throw error;}
}
