"""Exercise the CLI's human decisions using its real in-memory provider."""
from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from ledgerly import demo
from ledgerly.paypal import SandboxMock


class InteractiveDemoTests(unittest.TestCase):
    def run_demo(self, answers: list[str] | None):
        mock = SandboxMock()
        output = io.StringIO()
        before_decisions: list[list[str]] = []
        remaining = iter(answers or [])

        def decide(_prompt: str) -> str:
            before_decisions.append([path for _, path, _ in mock.requests])
            return next(remaining)

        args = ["ledgerly.demo", "--interactive"] if answers is not None else ["ledgerly.demo"]
        with patch.object(sys, "argv", args), patch.object(demo, "SandboxMock", return_value=mock), \
                patch("builtins.input", side_effect=decide), \
                patch.dict(os.environ, {"LEDGERLY_ALLOW_NETWORK": "0"}), \
                contextlib.redirect_stdout(output):
            demo.main()
        return mock, output.getvalue(), before_decisions

    def test_all_rejections_and_default_no_finish_without_outgoing_mock_actions(self):
        for answer in ("n", ""):
            with self.subTest(answer=answer):
                mock, output, decisions = self.run_demo([answer] * 20)
                self.assertGreater(len(mock.invoices), 0)
                self.assertEqual(len(decisions), len(mock.invoices))
                self.assertTrue(all(inv["status"] == "DRAFT" for inv in mock.invoices.values()))
                self.assertTrue(all(not inv["payments"]["transactions"] for inv in mock.invoices.values()))
                self.assertFalse(any(path.endswith(("/send", "/remind", "/payments"))
                                     for _, path, _ in mock.requests))
                self.assertIn("skipping the mock payment", output)
                self.assertNotIn("=== Payer pays", output)
                self.assertIn("=== Ledger", output)
                self.assertIn("(network calls: 0)", output)

    def test_actual_interactive_entrypoint_accepts_all_no_responses(self):
        root = Path(demo.__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "-B", "-m", "ledgerly.demo", "--interactive"],
            cwd=root, input="n\n" * 20, capture_output=True, text=True, timeout=10,
            env={"LEDGERLY_ALLOW_NETWORK": "0", "PYTHONPATH": str(root),
                 "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("approve? [y/N]", result.stdout)
        self.assertIn("=== Ledger", result.stdout)
        self.assertIn("(network calls: 0)", result.stdout)

    def test_a_later_approved_invoice_gets_paid_instead_of_the_first_draft(self):
        mock, output, decisions = self.run_demo(["n", "y"] + ["n"] * 20)
        invoices = list(mock.invoices.values())
        self.assertEqual(invoices[0]["status"], "DRAFT")
        self.assertEqual(invoices[1]["status"], "PAID")
        self.assertTrue(all(inv["status"] == "DRAFT" for inv in invoices[2:]))
        sends = [path for _, path, _ in mock.requests if path.endswith("/send")]
        self.assertEqual(sends, [f"/v2/invoicing/invoices/{invoices[1]['id']}/send"])
        self.assertFalse(any(path.endswith("/send") for path in decisions[1]))
        self.assertIn(f"=== Payer pays {invoices[1]['detail']['invoice_number']}", output)
        self.assertIn("=== Ledger", output)

    def test_remaining_sent_invoice_still_needs_a_reminder_decision(self):
        mock, output, decisions = self.run_demo(["y", "y"] + ["n"] * 20)
        invoices = list(mock.invoices.values())
        self.assertEqual(invoices[0]["status"], "PAID")
        self.assertEqual(invoices[1]["status"], "SENT")
        self.assertEqual(len(decisions), len(invoices) + 1)
        self.assertFalse(any(path.endswith("/remind") for _, path, _ in mock.requests))
        self.assertIn("reminder", output)
        self.assertIn("=== Ledger", output)

    def test_scripted_mode_keeps_the_existing_payment_and_reminder_walkthrough(self):
        mock, output, decisions = self.run_demo(None)
        self.assertEqual(decisions, [])
        self.assertEqual(sum(inv["status"] == "PAID" for inv in mock.invoices.values()), 1)
        self.assertEqual(sum(path.endswith("/send") for _, path, _ in mock.requests), len(mock.invoices))
        self.assertEqual(sum(path.endswith("/remind") for _, path, _ in mock.requests), len(mock.invoices) - 1)
        self.assertIn("(scripted demo: approving)", output)
        self.assertIn("=== Payer pays", output)
        self.assertIn("=== Ledger", output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
