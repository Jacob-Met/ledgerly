"""Maintained public-behavior controls for the local batch intake review."""
from __future__ import annotations

import codecs
import contextlib
import hashlib
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from ledgerly.extract import RulesExtractor
from ledgerly import intake_review as intake

ROOT = Path(__file__).resolve().parents[1]
GOOD = "From: Alex <alex@fictional.example>\n- 2 x Layout @ USD 100.25\nNet 15\n"
EUR = "From: Bea <bea@fictional.example>\n- 3 x Icons @ EUR 50.10\nNet 30\n"
MIXED = "From: Casey <casey@fictional.example>\n- 2 x Captions @ USD 25\n- 3 x Subtitles @ EUR 12.50\nNet 10\n"
BAD = "Subject: Unconfirmed\n- a few x Revisions @ USD 40\nNet 15\n"


class Markup(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.words = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.words.append(data)


class IntakeReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ledgerly-intake-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def source(self, name="email.txt", text=GOOD):
        path = self.root / name
        path.write_bytes(text.encode("utf-8") if isinstance(text, str) else text)
        return path

    def cli(self, output, *paths):
        return subprocess.run(
            [sys.executable, "-B", "-m", "ledgerly.intake_review", "--output", str(output),
             *map(str, paths)], cwd=ROOT, capture_output=True, text=True, timeout=15,
        )

    def test_native_findings_decimal_partitions_and_input_order_are_preserved(self):
        paths = [self.source("usd.txt"), self.source("eur.txt", EUR),
                 self.source("mixed.txt", MIXED), self.source("bad.txt", BAD)]
        report = intake.build_review([*paths, paths[0]])
        self.assertEqual(report["schema"], "ledgerly-intake-review/1")
        self.assertEqual([e["position"] for e in report["entries"]], [1, 2, 3, 4, 5])
        self.assertEqual([e["id"] for e in report["entries"]], [f"input-{n}" for n in range(1, 6)])
        self.assertEqual([e["path"] for e in report["entries"]], list(map(str, [*paths, paths[0]])))
        self.assertEqual([e["status"] for e in report["entries"]],
                         ["no_blocking_issues", "no_blocking_issues", "warnings",
                          "needs_correction", "no_blocking_issues"])
        self.assertEqual(report["entries"][0]["currency_totals"], [{"currency": "USD", "total": "200.50"}])
        self.assertEqual(report["entries"][1]["currency_totals"], [{"currency": "EUR", "total": "150.30"}])
        self.assertEqual(report["entries"][2]["currency_totals"],
                         [{"currency": "EUR", "total": "37.50"}, {"currency": "USD", "total": "50"}])
        self.assertIsNone(report["entries"][3]["currency_totals"])
        for entry in report["entries"]:
            native = RulesExtractor().extract(entry["source"]["text"])
            actual = entry["extraction"]
            for field in ["client_name", "client_email", "currency", "due_days", "confidence", "source"]:
                self.assertEqual(actual[field], getattr(native, field))
            self.assertEqual(actual["amount_paid"], str(native.amount_paid))
            self.assertEqual(actual["line_items"], [item.to_dict() for item in native.line_items])
            self.assertEqual(actual["issues"], [issue.to_dict() for issue in native.issues])
        self.assertEqual(report["summary"]["input_count"], 5)
        self.assertEqual(report["summary"]["failed_count"], 0)
        self.assertNotIn("total", report["summary"])

    def test_due_on_receipt_prior_payment_and_unknown_quantity_are_not_reinterpreted(self):
        paid = self.source("paid.txt", "From: Yuki <yuki@fictional.example>\n"
                           "- 2 x Illustration @ JPY 500\nDue on receipt.\nAlready paid JPY 200.\n")
        entry = intake.build_review([paid])["entries"][0]
        self.assertEqual(entry["extraction"]["due_days"], 0)
        self.assertEqual(entry["extraction"]["amount_paid"], "200")
        self.assertEqual(entry["currency_totals"], [{"currency": "JPY", "total": "1000"}])
        broken = intake.build_review([self.source("unknown.txt", BAD)])["entries"][0]
        self.assertEqual(broken["status"], "needs_correction")
        self.assertIsNone(broken["extraction"]["line_items"][0]["qty"])
        self.assertIsNone(broken["currency_totals"])

    def test_exact_source_custody_line_endings_bom_and_postcapture_change(self):
        raw = codecs.BOM_UTF8 + GOOD.replace("\n", "\r\n").encode("utf-8")
        path = self.source(text=raw)
        report = intake.create_review([path], self.root / "review")
        entry = report["entries"][0]
        self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(entry["source"], {"byte_count": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                                        "bom_removed": True, "text": raw[3:].decode("utf-8")})
        saved = (self.root / "review" / "review.json").read_bytes()
        path.write_text("a later source revision", encoding="utf-8")
        self.assertEqual((self.root / "review" / "review.json").read_bytes(), saved)
        self.assertEqual(json.loads(saved)["entries"][0]["source"], entry["source"])
        double = self.source("double.txt", codecs.BOM_UTF8 + codecs.BOM_UTF8 + GOOD.encode())
        self.assertTrue(intake.build_review([double])["entries"][0]["source"]["text"].startswith("\ufeff"))

    def test_invalid_utf8_nul_empty_and_missing_are_distinct(self):
        raw = b"From: \x80\n"
        invalid = self.source("invalid.txt", raw)
        nul = self.source("nul.txt", b"abc\0def")
        empty = self.source("empty.txt", b"")
        missing = self.root / "absent.txt"
        entries = intake.build_review([invalid, nul, empty, missing])["entries"]
        self.assertEqual([e["status"] for e in entries],
                         ["input_error", "input_error", "needs_correction", "input_error"])
        self.assertEqual([entries[n]["error"]["kind"] for n in [0, 1, 3]],
                         ["invalid_utf8", "non_text", "unreadable"])
        self.assertEqual(entries[0]["source"]["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertIsNone(entries[0]["source"]["text"])
        self.assertEqual(entries[1]["source"]["byte_count"], 7)
        self.assertEqual(entries[2]["source"]["text"], "")
        self.assertIsNone(entries[3]["source"])
        self.assertFalse(missing.exists())

    def test_regular_symlink_admitted_and_directory_fifo_refused_without_open(self):
        path = self.source()
        link = self.root / "email-link"
        try:
            link.symlink_to(path)
        except (OSError, NotImplementedError):
            self.skipTest("This host cannot create symlinks")
        self.assertEqual(intake.build_review([link])["entries"][0]["source"]["text"], GOOD)
        directory = self.root / "directory"
        directory.mkdir()
        streams = [directory]
        if hasattr(os, "mkfifo"):
            fifo = self.root / "mail-stream"
            os.mkfifo(fifo)
            streams.append(fifo)
        original = intake.os.open
        opened = []
        def observed(name, *args, **kwargs):
            opened.append(os.fspath(name))
            return original(name, *args, **kwargs)
        with patch.object(intake.os, "open", side_effect=observed):
            entries = intake.build_review(streams)["entries"]
        self.assertEqual(opened, [])
        self.assertTrue(all(e["error"]["kind"] == "not_regular" for e in entries))

    def test_oversized_input_is_visible_and_is_not_read(self):
        path = self.source(text=b"x" * (131072 + 1))
        with patch.object(intake.os, "fdopen", side_effect=AssertionError("oversize must not be read")):
            entry = intake.build_review([path])["entries"][0]
        self.assertEqual(entry["status"], "input_error")
        self.assertEqual(entry["error"]["kind"], "too_large")
        self.assertIsNone(entry["source"])

    def test_exact_file_and_batch_limits_and_duplicate_admission(self):
        path = self.source(text=b"\n" * 131072)
        exact = intake.build_review([path] * 16)
        self.assertEqual(exact["summary"]["admitted_byte_count"], 2097152)
        self.assertEqual(len(exact["entries"]), 16)
        destination = self.root / "over-budget"
        with self.assertRaises(intake.IntakeUsageError):
            intake.create_review([path] * 17, destination)
        self.assertFalse(destination.exists())
        tiny = self.source("tiny.txt", b"")
        self.assertEqual(len(intake.build_review([tiny] * 32)["entries"]), 32)
        with self.assertRaises(intake.IntakeUsageError):
            intake.create_review([tiny] * 33, destination)
        self.assertFalse(destination.exists())
        with self.assertRaises(intake.IntakeUsageError):
            intake.build_review([])

    def test_replacement_during_open_and_mutation_during_read_are_refused(self):
        path = self.source()
        replacement = self.source("replacement.txt", EUR)
        original_open = intake.os.open
        once = False
        def replace_then_open(name, flags, *args, **kwargs):
            nonlocal once
            if os.fspath(name) == str(path) and not once:
                once = True
                os.replace(replacement, path)
            return original_open(name, flags, *args, **kwargs)
        with patch.object(intake.os, "open", side_effect=replace_then_open):
            first = intake.build_review([path])["entries"][0]
        self.assertEqual(first["error"]["kind"], "changed_input")
        self.assertIsNone(first["source"])
        path.write_text(GOOD, encoding="utf-8")
        original_fstat = intake.os.fstat
        calls = 0
        def mutate_at_after_stat(descriptor):
            nonlocal calls
            calls += 1
            if calls == 2:
                path.write_bytes(EUR.encode("utf-8") + b" changed")
            return original_fstat(descriptor)
        with patch.object(intake.os, "fstat", side_effect=mutate_at_after_stat):
            second = intake.build_review([path])["entries"][0]
        self.assertEqual(second["error"]["kind"], "changed_input")
        self.assertIsNone(second["source"])

    def test_native_exception_is_per_input_and_keeps_source(self):
        paths = [self.source(), self.source("next.txt", EUR)]
        original = RulesExtractor.extract
        def selected_failure(instance, text):
            if text == GOOD:
                raise RuntimeError("<b>synthetic analysis failure</b>")
            return original(instance, text)
        with patch.object(RulesExtractor, "extract", selected_failure):
            report = intake.create_review(paths, self.root / "report")
        self.assertEqual([e["status"] for e in report["entries"]], ["analysis_error", "no_blocking_issues"])
        self.assertEqual(report["entries"][0]["source"]["text"], GOOD)
        self.assertIsNone(report["entries"][0]["extraction"])
        self.assertEqual(report["summary"]["failed_count"], 1)
        self.assertIn("&lt;b&gt;synthetic analysis failure&lt;/b&gt;",
                      (self.root / "report" / "index.html").read_text(encoding="utf-8"))

    def test_nonserializable_native_number_becomes_explicit_analysis_error(self):
        path = self.source()
        original = RulesExtractor.extract
        def invalid_number(instance, text):
            result = original(instance, text)
            result.confidence = float("nan")
            return result
        with patch.object(RulesExtractor, "extract", invalid_number):
            entry = intake.build_review([path])["entries"][0]
        self.assertEqual(entry["status"], "analysis_error")
        self.assertEqual(entry["source"]["text"], GOOD)
        self.assertIsNone(entry["extraction"])

    def test_html_is_literal_local_and_keeps_every_issue_and_identity(self):
        text = GOOD.replace("Layout", "<b>雪 & symbols</b>") + "\n<script>alert('literal')</script>\n"
        path = self.source("<img src=x>.txt", text)
        output = self.root / "report"
        report = intake.create_review([path, self.source("bad.txt", BAD)], output)
        parser = Markup()
        html = (output / "index.html").read_text(encoding="utf-8")
        parser.feed(html)
        visible = "".join(parser.words)
        self.assertIn("<b>雪 & symbols</b>", visible)
        self.assertIn("<script>alert('literal')</script>", visible)
        self.assertIn("<img src=x>.txt", visible)
        self.assertFalse(any(tag in {"script", "iframe", "img", "form", "object", "link"} for tag, _ in parser.elements))
        self.assertFalse(any(key.lower().startswith("on") for _, attrs in parser.elements for key in attrs))
        self.assertTrue(all(attrs["href"] == "review.json" or attrs["href"].startswith("#")
                            for _, attrs in parser.elements if "href" in attrs))
        self.assertEqual(len([1 for tag, _ in parser.elements if tag == "section"]), 2)
        self.assertEqual(len([1 for tag, _ in parser.elements if tag == "summary"]), 2)
        self.assertIn(report["entries"][0]["source"]["sha256"], visible)
        for issue in report["entries"][1]["extraction"]["issues"]:
            self.assertIn(issue["field"], visible)
            self.assertIn(issue["message"], visible)
        self.assertEqual(json.loads((output / "review.json").read_bytes()), report)

    def test_existing_file_directory_and_broken_link_are_preserved_before_analysis(self):
        path = self.source()
        file_output = self.root / "file-output"
        file_output.write_bytes(b"existing")
        directory = self.root / "directory-output"
        directory.mkdir()
        (directory / "retained").write_bytes(b"inside")
        destinations = [file_output, directory]
        link = self.root / "broken-output"
        try:
            link.symlink_to(self.root / "not-there")
            destinations.append(link)
        except (OSError, NotImplementedError):
            pass
        with patch.object(RulesExtractor, "extract", side_effect=AssertionError("existing output must refuse first")):
            for destination in destinations:
                with self.subTest(destination=destination.name), self.assertRaises(OSError):
                    intake.create_review([path], destination)
        self.assertEqual(file_output.read_bytes(), b"existing")
        self.assertEqual((directory / "retained").read_bytes(), b"inside")
        if link.is_symlink():
            self.assertEqual(os.readlink(link), str(self.root / "not-there"))

    def test_missing_output_parent_and_selected_input_descendant_are_refused(self):
        path = self.source()
        absent_parent = self.root / "absent-parent"
        with self.assertRaises(OSError):
            intake.create_review([path], absent_parent / "report")
        self.assertFalse(absent_parent.exists())
        destination = self.root / "report"
        missing = destination / "missing-input.txt"
        with self.assertRaises(OSError):
            intake.create_review([missing], destination)
        self.assertFalse(destination.exists())
        with self.assertRaises(OSError):
            intake.create_review([destination], destination)
        self.assertFalse(destination.exists())

    def test_render_failure_allocates_no_output_and_concurrent_claim_preserves_owner(self):
        path = self.source()
        output = self.root / "report"
        with patch.object(intake, "render_report", side_effect=ValueError("synthetic render failure")):
            with self.assertRaises(ValueError):
                intake.create_review([path], output)
        self.assertFalse(output.exists())
        render = intake.render_report
        def claim_during_render(report):
            output.mkdir()
            (output / "owner.txt").write_bytes(b"concurrent owner")
            return render(report)
        with patch.object(intake, "render_report", side_effect=claim_during_render):
            with self.assertRaises(FileExistsError):
                intake.create_review([path], output)
        self.assertEqual(sorted(p.name for p in output.iterdir()), ["owner.txt"])
        self.assertEqual((output / "owner.txt").read_bytes(), b"concurrent owner")

    def test_second_output_write_failure_has_no_success_and_retains_partial(self):
        path = self.source()
        output = self.root / "report"
        original = intake.os.open
        def fail_html(name, flags, *args, **kwargs):
            if Path(name) == output / "index.html":
                raise OSError("synthetic full device")
            return original(name, flags, *args, **kwargs)
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(intake.os, "open", side_effect=fail_html):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = intake.main(["--output", str(output), str(path)])
        self.assertEqual(code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("partial new report directory is retained", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())
        self.assertEqual(sorted(p.name for p in output.iterdir()), ["review.json"])
        self.assertEqual(json.loads((output / "review.json").read_bytes())["entries"][0]["source"]["text"], GOOD)
        self.assertEqual(path.read_text(), GOOD)
        with self.assertRaises(OSError):
            intake.create_review([path], output)

    def test_exclusive_fixed_file_creation_does_not_overwrite_racing_file(self):
        path = self.source()
        output = self.root / "report"
        original = intake.os.open
        injected = False
        def insert_collision(name, flags, *args, **kwargs):
            nonlocal injected
            if Path(name) == output / "review.json" and not injected:
                injected = True
                (output / "review.json").write_bytes(b"new owner")
            return original(name, flags, *args, **kwargs)
        with patch.object(intake.os, "open", side_effect=insert_collision):
            with self.assertRaises(FileExistsError):
                intake.create_review([path], output)
        self.assertEqual((output / "review.json").read_bytes(), b"new owner")
        self.assertFalse((output / "index.html").exists())

    def test_actual_cli_exit_states_complete_reports_and_source_preservation(self):
        good, bad = self.source(), self.source("bad.txt", BAD)
        initial = {str(p): p.read_bytes() for p in [good, bad]}
        success = self.cli(self.root / "all-analyzed", good, bad)
        self.assertEqual(success.returncode, 0, success.stderr)
        self.assertIn("Inputs: 2; analyzed: 2; failed: 0.", success.stdout)
        self.assertEqual(success.stderr, "")
        missing = self.root / "missing.txt"
        partial = self.cli(self.root / "some-failed", good, missing)
        self.assertEqual(partial.returncode, 2, partial.stderr)
        self.assertIn("Inputs: 2; analyzed: 1; failed: 1.", partial.stdout)
        record = json.loads((self.root / "some-failed" / "review.json").read_bytes())
        self.assertEqual(record["entries"][1]["path"], str(missing))
        existing = self.cli(self.root / "all-analyzed", good)
        self.assertEqual(existing.returncode, 1)
        self.assertEqual(existing.stdout, "")
        self.assertNotIn("Traceback", existing.stderr)
        invalid = self.cli(self.root / "invalid-batch", *([good] * 33))
        self.assertEqual(invalid.returncode, 2)
        self.assertEqual(invalid.stdout, "")
        self.assertFalse((self.root / "invalid-batch").exists())
        self.assertEqual({str(p): p.read_bytes() for p in [good, bad]}, initial)

    def test_native_cli_import_path_has_no_agent_provider_or_network_action(self):
        path = self.source()
        script = """
import json, runpy, sys
events=[]
def audit(event, args):
    if event in {'socket.connect', 'socket.connect_ex', 'socket.getaddrinfo'}:
        events.append(event)
        raise RuntimeError('network forbidden in intake review')
sys.addaudithook(audit)
sys.argv=['ledgerly.intake_review', '--output', sys.argv[2], sys.argv[1]]
try:
    runpy.run_module('ledgerly.intake_review', run_name='__main__')
except SystemExit as result:
    code=result.code
print(json.dumps({'exit':code, 'network_events':events,
                 'action_modules':[name for name in sys.modules
                    if name in {'ledgerly.agent','ledgerly.paypal','ledgerly.demo'}]}))
"""
        run = subprocess.run([sys.executable, "-B", "-c", script, str(path), str(self.root / "report")],
                             cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout.splitlines()[-1])
        self.assertEqual(result, {"exit": 0, "network_events": [], "action_modules": []})


if __name__ == "__main__":
    unittest.main()
