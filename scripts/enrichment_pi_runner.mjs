export * from '../enrichment/research/legacy/js/enrichment_pi_runner.mjs';
import {main} from '../enrichment/research/legacy/js/enrichment_pi_runner.mjs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const index = process.argv.indexOf('--request');
  if (index < 0 || !process.argv[index + 1]) {process.stderr.write('Usage: --request private.json\n'); process.exitCode = 2;}
  else main(process.argv[index + 1]).catch(error => {
    process.stdout.write(JSON.stringify({type: 'error', name: error.name}) + '\n', () => process.exit(1));
  });
}
