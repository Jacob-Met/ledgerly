"""Offline, authored receiving witness; no approval or network call."""
from datetime import date
from ledgerly.extract import RulesExtractor
from ledgerly.agent import Agent
from ledgerly.paypal import SandboxMock
import json

sentences = [
    "A deposit of $500 is due before work begins.",
    "The $500 deposit has not been paid.",
    "I will pay a $500 deposit next week.",
    "I already paid a $500 deposit by bank transfer.",
]
for sentence in sentences:
    email = "From: Example Client <client@synthetic.example>\n\n- Website build: $2000\n" + sentence + "\nNet 30\n"
    extraction = RulesExtractor().extract(email)
    provider = SandboxMock()
    agent = Agent(provider, {"name": "Synthetic Freelancer", "email_address": "freelancer@synthetic.example"}, today=lambda: date(2026, 10, 8))
    result = agent.tool_create_invoice(email)
    print(json.dumps({"sentence": sentence, "amount_paid": str(extraction.amount_paid), "errors": [issue.to_dict() for issue in extraction.errors], "created": result["ok"], "queued": [action["summary"] for action in agent.list_pending()]}, sort_keys=True))
