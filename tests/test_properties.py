"""
Property-based tests (hypothesis): invariants that must hold for any seed,
locale and argument combination, not just the seeds of the other tests.
"""
import functools
import unittest

from faker import Faker
from hypothesis import given, settings
from hypothesis import strategies as st

from faker_grocery import GroceryStoreProvider

# One locale per currency / tax regime: decimal EUR with included VAT, US
# sales tax added at the till, whole-number JPY, 3-decimal BHD, no VAT data.
LOCALES = ["fr_FR", "en_US", "de_DE", "ja_JP", "ar_BH", "en_CA", "pt_BR", "it_IT"]
SEEDS = st.integers(min_value=0, max_value=2**32 - 1)
SETTINGS = settings(max_examples=60, deadline=None)


@functools.cache
def _faker(locale: str) -> tuple[Faker, GroceryStoreProvider]:
    fake = Faker(locale)
    return fake, GroceryStoreProvider(fake)


def provider_for(locale: str, seed: int) -> GroceryStoreProvider:
    fake, provider = _faker(locale)
    fake.seed_instance(seed)
    return provider


def minor_unit(provider: GroceryStoreProvider) -> float:
    return 10 ** -provider._decimals


def ean_is_valid(code: str) -> bool:
    digits = [int(c) for c in code]
    return len(code) == 13 and sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits)) % 10 == 0


class TestProperties(unittest.TestCase):
    @SETTINGS
    @given(product_id=st.integers(min_value=0, max_value=10**10 - 1))
    def test_ean13_is_valid_and_in_store(self, product_id):
        code = GroceryStoreProvider._ean13(product_id)
        self.assertTrue(ean_is_valid(code), code)
        self.assertTrue(code.startswith("20"))
        self.assertEqual(int(code[2:12]), product_id)

    @SETTINGS
    @given(locale=st.sampled_from(LOCALES), seed=SEEDS,
           bounds=st.tuples(st.integers(1, 30), st.integers(0, 30)).map(lambda t: (t[0], t[0] + t[1])),
           family_size=st.integers(1, 8))
    def test_grocery_list_counts_and_total(self, locale, seed, bounds, family_size):
        provider = provider_for(locale, seed)
        basket = provider.grocery_list(min_items=bounds[0], max_items=bounds[1], family_size=family_size)
        self.assertEqual(basket["item_count"], len(basket["items"]))
        self.assertTrue(bounds[0] <= basket["item_count"] <= bounds[1])
        expected = sum(item["total_price"] for item in basket["items"])
        self.assertAlmostEqual(basket["total"], expected, delta=minor_unit(provider))
        for item in basket["items"]:
            self.assertGreater(item["quantity"], 0)
            self.assertGreaterEqual(item["total_price"], 0)
            self.assertTrue(ean_is_valid(item["ean"]))

    @SETTINGS
    @given(locale=st.sampled_from(LOCALES), seed=SEEDS, promotion_rate=st.floats(0, 1),
           payment_method=st.sampled_from([None, "card", "cash", "mobile"]))
    def test_receipt_amounts_add_up(self, locale, seed, promotion_rate, payment_method):
        provider = provider_for(locale, seed)
        receipt = provider.receipt(promotion_rate=promotion_rate, payment_method=payment_method)
        unit = minor_unit(provider)
        lines = receipt["lines"]
        self.assertEqual(receipt["item_count"], len(lines))
        for line in lines:
            self.assertGreaterEqual(line["discount"], 0)
            self.assertLessEqual(line["discount"], line["total_price"] + unit)
            self.assertEqual(line["promotion"] is None, line["discount"] == 0)
        self.assertAlmostEqual(receipt["subtotal"], sum(line["total_price"] for line in lines), delta=unit)
        self.assertAlmostEqual(receipt["discount_total"], sum(line["discount"] for line in lines), delta=unit)
        net = receipt["subtotal"] - receipt["discount_total"]
        self.assertAlmostEqual(receipt["tax_total"], sum(tax["amount"] for tax in receipt["taxes"]), delta=unit)
        expected_total = net if receipt["taxes_included"] else net + receipt["tax_total"]
        self.assertAlmostEqual(receipt["total"], expected_total, delta=2 * unit)
        if receipt["taxes_included"]:
            # Included VAT: bases + amounts give back the taxed lines.
            taxed = sum(tax["base"] + tax["amount"] for tax in receipt["taxes"])
            if receipt["taxes"]:
                self.assertAlmostEqual(taxed, net, delta=2 * unit * len(receipt["taxes"]))
        self.assertGreaterEqual(receipt["amount_tendered"], receipt["total"])
        self.assertAlmostEqual(receipt["change"], receipt["amount_tendered"] - receipt["total"], delta=unit)
        if receipt["payment_method"] != "cash":
            self.assertEqual(receipt["change"], 0)
        if payment_method is not None:
            self.assertEqual(receipt["payment_method"], payment_method)

    @SETTINGS
    @given(locale=st.sampled_from(LOCALES), seed=SEEDS, month=st.integers(1, 12))
    def test_product_record_is_consistent(self, locale, seed, month):
        provider = provider_for(locale, seed)
        record = provider.product_record(month=month)
        self.assertEqual(record["ean"], provider.product_ean(record["id"]))
        self.assertEqual(record["name"], provider.product_name(record["id"]))
        self.assertEqual(record["aisle"], provider.aisle_name(record["aisle_id"]))
        self.assertEqual(record["department"], provider.grocery_department_name(record["department_id"]))
        self.assertGreater(record["price"], 0)
        self.assertEqual(record["currency"], provider.grocery_currency())
        self.assertEqual(record["reference_price"] is None, record["reference_unit"] is None)


if __name__ == "__main__":
    unittest.main()
