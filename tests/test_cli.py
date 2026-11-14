"""
Tests for the command line (python -m faker_grocery / faker-grocery).
"""
import contextlib
import csv
import io
import json
import os
import tempfile
import unittest

from faker_grocery.__main__ import EXPORT_KINDS, export, main


def run_export(kind, fmt, count=3, **kwargs):
    out = io.StringIO()
    written = export(kind, count, kwargs.pop("locale", "fr_FR"), fmt, out, seed=kwargs.pop("seed", 7), **kwargs)
    return out.getvalue(), written


class TestExport(unittest.TestCase):
    def test_every_kind_in_every_format(self):
        for kind in EXPORT_KINDS:
            text, _ = run_export(kind, "json")
            records = json.loads(text)
            self.assertEqual(len(records), 3, msg=kind)
            lines = run_export(kind, "jsonl")[0].splitlines()
            self.assertEqual(len(lines), 3, msg=kind)
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


class TestMain(unittest.TestCase):
    def test_export_to_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "baskets.csv")
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(main(["export", "baskets", "-n", "5", "--seed", "1", "-o", path]), 0)
            self.assertIn("Wrote", err.getvalue())
            with open(path, encoding="utf-8") as f:
                self.assertEqual(len({row["basket_id"] for row in csv.DictReader(f)}), 5)

    def test_demo_runs(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(["demo", "--locale", "es_ES"]), 0)
        self.assertIn("Demo (es_ES)", out.getvalue())

    def test_invalid_arguments_exit(self):
        for argv in (["export", "baskets", "-n", "0"], ["export", "nope"], ["export", "baskets", "--format", "xml"]):
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                main(argv)


if __name__ == "__main__":
    unittest.main()
