import {beforeAll, expect, it} from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import {loadPyodide} from 'pyodide';
import {completedReviewsMarkup} from '../src/review-history';
import {approvalCardMarkup, approvalProposalMarkup} from '../src/approval-preview';

const record = (overrides: Record<string, unknown> = {}) => ({
  id: 'action-fictional-1', kind: 'send_reminder', invoice_id: 'INV-FICTIONAL-1',
  summary: 'Remind fictional client', status: 'REJECTED', created_at: '2026-01-02T10:04:03+00:00',
  payload: {subject: 'Question about Zoë’s invoice', note: 'First line\n<em>literal second line</em>\nEUR 80.00'},
  result: {reason: 'Rejected by the browser visitor'}, ...overrides,
});

it('keeps the original reminder, queue time and recorded reason with no action controls', () => {
  const action = record(), before = JSON.stringify(action);
  const markup = completedReviewsMarkup([action]);
  expect(markup).toContain('Original queued reminder');
  expect(markup).toContain('Question about Zoë’s invoice');
  expect(markup).toContain('First line\n&lt;em&gt;literal second line&lt;/em&gt;\nEUR 80.00');
  expect(markup).toContain('Queued at');
  expect(markup).toContain(action.created_at);
  expect(markup).toContain('Rejected by the browser visitor');
  expect(markup).not.toMatch(/<button|data-approve|data-reject|data-pay|<a\b/);
  expect(JSON.stringify(action)).toBe(before);
});

it('shows UNKNOWN in the collapsed summary only when the recorded result says UNKNOWN', () => {
  const unknown = completedReviewsMarkup([record({status: 'FAILED', result: {outcome: 'UNKNOWN', reason: 'Check the invoice', error_type: 'TimeoutError'}})]);
  expect(unknown.slice(0, unknown.indexOf('</summary>'))).toContain('FAILED · OUTCOME UNKNOWN');
  expect(unknown).toContain('TimeoutError');
  expect(unknown).toContain('Check the invoice');
  const refusal = completedReviewsMarkup([record({status: 'FAILED', result: {name: 'UNPROCESSABLE_ENTITY', message: 'Provider refused this request'}})]);
  expect(refusal).toContain('FAILED');
  expect(refusal).toContain('Provider refused this request');
  expect(refusal).not.toContain('OUTCOME UNKNOWN');
  expect(refusal).not.toContain('Outcome unknown.');
});

it('retains automatic rejection reasons without describing them as a human rejection', () => {
  const markup = completedReviewsMarkup([record({result: {reason: 'auto: reminder facts or review date changed'}})]);
  expect(markup).toContain('auto: reminder facts or review date changed');
  expect(markup).not.toContain('Rejected by the browser visitor');
});

it('renders queued invoice decimal text and literal visitor content through the shared proposal renderer', () => {
  const invoice = record({kind: 'send_invoice', status: 'APPROVED', summary: 'Invoice <script>literal()</script>',
    payload: {prepaid: '0.00', invoice: {detail: {currency_code: 'EUR', invoice_number: 'I-002', invoice_date: '2026-01-02', payment_term: {term_type: 'NET_30'}, note: '<img src=x onerror=window.injected=1>'},
      primary_recipients: [{billing_info: {name: {given_name: 'Zoë', surname: '<b>Client</b>'}, email_address: 'fictional@example.test'}}],
      items: [{name: 'Révision\n<svg onload=bad()>', quantity: '1.50', unit_amount: {currency_code: 'EUR', value: '80.00'}}]}},
    result: {payer_view: 'https://example.test/<untrusted>'}});
  const markup = completedReviewsMarkup([invoice]);
  expect(markup).toContain('Original queued invoice');
  expect(markup).toContain('1.50');
  expect(markup).toContain('EUR 80.00');
  expect(markup).toContain('EUR 0.00');
  expect(markup).toContain('fictional@example.test');
  expect(markup).toContain('Net 30 days');
  expect(markup).toContain('&lt;script&gt;literal()&lt;/script&gt;');
  expect(markup).toContain('&lt;img src=x onerror=window.injected=1&gt;');
  expect(markup).toContain('Zoë &lt;b&gt;Client&lt;/b&gt; · fictional@example.test');
  expect(markup).toContain('&lt;b&gt;Client&lt;/b&gt;');
  expect(markup).not.toMatch(/<script|<img|<svg|<button|data-approve|data-reject|<a\b/);
});

it('retains missing and non-object result values without claiming a successful delivery', () => {
  for (const value of [null, false, 0, '', ['recorded', '<literal>']]) {
    const markup = completedReviewsMarkup([record({status: 'APPROVED', result: value})]);
    expect(markup).toContain('Recorded result');
    expect(markup).not.toContain('delivered');
    expect(markup).not.toContain('OUTCOME UNKNOWN');
    if (value === null) expect(markup).toContain('No result details were recorded.');
    else {
      const encoded = markup.split('<pre data-review-result>')[1].split('</pre>')[0];
      const decoded = encoded.replaceAll('&quot;', '"').replaceAll('&#39;', "'").replaceAll('&lt;', '<').replaceAll('&gt;', '>').replaceAll('&amp;', '&');
      expect(JSON.parse(decoded)).toEqual(value);
    }
  }
});

it('excludes pending and unknown-status records without truncating completed history', () => {
  const rows = Array.from({length: 23}, (_, index) => record({id: 'closed-' + index}));
  const markup = completedReviewsMarkup([...rows, record({status: 'PENDING'}), record({status: 'FUTURE_STATUS'})]);
  expect(markup.match(/data-review-id=/g)).toHaveLength(23);
  expect(markup).not.toContain('PENDING');
  expect(markup).not.toContain('FUTURE_STATUS');
  expect(completedReviewsMarkup([])).toContain('No completed reviews');
  expect(completedReviewsMarkup(undefined)).toContain('No completed reviews');
});

it('keeps the pending proposal and approval controls in the existing card only', () => {
  const action = record();
  expect(approvalProposalMarkup(action)).toContain('Review queued reminder');
  expect(approvalProposalMarkup(action, 'completed')).toContain('Original queued reminder');
  expect(approvalProposalMarkup(action, 'completed')).not.toContain('<button');
  const pending = approvalCardMarkup(action);
  expect(pending).toContain('data-approve="action-fictional-1"');
  expect(pending).toContain('data-reject="action-fictional-1"');
  expect(pending).toContain('Review queued reminder');
  expect(pending).not.toContain('Original queued reminder');
});

let py: Awaited<ReturnType<typeof loadPyodide>>;
beforeAll(async () => {
  py = await loadPyodide();
  py.FS.mkdirTree('/demo/ledgerly');
  py.FS.mkdirTree('/demo/fixtures');
  py.FS.mkdirTree('/demo/tests');
  const web = process.cwd();
  for (const name of ['__init__.py', 'agent.py', 'extract.py', 'paypal.py']) {
    py.FS.writeFile('/demo/ledgerly/' + name, fs.readFileSync(path.join(web, 'public/python/ledgerly', name), 'utf8'));
  }
  for (const name of ['bridge.py', 'review.py', 'invoice_details.py', 'review_history.py']) {
    py.FS.writeFile('/demo/' + name, fs.readFileSync(path.join(web, 'public/python', name), 'utf8'));
  }
  py.FS.writeFile('/demo/fixtures/01_simple_usd_hourly.txt', fs.readFileSync(path.join(web, 'public/fixtures/01_simple_usd_hourly.txt'), 'utf8'));
  py.FS.writeFile('/demo/tests/test_review_history.py', fs.readFileSync(path.join(web, '../tests/test_review_history.py'), 'utf8'));
  await py.runPythonAsync("import sys; sys.path.insert(0, '/demo')");
});

it('runs all ten unchanged native receiving cases through actual Pyodide', async () => {
  const raw = await py.runPythonAsync(`
import importlib.util, io, json, unittest
spec = importlib.util.spec_from_file_location('history_receiving', '/demo/tests/test_review_history.py')
tests = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tests)
output = io.StringIO()
result = unittest.TextTestRunner(stream=output).run(unittest.defaultTestLoader.loadTestsFromTestCase(tests.CompletedReviewTests))
json.dumps({"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "successful": result.wasSuccessful(), "log": output.getvalue()})
`);
  const receipt = JSON.parse(String(raw));
  expect(receipt.log).toContain('Ran 10 tests');
  expect(receipt).toMatchObject({tests: 10, failures: 0, errors: 0, successful: true});
}, 30000);
