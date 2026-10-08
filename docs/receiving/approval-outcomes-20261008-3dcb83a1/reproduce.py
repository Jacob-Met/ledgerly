"""Offline actual Agent/SandboxMock reproduction, runnable against either source tree."""
import json
import os
import pathlib
import sys
from datetime import date, datetime, time, timezone
import urllib.request

os.environ["LEDGERLY_ALLOW_NETWORK"] = "0"
sys.dont_write_bytecode = True
source = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(source))
from ledgerly.agent import Agent
from ledgerly.paypal import SandboxMock

external_attempts = []
def no_network(*args, **kwargs):
    external_attempts.append("urlopen")
    raise AssertionError("The receiving control must remain offline")
urllib.request.urlopen = no_network

class LostResponse(SandboxMock):
    fail_at = None
    def remind_invoice(self, invoice_id, body=None):
        result = super().remind_invoice(invoice_id, body)
        if self.fail_at == "remind":
            self.fail_at = None
            raise TimeoutError("authored reminder response lost after mock effect")
        return result
    def get_invoice(self, invoice_id):
        result = super().get_invoice(invoice_id)
        if self.fail_at == "get":
            self.fail_at = None
            raise TimeoutError("authored read response lost before dispatch")
        return result

def reminder_posts(mock):
    return sum(path.endswith("/remind") for _, path, _ in mock.requests)

def run_case(failure):
    day = [date(2026, 10, 1)]
    mock = LostResponse(now=lambda: datetime.combine(day[0], time.min, tzinfo=timezone.utc))
    agent = Agent(mock, {"name": "Authored receiver", "email_address": "receiver@ledgerly.example"},
                  today=lambda: day[0])
    invoice = agent.tool_create_invoice((source/"fixtures/01_simple_usd_hourly.txt").read_text())["invoices"][0]
    agent.approve(invoice["approval_id"], approver="offline fixture")
    day[0] = date(2026, 10, 20)
    action_id = agent.tool_send_reminder(invoice["invoice_id"])["approval_id"]
    mock.fail_at = failure
    try:
        agent.approve(action_id, approver="offline fixture")
    except Exception as error:
        original_error = type(error).__name__
    else:
        raise AssertionError("authored first call must raise")
    first = {"error": original_error, "status": agent.pending[action_id].status,
             "listed_pending": any(a["id"] == action_id for a in agent.list_pending()),
             "reminder_posts": reminder_posts(mock)}
    try:
        retry = {"result": agent.approve(action_id, approver="explicit fixture retry")}
    except Exception as error:
        retry = {"error": type(error).__name__, "message": str(error)}
    return {"failure": failure, "first": first,
            "retry": retry, "final_status": agent.pending[action_id].status,
            "reminder_posts": reminder_posts(mock),
            "ledger_reminders_sent": agent.ledger[invoice["invoice_id"]].reminders_sent}

cases = [run_case("remind"), run_case("get")]
print(json.dumps({"source": str(source), "cases": cases,
                  "external_calls": len(external_attempts)}, indent=2))
