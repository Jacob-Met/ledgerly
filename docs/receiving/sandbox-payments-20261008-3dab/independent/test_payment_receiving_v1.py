"""Independent payment receiving: rounded invoices and sequential bridge retries."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import unittest
import urllib.request
from datetime import date
from decimal import Decimal

ROOT = Path(sys.argv[1]).resolve()
RECEIPT = Path(sys.argv[2])
sys.path[:0] = [str(ROOT), str(ROOT / "web-demo/python")]
os.environ["LEDGERLY_ALLOW_NETWORK"] = "0"
NETWORK_ATTEMPTS = []
def network_forbidden(*args, **kwargs):
    NETWORK_ATTEMPTS.append("forbidden network/provider entry")
    raise RuntimeError("Network/provider operations are forbidden in this authored review")
urllib.request.urlopen = network_forbidden
socket.create_connection = network_forbidden
from ledgerly import paypal
paypal.HttpPayPalClient.__init__ = network_forbidden
spec = importlib.util.spec_from_file_location("independent_payment_bridge", ROOT / "web-demo/python/bridge.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
OBSERVATIONS = []

class PaymentReview(unittest.TestCase):
    def call(self, demo, **request):
        bridge.SESSION = demo
        return json.loads(bridge.handle_json(json.dumps(request)))

    def approved(self, text=None):
        demo = bridge.Demo()
        demo.clock.day = date(2026, 10, 8)
        if text is None:
            text = (ROOT / "fixtures/02_gbp_proofreading.txt").read_text()
        draft = self.call(demo, action="draft", text=text)
        self.assertTrue(draft["ok"], draft)
        self.assertTrue(draft["result"]["unauthorized_send_blocked"])
        action = draft["state"]["pending"][0]
        self.assertEqual(demo.mock.invoices[action["invoice_id"]]["status"], "DRAFT")
        approved = self.call(demo, action="approve", action_id=action["id"])
        self.assertTrue(approved["ok"], approved)
        return demo, action["invoice_id"]

    @staticmethod
    def retained(demo, invoice_id):
        return (copy.deepcopy(demo.mock.invoices[invoice_id]),
                copy.deepcopy(demo.agent.export_state()),
                copy.deepcopy(demo.last_event))

    def test_currency_rounding_of_valid_fractional_quantities_remains_payable(self):
        for quantity, expected_total in (("1.5", "0.02"), ("1.3", "0.01")):
            with self.subTest(quantity=quantity):
                text = (ROOT / "fixtures/02_gbp_proofreading.txt").read_text()
                text = text.replace("18 hours @ £40/hr", quantity + " hours @ £0.01/hr")
                text = text.replace("Style sheet preparation: 2 hrs @ £40/hr\n", "")
                demo, invoice_id = self.approved(text)
                invoice = demo.mock.invoices[invoice_id]
                self.assertEqual(invoice["amount"]["value"], expected_total)
                items = copy.deepcopy(invoice["items"])
                first = self.call(demo, action="payment", invoice_id=invoice_id, amount="0.01")
                row = {"case": "fractional_quantity", "quantity": quantity, "total": expected_total,
                       "first_ok": first["ok"], "first_error": first.get("message"),
                       "paid_after": invoice["payments"]["paid_amount"]["value"],
                       "transaction_count": len(invoice["payments"]["transactions"])}
                OBSERVATIONS.append(row)
                self.assertTrue(first["ok"], first)
                self.assertEqual(invoice["payments"]["paid_amount"]["value"], "0.01")
                if quantity == "1.5":
                    self.assertEqual(invoice["status"], "PARTIALLY_PAID")
                    self.assertEqual(invoice["due_amount"]["value"], "0.01")
                    last = self.call(demo, action="payment", invoice_id=invoice_id)
                    self.assertTrue(last["ok"], last)
                    self.assertEqual(len(invoice["payments"]["transactions"]), 2)
                else:
                    self.assertEqual(len(invoice["payments"]["transactions"]), 1)
                self.assertEqual(invoice["status"], "PAID")
                self.assertEqual(invoice["payments"]["paid_amount"]["value"], expected_total)
                self.assertEqual(invoice["due_amount"]["value"], "0.00")
                self.assertEqual(invoice["items"], items)
                replay = self.call(demo, action="replay")
                self.assertTrue(replay["ok"], replay)
                self.assertTrue(replay["result"]["duplicate"])
                row.update(final_status=invoice["status"],
                           final_paid=invoice["payments"]["paid_amount"]["value"],
                           final_transactions=len(invoice["payments"]["transactions"]),
                           replay_duplicate=replay["result"]["duplicate"])

    def test_same_partial_invoice_survives_six_refusals_and_exact_retries(self):
        demo, invoice_id = self.approved()
        invoice = demo.mock.invoices[invoice_id]
        first = self.call(demo, action="payment", invoice_id=invoice_id, amount="12.34")
        self.assertTrue(first["ok"], first)
        first_transaction = copy.deepcopy(invoice["payments"]["transactions"][0])
        first_event = copy.deepcopy(demo.last_event)
        paid = Decimal("12.34")
        bad_values = (0, False, "NaN", "-0.01", "0.001", -0.0)
        for index, bad in enumerate(bad_values):
            before = self.retained(demo, invoice_id)
            request_count = len(demo.mock.requests)
            failed = self.call(demo, action="payment", invoice_id=invoice_id, amount=bad)
            row = {"case": "sequential_refusal_retry", "index": index, "value": bad,
                   "value_type": type(bad).__name__, "refused": not failed["ok"],
                   "error": failed.get("error"), "message": failed.get("message"),
                   "state_preserved": self.retained(demo, invoice_id) == before,
                   "mock_requests_preserved": len(demo.mock.requests) == request_count}
            OBSERVATIONS.append(row)
            self.assertFalse(failed["ok"], failed)
            self.assertEqual(self.retained(demo, invoice_id), before)
            self.assertEqual(len(demo.mock.requests), request_count)
            self.assertIs(demo.mock.invoices[invoice_id], invoice)
            replay = self.call(demo, action="replay")
            self.assertTrue(replay["ok"], replay)
            self.assertTrue(replay["result"]["duplicate"])
            self.assertEqual(demo.mock.invoices[invoice_id], before[0])
            retry = self.call(demo, action="payment", invoice_id=invoice_id, amount="1.23")
            self.assertTrue(retry["ok"], retry)
            paid += Decimal("1.23")
            self.assertEqual(Decimal(invoice["payments"]["paid_amount"]["value"]), paid)
            self.assertEqual(Decimal(invoice["due_amount"]["value"]), Decimal("800.00") - paid)
            self.assertEqual(Decimal(retry["state"]["ledger"][0]["paid_amount"]), paid)
            self.assertEqual(invoice["status"], "PARTIALLY_PAID")
            self.assertEqual(len(invoice["payments"]["transactions"]), index + 2)
            self.assertEqual(invoice["payments"]["transactions"][0], first_transaction)
            row.update(replay_duplicate=True, retry_ok=True, paid=str(paid),
                       transactions=len(invoice["payments"]["transactions"]))
        full = self.call(demo, action="payment", invoice_id=invoice_id, amount=None)
        self.assertTrue(full["ok"], full)
        self.assertEqual(invoice["status"], "PAID")
        self.assertEqual(invoice["payments"]["paid_amount"]["value"], "800.00")
        self.assertEqual(len(invoice["payments"]["transactions"]), len(bad_values) + 2)
        settled = copy.deepcopy(invoice)
        old_replay = demo.agent.handle_webhook(*first_event)
        self.assertTrue(old_replay["duplicate"], old_replay)
        self.assertEqual(invoice, settled)
        self.assertEqual(json.loads(demo.agent.export_state())["ledger"][0]["status"], "PAID")
        OBSERVATIONS.append({"case": "settlement", "paid": "800.00", "transactions": len(bad_values)+2,
                             "old_partial_event_duplicate": True, "old_event_did_not_regress_settled_invoice": True})

if __name__ == "__main__":
    files = {rel: hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
             for rel in ("ledgerly/paypal.py", "ledgerly/agent.py", "ledgerly/extract.py",
                         "web-demo/python/bridge.py", "web-demo/python/review.py")}
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PaymentReview))
    after = {rel: hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() for rel in files}
    payload = {"subject": str(ROOT), "python": sys.version, "optimize": sys.flags.optimize,
               "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "source_before": files, "source_after": after, "tests": result.testsRun,
               "failures": len(result.failures), "errors": len(result.errors),
               "skipped": len(result.skipped), "network_attempts": NETWORK_ATTEMPTS,
               "observations": OBSERVATIONS}
    RECEIPT.write_text(json.dumps(payload, indent=2, allow_nan=False)+"\n")
    ok = result.wasSuccessful() and files == after and not NETWORK_ATTEMPTS
    print("PAYMENT_REVIEW " + ("OK" if ok else "FAIL") +
          f" tests={result.testsRun} failures={len(result.failures)} errors={len(result.errors)}")
    raise SystemExit(0 if ok else 1)
