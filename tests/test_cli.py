"""
Tests for the command line (python -m faker_grocery / faker-grocery).
"""
import contextlib
import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from faker_grocery.__main__ import EXPORT_KINDS, _csv_cell, export, main


def run_export(kind, fmt, count=3, **kwargs):
    out = io.StringIO()
    written = export(kind, count, kwargs.pop("locale", "fr_FR"), fmt, out, seed=kwargs.pop("seed", 7), **kwargs)
    return out.getvalue(), written


class TestExport(unittest.TestCase):
    def test_every_kind_in_every_format(self):
        for kind in EXPORT_KINDS:
            text, _ = run_export(kind, "json")
            records = json.loads(text)
            # sales: -n is a number of days, one record per day and department.
            self.assertEqual(len(records), 3 * 21 if kind == "sales" else 3, msg=kind)
            lines = run_export(kind, "jsonl")[0].splitlines()
            self.assertEqual(len(lines), len(records), msg=kind)
            self.assertEqual(json.loads(lines[0]), records[0], msg=kind)
            text, written = run_export(kind, "csv")
            rows = list(csv.DictReader(io.StringIO(text)))
            self.assertEqual(len(rows), written, msg=kind)
            self.assertGreaterEqual(len(rows), 3, msg=kind)

    def test_basket_csv_has_one_row_per_item(self):
        records = json.loads(run_export("baskets", "json")[0])
        rows = list(csv.DictReader(io.StringIO(run_export("baskets", "csv")[0])))
        self.assertEqual(len(rows), sum(len(r["items"]) for r in records))
        self.assertEqual({row["basket_id"] for row in rows}, {"1", "2", "3"})
        self.assertIn("shopping_datetime", rows[0])
        self.assertIn("ean", rows[0])

    def test_receipt_csv_has_one_row_per_line(self):
        records = json.loads(run_export("receipts", "json")[0])
        rows = list(csv.DictReader(io.StringIO(run_export("receipts", "csv")[0])))
        self.assertEqual(len(rows), sum(len(r["lines"]) for r in records))
        self.assertIn("store_name", rows[0])
        self.assertIn("vat_rate", rows[0])

    def test_customers_export_trips(self):
        records = json.loads(run_export("customers", "json", count=2, trips=4)[0])
        self.assertTrue(all(len(r["baskets"]) == 4 for r in records))
        self.assertEqual([b["trip"] for b in records[0]["baskets"]], [1, 2, 3, 4])

    def test_seed_makes_output_reproducible(self):
        self.assertEqual(run_export("receipts", "jsonl", seed=3)[0], run_export("receipts", "jsonl", seed=3)[0])
        self.assertNotEqual(run_export("receipts", "jsonl", seed=3)[0], run_export("receipts", "jsonl", seed=4)[0])

    def test_locale_is_applied(self):
        record = json.loads(run_export("products", "json", count=1, locale="de_DE")[0])[0]
        self.assertEqual(record["currency"], "EUR")
        record = json.loads(run_export("products", "json", count=1, locale="ja_JP")[0])[0]
        self.assertEqual(record["currency"], "JPY")


    def test_json_is_streamed_identically_to_json_dump(self):
        text, written = run_export("baskets", "json", count=4)
        self.assertEqual(written, 4)
        records = json.loads(text)
        self.assertEqual(text, json.dumps(records, ensure_ascii=False, indent=2) + "\n")
        out = io.StringIO()
        self.assertEqual(export("products", 0, "en_US", "json", out), 0)
        self.assertEqual(json.loads(out.getvalue()), [])

    def test_csv_safe_quotes_formula_like_cells(self):
        for value in ("=SUM(A1)", "+1", "-1", "@cmd", "\tx", "\rx"):
            self.assertEqual(_csv_cell(value, True), "'" + value)
            self.assertEqual(_csv_cell(value, False), value)
        self.assertEqual(_csv_cell("Yaourt", True), "Yaourt")
        self.assertEqual(_csv_cell(-1.5, True), -1.5)
        # Only cells starting with a formula character change, e.g. promotion
        # labels such as "-30 %" (which is why the option is off by default).
        plain = list(csv.reader(io.StringIO(run_export("receipts", "csv", count=30)[0])))
        safe = list(csv.reader(io.StringIO(run_export("receipts", "csv", count=30, csv_safe=True)[0])))
        changed = {(a, b) for row_a, row_b in zip(plain, safe, strict=True) for a, b in zip(row_a, row_b, strict=True)
                   if a != b}
        self.assertTrue(changed)
        self.assertTrue(all(b == "'" + a and a.startswith("-") for a, b in changed))


class TestMain(unittest.TestCase):
    def test_export_to_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "baskets.csv")
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(main(["export", "baskets", "-n", "5", "--seed", "1", "-o", path]), 0)
            self.assertIn("Wrote", err.getvalue())
            with open(path, encoding="utf-8") as f:
                self.assertEqual(len({row["basket_id"] for row in csv.DictReader(f)}), 5)

    def test_unknown_locale_is_a_usage_error(self):
        for argv in (["export", "baskets", "--locale", "xx_XX"], ["demo", "--locale", "fr_XX"]):
            with self.assertRaises(SystemExit) as raised, contextlib.redirect_stderr(io.StringIO()) as err:
                main(argv)
            self.assertEqual(raised.exception.code, 2)
            self.assertIn("unknown Faker locale", err.getvalue())
        self.assertIn("fr_FR", err.getvalue())  # suggestion for the same language

    def test_unwritable_output_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "missing", "out.csv")
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(main(["export", "baskets", "-n", "1", "-o", path]), 1)
            self.assertIn("error", err.getvalue())

    def test_failed_export_leaves_no_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "out.csv")
            with open(path, "w", encoding="utf-8") as f:
                f.write("previous\n")
            with mock.patch("faker_grocery.__main__.export", side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError):
                    main(["export", "baskets", "-n", "1", "-o", path])
            self.assertEqual(os.listdir(directory), ["out.csv"])
            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), "previous\n")

    def test_closed_pipe_is_quiet(self):
        # `faker-grocery export ... | head -1` with an output larger than the
        # pipe buffer: the write itself fails, during the export.
        process = subprocess.Popen(
            [sys.executable, "-m", "faker_grocery", "export", "receipts", "-n", "2000", "--format", "jsonl"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        process.stdout.readline()
        process.stdout.close()
        stderr = process.stderr.read().decode()
        process.stderr.close()
        self.assertEqual(process.wait(timeout=60), 0, msg=stderr)
        self.assertNotIn("BrokenPipeError", stderr)

    def test_closed_pipe_on_final_flush_is_quiet(self):
        # A small output is still buffered when the export ends: the broken
        # pipe only shows on the flush, which must happen inside main().
        class ClosedPipe(io.StringIO):
            def flush(self):
                raise BrokenPipeError(32, "Broken pipe")

            def fileno(self):
                return 1

        with mock.patch("sys.stdout", ClosedPipe()), mock.patch("faker_grocery.__main__.os.dup2") as dup2, \
                mock.patch("faker_grocery.__main__.os.open", return_value=99):
            self.assertEqual(main(["export", "products", "-n", "2"]), 0)
        dup2.assert_called_once_with(99, 1)

    def test_demo_runs(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(["demo", "--locale", "es_ES"]), 0)
        self.assertIn("Demo (es_ES)", out.getvalue())

    def test_locale_without_demo_subcommand(self):
        for argv in (["--locale", "fr_FR"], ["--local", "fr_FR"], ["-l", "fr_FR"]):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(argv), 0)
            self.assertIn("Demo (fr_FR)", out.getvalue())
            self.assertNotIn("Demo (en_US)", out.getvalue())
        with contextlib.redirect_stdout(io.StringIO()) as out:
            main(["-l", "it_IT", "-l", "de_DE"])
        self.assertIn("Demo (it_IT)", out.getvalue())
        self.assertIn("Demo (de_DE)", out.getvalue())
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            main(["--locale", "xx_XX"])

    def test_invalid_arguments_exit(self):
        for argv in (["export", "baskets", "-n", "0"], ["export", "nope"], ["export", "baskets", "--format", "xml"]):
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                main(argv)


if __name__ == "__main__":
    unittest.main()
