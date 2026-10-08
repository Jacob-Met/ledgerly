# Browser receiver limitations retained with the evidence

These are limitations of the disposable receiving harness. The failed receipts
remain failed; they are not counted as application passes.

| Attempt | Source under test | Observed outcome |
| --- | --- | --- |
| Initial request interception | Original production | Puppeteer interception stalled nested worker loading. The receiver moved failure injection to its loopback HTTP server before recording the four usable baseline controls. |
| v3 retained review | Published source `84ac59dbcd20b96c8baf846a03f574840ea174f8` | The actual Python workflow completed and the recorded preservation, invalidation, fresh review and separate approval predicates were true. A driver edit intended to use `$$eval` instead produced `$eval`; its draft count was undefined and the receiver correctly returned `passed: false`. |
| v4 launch | Same frozen source | Chrome failed before navigation while the Mac reported ENOSPC and could not create its ephemeral profile. No application result JSON was produced. The independent receiver author reported this launch failure; this note is not presented as a captured product result. |
| v5 retained review | Final source `537eb5d587d08641c1e96150e9c0daee172366e7` | The new recovery-marker assertion and the functional predicates were true. The draft-counter replacement still produced `$eval`, so the receiver remained failed. |
| v6 final receiving | Final source `537eb5d587d08641c1e96150e9c0daee172366e7` | The driver uses the intended collection query. Four general cases and the separately selected retained-review case pass, with exactly one draft followed by a separate approval. |

The v3, v4 and v5 driver files and the actual v3/v5 failed JSON receipts are in
`harness-failures/`. The v3 and v4 files are byte-identical; their shared SHA-256
is `a2006c4a0b34e8dd68ea92dc891ef536489106f07c5ac2ae8181ff3fb3fa767b`.
The v5 driver is
`2e794533146954ae44dc8933eb363ebecab2033c8158bd75b83afd0544fe0e80`.
The final v6 driver is
`88506aa2039dfee1165e6ee3bb49c425ba7da6ad3fb7655f8a7da60db3b9c13c`.

The two product message defects found by independent visual review are separate
from these harness limitations: an unavailable message persisted after restart,
then a recovery instruction persisted after valid retained-field revalidation.
Both were corrected in the application and challenged by focused actual-source
expectations. The qualification README identifies the prior and final receipts.
