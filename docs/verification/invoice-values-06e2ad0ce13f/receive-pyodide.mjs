// Exercise the exact core through the existing browser bridge and local WASM runtime.
// Run after `npm ci` in web-demo; no application source or provider is changed.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const require = createRequire(path.join(root, 'web-demo/package.json'));
const {loadPyodide} = require('pyodide');
const py = await loadPyodide();
const sourceDigests = {};
py.FS.mkdirTree('/demo/ledgerly');
for (const name of ['__init__.py', 'agent.py', 'extract.py', 'paypal.py']) {
  const bytes = fs.readFileSync(path.join(root, 'ledgerly', name));
  sourceDigests[`ledgerly/${name}`] = crypto.createHash('sha256').update(bytes).digest('hex');
  py.FS.writeFile(`/demo/ledgerly/${name}`, bytes);
}
for (const name of ['bridge.py', 'review.py']) {
  const bytes = fs.readFileSync(path.join(root, 'web-demo/python', name));
  sourceDigests[`web-demo/python/${name}`] = crypto.createHash('sha256').update(bytes).digest('hex');
  py.FS.writeFile(`/demo/${name}`, bytes);
}
const result = await py.runPythonAsync(`
import json, sys
from decimal import Decimal
sys.path.insert(0, '/demo')
import bridge
from ledgerly.agent import Agent
from ledgerly.extract import LLMExtractor
from ledgerly.paypal import SandboxMock

prefix = 'From: Browser fixture <browser@example.test>\\n\\n'
invalid = {
    'fractional_price': '- 2 x Work @ USD 0.015\\n',
    'foreign_deposit': '- 1 x Work @ USD 100.00\\nDeposit already paid: EUR 25.00\\n',
    'signed_price': '- 1 x Anchor @ USD 5.00\\n- 1 x Work @ -$10\\n',
    'malformed_grouping': '- 1 x Anchor @ USD 5.00\\n- 1 x Work @ $1,23\\n',
    'numeric_tail': '- 1 x Anchor @ USD 5.00\\n- 1 x Work @ USD 12.345.67\\n',
    'outside_arithmetic_range': '- 1 x Work @ USD 1e999999999\\nTotal: USD 100\\n',
}
checks = []
def call(action, **values):
    return json.loads(bridge.handle_json(json.dumps(dict(action=action, **values))))
for label, body in invalid.items():
    call('reset')
    source = prefix + body + 'Net 30\\n'
    analysis = call('analyze', text=source)
    assert analysis['ok'], (label, analysis)
    assert any(i['severity'] == 'error' for i in analysis['result']['issues']), label
    drafted = call('draft', text=source)
    assert drafted['ok'], (label, drafted)
    assert drafted['state']['mock_requests'] == 0, label
    assert drafted['state']['ledger'] == [] and drafted['state']['pending'] == [], label
    checks.append(label)

call('reset')
source = prefix + '- .5 x Work @ USD 100.00\\nDeposit already paid: USD 10.00\\nNet 30\\n'
drafted = call('draft', text=source)
assert drafted['ok'] and drafted['result']['unauthorized_send_blocked'], drafted
assert Decimal(drafted['state']['ledger'][0]['total']) == Decimal('50.00'), drafted
pending = drafted['state']['pending'][0]
sent = call('approve', action_id=pending['id'])
assert sent['ok'], sent
assert sent['state']['ledger'][0]['status'] == 'PARTIALLY_PAID', sent
assert Decimal(sent['state']['ledger'][0]['paid_amount']) == Decimal('10.00'), sent
assert Decimal(sent['state']['ledger'][0]['balance']) == Decimal('40.00'), sent
assert sent['state']['external_calls'] == 0
checks.append('explicit_approval_preserves_exact_deposit_and_balance')

payload = {'client_name': 'Browser fixture', 'client_email': 'browser@example.test',
           'currency': 'USD', 'line_items': [{'desc': 'Work', 'qty': 'NaN',
           'unit_price': '10', 'currency': 'USD'}], 'due_days': 30, 'confidence': 1.0}
mock = SandboxMock()
agent = Agent(mock, {'name': 'Fixture', 'email_address': 'sender@example.test'},
              extractor=LLMExtractor(lambda _: json.dumps(payload)))
result = agent.tool_create_invoice(prefix + '- 1 x Work @ USD 10\\n')
assert result['needs_review'] and mock.requests == []
checks.append('structured_nonfinite_quantity')

call('reset')
source = prefix + '- 1 x Work @ USD 100.00\\nNet 30\\n'
call('analyze', text=source)
fields = {'client_name': 'Browser fixture', 'client_email': 'browser@example.test',
          'due_days': '30', 'amount_paid': '0', 'line_items': [
          {'desc': 'Reviewed work', 'qty': '2', 'unit_price': '0.015',
           'currency': 'USD', 'unit': ''}]}
checked = call('review', text=source, confirmed=True, fields=fields)
assert checked['ok'] and checked['result']['valid'] is False, checked
assert checked['result']['review_id'] is None and checked['state']['mock_requests'] == 0
checks.append('current_review_adapter_refuses_implicit_rounding')
fields['line_items'][0].update(qty='0.5', unit_price='85.00')
fields['amount_paid'] = '10.00'
checked = call('review', text=source, confirmed=True, fields=fields)
assert checked['ok'] and checked['result']['valid'], checked
revision = checked['result']['review_id']
drafted = call('draft', text=source, review_id=revision)
assert drafted['ok'] and drafted['result']['reviewed'], drafted
assert drafted['result']['unauthorized_send_blocked'], drafted
assert Decimal(drafted['state']['ledger'][0]['total']) == Decimal('42.50'), drafted
calls = drafted['state']['mock_requests']
replayed = call('draft', text=source, review_id=revision)
assert replayed['ok'] is False and replayed['state']['mock_requests'] == calls, replayed
assert len(replayed['state']['ledger']) == 1 and len(replayed['state']['pending']) == 1
checks.append('current_review_adapter_keeps_checked_revision_one_use')
json.dumps({'python': sys.version, 'checks': checks, 'passed': len(checks), 'external_calls': 0})
`);
console.log(JSON.stringify({sourceDigests, ...JSON.parse(String(result))}, null, 2));
