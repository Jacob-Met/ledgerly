# Ledgerly current-main composition receiving

**Accepted for the exact source tuple below.** The two already qualified scopes merge cleanly on pinned main `4bdaaa9995987c3e4a0134dfe792d4afb0d8fe7e`. No conflict resolution or production-source edit was needed in the receiver checkout. This receipt preserves the earlier main187 composition separately and qualifies only the new pinned inputs.

## Immutable inputs and result

| Role | Git commit |
| --- | --- |
| Pinned owner main | `4bdaaa9995987c3e4a0134dfe792d4afb0d8fe7e` |
| Accepted extraction and confirmed-payment composition | `22b7b5404e0bde8c6796d3abd8c5d177b5e84e1f` |
| Accepted webhook admission, rebased on pinned main | `0f1a7f7e72d932d10698258efbcbb38a0d93f9e9` |
| Local receiver composition | `4e42e1d283ac1b452b1534b86a42adb6629568ee` |
| Local receiver tree | `92358850d62ec8bdd1e8bd34e0170281f88c4a23` |

The composite `agent.py` blob is `962e8ec37a9fa09dec30e4f13f4f70c05c6022f0`, SHA-256 `1f260b563ed657522bed777d438029b035bd43baa0b30b2f024950875d8f5a15`. The extractor remains blob `100e581d3ef0d99555f49264859d01b535c6094f`; the PayPal module remains blob `43554a287c3b94b48e5376d9fa10f9287e1bea3f`. Complete sources and all full hashes are included.

## Source preservation

The receiver verified the exact `tool_create_invoice` method from the accepted extraction commit and the exact initializer and `handle_webhook` method from the accepted webhook commit. The other 17 Agent methods and the complete LedgerEntry class match pinned owner main. This retains the owner's current-invoice refresh, reminder review, and deadline semantics. The confirmed-payment extractor is the complete accepted current-main file; its separately preserved focused receipt proves the owner confirmation condition and uncertainty handling survive the resolved component merge.

The complete `web-demo/src`, `web-demo/tests`, and `web-demo/python` Git trees match pinned main. Source proofs and raw local Git operations are included in `composition-source.json` and `git-operations.json`.

## Executed qualification

| Gate | Result |
| --- | --- |
| Complete native suite | 235 passed; 34 subtests passed; zero failures |
| Existing engine/review tests in actual Pyodide | 10 passed across two test files; zero failures |
| Source, test, fixture and configuration pins | All 44 unchanged through both runs |
| Standard staged Python, fixtures and runtime files | All 22 byte-equal to their inputs |
| Borrowed original Pyodide runtime inputs | All five unchanged |
| Post-test tracked checkout | Clean; same commit and tree |

Native execution used Python 3.12.14 and pytest 9.1.1 with bytecode and pytest cache disabled. Browser-runtime qualification used Node 24.19.0, npm 11.9.0, Pyodide 0.29.3, and Vitest 5.0.3. It ran the project's original `npm test` script, including its complete standard staging step. Dependencies were reused through links under an owned node_modules directory; caches and generated files were isolated from author checkouts.

Commands, from the repository and web-demo directories respectively:

```sh
python -B -m pytest -p no:cacheprovider -q tests
npm test -- tests/engine.test.ts tests/review.test.ts
```

The exact invoked interpreter, working directories, UTC timestamps, raw output, and input hashes are retained. The npm environment warning about its pre-existing proxy configuration did not affect the successful execution. The selected Pyodide tests ran the existing offline core and SandboxMock; no provider or live payment operation was enabled.

## Integration boundary

This local receiver merge was not published or deployed, and the receiver did not edit either author's tree. The existing component negative controls remain in their original evidence packets; no redundant new tests were authored for this clean composition. This receipt does not qualify future executable changes or unselected JavaScript suites. Copy this evidence directory unchanged into the established repository; its manifest paths are relative to repository or packet root.
