# Batch intake review

Ledgerly can review several saved job-email text files in one local document. This is
useful when you want to check a collection of incoming jobs before drafting invoices:
you can compare the extracted recipients, work, prices and unresolved findings while
keeping each source email attached to its result.

## Run a review

From the repository with Python 3.12 or later:

```bash
python -m ledgerly.intake_review --output ./intake-review \
  ./job-email-a.txt ./job-email-b.txt
```

The core needs no additional packages. Supply the input paths in the order you want to
review them. Quote paths containing spaces. For a filename beginning with a hyphen,
put `--` before the input list.

The output parent must already exist, and `intake-review` must be a new directory.
The command creates two files:

| File | Purpose |
| --- | --- |
| `index.html` | A standalone readable report. Open it directly in a browser; no server or JavaScript is needed. |
| `review.json` | The matching inspection record, including all source text and native findings. |

The HTML has a linked input index, status counts, and a section for every selected file.
Each analyzed section shows the recipient, payment term, reported prior payment,
heuristic confidence, line items and native issues. Expand **Original email and source
identity** to inspect the captured text, raw byte count and SHA-256. Wide item tables
scroll within their section on a narrow display. Links, disclosures and table regions
are reachable with the keyboard.

Both files deliberately include the selected source text and paths. Keep them with the
same care as the original emails. They contain fixed captured results; changing an
email afterward does not change an existing report.

## Understand the results

The command calls Ledgerly's existing `RulesExtractor`. It preserves the extractor's
field values, ordered items, field/severity/message findings and native decimal text.
It does not contact an LLM, mail account or payment provider.

| Status in JSON | Label in HTML | Meaning |
| --- | --- | --- |
| `no_blocking_issues` | No blocking issues found | Native extraction completed without errors or warnings. Informational findings can still appear. |
| `warnings` | Warnings to review | Native warnings require your attention; there are no native errors. |
| `needs_correction` | Needs correction | At least one native extraction error remains. |
| `input_error` | Input could not be read | The selected file was missing, inaccessible, changed during reading, or outside the admitted text-file limits. |
| `analysis_error` | Extraction did not complete | The native extraction or its result serialization failed. Captured source identity remains available. |

Every selected argument has an ordinal identity, including repeated paths and failed
inputs. A repeated filename is analyzed as another selection; files and clients are
never merged. The batch counts all entries instead of quietly discarding failures.

**No blocking issues found is not approval.** Confidence is the extractor's heuristic,
not a probability or an external verification. Human checking and Ledgerly's existing
explicit send-approval flow remain separate. This command creates no invoice draft,
queue entry, approval, payment or reminder.

### Money and terms

For an extraction without errors, item totals use the existing native currency
partitions and total calculation. USD and EUR totals remain separate, and there is no
cross-file money total. Decimal spelling is preserved: a native value of `50` stays
`50`, rather than being reformatted as `50.00`.

When any native error exists, totals are explicitly unavailable. The report keeps the
original items and issues, including unknown quantities, without displaying an unknown
quantity as a valid zero-valued total.

A due-day value of 0 means due on receipt. Reported prior payment is displayed as the
native extracted decimal text; the report does not verify it or subtract it to invent
an amount due. An extracted email address is not externally verified.

## Input limits and custody

Choose 1–32 explicit regular files. There is no directory scan or recursion. A
caller-selected symlink may refer to a regular file; directories and stream-like paths
such as FIFOs are refused without consuming their stream.

Each file may contain at most 128 KiB of raw bytes. Oversized files remain visible as
failed inputs. All admitted text together may contain at most 2 MiB, counting repeated
selections each time. Exceeding that whole-batch limit refuses the command before it
creates an output directory.

Text is decoded as strict UTF-8. One optional leading UTF-8 BOM is removed for
extraction and recorded. NUL-containing files are refused. An empty UTF-8 file is
analyzed normally and receives the existing missing-field issues. JSON preserves
decoded line endings; browser rendering may normalize line endings visually.

The command never rewrites, moves or deletes the inputs. It compares file identity,
size and modification metadata around the bounded read; an observable replacement or
modification is refused for that entry. This identifies captured bytes, rather than
providing a filesystem transaction or a guarantee about later changes to the path.
Unreadable inputs have no source hash. Fully read but invalid UTF-8 or NUL-containing
inputs retain their raw byte count and hash without an admitted text value.

## Output preservation and exit codes

The destination must not already exist, even as an empty directory or broken symlink.
Its parent must already be a directory. The destination also cannot contain a selected
input path, including a currently missing input. These refusals preserve existing
files.

All input processing and rendering finish before the command exclusively creates the
new output directory. Both fixed report filenames are created exclusively. A competing
creation or a disk/write failure is reported without overwriting or cleaning up the
other content.

| Exit code | Meaning |
| --- | --- |
| 0 | Both report files were written, and every selected file was analyzed. Correction findings and warnings may still be present. |
| 2 | Both files were written with at least one input/analysis failure, **or** CLI/batch admission was refused before output creation. Read the terminal message to distinguish them. |
| 1 | The destination was refused or publication failed. No successful-publication message is printed. |

On a completed report, stdout prints the HTML path and analyzed/failed counts after
both files close. On an output failure, any partial new directory is retained for
inspection; choose a different new destination for a retry. The pair is not guaranteed
to publish atomically across a crash or disk failure. A partial JSON file or an
unpaired JSON record should not be treated as a completed report.

## JSON inspection contract

The top-level schema is `ledgerly-intake-review/1`, with one UTC generation timestamp,
the extractor name, summary counts and ordered `entries`. Each entry includes:

- Its `input-N` identity, one-based position, selected path and explicit status.
- Captured `source` metadata and exact decoded text where admitted, or an explicit
  read error.
- Native extraction fields and ordered line items/issues, or an explicit analysis
  error.
- Separate native `currency_totals` for an error-free extraction, or `null` when no
  accepted total is available.

Decimal values are strings. Missing field values stay missing. The record is for
inspection; Ledgerly does not import it as a resumable browser intake, invoice,
checked-revision token or accounting transaction.

## Maintained verification

The focused controls use the standard library and can run without pytest:

```bash
python -B -m unittest discover -s tests -p test_intake_review.py -v
```

They exercise native field preservation, separate currencies, input limits and
identity, literal HTML, output collisions and partial failures, actual CLI exit
behavior, and the absence of Agent/provider/network actions. The repository's normal
pytest gate also discovers these unittest controls.
