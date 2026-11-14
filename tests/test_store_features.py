"""
Tests for the store features added in 0.10.0: weighted departments/aisles,
premium prices, opening hours, package sizes and EAN-13 barcodes,
seasonality, coherent baskets, recurring customers and receipts.
"""
import datetime
import os
import statistics
import sys
import unittest

from faker import Faker

from faker_grocery import GroceryStoreProvider

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from build_data import (  # noqa: E402
    base_price_for,
    load_aisle_complements,
    merge_tail,
    price_range_for,
    triangular_price,
)
from store_tables import parse_size, season_mask  # noqa: E402


def make_faker(locale="fr_FR", seed=20261114):
    fake = Faker(locale)
    fake.add_provider(GroceryStoreProvider)
    fake.seed_instance(seed)
    return fake


def provider_of(fake):
    return next(p for p in fake.providers if isinstance(p, GroceryStoreProvider))


class TestWeightedDepartmentsAndAisles(unittest.TestCase):
    def test_popular_departments_come_up_more_often(self):
        fake = make_faker("en_US")
        ids = [fake.department_id() for _ in range(3000)]
        self.assertGreater(ids.count(4), 10 * max(1, ids.count(10)))  # produce vs bulk

    def test_unweighted_departments_are_uniform(self):
        fake = make_faker("en_US")
        ids = [fake.department_id(weighted=False) for _ in range(4200)]
        self.assertGreater(ids.count(10), 100)

    def test_weighted_aisle_stays_in_department(self):
        fake = make_faker()
        data = provider_of(fake)._data
        for _ in range(200):
            self.assertEqual(data["aisles"][str(fake.aisle_id(department=4))]["department_id"], 4)
        self.assertIn(fake.aisle(department=16, weighted=False), {a["fr"] for a in data["aisles"].values()})


class TestPrices(unittest.TestCase):
    def test_organic_products_get_the_premium_surcharge(self):
        product = {"id": 123, "aisle_id": 24, "department_id": 4, "unit": "piece",
                   "name": {"en": "Organic Fuji Apple"}}
        low, high = price_range_for(24, 4, "piece")
        self.assertEqual(base_price_for(product), round(triangular_price(123, low, high) * 1.25, 2))
        product["name"]["en"] = "Fuji Apple"
        self.assertEqual(base_price_for(product), triangular_price(123, low, high))

    def test_department_price_is_skewed_towards_cheap(self):
        fake = make_faker()
        low, high = provider_of(fake)._data["price_ranges"]["12"]
        prices = [fake.price(department=12) for _ in range(3000)]
        self.assertTrue(all(low <= p <= high for p in prices))
        self.assertLess(statistics.mean(prices), (low + high) / 2)


class TestOpeningHours(unittest.TestCase):
    def test_country_opening_hours(self):
        self.assertEqual(make_faker("fr_FR").grocery_opening_hours(), (8, 21))
        self.assertEqual(make_faker("en_US").grocery_opening_hours(), (7, 23))
        self.assertEqual(make_faker("ja_JP").grocery_opening_hours(), (9, 22))
        self.assertEqual(make_faker("ru_RU").grocery_opening_hours(), (8, 20))  # default

    def test_shopping_datetime_uses_country_hours_unless_given(self):
        fake = make_faker("en_US")
        hours = {fake.shopping_datetime().hour for _ in range(2000)}
        self.assertTrue(hours <= set(range(7, 23)))
        self.assertTrue(hours & {7, 20, 21, 22})
        self.assertTrue(all(10 <= fake.shopping_datetime(open_hour=10).hour < 23 for _ in range(100)))


class TestSizesAndBarcodes(unittest.TestCase):
    def setUp(self):
        self.fake = make_faker()
        self.provider = provider_of(self.fake)

    def test_ean13_is_valid_and_stable(self):
        record = self.fake.product_record()
        ean = record["ean"]
        self.assertEqual(len(ean), 13)
        self.assertTrue(ean.startswith("20"))
        digits = [int(d) for d in ean]
        self.assertEqual(sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits)) % 10, 0)
        self.assertEqual(self.fake.product_ean(record["id"]), ean)
        self.assertEqual(self.provider._ean13(24852), "2000000248523")

    def test_size_labels(self):
        self.assertEqual(self.provider._size_label([1, 500, "g"]), "500 g")
        self.assertEqual(self.provider._size_label([1, 1500, "ml"]), "1,5 L")
        self.assertEqual(self.provider._size_label([6, 330, "ml"]), "6 x 330 mL")
        self.assertEqual(self.provider._size_label([12, None, None]), "12 pièce(s)")
        self.assertIsNone(self.provider._size_label(None))
        en = provider_of(make_faker("en_US"))
        self.assertEqual(en._size_label([1, 1500, "ml"]), "1.5 L")

    def test_reference_price_matches_size(self):
        data = self.provider._data
        for _ in range(300):
            record = self.fake.product_record()
            row = data["by_id"][record["id"]]
            size, unit = row[data["size_col"]], row[data["unit_col"]]
            if unit in data["measured_units"]:
                self.assertEqual(record["reference_price"], record["price"])
                self.assertIsNone(record["size"])
            elif size is None or size[1] is None:
                self.assertIsNone(record["reference_price"])
            else:
                expected = round(record["price"] / (size[0] * size[1] / 1000), 2)
                self.assertEqual(record["reference_price"], expected)
                self.assertIn(record["reference_unit"], {"kg", "L"})

    def test_sizes_stated_in_names_are_parsed(self):
        self.assertEqual(parse_size("Havarti Light 8 oz", 2, 16), [1, 225, "g"])
        self.assertEqual(parse_size("Coconut Water 16 fl oz", 98, 7), [1, 475, "ml"])
        self.assertEqual(parse_size("Fruit Punch 12 Pk 12 Floz", 98, 7), [12, 355, "ml"])
        self.assertEqual(parse_size("2% Milk Gallon", 84, 16), [1, 3785, "ml"])
        self.assertEqual(parse_size("Goldfish 9ct", 2, 16), [9, None, None])
        self.assertIsNone(parse_size("Organic Bananas", 24, 4))

    def test_bigger_sizes_for_dearer_products(self):
        data = self.provider._data
        rows = [r for r in data["by_aisle"][121] if r[data["size_col"]] and r[data["base_price_col"]] < 3]
        big = [r for r in data["by_aisle"][121] if r[data["size_col"]] and r[data["base_price_col"]] > 5]
        self.assertTrue(rows and big)
        self.assertLess(statistics.mean(r[data["size_col"]][1] for r in rows),
                        statistics.mean(r[data["size_col"]][1] for r in big))


class TestSeasonality(unittest.TestCase):
    def test_season_mask(self):
        self.assertEqual(season_mask("Organic Strawberries", 24), (1 << 4) | (1 << 5) | (1 << 6))
        self.assertEqual(season_mask("Strawberry Yogurt", 120), 0)
        self.assertEqual(season_mask("Banana", 24), 0)

    def count_strawberries(self, locale, month):
        fake = make_faker(locale)
        names = [fake.product_record(aisle=24, month=month)["name"] for _ in range(3000)]
        return sum("strawberr" in n.lower() or "fraise" in n.lower() for n in names)

    def test_strawberries_in_june_not_january(self):
        self.assertGreater(self.count_strawberries("fr_FR", 6), 3 * self.count_strawberries("fr_FR", 1))

    def test_southern_hemisphere_is_shifted(self):
        self.assertGreater(self.count_strawberries("en_AU", 12), 3 * self.count_strawberries("en_AU", 6))

    def test_basket_follows_the_season_of_its_date(self):
        fake = make_faker()
        june = datetime.date(2025, 6, 15)
        baskets = [fake.grocery_list(date=june, department=4) for _ in range(100)]
        self.assertTrue(any("raise" in i["product"] for b in baskets for i in b["items"]))

    def test_invalid_month_raises(self):
        fake = make_faker()
        for month in (0, 13, 1.5, True):
            with self.assertRaises(ValueError):
                fake.product(month=month)


class TestCoherentBaskets(unittest.TestCase):
    def pasta_with_sauce_rate(self, coherent):
        fake = make_faker("en_US")
        by_id = provider_of(fake)._data["by_id"]
        with_pasta = with_sauce = 0
        for _ in range(3000):
            aisles = {by_id[item["product_id"]][1] for item in fake.grocery_list(coherent=coherent)["items"]}
            if 131 in aisles:  # dry pasta
                with_pasta += 1
                if 9 in aisles:  # pasta sauce
                    with_sauce += 1
        return with_sauce / with_pasta

    def test_complements_make_pasta_and_sauce_go_together(self):
        self.assertGreater(self.pasta_with_sauce_rate(True), self.pasta_with_sauce_rate(False) + 0.15)

    def test_item_count_is_kept(self):
        fake = make_faker()
        for _ in range(50):
            basket = fake.grocery_list(min_items=3, max_items=8)
            self.assertEqual(len(basket["items"]), basket["item_count"])


class TestCustomers(unittest.TestCase):
    def test_profile(self):
        fake = make_faker()
        profile = fake.customer_profile(family_size=4)
        self.assertEqual(profile["family_size"], 4)
        self.assertEqual(len(profile["favorite_product_ids"]), 24)
        self.assertEqual(len(set(profile["favorite_product_ids"])), 24)
        self.assertTrue(0.4 <= profile["reorder_rate"] <= 0.75)
        self.assertTrue(profile["name"])

    def test_history(self):
        fake = make_faker()
        profile = fake.customer_profile()
        end = datetime.date(2026, 6, 30)
        history = fake.customer_history(profile, trips=6, end_date=end)
        self.assertEqual(len(history), 6)
        dates = [b["shopping_datetime"].date() for b in history]
        self.assertEqual(dates, sorted(dates))
        self.assertEqual(dates[-1], end)
        favorites = set(profile["favorite_product_ids"])
        reordered = sum(i["product_id"] in favorites for b in history for i in b["items"])
        self.assertGreater(reordered / sum(len(b["items"]) for b in history), 0.25)
        self.assertTrue(all(b["customer_id"] == profile["customer_id"] for b in history))

    def test_history_invalid_trips_raises(self):
        with self.assertRaises(ValueError):
            make_faker().customer_history(trips=0)


class TestReceipts(unittest.TestCase):
    def check_consistency(self, receipt, decimals=2):
        lines = receipt["lines"]
        self.assertEqual(receipt["item_count"], len(lines))
        self.assertAlmostEqual(receipt["subtotal"], round(sum(line["total_price"] for line in lines), decimals))
        self.assertAlmostEqual(receipt["discount_total"], round(sum(line["discount"] for line in lines), decimals))
        net = round(receipt["subtotal"] - receipt["discount_total"], decimals)
        tax = round(sum(t["amount"] for t in receipt["taxes"]), decimals)
        self.assertAlmostEqual(receipt["tax_total"], tax)
        expected = net if receipt["taxes_included"] else round(net + tax, decimals)
        self.assertAlmostEqual(receipt["total"], expected)
        self.assertGreaterEqual(receipt["amount_tendered"], receipt["total"])
        self.assertAlmostEqual(receipt["change"], round(receipt["amount_tendered"] - receipt["total"], decimals))
        for line in lines:
            self.assertTrue(0 <= line["discount"] <= line["total_price"])

    def test_receipts_are_consistent_across_locales(self):
        for locale in ("fr_FR", "en_US", "de_DE", "ja_JP", "ar_BH", "fa_IR", "en_GB"):
            fake = make_faker(locale)
            decimals = provider_of(fake)._decimals
            for _ in range(15):
                self.check_consistency(fake.receipt(promotion_rate=0.5), decimals)

    def test_french_vat(self):
        fake = make_faker()
        rates = {line["vat_rate"] for _ in range(30) for line in fake.receipt()["lines"]}
        self.assertTrue(rates <= {0.055, 0.20})
        self.assertIn(0.055, rates)
        receipt = fake.receipt()
        self.assertTrue(receipt["taxes_included"])
        for tax in receipt["taxes"]:
            self.assertAlmostEqual(tax["amount"], tax["base"] * tax["rate"], delta=0.02)

    def test_us_sales_tax_is_added(self):
        fake = make_faker("en_US")
        receipt = fake.receipt(fake.grocery_list(department=17, min_items=3, max_items=3))  # household
        self.assertFalse(receipt["taxes_included"])
        self.assertGreater(receipt["tax_total"], 0)
        self.assertGreater(receipt["total"], receipt["subtotal"] - receipt["discount_total"])

    def test_unknown_country_has_no_tax_breakdown(self):
        receipt = make_faker("fa_IR").receipt()
        self.assertEqual(receipt["taxes"], [])
        self.assertTrue(all(line["vat_rate"] is None for line in receipt["lines"]))

    def test_promotions(self):
        fake = make_faker()
        self.assertTrue(all(line["promotion"] is None for line in fake.receipt(promotion_rate=0)["lines"]))
        lines = [line for _ in range(10) for line in fake.receipt(promotion_rate=1)["lines"]]
        self.assertTrue(all(line["promotion"] for line in lines))
        self.assertTrue(all(line["discount"] > 0 or line["total_price"] < 0.05 for line in lines))

    def test_payment(self):
        fake = make_faker()
        card = fake.receipt(payment_method="card")
        self.assertEqual(card["change"], 0)
        cash = fake.receipt(payment_method="cash")
        self.assertGreaterEqual(cash["amount_tendered"], cash["total"])
        with self.assertRaises(ValueError):
            fake.receipt(payment_method="cheque")
        with self.assertRaises(ValueError):
            fake.receipt(promotion_rate=2)

    def test_receipt_of_a_given_basket(self):
        fake = make_faker()
        history = fake.customer_history(trips=1)
        receipt = fake.receipt(history[0])
        self.assertEqual([line["product_id"] for line in receipt["lines"]],
                         [item["product_id"] for item in history[0]["items"]])
        self.assertEqual(receipt["datetime"], history[0]["shopping_datetime"])
        self.assertEqual(receipt["customer_id"], history[0]["customer_id"])

    def test_store(self):
        store = make_faker().grocery_store()
        self.assertTrue(store["name"] and store["address"])
        self.assertTrue(1 <= store["store_id"] <= 9999)


class TestMeasuredBehaviour(unittest.TestCase):
    """Behaviour driven by the Instacart order statistics (DATAS/)."""

    def test_complements_come_from_co_purchases(self):
        complements = {(a, b): p for a, b, p in load_aisle_complements()}
        self.assertIn((131, 9), complements)  # dry pasta -> pasta sauce
        self.assertIn((43, 106), complements)  # buns rolls -> hot dogs bacon sausage
        self.assertTrue(all(0 < p <= 0.4 for p in complements.values()))
        per_aisle = {}
        for a, _ in complements:
            per_aisle[a] = per_aisle.get(a, 0) + 1
        self.assertLessEqual(max(per_aisle.values()), 3)

    def test_merge_tail(self):
        self.assertEqual(merge_tail([[1, 5], [2, 3], [3, 2], [4, 1]], 3), [[1, 5], [2, 3], [3, 3]])

    def test_basket_sizes_follow_instacart(self):
        fake = make_faker("en_US")
        counts = [fake.grocery_list()["item_count"] for _ in range(2000)]
        self.assertAlmostEqual(statistics.mean(counts), 10.1, delta=1.0)  # Instacart mean, couple
        self.assertLess(statistics.median(counts), statistics.mean(counts))  # skewed: many small baskets
        singles = [fake.grocery_list(family_size=1)["item_count"] for _ in range(1000)]
        families = [fake.grocery_list(family_size=5)["item_count"] for _ in range(1000)]
        self.assertLess(statistics.mean(singles) * 1.5, statistics.mean(families))

    def test_one_bound_clamps_the_measured_count(self):
        fake = make_faker()
        self.assertTrue(all(fake.grocery_list(min_items=12)["item_count"] >= 12 for _ in range(50)))
        self.assertTrue(all(fake.grocery_list(max_items=4)["item_count"] <= 4 for _ in range(50)))
        with self.assertRaises(ValueError):
            fake.grocery_list(min_items=-1)

    def test_customer_behaviour_follows_instacart(self):
        fake = make_faker()
        profiles = [fake.customer_profile() for _ in range(300)]
        intervals = [p["shopping_interval_days"] for p in profiles]
        self.assertTrue(all(1 <= i <= 30 for i in intervals))
        self.assertGreater(intervals.count(7) + intervals.count(30), 0.15 * len(intervals))
        rates = [p["reorder_rate"] for p in profiles]
        self.assertAlmostEqual(statistics.mean(rates), 0.45, delta=0.08)

    def test_favorites_are_re_ordered_staples(self):
        fake = make_faker()
        data = provider_of(fake)._data
        col, order_col = data["reorder_count_col"], data["order_count_col"]
        favorites = [pid for _ in range(30) for pid in fake.customer_profile()["favorite_product_ids"]]
        rows = [data["by_id"][pid] for pid in favorites]
        share = sum(r[col] for r in rows) / sum(r[order_col] for r in rows)
        self.assertGreater(share, 0.6)  # more re-ordered than the catalog average (~59%)


class TestReproducibility(unittest.TestCase):
    def test_same_seed_same_receipt(self):
        date = datetime.date(2026, 3, 1)
        first = make_faker(seed=7).receipt(make_faker(seed=7).grocery_list(date=date))
        second = make_faker(seed=7).receipt(make_faker(seed=7).grocery_list(date=date))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
