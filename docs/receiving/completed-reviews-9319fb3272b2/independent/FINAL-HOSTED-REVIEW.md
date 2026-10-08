# Independent final hosted-receiving addendum

Reviewer: `hamon-ultra-9319fb3272b2-20261008/native_capability`.

**Accepted:** the exact current-main source adaptations and final hosted receiving described below. This is independent source review and readback of immutable actual execution records. I did not launch another browser, call RDC, or replace the original independent report.

| Binding | Exact pin |
|---|---|
| Qualified PR36 head | `ae1e859aa26bffdee7e8b8cb673acd6c74420263` |
| Qualified tree | `de61c0086dd1591413820c05de33a3f2a7d49491` |
| Actual hosted checkout | `b1aeba460fe9b6b321248ef534d7cd3b0dc444b7` |
| Incoming main | `fba278f552e868ad2b94b7f1dc309eed6f1e8514` |
| Browser receipt Git blob | `2e2b725e3f24dde3f1ac4b972f22df411023ed14` |
| Browser receipt SHA-256 | `34902f66bb2f368636601abd2dc1b65af1267e579638114e5cdb302c23c958fe` |

I independently verified that the hosted checkout has the incoming-main and qualified-head parents and the exact qualified tree. Its 33,000-byte browser receipt rehashes to both the Git blob and SHA-256 above.

## Receiving accepted

The [final Verify run](https://github.com/Jacob-Met/ledgerly/actions/runs/37808603895) has successful core/browser jobs. I read the core log's **347 tests and 118 subtests** on Python 3.12.15 and the final browser receipt's **29/29 passing groups** on Node 22.23.3. The [separate invoice-record run](https://github.com/Jacob-Met/ledgerly/actions/runs/37808603940) also completed successfully.

The healthy receiving trace preserves both outer and nested disclosure/focus through the following snapshot, keeps the unrelated USD send pending when a distinct reminder is approved, and retains the earlier auto-rejected reminder with its original result. Explicit restart produces empty history while retaining the source email; the separately confirmed Reset clears its own new history.

The fault Worker records only `init → analyze → draft → approve`. Its actual response has application `ok=false` and `TimeoutError`; the original action becomes **FAILED / UNKNOWN**, with the mock provider **SENT** and local ledger **DRAFT**. Reading the retained proposal does not retry, mutate the provider, introduce action controls, or make an external call. The mock request count is five, including the newly integrated fresh GET. The real mock send precedes the explicitly labeled response-loss injection; no real provider send is claimed.

All three attached Worker sessions—initial, restarted, and fault—have their own correlated `bridge.py` request. The receipt records 53 network observations, no off-origin request, and no uncaught page/Worker error. Both owned browsers exit **0**, without a signal or fallback, and both profiles are removed. All 45 declared application inputs and 32 built files remain unchanged.

## Current-main source preservation

The incoming 693-leaf tree becomes 799 leaves: **679 exact existing leaves**, 14 existing paths within the owned integration, 106 owned source/evidence additions, and no removals. The complete path mapping is in the companion JSON.

All 24 paths from incoming PR40 are accounted for: 23 remain exact. The sole shared-test difference adds `review_history.py` to the existing invoice-details loader; the new GET-before-POST assertions remain intact. The incoming Agent is exact blob `e4e26ebd7259bd61d14819593a17d3d0738bbf30`.

The history refusal fixture now lets the fresh GET see the reviewed DRAFT before its wrapper changes the isolated provider record to CANCELLED and delegates to the **real mock send**. Its exact GET/POST sequence and original FAILED/body/payload/no-UNKNOWN assertions are preserved. It does not bypass or weaken the incoming freshness rule.

## Captures and retained limits

The final receiver waits for fonts, scrolls instantly, waits two frames, and records target geometry before and after capture. It explicitly hides page scrollbars before navigation; no application stylesheet or source was changed for capture. All four records pass stable geometry and actual PNG-dimension checks: **546×2471**, **336×595**, **336×790**, and **336×944**. These are full target clips, which may exceed the viewport height.

I independently inspected these geometry records and source gates. Integration separately reports direct viewing of all four final images with the target header, body, and result included; I do not claim a second pixel inspection.

The original independent report and its failed native attempts remain unchanged. Hosted attempt 2 retains its incorrect empty-pending assertion failure; attempt 3 retains its clipped phone image; attempt 4 remains overall false after 13 passing application groups because target width/height changed during capture. None is relabeled as a clean run. The uncertain native archive command remains unresolved under the shared RDC outage.

No blocking source or semantic finding remains at the exact pins above. Final evidence publication and normal merge remain with the owning integration/root lane.
