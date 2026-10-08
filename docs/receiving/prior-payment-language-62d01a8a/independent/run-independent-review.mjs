import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';

const [sourceDirectory, label, mode = 'normal'] = process.argv.slice(2);
if (!sourceDirectory || !label || !['normal', 'optimized'].includes(mode)) throw new Error('Usage: node run-independent-review.mjs SOURCE_DIRECTORY LABEL [normal|optimized]');
const source = path.resolve(sourceDirectory);
const sha256 = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const files = ['ledgerly/extract.py', 'ledgerly/agent.py', 'ledgerly/paypal.py', 'web-demo/python/review.py'];
const pins = () => Object.fromEntries(files.map(file => [file, sha256(fs.readFileSync(path.join(source, file)))]));
const before = pins();
const evaluator = fs.readFileSync('independent-payment-review.py');
const args = [...(mode === 'optimized' ? ['-O'] : []), 'independent-payment-review.py'];
const result = spawnSync('python', args, { encoding: 'utf8', env: { ...process.env, LEDGERLY_REVIEW_ROOT: source }, timeout: 30000 });
if (result.error) throw result.error;
const output = result.stdout + result.stderr;
fs.writeFileSync(label + '.log', output, { flag: 'wx' });
const sourceUnchanged = JSON.stringify(before) === JSON.stringify(pins());
const receipt = { source_root: source, mode, command: ['python', ...args], exit_code: result.status, signal: result.signal,
  source_sha256: before, source_unchanged: sourceUnchanged, evaluator_sha256: sha256(evaluator),
  log: label + '.log', log_sha256: sha256(Buffer.from(output)), summary: output.split('\n').filter(line => /^Ran |^FAILED|^OK/.test(line)) };
fs.writeFileSync(label + '.json', JSON.stringify(receipt, null, 2) + '\n', { flag: 'wx' });
console.log(JSON.stringify(receipt, null, 2));
if (!sourceUnchanged || result.signal) process.exitCode = 1;
