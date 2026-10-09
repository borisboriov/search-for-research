import assert from 'node:assert/strict';
import {mkdtempSync, rmSync, readFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {test} from 'node:test';
import {allowedCall, createGuardedFetch, writeOnce} from './enrichment_pi_runner.mjs';

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
