# Invoice-send review receiving

The current source in this change is `ledgerly/agent.py` at SHA-256
`969b6f62ed0958705b3041831cfc0624951cd49893419f3ac2b1d5232d56dd97`.
Its extended send-review regression matrix is SHA-256
`e522faa100de6443978505e00c3ba504c40cd3a866954a0bacb4b694252dad50`.

Approval performs a fresh provider read before a send permit. Known changed
content or a known non-draft status rejects the original review. An unusable
read, including a status outside the existing provider enum, leaves that
review pending for an explicit retry. The original outgoing refusal and
uncertain-outcome rules remain in place. A provider edit after the read can
still race the separate send operation.

## Read the evidence

| File or archive | Role |
|---|---|
| [INDEPENDENT-QUALIFICATION.md](INDEPENDENT-QUALIFICATION.md) | Final independent source, boundary, adapter and tree acceptance |
| [INDEPENDENT-PROBE.py.txt](INDEPENDENT-PROBE.py.txt) | Exact readable probe; original executable filename is retained inside the archive |
| [independent-receiving.tar.gz](independent-receiving.tar.gz) | Complete independent probe, original failures, successor runs and source custody |
| [STATUS-RECEIVING.md](STATUS-RECEIVING.md) | Narrow f2bc-to-969b status admission correction and current native result |
| [status-receiving.tar.gz](status-receiving.tar.gz) | Exact status probe, negative and passing runs, both sources and extended regression matrix |
| [AUTHOR-QUALIFICATION.md](AUTHOR-QUALIFICATION.md) | Original preflight implementation, policy-adapter reasoning and historical qualification |
| [author-evidence.tar.gz](author-evidence.tar.gz) | Original baseline/candidate source capsules, unmodified old tests, complete failed controls and initial native runs |
| [current-main-receiving.json](current-main-receiving.json) | Earlier invoice-details consumer receiving and exact request-count adapter |
| [current-main-b9c-native-receiving.json](current-main-b9c-native-receiving.json) | Historical f2bc receiving of the newer payment-admission/consumer source |

The original author packet describes the earlier f2bc source. It remains
unchanged as historical evidence; the status packet and final independent
qualification identify the production successor. The status archive contains
the final authored current-native result: **245 tests and 96 subtests pass,
with no skips**, against main commit
`b9c24ace6b57a17215a53c50b674bd187d13f8ed`.

The unchanged independent probe has seven methods and fifteen cases. It
passes on the final successor with both the earlier native dependencies and
the b9c dependencies, including optimized Python receiving. Its original
negative controls and intermediate f2bc status failures remain retained.

Three old fixture adapters are explicit: a real post-read POST refusal
continues to test consumed outgoing errors; provider-term fixtures reject
the old approval before their separate external mock-send projection;
and the browser-Python details fixture asserts the actual GET then POST.
No retained review payload is rewritten to manufacture approval.

All these source tests use authored local mock data. They establish neither
a live provider send nor installed application adoption. The pull request's
actual merge-tree CI supplies the separate current integration gate.
