"""Independent receipt-term histories through Ledgerly's actual Python bridge.

Usage: python -B check_receipt_receiving.py SOURCE_ROOT RESULT_JSON
All invoice effects are in SandboxMock. No browser or live provider is invoked.
"""
from copy import deepcopy
from dataclasses import asdict
from datetime import date
import hashlib
from itertools import product
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

SOURCE = Path(sys.argv[1]).resolve()
OUTPUT = Path(sys.argv[2]).resolve()
sys.path[:0] = [str(SOURCE), str(SOURCE / 'web-demo/python')]
import ledgerly.agent
import ledgerly.paypal
from bridge import Demo
from ledgerly.paypal import SandboxMock

assert Path(ledgerly.agent.__file__).resolve() == SOURCE / 'ledgerly/agent.py'
assert Path(ledgerly.paypal.__file__).resolve() == SOURCE / 'ledgerly/paypal.py'
FIXTURE = (SOURCE / 'fixtures/01_simple_usd_hourly.txt').read_text()
GROUPS = {}
TERMS = {
    'receipt': ({'term_type': 'DUE_ON_RECEIPT'}, None, date(2026, 10, 8)),
    'none': ({'term_type': 'NO_DUE_DATE'}, None, None),
    'explicit_receipt': ({'term_type': 'DUE_ON_RECEIPT', 'due_date': '2026-11-03'}, date(2026, 11, 3), date(2026, 11, 3)),
    'positive': ({'term_type': 'NET_15', 'due_date': '2026-10-25'}, date(2026, 10, 25), date(2026, 10, 25)),
}


def calls(demo, verb=None, suffix=None):
    return [row for row in demo.mock.requests
            if (verb is None or row[0] == verb) and (suffix is None or row[1].endswith(suffix))]


class IndependentReceiptReceiving(unittest.TestCase):
    def demo(self):
        demo = Demo()
        self.assertIsInstance(demo.mock, SandboxMock)
        demo.clock.day = date(2026, 10, 1)
        return demo

    def draft(self, demo, term='due on receipt', direct=False):
        existing = set(demo.agent.ledger)
        text = FIXTURE.replace('Net 15', term)
        if direct:
            created = demo.agent.tool_create_invoice(text)
            self.assertTrue(created['ok'])
        else:
            out = demo.dispatch({'action': 'draft', 'text': text})
            self.assertTrue(out['result']['unauthorized_send_blocked'])
        new_ids = set(demo.agent.ledger) - existing
        self.assertEqual(len(new_ids), 1)
        iid = new_ids.pop()
        pending = [a for a in demo.agent.pending.values()
                   if a.invoice_id == iid and a.kind == 'send_invoice' and a.status == 'PENDING']
        self.assertEqual(len(pending), 1)
        return iid, pending[0].id, demo.agent.ledger[iid]

    def refresh(self, demo, iid):
        try:
            return demo.agent.tool_get_status(iid)
        except ValueError as exc:
            self.fail(f'Valid supported provider term was refused: {exc}')

    def test_64_three_refresh_histories_keep_current_term_authority(self):
        histories = 0
        for sequence in product(TERMS, repeat=3):
            with self.subTest(sequence=sequence):
                demo = self.demo()
                iid, aid, entry = self.draft(demo, 'Net 12')
                for label in sequence:
                    term, draft_due, _ = TERMS[label]
                    demo.mock.invoices[iid]['detail']['payment_term'] = deepcopy(term)
                    self.refresh(demo, iid)
                    self.assertEqual(entry.due_on, draft_due)
                    self.assertEqual(entry.invoice_due_on, date(2026, 10, 13),
                                     'Provider refresh must not rewrite the historical draft deadline.')
                    self.assertEqual(demo.agent.client._permits, set())
                demo.clock.day = date(2026, 10, 8)
                read_count = len(calls(demo, 'GET'))
                demo.dispatch({'action': 'approve', 'action_id': aid})
                self.assertEqual(len(calls(demo, 'GET')), read_count)
                self.assertEqual(entry.due_on, TERMS[sequence[-1]][2])
                self.refresh(demo, iid)
                self.assertEqual(entry.due_on, TERMS[sequence[-1]][2])
                self.assertEqual(len(calls(demo, 'POST', '/send')), 1)
                self.assertEqual(calls(demo, 'POST', '/remind'), [])
                histories += 1
        GROUPS['refresh_histories'] = {'histories': histories, 'provider_refreshes': histories * 4,
                                       'explicit_mock_invoice_sends': histories}

    def test_mixed_ledger_chases_only_the_invoice_actually_overdue(self):
        demo = self.demo()
        receipt, receipt_aid, receipt_entry = self.draft(demo)
        positive, positive_aid, positive_entry = self.draft(demo, 'Net 12')
        never, never_aid, never_entry = self.draft(demo, 'Net 12')
        demo.mock.invoices[never]['detail']['payment_term'] = {'term_type': 'NO_DUE_DATE'}
        self.refresh(demo, never)
        demo.clock.day = date(2026, 10, 8)
        for aid in (positive_aid, receipt_aid, never_aid):
            demo.dispatch({'action': 'approve', 'action_id': aid})
        self.assertEqual([receipt_entry.due_on, positive_entry.due_on, never_entry.due_on],
                         [date(2026, 10, 8), date(2026, 10, 13), None])
        self.assertEqual(demo.dispatch({'action': 'chase'})['state']['pending'], [])
        demo.clock.day = date(2026, 10, 9)
        first = demo.dispatch({'action': 'chase'})['state']['pending']
        self.assertEqual([(p['kind'], p['invoice_id']) for p in first], [('send_reminder', receipt)])
        self.assertIn('(1d overdue,', first[0]['summary'])
        demo.dispatch({'action': 'approve', 'action_id': first[0]['id']})
        demo.clock.day = date(2026, 10, 14)
        second = demo.dispatch({'action': 'chase'})['state']['pending']
        self.assertEqual([(p['kind'], p['invoice_id']) for p in second], [('send_reminder', positive)])
        self.assertIn('(1d overdue,', second[0]['summary'])
        demo.dispatch({'action': 'approve', 'action_id': second[0]['id']})
        self.assertEqual(len(calls(demo, 'POST', '/send')), 3)
        self.assertEqual(len(calls(demo, 'POST', '/remind')), 2)
        self.assertIsNone(never_entry.due_on)
        self.assertEqual(demo.agent.client._permits, set())
        GROUPS['mixed_ledger'] = {'invoices': 3, 'mock_sends': 3, 'mock_reminders': 2,
                                  'no_same_day_receipt_reminder': True, 'cooldown_preserved': True}

    def test_malformed_receipt_preflight_preserves_pending_then_exact_retry(self):
        cases = 0
        for value in (None, False, True, 0, 8, '', [], {}, '2026-02-30', '2026-10-08T12:00:00Z'):
            with self.subTest(value=value):
                demo = self.demo()
                iid, aid, entry = self.draft(demo)
                demo.clock.day = date(2026, 10, 8)
                demo.dispatch({'action': 'approve', 'action_id': aid})
                demo.clock.day = date(2026, 10, 9)
                reminder = demo.dispatch({'action': 'chase'})['state']['pending'][0]
                rid = reminder['id']
                good = deepcopy(demo.mock.invoices[iid])
                before_entry = asdict(entry)
                before_action = asdict(demo.agent.pending[rid])
                before_audit = deepcopy(demo.agent.audit)
                demo.mock.invoices[iid]['detail']['payment_term'] = {'term_type': 'DUE_ON_RECEIPT', 'due_date': value}
                demo.mock.invoices[iid]['detail']['invoice_number'] = 'UNREVIEWED-FRESH-PARTIAL'
                with self.assertRaises(ValueError):
                    demo.agent.approve(rid)
                self.assertEqual(asdict(entry), before_entry)
                self.assertEqual(asdict(demo.agent.pending[rid]), before_action)
                self.assertEqual(demo.agent.audit, before_audit)
                self.assertEqual(calls(demo, 'POST', '/remind'), [])
                self.assertEqual(demo.agent.client._permits, set())
                demo.mock.invoices[iid] = good
                self.assertTrue(demo.agent.approve(rid)['reminded'])
                self.assertEqual(len(calls(demo, 'POST', '/remind')), 1)
                with self.assertRaises(ValueError):
                    demo.agent.approve(rid)
                self.assertEqual(len(calls(demo, 'POST', '/remind')), 1)
                cases += 1
        GROUPS['malformed_preflight_recovery'] = {'malformed_variants': cases,
            'cache_pending_payload_and_audit_unchanged_on_failure': True, 'explicit_retry_sends_exactly_once': True}

    def test_successful_send_has_no_new_dependency_on_a_post_send_read(self):
        for direct in (False, True):
            with self.subTest(direct=direct):
                demo = self.demo()
                iid, aid, entry = self.draft(demo, direct=direct)
                demo.clock.day = date(2026, 10, 8)
                with patch.object(demo.mock, 'get_invoice', side_effect=AssertionError('unexpected post-send read')) as read:
                    demo.dispatch({'action': 'approve', 'action_id': aid})
                    self.assertEqual(entry.due_on, date(2026, 10, 8))
                    read.assert_not_called()
                self.assertEqual(demo.agent.pending[aid].status, 'APPROVED')
                self.assertEqual(demo.mock.invoices[iid]['detail']['payment_term']['due_date'], '2026-10-08')
                self.assertEqual(len(calls(demo, 'POST', '/send')), 1)
                self.assertEqual(demo.agent.client._permits, set())
        GROUPS['send_without_followup_read'] = {'RulePlanner_and_direct_tool_entry': True, 'cases': 2}


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(IndependentReceiptReceiving)
    with patch('urllib.request.urlopen', side_effect=AssertionError('live network forbidden in independent receiving')):
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    receipt = {'source_root': str(SOURCE), 'source_sha256': {
        path: hashlib.sha256((SOURCE / path).read_bytes()).hexdigest()
        for path in ('ledgerly/agent.py', 'ledgerly/paypal.py', 'web-demo/python/bridge.py', 'web-demo/python/review.py')},
        'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
        'groups': GROUPS, 'passed': result.wasSuccessful(),
        'scope': 'Actual Demo/RulePlanner/Agent/SandboxMock in CPython with urllib network blocked; no browser, provider, production invoice, or external message.'}
    OUTPUT.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': receipt['passed'], 'tests_run': result.testsRun,
                       'failures': len(result.failures), 'errors': len(result.errors), 'groups': GROUPS}))
    sys.exit(not result.wasSuccessful())
