# Interrupted draft creation receiving

This contribution retains useful recovery facts when a later currency draft fails.
The source fence is only `Agent.tool_create_invoice`; the successful creation tail,
whole-job value admission, approval, provider, reminder and webhook implementations
retain their prior source.

## Source and behavior

Base: `da2e47043d7f18aa231d80b568dd30e31ed8b77c` (tree `ea9857cebc1fa91582f1f65ea6be34cd86eb23c0`).
The public contract was frozen in [issue52](https://github.com/Jacob-Met/ledgerly/issues/52)
before production edits. Native receiving executes the real Agent, RulePlanner and
SandboxMock. Faults are confined to invoice-number, create-call and response boundaries.
A lost-response case first creates a real mock invoice; its existence in the mock does
not give the Agent its missing identity.

An interruption returns known invoice/approval IDs, the failed currency/phase/number,
and unattempted later currencies. Once create has been called, every error or unusable
receipt is UNKNOWN. Existing provider error details are detached for inspection.
The existing RulePlanner can read confirmed invoices afterward; it cannot retry a create
or advance to a later currency through this result. The message warns that an explicit
new invocation can duplicate earlier drafts. No cross-call idempotency is promised.

## Author native results

The same maintained `tests/test_draft_creation_outcomes.py` has **11 methods**, including
10 parameter subcases. All pass on the candidate. On the unchanged base it reports
4 failures and 11 errors across those tests/subcases; ordinary success, complete
representation and invalid-value controls pass. Logs and exact source/test hashes are
retained alongside this file.

Checks cover partial allocation, local preparation failure, actual creation followed
by response loss, explicit provider refusal, absent/contradictory/duplicate/non-success
receipts, exact IDs/totals/currencies, strict stopping, detached output, unchanged
validation-before-effects, and separately approved use of a retained draft.

Run the maintained file with native `python -B -m unittest discover -s tests -p
test_draft_creation_outcomes.py`, or the repository's normal pytest gate. Current author
execution used exact source modules from memory because shared disks were full.
The attempted broader local pytest command could not import pytest; the historical
receiving venv was also gone. Neither is a passing regression result. The ordinary
published repository workflow remains required.

## Independent and integration state

The independent receiver froze before candidate access; its executable, original-source
1-pass/3-failure observations and producer-format correction are durable in
[issue52 comment6068393407](https://github.com/Jacob-Met/ledgerly/issues/52#issuecomment-6068393407).
Candidate independent receiving and hosted current-source gates are pending at this
source publication. Root owns final composition and integration.

`execution-notes.json` retains the unavailable pytest run, initial source-loader failure
(which did not execute candidate modules), and the exploratory request-history alias.
The exploratory baseline/retry and corrected candidate traces are separate from the
unchanged maintained test baseline. All provider behavior is synthetic and offline.
