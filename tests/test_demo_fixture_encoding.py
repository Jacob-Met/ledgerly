"""The shipped demo must read the same invoice scope under legacy locale defaults."""
from __future__ import annotations

import contextlib
from decimal import Decimal
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from ledgerly import demo
from ledgerly.paypal import SandboxMock


class DemoFixtureEncodingTests(unittest.TestCase):
    def test_legacy_default_keeps_both_priya_currency_drafts(self):
        original_read = Path.read_text

        def legacy_default(path, encoding=None, errors=None, **kwargs):
            # Model a Windows cp1252 file default on every test platform.
            # Explicit encodings still use the actual pathlib file reader.
            return original_read(path, encoding=encoding or "cp1252",
                                 errors=errors, **kwargs)

        mock = SandboxMock()
        output = io.StringIO()
        with patch.object(Path, "read_text", legacy_default), \
                patch.object(demo, "SandboxMock", return_value=mock), \
                patch.object(sys, "argv", ["ledgerly.demo", "--interactive"]), \
                patch("builtins.input", return_value="n") as decide, \
                contextlib.redirect_stdout(output):
            demo.main()

        actual = sorted(
            (invoice["primary_recipients"][0]["billing_info"]["email_address"],
             invoice["detail"]["currency_code"],
             Decimal(invoice["amount"]["value"]), invoice["status"])
            for invoice in mock.invoices.values()
        )
        self.assertEqual(actual, sorted([
            ("maya.chen@brightfern.example", "USD", Decimal("1320"), "DRAFT"),
            ("priya@orbitlabs.example", "USD", Decimal("1900"), "DRAFT"),
            ("priya@orbitlabs.example", "EUR", Decimal("360"), "DRAFT"),
            ("victor@quickflip.example", "USD", Decimal("450"), "DRAFT"),
        ]))
        self.assertEqual(decide.call_count, 4)
        self.assertFalse(any(path.endswith(("/send", "/remind", "/payments"))
                             for _, path, _ in mock.requests))
        self.assertTrue(all(not invoice["payments"]["transactions"]
                            for invoice in mock.invoices.values()))
        self.assertIn("skipping the mock payment", output.getvalue())
        self.assertNotIn("=== Payer pays", output.getvalue())
        self.assertIn("(network calls: 0)", output.getvalue())


if __name__ == "__main__":
    unittest.main()
