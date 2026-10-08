"""Bounded native reproduction of overdue batch starvation; no product edits."""
import argparse
from datetime import date, timedelta, datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--pins', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.dont_write_bytecode = True
sys.path[:0] = [str(args.source / 'web-demo/python'), str(args.source)]
pins = json.loads(args.pins.read_text())

def verify():
    for item in pins['files']:
        data = (args.source / item['path']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == item['sha256'], item['path']

verify()
from bridge import Demo
from ledgerly.paypal import SandboxMock

fixture = (args.source / 'fixtures/01_simple_usd_hourly.txt').read_text()

def scenario(count):
    demo = Demo()
    demo.clock.day = date(2026, 10, 8)
    assert isinstance(demo.mock, SandboxMock)
    invoice_ids = []
    for index in range(count):
        text = fixture.replace("Landing page copy - let's go", f'Fictional batch invoice {index + 1}')
        drafted = demo.dispatch({'action': 'draft', 'text': text})
        assert drafted['result']['unauthorized_send_blocked'] is True
        pending = drafted['state']['pending']
        assert len(pending) == 1 and pending[0]['kind'] == 'send_invoice'
        action = pending[0]
        sent = demo.dispatch({'action': 'approve', 'action_id': action['id']})
        assert sent['result']['approved'] is True
        invoice_ids.append(action['invoice_id'])
    state = demo.snapshot()
    assert len(state['ledger']) == count and not state['pending']
    due = date.fromisoformat(state['ledger'][0]['due_on'])
    demo.dispatch({'action': 'advance', 'day': (due + timedelta(days=1)).isoformat()})
    eligible = demo.agent.tool_list_overdue()['overdue']
    assert len(eligible) == count
    attempts = []

    def chase(label):
        before_audit = len(demo.agent.audit)
        before_requests = len(demo.mock.requests)
        response = demo.dispatch({'action': 'chase'})
        state = response['state']
        actions = state['pending']
        assert all(a['kind'] == 'send_reminder' for a in actions)
        visited = [row['args']['invoice_id'] for row in demo.agent.audit[before_audit:]
                   if row.get('event') == 'tool' and row.get('tool') == 'send_reminder']
        record = {'label': label, 'final': response['result']['final'],
                  'pending_action_ids': [a['id'] for a in actions],
                  'pending_invoice_ids': [a['invoice_id'] for a in actions],
                  'visited_invoice_ids': visited,
                  'mock_request_delta': len(demo.mock.requests) - before_requests,
                  'external_calls': state['external_calls']}
        attempts.append(record)
        assert state['external_calls'] == 0
        return response

    first = chase('first explicit scan')
    if count == 10:
        assert len(first['state']['pending']) == 10
        assert first['result']['final'] != 'step limit reached'
    else:
        assert count == 13 and len(first['state']['pending']) == 11
        assert first['result']['final'] == 'step limit reached'
        assert attempts[0]['visited_invoice_ids'] == invoice_ids[:11]
        repeated = chase('second explicit scan while first reminders await approval')
        assert repeated['state']['pending'] == first['state']['pending']
        assert attempts[1]['visited_invoice_ids'] == invoice_ids[:11]
        for action in first['state']['pending']:
            approved = demo.dispatch({'action': 'approve', 'action_id': action['id']})
            assert approved['result']['approved'] is True
        after_approval = chase('third explicit scan after approving all eleven queued reminders')
        assert not after_approval['state']['pending']
        assert attempts[2]['visited_invoice_ids'] == invoice_ids[:11]
        assert len(demo.agent.tool_list_overdue()['overdue']) == 13
        assert all(demo.agent.ledger[i].reminders_sent == 1 for i in invoice_ids[:11])
        assert all(demo.agent.ledger[i].reminders_sent == 0 for i in invoice_ids[11:])
    return {'invoice_count': count, 'today': demo.clock.day.isoformat(),
            'due_on': due.isoformat(), 'invoice_ids_in_native_order': invoice_ids,
            'attempts': attempts,
            'reminders_sent_by_invoice': {i: demo.agent.ledger[i].reminders_sent for i in invoice_ids},
            'source_mutated': False}

receipt = {'started_utc': datetime.now(timezone.utc).isoformat(),
           'source_commit': pins['commit'], 'source_tree': pins['tree'],
           'producer': 'Exact bridge.Demo -> Agent/RulePlanner/GatedClient/SandboxMock',
           'scope': 'Fictional in-memory native controls, not an actual browser run or live invoice claim',
           'small_batch_control': scenario(10), 'larger_batch_reproduction': scenario(13)}
verify()
receipt.update({'completed_utc': datetime.now(timezone.utc).isoformat(),
                'source_inputs_verified_before_after': len(pins['files']),
                'baseline_gap_reproduced': True,
                'interpretation': 'Each scan spends its twelve-step budget on list_overdue plus the first eleven invoice attempts. Repeated scans revisit those same invoices, even while their reminders are pending or cooling down, leaving the last two unvisited.'})
args.output.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'baseline_gap_reproduced': True, 'small_batch_queued': 10,
                  'larger_batch_invoices': 13, 'first_scan_queued': 11,
                  'repeated_scan_new_reminders': 0, 'never_visited_tail': 2,
                  'source_inputs_verified_before_after': len(pins['files']),
                  'external_calls': 0, 'output': str(args.output)}))
