"""Compact independent CLI review: explicit SandboxMock, network disabled."""
from __future__ import annotations
import contextlib
import io
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(os.environ['LEDGERLY_REVIEW_ROOT']).resolve()))
from ledgerly import demo
from ledgerly.paypal import SandboxMock


class DeclinedDemoReview(unittest.TestCase):
    def execute(self, decide):
        mock = SandboxMock()
        output = io.StringIO()
        prompts = []

        def answer(prompt):
            prompts.append(prompt)
            return decide(mock, len(prompts))

        with patch.object(demo, 'SandboxMock', return_value=mock), \
             patch.object(sys, 'argv', ['ledgerly.demo', '--interactive']), \
             patch('builtins.input', side_effect=answer), \
             patch.dict(os.environ, {'LEDGERLY_ALLOW_NETWORK': '0'}), \
             patch.object(mock, 'simulate_payer_payment', wraps=mock.simulate_payer_payment) as payment, \
             contextlib.redirect_stdout(output):
            demo.main()
        return mock, output.getvalue(), prompts, payment.call_args_list

    def terminal(self, mock, output):
        self.assertIn('=== Gate check: trying to send without approval', output)
        self.assertIn('blocked:', output)
        self.assertIn('=== Ledger\n', output)
        terminal = output.split('=== Ledger\n', 1)[1]
        for invoice in mock.invoices.values():
            self.assertIn(invoice['detail']['invoice_number'], terminal)
        self.assertTrue(terminal.rstrip().endswith('(network calls: 0)'))

    def test_non_y_answers_preserve_every_decline_and_finish_report(self):
        answers = ('', ' ', 'n', 'NO', 'yes', '0', '\t')
        mock, output, prompts, payments = self.execute(lambda client, n: answers[(n-1) % len(answers)])
        self.assertGreater(len(prompts), 0)
        self.assertEqual(len(prompts), len(mock.invoices))
        self.assertEqual(payments, [])
        self.assertTrue(all(invoice['status'] == 'DRAFT' for invoice in mock.invoices.values()))
        self.assertFalse(any(path.endswith(('/send', '/remind', '/payments')) for _, path, _ in mock.requests))
        self.assertIn('skipping the mock payment', output)
        self.terminal(mock, output)

    def test_only_last_explicit_approval_is_paid_after_that_decision(self):
        decision_snapshots = []
        def decide(client, n):
            decision_snapshots.append(list(client.requests))
            return ' \tY \n' if n == len(client.invoices) else ''
        mock, output, prompts, payments = self.execute(decide)
        invoices = list(mock.invoices.values())
        self.assertGreaterEqual(len(invoices), 2)
        self.assertEqual(len(prompts), len(invoices))
        self.assertTrue(all(invoice['status'] == 'DRAFT' for invoice in invoices[:-1]))
        self.assertEqual(invoices[-1]['status'], 'PAID')
        self.assertEqual([call.args[0] for call in payments], [invoices[-1]['id']])
        self.assertFalse(any(path.endswith('/send') for rows in decision_snapshots for _, path, _ in rows))
        self.assertEqual([path for _, path, _ in mock.requests if path.endswith('/send')],
            ['/v2/invoicing/invoices/' + invoices[-1]['id'] + '/send'])
        self.terminal(mock, output)

    def test_every_overdue_reminder_still_requires_a_separate_yes(self):
        send_decisions = []
        def decide(client, n):
            if n <= len(client.invoices):
                send_decisions.append(sum(path.endswith('/send') for _, path, _ in client.requests))
                return 'y'
            return ''
        mock, output, prompts, payments = self.execute(decide)
        invoices = list(mock.invoices.values())
        self.assertEqual(send_decisions, list(range(len(invoices))))
        self.assertEqual(len(prompts), len(invoices) * 2 - 1)
        self.assertEqual(len(payments), 1)
        self.assertEqual(sum(invoice['status'] == 'PAID' for invoice in invoices), 1)
        self.assertEqual(sum(invoice['status'] == 'SENT' for invoice in invoices), len(invoices)-1)
        self.assertFalse(any(path.endswith('/remind') for _, path, _ in mock.requests))
        self.terminal(mock, output)


if __name__ == '__main__':
    unittest.main(verbosity=2)
