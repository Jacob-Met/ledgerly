"""Browser rejection notes through the actual Demo, Agent and SandboxMock."""
from copy import deepcopy
from datetime import date, timedelta
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web-demo" / "python"))
import bridge

SOURCE = "From: Maya Chen <maya.chen@brightfern.example>\nTo: jacob@ledgerly.example\nSubject: Landing page copy - let's go\n\nHi Jacob,\n\nGreat call yesterday. Confirming the scope:\n\n- 12 hours of copywriting at $85/hr\n- 1 x SEO keyword audit @ $300\n\nPayment terms Net 15 as usual.\n\nThanks,\nMaya\n"
DEFAULT_REASON = "Rejected by the browser visitor"


class BrowserRejectionReasonTests(unittest.TestCase):
    def setUp(self):
        bridge.SESSION = bridge.Demo()
        bridge.SESSION.clock.day = date(2026, 10, 8)

    def call(self, action, **payload):
        return json.loads(bridge.handle_json(json.dumps({"action": action, **payload})))

    def draft(self, text=SOURCE):
        result = self.call("draft", text=text)
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["result"]["unauthorized_send_blocked"])
        return result["state"]["pending"][-1]

    def retained_state(self):
        return deepcopy({
            "requests": bridge.SESSION.mock.requests,
            "invoices": bridge.SESSION.mock.invoices,
            "pending": {key: value.to_dict() for key, value in bridge.SESSION.agent.pending.items()},
            "ledger": {key: value.to_dict() for key, value in bridge.SESSION.agent.ledger.items()},
            "audit": bridge.SESSION.agent.audit,
        })

    def test_rejection_keeps_literal_reason_and_refuses_repeat(self):
        action = self.draft()
        reason = "  Revise <milestone> & recipient — 🧾\nKeep the original quote.  "
        requests = deepcopy(bridge.SESSION.mock.requests)
        reply = self.call("reject", action_id=action["id"], reason=reason)
        self.assertTrue(reply["ok"], reply)
        self.assertEqual(reply["result"].get("reason"), reason)
        retained = bridge.SESSION.agent.pending[action["id"]]
        self.assertEqual((retained.status, retained.result), ("REJECTED", {"reason": reason}))
        self.assertEqual(bridge.SESSION.agent.audit[-1]["reason"], reason)
        self.assertEqual(bridge.SESSION.mock.requests, requests)
        self.assertEqual(reply["state"]["pending"], [])
        state = self.retained_state()
        again = self.call("reject", action_id=action["id"], reason="A second reason")
        self.assertFalse(again["ok"])
        self.assertEqual(self.retained_state(), state)

    def test_missing_empty_and_whitespace_keep_legacy_reason(self):
        for payload in ({}, {"reason": ""}, {"reason": " \t\r\n "}):
            with self.subTest(payload=payload):
                self.setUp()
                action = self.draft()
                requests = deepcopy(bridge.SESSION.mock.requests)
                result = self.call("reject", action_id=action["id"], **payload)
                self.assertTrue(result["ok"], result)
                self.assertEqual(bridge.SESSION.agent.pending[action["id"]].result, {"reason": DEFAULT_REASON})
                self.assertEqual(bridge.SESSION.mock.requests, requests)

    def test_non_text_reasons_refuse_without_consuming_the_action(self):
        for reason in (None, True, 17, [], {"note": "not plain text"}):
            with self.subTest(reason=reason):
                self.setUp()
                action = self.draft()
                before = self.retained_state()
                reply = self.call("reject", action_id=action["id"], reason=reason)
                self.assertFalse(reply["ok"], reply)
                self.assertEqual(reply["error"], "ValueError")
                self.assertEqual(self.retained_state(), before)

    def test_limit_counts_characters_and_allows_a_valid_retry(self):
        action = self.draft()
        before = self.retained_state()
        refused = self.call("reject", action_id=action["id"], reason="🧾" * 501)
        self.assertFalse(refused["ok"], refused)
        self.assertEqual(refused["error"], "ValueError")
        self.assertEqual(self.retained_state(), before)
        reason = "🧾" * 500
        accepted = self.call("reject", action_id=action["id"], reason=reason)
        self.assertTrue(accepted["ok"], accepted)
        self.assertEqual(bridge.SESSION.agent.pending[action["id"]].result["reason"], reason)
        self.assertEqual(bridge.SESSION.mock.requests, before["requests"])

    def test_selected_reason_does_not_cross_to_another_action_or_approval(self):
        first = self.draft()
        second = self.draft(SOURCE.replace("Maya", "Nora").replace("maya.chen", "nora.chen"))
        self.assertNotEqual(first["id"], second["id"])
        second_before = deepcopy(bridge.SESSION.agent.pending[second["id"]].to_dict())
        reason = "First invoice needs corrected scope."
        rejected = self.call("reject", action_id=first["id"], reason=reason)
        self.assertTrue(rejected["ok"], rejected)
        self.assertEqual(bridge.SESSION.agent.pending[first["id"]].result["reason"], reason)
        self.assertEqual(bridge.SESSION.agent.pending[second["id"]].to_dict(), second_before)
        self.assertEqual([action["id"] for action in rejected["state"]["pending"]], [second["id"]])
        approved = self.call("approve", action_id=second["id"])
        self.assertTrue(approved["ok"], approved)
        self.assertEqual(bridge.SESSION.agent.pending[second["id"]].status, "APPROVED")
        self.assertEqual(bridge.SESSION.agent.pending[first["id"]].result["reason"], reason)

    def test_reminder_rejection_keeps_its_note_without_sending(self):
        action = self.draft()
        approved = self.call("approve", action_id=action["id"])
        self.assertTrue(approved["ok"], approved)
        due = date.fromisoformat(approved["state"]["ledger"][0]["due_on"])
        advanced = self.call("advance", day=(due + timedelta(days=2)).isoformat())
        self.assertTrue(advanced["ok"], advanced)
        chased = self.call("chase")
        self.assertTrue(chased["ok"], chased)
        reminder = next(action for action in chased["state"]["pending"] if action["kind"] == "send_reminder")
        requests = deepcopy(bridge.SESSION.mock.requests)
        ledger = deepcopy(chased["state"]["ledger"])
        reason = "The client requested a pause.\nCheck back next week."
        rejected = self.call("reject", action_id=reminder["id"], reason=reason)
        self.assertTrue(rejected["ok"], rejected)
        self.assertEqual(rejected["result"].get("reason"), reason)
        self.assertEqual(bridge.SESSION.agent.pending[reminder["id"]].result["reason"], reason)
        self.assertEqual(rejected["state"]["ledger"], ledger)
        self.assertEqual(bridge.SESSION.mock.requests, requests)


if __name__ == "__main__":
    unittest.main()
