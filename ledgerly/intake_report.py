"""Standalone, script-free presentation of a captured native intake review."""
from __future__ import annotations

from html import escape
from pathlib import Path

LABELS = {
    "input_error": "Input could not be read",
    "analysis_error": "Extraction did not complete",
    "needs_correction": "Needs correction",
    "warnings": "Warnings to review",
    "no_blocking_issues": "No blocking issues found",
}

CSS = """
:root { color-scheme: light; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #17252d; background: #f2f5f5; line-height: 1.5; }
* { box-sizing: border-box; }
body { margin: 0; padding: 28px 18px 56px; }
main { max-width: 1080px; margin: auto; }
a { color: #0b5960; text-underline-offset: .2em; }
a:focus-visible, summary:focus-visible, [tabindex]:focus-visible { outline: 3px solid #bd6e15; outline-offset: 4px; border-radius: 3px; }
header { padding: 24px 28px; background: #123f46; color: #fff; border-radius: 16px; }
header a { color: #fff; }
.eyebrow { margin: 0 0 8px; letter-spacing: .12em; text-transform: uppercase; font-size: .78rem; font-weight: 750; }
h1 { margin: 0 0 12px; font-size: clamp(1.8rem, 4vw, 2.5rem); line-height: 1.15; }
h2 { font-size: 1.2rem; line-height: 1.35; margin: 0 0 10px; overflow-wrap: anywhere; }
h3 { font-size: 1rem; margin: 22px 0 10px; }
p { margin: 8px 0 12px; }
.facts { font-size: .86rem; opacity: .88; overflow-wrap: anywhere; }
.summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(145px, 1fr)); gap: 10px; margin: 18px 0; }
.summary div { background: #fff; border: 1px solid #d4dfdf; padding: 13px 16px; border-radius: 10px; }
.summary strong { display: block; font-size: 1.6rem; }
.summary span { font-size: .87rem; }
.notice { border-left: 4px solid #b36510; background: #fff6e8; padding: 12px 16px; margin: 18px 0; }
section, nav { margin: 18px 0; border: 1px solid #d4dfdf; border-radius: 12px; background: #fff; padding: 22px 24px; }
nav ol { margin: 10px 0 0; padding-left: 24px; }
nav li { padding: 8px 0; }
nav a { font-weight: 650; overflow-wrap: anywhere; }
.entry-heading { display: flex; justify-content: space-between; gap: 14px; align-items: flex-start; flex-wrap: wrap; }
.badge { display: inline-block; padding: 4px 9px; border-radius: 6px; background: #e2eef0; color: #17474d; font-size: .78rem; font-weight: 700; }
.badge.needs_correction, .badge.input_error, .badge.analysis_error { color: #863323; background: #fbe9e5; }
.badge.warnings { color: #745109; background: #fff0cb; }
.path { font-size: .8rem; color: #4d626a; margin: 0 0 16px; overflow-wrap: anywhere; }
dl { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 24px; margin: 0; }
dl div { min-width: 0; }
dt { color: #536871; font-size: .78rem; font-weight: 700; }
dd { margin: 3px 0 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.table-wrap { overflow: auto; max-width: 100%; border: 1px solid #dce4e5; border-radius: 8px; }
table { width: 100%; border-collapse: collapse; min-width: 610px; font-size: .86rem; }
caption { text-align: left; padding: 10px 12px; font-weight: 700; background: #f7fafa; }
th, td { text-align: left; vertical-align: top; padding: 10px 12px; border-top: 1px solid #e1e8e9; }
th { white-space: nowrap; color: #49616b; background: #f7fafa; }
td.description { min-width: 160px; white-space: pre-wrap; overflow-wrap: anywhere; }
td.amount { font-variant-numeric: tabular-nums; white-space: nowrap; }
.totals { display: flex; gap: 12px; flex-wrap: wrap; margin: 12px 0; }
.total { border: 1px solid #cbdcde; background: #f1f8f8; border-radius: 8px; padding: 10px 14px; font-variant-numeric: tabular-nums; }
.total b { margin-right: 10px; }
.issues { margin: 8px 0; padding-left: 22px; }
.issues li { margin: 10px 0; padding-left: 3px; overflow-wrap: anywhere; }
.issues p { margin: 4px 0; white-space: pre-wrap; }
.issue-field { font-size: .8rem; color: #52666e; }
details { margin-top: 20px; border-top: 1px solid #dce4e5; padding-top: 14px; }
summary { cursor: pointer; font-weight: 700; padding: 4px 0; }
.source-info { margin-top: 12px; font-size: .8rem; }
pre { margin: 12px 0; padding: 14px; max-height: 28rem; overflow: auto; background: #f4f7f8; border: 1px solid #dce4e5; border-radius: 7px; white-space: pre-wrap; overflow-wrap: anywhere; font-size: .82rem; }
code { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
.back { margin: 20px 0 0; font-size: .8rem; }
footer { margin-top: 24px; color: #536871; font-size: .85rem; }
@media (max-width: 500px) { body { padding: 14px 10px 32px; } header, section, nav { padding: 18px 16px; } dl { grid-template-columns: 1fr; } .summary { grid-template-columns: 1fr 1fr; } }
@media print { body { padding: 0; background: #fff; } header { color: #17252d; background: #fff; border: 1px solid #d4dfdf; } header a { color: #17252d; } .table-wrap { overflow: visible; } table { min-width: 0; } section { break-inside: avoid; } .back { display: none; } }
"""


def _text(value: object, missing: str = "Not extracted") -> str:
    if value is None or value == "":
        return missing
    # POSIX filenames can contain undecodable bytes; keep their escaped spelling readable.
    return str(value).encode("utf-8", "backslashreplace").decode("utf-8").replace("\0", "\\u0000")


def _e(value: object, missing: str = "Not extracted") -> str:
    return escape(_text(value, missing), quote=True)


def _badge(status: str) -> str:
    return f'<span class="badge {status}">{LABELS[status]}</span>'


def _field(label: str, value: object) -> str:
    return f"<div><dt>{escape(label)}</dt><dd>{_e(value)}</dd></div>"


def _source(entry: dict) -> str:
    source = entry["source"]
    if source is None:
        return ""
    identity = (
        f'<dl class="source-info">{_field("Raw byte count", source["byte_count"])}'
        f'{_field("Raw source SHA-256", source["sha256"])}'
        f'{_field("Leading UTF-8 BOM removed for extraction", "Yes" if source["bom_removed"] else "No")}</dl>'
    )
    if source["text"] is None:
        return '<details><summary>Captured source identity</summary>' + identity + "<p>Text was not admitted for extraction.</p></details>"
    return (
        '<details><summary>Original email and source identity</summary>'
        + identity
        + f'<pre tabindex="0" aria-label="Original email for input {entry["position"]}">{_e(source["text"], "")}</pre></details>'
    )


def _extraction(entry: dict) -> str:
    ex = entry["extraction"]
    if ex is None:
        error = entry["error"]
        return f'<div class="notice"><b>{_e(error["kind"])}</b><p>{_e(error["message"])}</p></div>'
    fields = "".join([
        _field("Extracted recipient", ex["client_email"]),
        _field("Extracted client name", ex["client_name"]),
        _field("Selected invoice currency", ex["currency"]),
        _field("Extracted payment term (days; 0 means due on receipt)", ex["due_days"]),
        _field("Reported prior payment (native decimal text)", ex["amount_paid"]),
        _field("Heuristic confidence (not a probability)", ex["confidence"]),
    ])
    rows = []
    for position, item in enumerate(ex["line_items"], 1):
        rows.append(
            f'<tr><td>{position}</td><td class="description">{_e(item["desc"])}</td>'
            f'<td class="amount">{_e(item["qty"])}</td><td class="amount">{_e(item["unit_price"])}</td>'
            f'<td>{_e(item["currency"])}</td><td>{_e(item["unit"])}</td></tr>'
        )
    if rows:
        table = (
            f'<div class="table-wrap" tabindex="0" role="region" aria-label="Extracted line items for input {entry["position"]}">'
            '<table><caption>Extracted line items</caption><thead><tr><th scope="col">#</th><th scope="col">Work</th>'
            '<th scope="col">Quantity</th><th scope="col">Unit price</th><th scope="col">Currency</th><th scope="col">Unit</th>'
            '</tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>"
        )
    else:
        table = "<p>No line items were extracted.</p>"
    if entry["currency_totals"] is None:
        totals = '<p class="notice">Totals are unavailable until the native extraction errors are corrected. No unknown quantity is treated as a valid zero total.</p>'
    else:
        totals = (
            '<h3>Item totals by currency</h3><div class="totals">'
            + "".join(f'<div class="total"><b>{_e(part["currency"])}</b>{_e(part["total"])}</div>' for part in entry["currency_totals"])
            + "</div><p class='facts'>Native item totals stay separate. Reported prior payment is not subtracted here.</p>"
        )
    if ex["issues"]:
        issues = (
            "<h3>Native findings</h3><ul class='issues'>"
            + "".join(
                f'<li><b>{_e(issue["severity"])}</b> <code class="issue-field">{_e(issue["field"])}</code>'
                f'<p>{_e(issue["message"])}</p></li>' for issue in ex["issues"]
            )
            + "</ul>"
        )
    else:
        issues = "<h3>Native findings</h3><p>The extractor recorded no field issues. Human checking is still required.</p>"
    return "<dl>" + fields + "</dl><h3>Work and prices</h3>" + table + totals + issues


def render_report(report: dict) -> str:
    """Render a trusted record produced by intake_review; this is not a file importer."""
    counts = report["summary"]
    states = counts["statuses"]
    index = []
    sections = []
    for entry in report["entries"]:
        name = Path(entry["path"]).name or entry["path"]
        index.append(
            f'<li><a href="#{entry["id"]}">{entry["position"]}. {_e(name)}</a> {_badge(entry["status"])}'
            f'<div class="path">{_e(entry["path"])}</div></li>'
        )
        sections.append(
            f'<section id="{entry["id"]}" aria-labelledby="{entry["id"]}-heading">'
            f'<div class="entry-heading"><h2 id="{entry["id"]}-heading">{entry["position"]}. {_e(name)}</h2>'
            + _badge(entry["status"]) + "</div>"
            + f'<p class="path">Selected path: {_e(entry["path"])}</p>'
            + _extraction(entry) + _source(entry)
            + '<p class="back"><a href="#input-index">Back to input index</a></p></section>'
        )
    failed = (
        f'<p class="notice"><b>{counts["failed_count"]} input(s) could not be analyzed.</b> Every failed selection remains listed below with its explanation.</p>'
        if counts["failed_count"] else ""
    )
    summary = "".join(
        f"<div><strong>{number}</strong><span>{label}</span></div>" for number, label in [
            (counts["input_count"], "Selected inputs"), (counts["analyzed_count"], "Analyzed"),
            (states["needs_correction"], "Need correction"), (states["warnings"], "Have warnings"),
            (states["no_blocking_issues"], "No blocking issues found"), (counts["failed_count"], "Could not be analyzed"),
        ]
    )
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">'
        "<title>Ledgerly · Batch intake review</title><style>" + CSS + "</style></head><body><main>"
        '<header><p class="eyebrow">Ledgerly · Local review</p><h1>Batch intake review</h1>'
        "<p>Review each job email's extracted work, prices and findings before creating an invoice.</p>"
        "<p>This read-only record creates no drafts or approvals. Human checking and the existing explicit send approval remain separate.</p>"
        f'<p class="facts">Generated {_e(report["generated_at"])} · <a href="review.json">Open matching JSON record</a></p></header>'
        '<div class="summary" aria-label="Batch counts">' + summary + "</div>" + failed
        + '<nav id="input-index" aria-labelledby="input-index-title"><h2 id="input-index-title">Selected files, in supplied order</h2><ol>'
        + "".join(index) + "</ol></nav>" + "".join(sections)
        + "<footer><p>Produced by Ledgerly's unchanged native RulesExtractor. Confidence is a heuristic. "
        "No currencies or files are combined, and reported prior payment is not verified by this report.</p>"
        "<p>The HTML and JSON deliberately retain the selected source text. They are fixed local review records, "
        "not payable invoices, accounting imports or saved sandbox sessions.</p></footer></main></body></html>\n"
    )
