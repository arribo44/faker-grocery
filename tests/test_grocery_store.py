"""
Unit tests for the GroceryStoreProvider.
"""
import datetime
import unittest

from faker import Faker

from faker_grocery import GroceryStoreProvider


class TestGroceryStoreProvider(unittest.TestCase):
    def setUp(self):
        self.fake = Faker("fr_FR")
        self.fake.add_provider(GroceryStoreProvider)
        self.provider = GroceryStoreProvider(self.fake)

    def test_locale_property(self):
        # NB: `self.fake.locale` is shadowed by Faker's own `locale` attribute;
        # the provider's `locale` is only reachable on the provider instance.
        self.assertEqual(self.provider.locale, "fr_FR")

    def test_language_resolution(self):
        self.assertEqual(self.provider.language, "fr")
        fake_en = Faker("en_US")
        fake_en.add_provider(GroceryStoreProvider)
        self.assertEqual(GroceryStoreProvider(fake_en).language, "en")

    def test_unsupported_locale_falls_back_to_default(self):
        fake_it = Faker("it_IT")
        fake_it.add_provider(GroceryStoreProvider)
        self.assertEqual(GroceryStoreProvider(fake_it).language, "en")

    def test_department(self):
        dept = self.fake.department()
        names = [info["fr"] for info in self.provider.departments.values()]
        self.assertIn(dept, names)

    def test_department_id(self):
        dept_id = self.fake.department_id()
        self.assertIn(str(dept_id), self.provider.departments)

    def test_department_name(self):
        for dept_id in self.provider.departments:
            name = self.fake.department_name(dept_id)
            self.assertEqual(name, self.provider.departments[dept_id]["fr"])

    def test_departments_property_shape(self):
        self.assertEqual(len(self.provider.departments), 21)
        for info in self.provider.departments.values():
            self.assertIn("en", info)
            self.assertIn("fr", info)

    def test_aisles_property_shape(self):
        self.assertEqual(len(self.provider.aisles), 134)
        for info in self.provider.aisles.values():
            self.assertIn("en", info)
            self.assertIn("fr", info)
            self.assertIn("department_id", info)
            self.assertIn(str(info["department_id"]), self.provider.departments)

    def test_aisle_without_department(self):
        aisle = self.fake.aisle()
        names = [info["fr"] for info in self.provider.aisles.values()]
        self.assertIn(aisle, names)

    def test_aisle_with_department_filter(self):
        for dept_id in self.provider.departments:
            aisle = self.fake.aisle(department=dept_id)
            expected_aisles = {
                info["fr"] for info in self.provider.aisles.values()
                if info["department_id"] == int(dept_id)
            }
            self.assertIn(aisle, expected_aisles)

    def test_aisle_with_department_name_filter(self):
        dept_name = self.provider.departments["4"]["fr"]  # produce
        aisle_id = self.fake.aisle_id(department=dept_name)
        self.assertEqual(self.provider.aisles[str(aisle_id)]["department_id"], 4)

    def test_aisle_unknown_department_raises(self):
        with self.assertRaises(ValueError):
            self.fake.aisle(department="not a real department")

    def test_aisle_with_integer_department_id(self):
        # department=16 as a plain int, not the string key "16" used elsewhere.
        aisle = self.fake.aisle(department=16)
        expected_aisles = {
            info["fr"] for info in self.provider.aisles.values()
            if info["department_id"] == 16
        }
        self.assertIn(aisle, expected_aisles)

    def test_aisle_id_without_filter(self):
        aisle_id = self.fake.aisle_id()
        self.assertIn(str(aisle_id), self.provider.aisles)

    def test_aisle_id_with_integer_department(self):
        aisle_id = self.fake.aisle_id(department=16)
        self.assertEqual(self.provider.aisles[str(aisle_id)]["department_id"], 16)

    def test_aisle_name(self):
        for aisle_id, info in self.provider.aisles.items():
            self.assertEqual(self.fake.aisle_name(aisle_id), info["fr"])

    def test_department_name_with_integer_id(self):
        self.assertEqual(self.fake.department_name(16), self.provider.departments["16"]["fr"])

    def test_department_resolution_accepts_other_language_name(self):
        # The fr_FR provider should still resolve a department given by its
        # English name (name resolution loops over every known language).
        english_name = self.provider.departments["16"]["en"]  # "dairy eggs"
        aisle_id = self.fake.aisle_id(department=english_name)
        self.assertEqual(self.provider.aisles[str(aisle_id)]["department_id"], 16)

    def test_product_unknown_aisle_raises(self):
        with self.assertRaises(ValueError):
            self.fake.product(aisle="not a real aisle")

    def test_product_without_filter(self):
        product = self.fake.product()
        self.assertIsInstance(product, str)
        self.assertGreater(len(product), 0)

    def test_product_with_aisle_filter(self):
        name = self.fake.product(aisle="84")  # milk
        expected_names = {
            row[self.provider._data["name_col"]["fr"]]
            for row in self.provider._data["by_aisle"][84]
        }
        self.assertIn(name, expected_names)

    def test_product_with_integer_aisle_filter(self):
        name = self.fake.product(aisle=84)  # milk, as a plain int
        expected_names = {
            row[self.provider._data["name_col"]["fr"]]
            for row in self.provider._data["by_aisle"][84]
        }
        self.assertIn(name, expected_names)

    def test_product_record_with_aisle_filter(self):
        record = self.fake.product_record(aisle="84")  # milk
        self.assertEqual(record["aisle_id"], 84)
        self.assertEqual(record["department_id"], 16)

    def test_product_with_department_filter(self):
        record = self.fake.product_record(department="16")  # dairy eggs
        self.assertEqual(record["department_id"], 16)

    def test_product_aisle_department_mismatch_raises(self):
        with self.assertRaises(ValueError):
            self.fake.product(aisle="84", department="1")  # milk aisle is not in frozen

    def test_product_record_fields(self):
        record = self.fake.product_record()
        for key in ["id", "name", "aisle_id", "aisle", "department_id", "department", "base_price", "price"]:
            self.assertIn(key, record)

    def test_product_record_price_is_jittered_base_price(self):
        record = self.fake.product_record()
        base = record["base_price"]
        self.assertGreaterEqual(record["price"], round(base * 0.95, 2) - 0.01)
        self.assertLessEqual(record["price"], round(base * 1.05, 2) + 0.01)

    def test_price_for_product_varies_around_base_price(self):
        row = self.provider._data["products"][0]
        product_id, base_price = row[0], row[self.provider._data["base_price_col"]]
        prices = [self.fake.price(product=product_id) for _ in range(30)]
        for p in prices:
            self.assertGreaterEqual(p, round(base_price * 0.95, 2) - 0.01)
            self.assertLessEqual(p, round(base_price * 1.05, 2) + 0.01)
        # Not all jittered draws should be identical (it is a random +/-5%).
        self.assertGreater(len(set(prices)), 1)

    def test_price_for_unknown_product_raises(self):
        with self.assertRaises(ValueError):
            self.fake.price(product=999999999)

    def test_product_name_lookup(self):
        row = self.provider._data["products"][0]
        name = self.fake.product_name(row[0])
        self.assertEqual(name, row[self.provider._data["name_col"]["fr"]])

    def test_price_default(self):
        price = self.fake.price()
        self.assertIsInstance(price, float)
        self.assertGreater(price, 0)

    def test_price_with_department(self):
        min_p, max_p = self.provider._data["price_ranges"]["12"]  # meat seafood
        price = self.fake.price(department="12")
        self.assertGreaterEqual(price, min_p)
        self.assertLessEqual(price, max_p)

    def test_price_with_custom_range(self):
        price = self.fake.price(min_price=10.0, max_price=20.0)
        self.assertGreaterEqual(price, 10.0)
        self.assertLessEqual(price, 20.0)

    def test_quantity(self):
        qty = self.fake.quantity()
        self.assertIsInstance(qty, int)
        self.assertGreaterEqual(qty, 1)
        self.assertLessEqual(qty, 10)

    def test_quantity_with_custom_max(self):
        for _ in range(30):
            qty = self.fake.quantity(max_quantity=3)
            self.assertGreaterEqual(qty, 1)
            self.assertLessEqual(qty, 3)

    def test_unit(self):
        unit = self.fake.unit()
        all_labels = {info["fr"] for info in self.provider._data["unit_labels"].values()}
        self.assertIn(unit, all_labels)

    def test_unit_with_department_filter_is_plausible(self):
        # e.g. "9 bottle x Bread" should not happen: department=3 (bakery)
        # must only ever yield bakery-plausible units.
        expected_keys = self.provider._data["department_units"]["3"]
        expected_labels = {self.provider._data["unit_labels"][k]["fr"] for k in expected_keys}
        for _ in range(30):
            unit = self.fake.unit(department="3")
            self.assertIn(unit, expected_labels)

    def test_grocery_item(self):
        item = self.fake.grocery_item()
        for key in ["product", "product_id", "aisle", "department", "quantity", "unit", "unit_price", "total_price"]:
            self.assertIn(key, item)
        expected_total = round(item["quantity"] * item["unit_price"], 2)
        self.assertEqual(item["total_price"], expected_total)

    def test_grocery_item_with_aisle_filter(self):
        item = self.fake.grocery_item(aisle="84")  # milk
        self.assertEqual(item["aisle"], self.provider.aisles["84"]["fr"])

    def test_grocery_item_with_department_filter(self):
        item = self.fake.grocery_item(department="16")  # dairy eggs
        self.assertEqual(item["department"], self.provider.departments["16"]["fr"])

    def test_grocery_list(self):
        shopping_list = self.fake.grocery_list(min_items=2, max_items=4)
        self.assertIn("items", shopping_list)
        self.assertIn("item_count", shopping_list)
        self.assertIn("total", shopping_list)
        self.assertEqual(len(shopping_list["items"]), shopping_list["item_count"])
        self.assertGreaterEqual(shopping_list["item_count"], 2)
        self.assertLessEqual(shopping_list["item_count"], 4)
        expected_total = round(sum(i["total_price"] for i in shopping_list["items"]), 2)
        self.assertEqual(shopping_list["total"], expected_total)

    def test_grocery_list_department_filter(self):
        shopping_list = self.fake.grocery_list(min_items=3, max_items=3, department="16")
        for item in shopping_list["items"]:
            self.assertEqual(item["department"], self.provider.departments["16"]["fr"])

    def test_grocery_list_default_family_size_is_couple(self):
        shopping_list = self.fake.grocery_list()
        self.assertEqual(shopping_list["family_size"], 2)

    def test_grocery_list_item_count_scales_with_family_size(self):
        # Larger households should get larger default baskets than a single person.
        single_counts = [self.fake.grocery_list(family_size=1)["item_count"] for _ in range(20)]
        big_family_counts = [self.fake.grocery_list(family_size=6)["item_count"] for _ in range(20)]
        self.assertLess(max(single_counts), max(big_family_counts))

    def test_grocery_list_explicit_min_max_override_family_size_defaults(self):
        shopping_list = self.fake.grocery_list(min_items=2, max_items=2, family_size=6)
        self.assertEqual(shopping_list["item_count"], 2)

    def test_grocery_item_quantity_scales_with_family_size(self):
        single_quantities = [self.fake.grocery_item(family_size=1)["quantity"] for _ in range(50)]
        big_family_quantities = [self.fake.grocery_item(family_size=8)["quantity"] for _ in range(50)]
        self.assertLessEqual(max(single_quantities), 2)
        self.assertGreaterEqual(max(big_family_quantities), 3)

    def test_grocery_list_without_datetime_by_default(self):
        shopping_list = self.fake.grocery_list(min_items=1, max_items=1)
        self.assertNotIn("shopping_datetime", shopping_list)

    def test_grocery_list_with_datetime(self):
        shopping_list = self.fake.grocery_list(min_items=1, max_items=1, with_datetime=True)
        self.assertIsInstance(shopping_list["shopping_datetime"], datetime.datetime)

    def test_grocery_list_with_explicit_date(self):
        fixed_date = datetime.date(2025, 12, 24)
        shopping_list = self.fake.grocery_list(min_items=1, max_items=1, date=fixed_date)
        self.assertEqual(shopping_list["shopping_datetime"].date(), fixed_date)

    def test_shopping_datetime_within_opening_hours(self):
        for _ in range(50):
            dt = self.fake.shopping_datetime(open_hour=8, close_hour=20)
            self.assertGreaterEqual(dt.hour, 8)
            self.assertLess(dt.hour, 20)

    def test_shopping_datetime_with_explicit_date(self):
        fixed_date = datetime.date(2025, 1, 1)
        dt = self.fake.shopping_datetime(date=fixed_date)
        self.assertEqual(dt.date(), fixed_date)

    # -- internal consistency / data integrity ---------------------------------
    # These don't just check that a field looks plausible in isolation; they
    # check that fields agree with each other (the price matches the
    # department it claims to be in, the aisle matches its declared
    # department, the unit matches what the product actually is, etc.) - the
    # kind of cross-field coherence that's easy to lose when values are
    # generated independently.

    def test_every_product_base_price_is_within_its_department_range(self):
        price_ranges = self.provider._data["price_ranges"]
        base_price_col = self.provider._data["base_price_col"]
        for row in self.provider._data["products"]:
            department_id = row[2]
            low, high = price_ranges[str(department_id)]
            base_price = row[base_price_col]
            self.assertGreaterEqual(base_price, low, msg=row)
            self.assertLessEqual(base_price, high, msg=row)

    def test_every_product_department_matches_its_aisle_department(self):
        aisles = self.provider.aisles
        for row in self.provider._data["products"]:
            aisle_id, department_id = row[1], row[2]
            self.assertEqual(
                aisles[str(aisle_id)]["department_id"], department_id,
                msg=f"product {row[0]} claims department {department_id} but aisle {aisle_id} belongs to "
                    f"{aisles[str(aisle_id)]['department_id']}",
            )

    def test_department_units_reference_only_known_unit_keys(self):
        unit_keys = set(self.provider._data["unit_labels"].keys())
        for dept_id, keys in self.provider._data["department_units"].items():
            self.assertTrue(keys, msg=f"department {dept_id} has no plausible units")
            self.assertTrue(set(keys) <= unit_keys, msg=f"department {dept_id}: {set(keys) - unit_keys}")

    def test_every_department_has_a_price_range_and_units(self):
        self.assertEqual(set(self.provider.departments), set(self.provider._data["price_ranges"]))
        self.assertEqual(set(self.provider.departments), set(self.provider._data["department_units"]))

    def test_grocery_item_unit_matches_its_own_department(self):
        # Regression guard for the "9 bottle x Bread" kind of incoherence:
        # the unit returned must always be plausible for the item's own
        # department, across many draws spanning different departments.
        for dept_id in self.provider.departments:
            expected_keys = self.provider._data["department_units"][dept_id]
            expected_labels = {self.provider._data["unit_labels"][k]["fr"] for k in expected_keys}
            item = self.fake.grocery_item(department=dept_id)
            self.assertIn(item["unit"], expected_labels)

    def test_grocery_item_price_is_consistent_with_its_department_range(self):
        price_ranges = self.provider._data["price_ranges"]
        for dept_id in self.provider.departments:
            low, high = price_ranges[dept_id]
            item = self.fake.grocery_item(department=dept_id)
            # unit_price is base_price jittered +/-5%, and base_price itself
            # is bounded by [low, high] - allow a small rounding margin.
            self.assertGreaterEqual(item["unit_price"], round(low * 0.94, 2))
            self.assertLessEqual(item["unit_price"], round(high * 1.06, 2))

    def test_product_record_aisle_and_department_match_the_catalog(self):
        # The names embedded in a product_record() must agree with an
        # independent lookup by id - not just look like plausible strings.
        for _ in range(50):
            record = self.fake.product_record()
            aisle_info = self.provider.aisles[str(record["aisle_id"])]
            department_info = self.provider.departments[str(record["department_id"])]
            self.assertEqual(record["aisle"], aisle_info["fr"])
            self.assertEqual(record["department"], department_info["fr"])
            self.assertEqual(aisle_info["department_id"], record["department_id"])

    def test_grocery_list_department_filter_is_fully_consistent(self):
        # Every field of every item (aisle, department, unit, price) must be
        # coherent with the single department the whole basket was
        # restricted to - not just the 'department' label.
        dept_id = "12"  # meat seafood
        low, high = self.provider._data["price_ranges"][dept_id]
        expected_unit_labels = {
            self.provider._data["unit_labels"][k]["fr"]
            for k in self.provider._data["department_units"][dept_id]
        }
        shopping_list = self.fake.grocery_list(min_items=10, max_items=10, department=dept_id)
        for item in shopping_list["items"]:
            self.assertEqual(item["department"], self.provider.departments[dept_id]["fr"])
            self.assertIn(item["unit"], expected_unit_labels)
            self.assertGreaterEqual(item["unit_price"], round(low * 0.94, 2))
            self.assertLessEqual(item["unit_price"], round(high * 1.06, 2))
            self.assertEqual(item["total_price"], round(item["quantity"] * item["unit_price"], 2))

    def test_shopping_datetime_accepts_datetime_instance(self):
        # Passing a full datetime (not just a date) should still work: only
        # its date part is kept, the time is re-rolled within opening hours.
        fixed_datetime = datetime.datetime(2025, 6, 15, 3, 30, 0)
        dt = self.fake.shopping_datetime(date=fixed_datetime)
        self.assertEqual(dt.date(), fixed_datetime.date())
        self.assertGreaterEqual(dt.hour, 8)
        self.assertLess(dt.hour, 20)

    # -- argument validation ------------------------------------------------------

    def test_price_with_only_one_bound_raises(self):
        # Previously min_price alone was silently ignored (price(min_price=5) -> 4.95).
        with self.assertRaises(ValueError):
            self.fake.price(min_price=5.0)
        with self.assertRaises(ValueError):
            self.fake.price(max_price=5.0)

    def test_price_with_inverted_range_raises(self):
        with self.assertRaises(ValueError):
            self.fake.price(min_price=20.0, max_price=10.0)

    def test_shopping_datetime_invalid_hours_raise(self):
        # Previously open_hour=20, close_hour=8 returned a 20:xx time.
        for open_hour, close_hour in [(20, 8), (10, 10), (-1, 8), (8, 25)]:
            with self.assertRaises(ValueError):
                self.fake.shopping_datetime(open_hour=open_hour, close_hour=close_hour)

    def test_shopping_datetime_full_day_opening_hours(self):
        for _ in range(50):
            dt = self.fake.shopping_datetime(open_hour=0, close_hour=24)
            self.assertLessEqual(dt.hour, 23)

    def test_grocery_list_inverted_item_range_raises(self):
        with self.assertRaises(ValueError):
            self.fake.grocery_list(min_items=10, max_items=5)

    def test_grocery_list_invalid_family_size_raises(self):
        for family_size in [0, -3, 2.5, True]:
            with self.assertRaises(ValueError):
                self.fake.grocery_list(family_size=family_size)

    def test_grocery_item_invalid_family_size_raises(self):
        with self.assertRaises(ValueError):
            self.fake.grocery_item(family_size=0)

    def test_grocery_list_unknown_department_raises(self):
        with self.assertRaises(ValueError):
            self.fake.grocery_list(department="not a real department")

    def test_unknown_ids_raise_value_error(self):
        # Previously these leaked a bare KeyError.
        for call in [
            lambda: self.fake.department_name(99),
            lambda: self.fake.aisle_name(9999),
            lambda: self.fake.unit(department=99),
            lambda: self.fake.aisle(department=99),
            lambda: self.fake.product(aisle=9999),
            lambda: self.fake.product_name("not an id"),
        ]:
            with self.assertRaises(ValueError):
                call()

    def test_bool_is_not_accepted_as_an_id(self):
        # bool is a subclass of int: department=True used to mean department 1.
        with self.assertRaises(ValueError):
            self.fake.aisle(department=True)
        with self.assertRaises(ValueError):
            self.fake.product(aisle=False)

    def test_same_seed_gives_same_grocery_list(self):
        Faker.seed(1234)
        first = self.fake.grocery_list(with_datetime=True)
        Faker.seed(1234)
        second = self.fake.grocery_list(with_datetime=True)
        self.assertEqual(first, second)

    def test_multi_locale_faker_via_per_locale_add_provider(self):
        # Faker's multi-locale proxy doesn't implement add_provider(); it has
        # to be added to each locale's generator (as documented in the README).
        fake = Faker(["fr_FR", "en_US"])
        for locale in ("fr_FR", "en_US"):
            fake[locale].add_provider(GroceryStoreProvider)
        self.assertIn(fake["fr_FR"].department_name(16), {self.provider.departments["16"]["fr"]})
        self.assertIn(fake["en_US"].department_name(16), {self.provider.departments["16"]["en"]})


if __name__ == "__main__":
    unittest.main()
