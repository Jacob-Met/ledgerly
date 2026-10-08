"""Review explicit local job-email files using Ledgerly's unchanged rules extractor.

Run: python -m ledgerly.intake_review --output NEW_DIRECTORY EMAIL [EMAIL ...]
"""
from __future__ import annotations

import argparse
import codecs
import hashlib
import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .extract import RulesExtractor, split_by_currency
from .intake_report import render_report

MAX_FILES = 32
MAX_FILE_BYTES = 128 * 1024
MAX_BATCH_BYTES = 2 * 1024 * 1024
SCHEMA = "ledgerly-intake-review/1"
STATUSES = ("input_error", "analysis_error", "needs_correction", "warnings", "no_blocking_issues")


class IntakeUsageError(ValueError):
    """The complete batch cannot be admitted."""


class InputFailure(Exception):
    def __init__(self, kind: str, message: str, source: dict | None = None):
        super().__init__(message)
        self.kind = kind
        self.source = source


def _arguments(paths: Sequence[str | os.PathLike[str]]) -> list[str]:
    if isinstance(paths, (str, bytes)) or not 1 <= len(paths) <= MAX_FILES:
        raise IntakeUsageError(f"Choose between 1 and {MAX_FILES} explicit email files.")
    out = []
    for path in paths:
        try:
            value = os.fspath(path)
        except TypeError as error:
            raise IntakeUsageError("Every input must be a filesystem path.") from error
        if not isinstance(value, str):
            raise IntakeUsageError("Input paths must be text, not bytes.")
        out.append(value)
    return out


def _stamp(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _read_source(path: str) -> dict:
    descriptor = None
    try:
        named_before = os.stat(path)
        if not stat.S_ISREG(named_before.st_mode):
            raise InputFailure("not_regular", "Choose a regular text file; streams and directories are not read.")
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
        descriptor = os.open(path, flags)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise InputFailure("not_regular", "The selected path no longer names a regular file.")
        if _stamp(before) != _stamp(named_before):
            raise InputFailure("changed_input", "The selected file changed before it could be read.")
        if before.st_size > MAX_FILE_BYTES:
            raise InputFailure("too_large", f"The selected file exceeds {MAX_FILE_BYTES} raw bytes.")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            raw = stream.read(MAX_FILE_BYTES + 1)
            after = os.fstat(stream.fileno())
            try:
                named_after = os.stat(path)
            except OSError as error:
                raise InputFailure("changed_input", "The selected path changed while it was being read.") from error
        if len(raw) > MAX_FILE_BYTES:
            raise InputFailure("too_large", f"The selected file exceeds {MAX_FILE_BYTES} raw bytes.")
        if len(raw) != before.st_size or _stamp(before) != _stamp(after) or _stamp(after) != _stamp(named_after):
            raise InputFailure("changed_input", "The selected file changed while it was being read.")
    except InputFailure:
        raise
    except (OSError, ValueError) as error:
        raise InputFailure("unreadable", f"{type(error).__name__}: {error}") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)

    source = {
        "byte_count": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bom_removed": raw.startswith(codecs.BOM_UTF8),
        "text": None,
    }
    try:
        text = raw.decode("utf-8-sig" if source["bom_removed"] else "utf-8")
    except UnicodeDecodeError as error:
        raise InputFailure("invalid_utf8", f"The file is not valid UTF-8 at byte {error.start}.", source) from error
    if "\0" in text:
        raise InputFailure("non_text", "The file contains NUL characters and is not admitted as email text.", source)
    source["text"] = text
    return source


def _extract(source: dict) -> tuple[dict, list[dict] | None, str]:
    result = RulesExtractor().extract(source["text"])
    extraction = {
        "client_name": result.client_name,
        "client_email": result.client_email,
        "currency": result.currency,
        "due_days": result.due_days,
        "amount_paid": str(result.amount_paid),
        "line_items": [item.to_dict() for item in result.line_items],
        "confidence": result.confidence,
        "issues": [issue.to_dict() for issue in result.issues],
        "source": result.source,
    }
    if result.errors:
        status = "needs_correction"
        totals = None
    else:
        status = "warnings" if any(issue.severity == "warning" for issue in result.issues) else "no_blocking_issues"
        totals = [{"currency": part.currency, "total": str(part.total())} for part in split_by_currency(result)]
    # An exception here belongs to this input, before any report is published.
    json.dumps({"extraction": extraction, "totals": totals}, allow_nan=False)
    return extraction, totals, status


def build_review(paths: Sequence[str | os.PathLike[str]]) -> dict:
    """Capture and analyze selected files without allocating an output directory."""
    arguments = _arguments(paths)
    entries = []
    admitted_bytes = 0
    for position, path in enumerate(arguments, 1):
        entry = {
            "id": f"input-{position}",
            "position": position,
            "path": path,
            "status": "input_error",
            "source": None,
            "error": None,
            "extraction": None,
            "currency_totals": None,
        }
        try:
            source = _read_source(path)
        except InputFailure as error:
            entry["source"] = error.source
            entry["error"] = {"kind": error.kind, "message": str(error)}
            entries.append(entry)
            continue
        admitted_bytes += source["byte_count"]
        if admitted_bytes > MAX_BATCH_BYTES:
            raise IntakeUsageError(f"The selected admitted source files exceed {MAX_BATCH_BYTES} raw bytes in total.")
        entry["source"] = source
        try:
            extraction, totals, status = _extract(source)
            entry.update(extraction=extraction, currency_totals=totals, status=status)
        except Exception as error:
            entry["status"] = "analysis_error"
            entry["error"] = {"kind": type(error).__name__, "message": str(error)}
        entries.append(entry)
    counts = {status: sum(entry["status"] == status for entry in entries) for status in STATUSES}
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "extractor": "ledgerly.extract.RulesExtractor",
        "summary": {
            "input_count": len(entries),
            "analyzed_count": len(entries) - counts["input_error"] - counts["analysis_error"],
            "failed_count": counts["input_error"] + counts["analysis_error"],
            "admitted_byte_count": admitted_bytes,
            "statuses": counts,
        },
        "entries": entries,
    }


def _destination(value: str | os.PathLike[str], arguments: list[str]) -> Path:
    destination = Path(value)
    if os.path.lexists(destination):
        raise OSError("The output destination already exists; choose a new directory.")
    if not destination.parent.is_dir():
        raise OSError("The output parent must already be a directory.")
    resolved = destination.resolve()
    for argument in arguments:
        try:
            selected = Path(argument).resolve()
        except (OSError, RuntimeError, ValueError):
            continue  # The input reader will retain an explicit failed entry.
        if selected == resolved or selected.is_relative_to(resolved):
            raise OSError("The output directory cannot contain a selected input path.")
    return destination


def _write_new(path: Path, content: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)


def create_review(paths: Sequence[str | os.PathLike[str]], output: str | os.PathLike[str]) -> dict:
    """Create two new local report files; preserve any partial new output on failure."""
    arguments = _arguments(paths)
    destination = _destination(output, arguments)
    report = build_review(arguments)
    json_bytes = (json.dumps(report, ensure_ascii=True, allow_nan=False, indent=2) + "\n").encode("utf-8")
    html_bytes = render_report(report).encode("utf-8")
    destination.mkdir(mode=0o700, exist_ok=False)
    _write_new(destination / "review.json", json_bytes)
    _write_new(destination / "index.html", html_bytes)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review explicitly selected local job emails with Ledgerly's native rules extractor.")
    parser.add_argument("--output", required=True, help="New report directory whose parent already exists.")
    parser.add_argument("files", nargs="+", metavar="EMAIL_FILE", help="Explicit UTF-8 text files in the desired review order.")
    args = parser.parse_args(argv)
    try:
        report = create_review(args.files, args.output)
    except IntakeUsageError as error:
        print(f"Input selection refused: {error}", file=sys.stderr)
        return 2
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Report was not published successfully: {error}", file=sys.stderr)
        print("Any partial new report directory is retained; inspect it and choose a new destination.", file=sys.stderr)
        return 1
    counts = report["summary"]
    try:
        print(f"Saved intake review: {Path(args.output) / 'index.html'}", flush=True)
        print(f"Inputs: {counts['input_count']}; analyzed: {counts['analyzed_count']}; failed: {counts['failed_count']}.", flush=True)
    except OSError:
        try:
            sys.stdout.close()
        except OSError:
            pass
        return 1
    return 2 if counts["failed_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
