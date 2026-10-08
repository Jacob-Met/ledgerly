"""Receipt terms across bridge, provider refresh, and approved/external mock sends."""
from copy import deepcopy
from dataclasses import asdict, fields
from datetime import date, timedelta
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web-demo" / "python"))
from bridge import Demo
from ledgerly.agent import ApprovalRequired, LedgerEntry
from ledgerly.paypal import PayPalError, SandboxMock, payment_term

SOURCE = (Path(__file__).resolve().parents[1] / "fixtures" / "01_simple_usd_hourly.txt").read_text()


class ReceiptTermReceiving(unittest.TestCase):
    def draft(self, day=date(2026, 10, 1), reviewed=False, terms="due on receipt"):
        demo = Demo()
        self.assertIsInstance(demo.mock, SandboxMock)
        demo.clock.day = day
        text = SOURCE.replace("Net 15", terms)
        request = {"action": "draft", "text": text}
        if reviewed:
            demo.dispatch({"action": "analyze", "text": text})
            checked = demo.dispatch({"action": "review", "text": text, "confirmed": True,
                                    "fields": {"client_name": "Maya Chen", "client_email": "maya@example.test",
                                               "due_days": "0", "amount_paid": "0",
                                               "line_items": [{"desc": "Reviewed copy", "qty": "1",
                                                               "unit_price": "40", "currency": "USD", "unit": "hours"}]}})
            self.assertTrue(checked["result"]["valid"])
            request["review_id"] = checked["result"]["review_id"]
        out = demo.dispatch(request)
        self.assertTrue(out["result"]["unauthorized_send_blocked"])
        self.assertEqual([p["kind"] for p in out["state"]["pending"]], ["send_invoice"])
        action = out["state"]["pending"][0]
        return demo, action, demo.agent.ledger[action["invoice_id"]]

    @staticmethod
    def sent(mock, operation):
        return [body for method, path, body in mock.requests
                if method == "POST" and path.endswith("/" + operation)]

    def reject_stale_then_observe_external_send(self, demo, action):
        """Keep provider-date receiving without approving changed invoice words.

        The external send is an authored provider-side event, using SandboxMock
        directly. Unchanged workflow cases still test Agent-approved sends.
        """
        invoice_id = action["invoice_id"]
        payload = deepcopy(demo.agent.pending[action["id"]].payload)
        cached = asdict(demo.agent.ledger[invoice_id])
        sends = self.sent(demo.mock, "send")
        with self.assertRaisesRegex(ValueError, "already REJECTED.*review"):
            demo.dispatch({"action": "approve", "action_id": action["id"]})
        self.assertEqual(demo.agent.pending[action["id"]].status, "REJECTED")
        self.assertEqual(demo.agent.pending[action["id"]].payload, payload)
        self.assertEqual(asdict(demo.agent.ledger[invoice_id]), cached)
        self.assertEqual(self.sent(demo.mock, "send"), sends)
        self.assertEqual(demo.agent.client._permits, set())
        demo.mock.send_invoice(invoice_id)
        self.assertEqual(len(self.sent(demo.mock, "send")), len(sends) + 1)
        demo.agent.tool_get_status(invoice_id)

    def test_raw_and_reviewed_receipt_workflows_across_calendar_boundaries(self):
        for reviewed in (False, True):
            for drafted_on, sent_on in ((date(2026, 10, 1), date(2026, 10, 8)),
                                       (date(2026, 12, 25), date(2027, 1, 2)),
                                       (date(2028, 2, 20), date(2028, 2, 29)),
                                       (date(2027, 2, 28), date(2027, 3, 1))):
                with self.subTest(reviewed=reviewed, sent_on=sent_on):
                    demo, action, entry = self.draft(drafted_on, reviewed)
                    iid = action["invoice_id"]
                    term = demo.mock.invoices[iid]["detail"]["payment_term"]
                    self.assertEqual(term, {"term_type": "DUE_ON_RECEIPT"})
                    self.assertIsNone(entry.due_on)
                    self.assertTrue(getattr(entry, "provider_receipt_pending", False))
                    self.assertFalse(entry.provider_due_known)
                    self.assertEqual(self.sent(demo.mock, "send"), [])
                    demo.dispatch({"action": "advance", "day": sent_on.isoformat()})
                    self.assertIsNone(entry.due_on)
                    demo.dispatch({"action": "approve", "action_id": action["id"]})
                    self.assertEqual(entry.sent_on, sent_on)
                    self.assertEqual(entry.due_on, sent_on)
                    self.assertEqual(term["due_date"], sent_on.isoformat())
                    self.assertEqual(demo.mock.invoices[iid]["detail"]["metadata"]["last_sent_time"][:10], sent_on.isoformat())
                    self.assertEqual(demo.dispatch({"action": "chase"})["state"]["pending"], [])
                    demo.agent.tool_get_status(iid)
                    self.assertTrue(entry.provider_due_known)
                    self.assertFalse(getattr(entry, "provider_receipt_pending", False))
                    self.assertEqual(entry.due_on, sent_on)
                    demo.dispatch({"action": "advance", "day": (sent_on + timedelta(days=1)).isoformat()})
                    chased = demo.dispatch({"action": "chase"})
                    reminders = chased["state"]["pending"]
                    self.assertEqual([p["kind"] for p in reminders], ["send_reminder"])
                    self.assertIn("(1d overdue,", reminders[0]["summary"])
                    self.assertIn(sent_on.strftime("%b %d, %Y"), reminders[0]["payload"]["note"])
                    self.assertEqual(self.sent(demo.mock, "remind"), [])
                    demo.dispatch({"action": "approve", "action_id": reminders[0]["id"]})
                    self.assertEqual(len(self.sent(demo.mock, "send")), 1)
                    self.assertEqual(len(self.sent(demo.mock, "remind")), 1)
                    with self.assertRaises(ValueError):
                        demo.agent.approve(reminders[0]["id"])
                    self.assertEqual(demo.snapshot()["external_calls"], 0)

    def test_receipt_builder_does_not_choose_a_date_before_receipt(self):
        for day in (date(2026, 10, 1), date(2028, 2, 29)):
            self.assertEqual(payment_term(0, day), {"term_type": "DUE_ON_RECEIPT"})
        self.assertEqual(payment_term(None, date(2026, 10, 1)), {"term_type": "NO_DUE_DATE"})
        self.assertEqual(payment_term(12, date(2026, 10, 1)),
                         {"term_type": "DUE_ON_DATE_SPECIFIED", "due_date": "2026-10-13"})

    def test_provider_replaces_positive_draft_with_unresolved_receipt_term(self):
        demo, action, entry = self.draft(terms="Net 12")
        self.assertEqual(entry.invoice_due_on, date(2026, 10, 13))
        self.assertEqual(entry.due_on, date(2026, 10, 13))
        demo.mock.invoices[action["invoice_id"]]["detail"]["payment_term"] = {"term_type": "DUE_ON_RECEIPT"}
        try:
            demo.agent.tool_get_status(action["invoice_id"])
        except ValueError as exc:
            self.fail(f"Valid undated draft receipt term was refused: {exc}")
        self.assertIsNone(entry.due_on)
        self.assertEqual(entry.invoice_due_on, date(2026, 10, 13))
        self.assertTrue(getattr(entry, "provider_receipt_pending", False))
        demo.dispatch({"action": "advance", "day": "2026-10-08"})
        self.reject_stale_then_observe_external_send(demo, action)
        self.assertEqual(entry.due_on, date(2026, 10, 8))
        self.assertEqual(demo.dispatch({"action": "chase"})["state"]["pending"], [])
        demo.agent.tool_get_status(action["invoice_id"])
        self.assertEqual(entry.due_on, date(2026, 10, 8))
        self.assertFalse(getattr(entry, "provider_receipt_pending", False))

    def test_explicit_provider_date_and_no_due_date_replace_pending_receipt(self):
        for term, expected in (({"term_type": "DUE_ON_RECEIPT", "due_date": "2026-11-01"}, date(2026, 11, 1)),
                               ({"term_type": "DUE_ON_DATE_SPECIFIED", "due_date": "2026-11-03"}, date(2026, 11, 3)),
                               ({"term_type": "NO_DUE_DATE"}, None)):
            with self.subTest(term=term):
                demo, action, entry = self.draft()
                demo.mock.invoices[action["invoice_id"]]["detail"]["payment_term"] = deepcopy(term)
                demo.agent.tool_get_status(action["invoice_id"])
                self.assertFalse(getattr(entry, "provider_receipt_pending", False))
                self.assertTrue(entry.provider_due_known)
                self.assertEqual(entry.due_on, expected)
                demo.dispatch({"action": "advance", "day": "2026-10-08"})
                self.reject_stale_then_observe_external_send(demo, action)
                self.assertEqual(entry.due_on, expected)
                self.assertEqual(demo.mock.invoices[action["invoice_id"]]["detail"]["payment_term"], term)
                demo.agent.tool_get_status(action["invoice_id"])
                self.assertEqual(entry.due_on, expected)
                self.assertEqual(self.sent(demo.mock, "remind"), [])

    def test_bad_provider_terms_do_not_replace_any_cached_fact(self):
        for term in (None, {}, {"term_type": "DUE_ON_DATE_SPECIFIED"},
                     *({"term_type": "DUE_ON_RECEIPT", "due_date": invalid}
                       for invalid in (None, False, 0, "", [], {}, "2026-02-30"))):
            with self.subTest(term=term):
                demo, action, entry = self.draft()
                before = asdict(entry)
                inv = demo.mock.invoices[action["invoice_id"]]
                inv["detail"]["payment_term"] = term
                inv["detail"]["invoice_number"] = "UNREVIEWED-BAD-TERM"
                with self.assertRaises(ValueError):
                    demo.agent.tool_get_status(action["invoice_id"])
                self.assertEqual(asdict(entry), before)
                self.assertEqual(self.sent(demo.mock, "send"), [])
                self.assertEqual(demo.agent.client._permits, set())

    def test_failed_or_unapproved_send_does_not_resolve_receipt_date(self):
        demo, action, entry = self.draft()
        iid = action["invoice_id"]
        with self.assertRaises(ApprovalRequired):
            demo.agent.client.send_invoice(iid)
        demo.mock.invoices[iid]["_has_recipient_email"] = False
        demo.dispatch({"action": "advance", "day": "2026-10-08"})
        with self.assertRaises(PayPalError):
            demo.agent.approve(action["id"])
        self.assertEqual(entry.status, "DRAFT")
        self.assertIsNone(entry.sent_on)
        self.assertIsNone(entry.due_on)
        self.assertNotIn("due_date", demo.mock.invoices[iid]["detail"]["payment_term"])
        self.assertIsNone(demo.mock.invoices[iid]["detail"]["metadata"].get("last_sent_time"))
        self.assertEqual(self.sent(demo.mock, "remind"), [])
        self.assertEqual(demo.agent.client._permits, set())

    def test_later_provider_date_edit_still_invalidates_the_old_reminder(self):
        demo, action, entry = self.draft()
        demo.dispatch({"action": "advance", "day": "2026-10-08"})
        demo.dispatch({"action": "approve", "action_id": action["id"]})
        demo.dispatch({"action": "advance", "day": "2026-10-09"})
        reminder = demo.dispatch({"action": "chase"})["state"]["pending"][0]
        old_note = reminder["payload"]["note"]
        demo.mock.invoices[action["invoice_id"]]["detail"]["payment_term"]["due_date"] = "2026-11-01"
        with self.assertRaises(ValueError):
            demo.agent.approve(reminder["id"])
        self.assertEqual(demo.agent.pending[reminder["id"]].status, "REJECTED")
        self.assertEqual(demo.agent.pending[reminder["id"]].payload["note"], old_note)
        self.assertEqual(entry.due_on, date(2026, 11, 1))
        self.assertFalse(demo.agent.tool_send_reminder(action["invoice_id"])["ok"])
        self.assertEqual(self.sent(demo.mock, "remind"), [])

    def test_unresolved_sent_provider_receipt_is_held_without_erasing_known_state(self):
        demo, action, entry = self.draft()
        demo.dispatch({"action": "advance", "day": "2026-10-08"})
        demo.dispatch({"action": "approve", "action_id": action["id"]})
        demo.agent.tool_get_status(action["invoice_id"])
        before = asdict(entry)
        del demo.mock.invoices[action["invoice_id"]]["detail"]["payment_term"]["due_date"]
        with self.assertRaises(ValueError):
            demo.agent.tool_get_status(action["invoice_id"])
        self.assertEqual(asdict(entry), before)
        self.assertEqual(self.sent(demo.mock, "remind"), [])

    def test_receipt_term_observed_after_external_send_cannot_invent_a_deadline(self):
        demo, action, entry = self.draft()
        before = asdict(entry)
        demo.mock.invoices[action["invoice_id"]]["status"] = "SENT"
        demo.mock.invoices[action["invoice_id"]]["detail"]["payment_term"] = {"term_type": "DUE_ON_RECEIPT"}
        demo.dispatch({"action": "advance", "day": "2026-10-20"})
        with self.assertRaises(ValueError):
            demo.agent.tool_get_status(action["invoice_id"])
        self.assertEqual(asdict(entry), before)
        self.assertIsNone(entry.sent_on)
        self.assertIsNone(entry.due_on)
        self.assertEqual(self.sent(demo.mock, "send"), [])
        self.assertEqual(self.sent(demo.mock, "remind"), [])

    def test_receipt_marker_does_not_survive_a_valid_provider_term_replacement(self):
        demo, action, entry = self.draft(terms="Net 12")
        for term, expected, pending in (({"term_type": "DUE_ON_RECEIPT"}, None, True),
                                        ({"term_type": "NO_DUE_DATE"}, None, False),
                                        ({"term_type": "NET_15", "due_date": "2026-10-30"}, date(2026, 10, 30), False),
                                        ({"term_type": "DUE_ON_RECEIPT"}, None, True),
                                        ({"term_type": "DUE_ON_DATE_SPECIFIED", "due_date": "2026-11-03"}, date(2026, 11, 3), False)):
            with self.subTest(term=term):
                demo.mock.invoices[action["invoice_id"]]["detail"]["payment_term"] = term
                try:
                    demo.agent.tool_get_status(action["invoice_id"])
                except ValueError as exc:
                    self.fail(f"Valid provider term replacement was refused: {exc}")
                self.assertEqual(entry.due_on, expected)
                self.assertEqual(getattr(entry, "provider_receipt_pending", False), pending)
                self.assertEqual(entry.provider_due_known, not pending)
        demo.dispatch({"action": "advance", "day": "2026-10-08"})
        self.reject_stale_then_observe_external_send(demo, action)
        self.assertEqual(entry.due_on, date(2026, 11, 3))
        self.assertEqual(self.sent(demo.mock, "remind"), [])

    def test_current_ledger_positional_prefix_is_unchanged(self):
        prefix = ["invoice_id", "invoice_number", "client_name", "client_email", "currency", "total", "due_days",
                  "status", "sent_on", "paid_amount", "reminders_sent", "last_reminder_on", "prepaid",
                  "provider_due_on", "provider_due_known", "invoice_due_on"]
        self.assertEqual([f.name for f in fields(LedgerEntry)][:len(prefix)], prefix)


if __name__ == "__main__":
    unittest.main(verbosity=2)
