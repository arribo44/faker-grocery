"""
Tests for product labels and diets, sales time series, and the pandas /
Parquet exports (skipped when pandas / pyarrow aren't installed).
"""
import datetime
import importlib.util
import os
import tempfile
import unittest
import unittest.mock

from faker import Faker

from faker_grocery import GroceryStoreProvider
from faker_grocery.export import DIETS, records, to_dataframe

HAS_PANDAS = importlib.util.find_spec("pandas") is not None
HAS_PYARROW = importlib.util.find_spec("pyarrow") is not None


def make(locale="fr_FR", seed=1):
    fake = Faker(locale)
    fake.seed_instance(seed)
    return GroceryStoreProvider(fake)


class TestLabels(unittest.TestCase):
    def setUp(self):
        self.provider = make()

    def test_record_carries_labels(self):
        record = self.provider.product_record()
        self.assertIsInstance(record["labels"], list)
        self.assertEqual(record["labels"], self.provider.product_labels(record["id"]))
        self.assertTrue(set(record["labels"]) <= set(self.provider.grocery_labels()))

    def test_labels_come_from_names(self):
        # 24852 is "Banana"; 13176 "Bag of Organic Bananas".
        self.assertEqual(self.provider.product_labels(24852), [])
        self.assertEqual(self.provider.product_labels(13176), ["organic"])

    def test_label_filter(self):
        for _ in range(50):
            record = self.provider.product_record(labels="organic")
            self.assertIn("organic", record["labels"])
            record = self.provider.product_record(labels=["vegan", "gluten_free"])
            self.assertTrue({"vegan", "gluten_free"} <= set(record["labels"]))
        self.assertIsInstance(self.provider.product(labels="kosher", aisle=None), str)

    def test_vegan_implies_lactose_free(self):
        for _ in range(30):
            self.assertIn("lactose_free", self.provider.product_record(labels="vegan")["labels"])

    def test_localized_names(self):
        self.assertEqual(self.provider.grocery_label_name("gluten_free"), "sans gluten")
        self.assertEqual(self.provider.grocery_label_name("organic"), "bio")
        self.assertEqual(self.provider.grocery_diet_name("vegetarian"), "végétarien")
        self.assertEqual(make("de_DE").grocery_label_name("whole_grain"), "Vollkorn")
        self.assertEqual(make("en_US").grocery_diet_name("vegan"), "vegan")

    def test_unknown_label_or_diet(self):
        with self.assertRaises(ValueError):
            self.provider.product(labels="halal")
        with self.assertRaises(ValueError):
            self.provider.product(diet="paleo")
        with self.assertRaises(ValueError):
            self.provider.grocery_label_name("halal")
        with self.assertRaises(ValueError):
            self.provider.grocery_list(diet="paleo")

    def test_impossible_filter(self):
        # No beer is labelled kosher, non-GMO and sugar free at once.
        with self.assertRaises(ValueError):
            self.provider.product(aisle=27, labels=["kosher", "non_gmo", "sugar_free"])

    def test_export_diets_match_the_catalog(self):
        self.assertEqual(list(DIETS), self.provider.grocery_diets())

    def test_filters_keep_the_default_draws(self):
        # Adding the features must not change what a seed gives without them.
        a, b = make(seed=5), make(seed=5)
        self.assertEqual([a.product() for _ in range(20)], [b.product(labels=None, diet=None) for _ in range(20)])


class TestDiets(unittest.TestCase):
    def setUp(self):
        self.provider = make(seed=2)

    def test_diet_rules(self):
        fits = self.provider.product_fits_diet
        # Packaged poultry, bacon: not vegetarian.
        self.assertFalse(fits(self.provider.product_record(aisle=49)["id"], "vegetarian"))
        # Fresh fruit: fits every diet.
        banana = 24852
        self.assertTrue(all(fits(banana, diet) for diet in self.provider.grocery_diets()))
        # Milk: not vegan nor lactose free unless plant-based / labelled.
        for _ in range(20):
            record = self.provider.product_record(aisle=84)
            if "lactose_free" not in record["labels"]:
                self.assertFalse(fits(record["id"], "lactose_free"))
                self.assertFalse(fits(record["id"], "vegan"))
        # Bread needs a gluten free label.
        for _ in range(20):
            record = self.provider.product_record(aisle=112)
            self.assertEqual(fits(record["id"], "gluten_free"), "gluten_free" in record["labels"])

    def test_diet_filter_on_products_and_baskets(self):
        for diet in self.provider.grocery_diets():
            for _ in range(20):
                self.assertTrue(self.provider.product_fits_diet(self.provider.product_record(diet=diet)["id"], diet))
            basket = self.provider.grocery_list(diet=diet, min_items=15, max_items=25)
            self.assertTrue(all(self.provider.product_fits_diet(i["product_id"], diet) for i in basket["items"]))

    def test_customer_diet(self):
        customer = self.provider.customer_profile(diet="gluten_free")
        self.assertEqual(customer["diet"], "gluten_free")
        fits = self.provider.product_fits_diet
        self.assertTrue(all(fits(pid, "gluten_free") for pid in customer["favorite_product_ids"]))
        for basket in self.provider.customer_history(customer, trips=4):
            self.assertTrue(all(fits(item["product_id"], "gluten_free") for item in basket["items"]))
        self.assertIsNone(self.provider.customer_profile()["diet"])

    def test_random_diet_shares(self):
        diets = [self.provider.customer_profile(family_size=1, diet="random")["diet"] for _ in range(600)]
        share = sum(d is not None for d in diets) / len(diets)
        self.assertTrue(0.06 < share < 0.22, share)  # ~13%
        self.assertTrue(set(diets) - {None} <= set(self.provider.grocery_diets()))


class TestSalesSeries(unittest.TestCase):
    def test_groupings_add_up(self):
        start = datetime.date(2026, 3, 2)
        for by, per_day in (("total", 1), ("department", 21), ("aisle", 134)):
            rows = make(seed=4).sales_series(start, start + datetime.timedelta(days=6), by=by)
            self.assertEqual(len(rows), 7 * per_day, msg=by)
        total = make(seed=4).sales_series(start, start, by="total")[0]
        aisles = make(seed=4).sales_series(start, start, by="aisle")
        departments = make(seed=4).sales_series(start, start, by="department")
        self.assertEqual(total["items"], sum(r["items"] for r in aisles))
        self.assertEqual(total["items"], sum(r["items"] for r in departments))
        self.assertAlmostEqual(total["revenue"], sum(r["revenue"] for r in departments), delta=0.1)
        self.assertEqual({r["baskets"] for r in aisles}, {total["baskets"]})
        self.assertEqual(aisles[0]["currency"], "EUR")
        self.assertIn("aisle", aisles[0])
        self.assertNotIn("aisle", departments[0])

    def test_weekly_pattern_and_closed_days(self):
        rows = make("de_DE", seed=1).sales_series(datetime.date(2026, 1, 5), datetime.date(2026, 3, 29), by="total")
        by_weekday = [sum(r["baskets"] for r in rows if r["date"].weekday() == d) / 12 for d in range(7)]
        self.assertEqual(by_weekday[6], 0)  # German shops are closed on Sunday
        self.assertGreater(by_weekday[5], by_weekday[1])  # Saturday busier than Tuesday
        self.assertTrue(all(r["revenue"] == 0 for r in rows if r["date"].weekday() == 6))

    def test_traffic_level_and_revenue(self):
        rows = make("en_US", seed=3).sales_series(datetime.date(2026, 1, 1), datetime.date(2026, 4, 30),
                                                  by="total", baskets_per_day=500)
        mean = sum(r["baskets"] for r in rows) / len(rows)
        self.assertTrue(450 < mean < 550, mean)
        items_per_basket = sum(r["items"] for r in rows) / sum(r["baskets"] for r in rows)
        self.assertTrue(8 < items_per_basket < 13, items_per_basket)
        self.assertEqual(rows[0]["currency"], "USD")

    def test_no_noise_is_smooth(self):
        rows = make("en_US", seed=3).sales_series(datetime.date(2026, 1, 5), datetime.date(2026, 2, 1),
                                                  by="total", noise=0)
        mondays = [r["baskets"] for r in rows if r["date"].weekday() == 0]
        self.assertLess(max(mondays) - min(mondays), 200)

    def test_seasonal_mix(self):
        provider = make(seed=1)
        # Fresh fruit (aisle 24) weighs differently in January and July.
        self.assertNotAlmostEqual(provider._aisle_shares(1)[24], provider._aisle_shares(7)[24], places=3)

    def test_reproducible_and_defaults(self):
        a = make(seed=9).sales_series(datetime.date(2026, 5, 1), datetime.date(2026, 5, 10))
        b = make(seed=9).sales_series(datetime.date(2026, 5, 1), datetime.date(2026, 5, 10))
        self.assertEqual(a, b)
        rows = make().sales_series(by="total")
        self.assertEqual(len(rows), 30)
        self.assertEqual(rows[-1]["date"], datetime.date.today())

    def test_invalid_arguments(self):
        provider = make()
        day = datetime.date(2026, 1, 1)
        for kwargs in ({"by": "week"}, {"baskets_per_day": -1}, {"noise": 2},
                       {"end": day - datetime.timedelta(days=1)}):
            with self.assertRaises(ValueError, msg=kwargs):
                provider.sales_series(**{"start": day, "end": day, **kwargs})

    def test_export_records_cover_the_days(self):
        rows = list(records(make(), "sales", 45, start=datetime.date(2026, 1, 20), by="total"))
        self.assertEqual(len(rows), 45)
        self.assertEqual(rows[0]["date"], datetime.date(2026, 1, 20))
        self.assertEqual(rows[-1]["date"], datetime.date(2026, 3, 5))


@unittest.skipUnless(HAS_PANDAS, "pandas not installed")
class TestDataFrame(unittest.TestCase):
    def test_flat_baskets(self):
        df = to_dataframe("baskets", 20, locale="fr_FR", seed=1)
        self.assertEqual(df["basket_id"].nunique(), 20)
        self.assertEqual(str(df["shopping_datetime"].dtype)[:10], "datetime64")
        self.assertIn("product", df.columns)

    def test_nested_and_options(self):
        df = to_dataframe("receipts", 3, flat=False)
        self.assertEqual(len(df), 3)
        self.assertIn("lines", df.columns)
        sales = to_dataframe("sales", 10, locale="de_DE", by="total", start=datetime.date(2026, 1, 1))
        self.assertEqual(len(sales), 10)
        self.assertEqual(str(sales["date"].dtype)[:10], "datetime64")
        vegan = to_dataframe("products", 30, diet="vegan", seed=2)
        provider = make()
        self.assertTrue(all(provider.product_fits_diet(pid, "vegan") for pid in vegan["id"]))


@unittest.skipUnless(HAS_PYARROW and HAS_PANDAS, "pyarrow / pandas not installed")
class TestParquet(unittest.TestCase):
    def test_every_kind(self):
        import pandas as pd

        from faker_grocery.__main__ import main

        with tempfile.TemporaryDirectory() as directory:
            for kind in ("baskets", "receipts", "customers", "products", "sales"):
                path = os.path.join(directory, f"{kind}.parquet")
                with unittest.mock.patch("sys.stderr"):
                    self.assertEqual(main(["export", kind, "-n", "5", "--format", "parquet", "-o", path,
                                           "--seed", "1"]), 0)
                df = pd.read_parquet(path)
                self.assertGreater(len(df), 0, msg=kind)
            products = pd.read_parquet(os.path.join(directory, "products.parquet"))
            self.assertIn("labels", products.columns)

    def test_parquet_needs_an_output_file(self):
        from faker_grocery.__main__ import main

        with self.assertRaises(SystemExit), unittest.mock.patch("sys.stderr"):
            main(["export", "products", "--format", "parquet"])


if __name__ == "__main__":
    unittest.main()
