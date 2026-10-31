"""
Unit tests for the GroceryStoreProvider.
"""
import datetime
import unittest

from faker import Faker

from faker_grocery import GroceryStoreProvider


class TestGroceryStoreProvider(unittest.TestCase):
    def setUp(self):
        # Fixed seed: every test sees the same draws on every run, so a
        # failure is reproducible instead of showing up once in a while
        # (broad randomized coverage lives in test_invariants_over_many_draws).
        Faker.seed(20261031)
        self.fake = Faker("fr_FR")
        self.fake.add_provider(GroceryStoreProvider)
        self.provider = GroceryStoreProvider(self.fake)

    def billed_quantity(self, item, lang="fr"):
        """The quantity an item's unit_price applies to: the article count for
        counted units, the quantity converted to kg/L for measured ones."""
        data = self.provider._data
        for unit_key, spec in data["measured_units"].items():
            if data["unit_labels"][unit_key][lang] == item["unit"]:
                return round(item["quantity"] * spec["factor"], 6)
        return item["quantity"]

    def price_factor(self, currency):
        info = self.provider._data["currencies"][currency]
        return info["rate"] * info["price_level"]

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
        dept = self.fake.grocery_department()
        names = [info["fr"] for info in self.provider.departments.values()]
        self.assertIn(dept, names)

    def test_department_id(self):
        dept_id = self.fake.department_id()
        self.assertIn(str(dept_id), self.provider.departments)

    def test_grocery_department_name(self):
        for dept_id in self.provider.departments:
            name = self.fake.grocery_department_name(dept_id)
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

    def test_grocery_department_name_with_integer_id(self):
        self.assertEqual(self.fake.grocery_department_name(16), self.provider.departments["16"]["fr"])

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
        expected_total = round(self.billed_quantity(item) * item["unit_price"], 2)
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
        # Department 21 ("missing") only uses counted units (piece/pack).
        single_quantities = [self.fake.grocery_item(department=21, family_size=1)["quantity"] for _ in range(50)]
        big_family_quantities = [self.fake.grocery_item(department=21, family_size=8)["quantity"] for _ in range(50)]
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

    def eur_price_range(self, row):
        """The EUR range a product's base_price comes from: its aisle's per-kg/L
        range if sold by weight/volume, else its department's per-article range."""
        data = self.provider._data
        if row[data["unit_col"]] in data["measured_units"]:
            return self.provider._data["measured_price_ranges"][str(row[1])]
        return data["price_ranges"][str(row[2])]

    def test_every_product_base_price_is_within_its_price_range(self):
        base_price_col = self.provider._data["base_price_col"]
        for row in self.provider._data["products"]:
            low, high = self.eur_price_range(row)
            base_price = row[base_price_col]
            self.assertGreaterEqual(base_price, low, msg=row)
            self.assertLessEqual(base_price, high, msg=row)

    def test_every_product_unit_is_one_of_its_aisle_units(self):
        data = self.provider._data
        for row in data["products"]:
            self.assertIn(row[data["unit_col"]], data["aisle_units"][str(row[1])], msg=row)

    def test_measured_units_only_in_aisles_with_a_per_kg_range(self):
        data = self.provider._data
        ranges = self.provider._data["measured_price_ranges"]
        for aisle_id, units in data["aisle_units"].items():
            if set(units) & set(data["measured_units"]):
                self.assertIn(aisle_id, ranges)

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

    def test_grocery_item_price_is_consistent_with_its_price_range(self):
        for dept_id in self.provider.departments:
            item = self.fake.grocery_item(department=dept_id)
            low, high = self.eur_price_range(self.provider._data["by_id"][item["product_id"]])
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

    def test_product_unit_is_fixed(self):
        # A given product is always sold in the same unit.
        units = {}
        for _ in range(500):
            item = self.fake.grocery_item(department=4)  # produce
            units.setdefault(item["product_id"], set()).add(item["unit"])
        self.assertTrue(all(len(u) == 1 for u in units.values()))

    def test_product_record_has_unit_and_price_basis(self):
        for _ in range(50):
            record = self.fake.product_record()
            self.assertIn("unit", record)
            self.assertIn(record["price_per"], {record["unit"], "kg", "L"})

    def test_food_cans_and_drink_cans_are_distinct(self):
        labels = self.provider._data["unit_labels"]
        self.assertEqual(labels["tin"]["fr"], "boîte de conserve")
        self.assertEqual(labels["can"]["fr"], "canette")
        self.assertEqual(self.fake.unit(aisle=59), "boîte de conserve")  # canned meals beans

    def test_unit_with_aisle_filter(self):
        for _ in range(20):
            self.assertEqual(self.fake.unit(aisle=104), "pot")  # spices: jars only

    def test_grocery_list_department_filter_is_fully_consistent(self):
        # Every field of every item (aisle, department, unit, price) must be
        # coherent with the single department the whole basket was
        # restricted to - not just the 'department' label.
        dept_id = "12"  # meat seafood
        expected_unit_labels = {
            self.provider._data["unit_labels"][k]["fr"]
            for k in self.provider._data["department_units"][dept_id]
        }
        shopping_list = self.fake.grocery_list(min_items=10, max_items=10, department=dept_id)
        for item in shopping_list["items"]:
            self.assertEqual(item["department"], self.provider.departments[dept_id]["fr"])
            self.assertIn(item["unit"], expected_unit_labels)
            low, high = self.eur_price_range(self.provider._data["by_id"][item["product_id"]])
            self.assertGreaterEqual(item["unit_price"], round(low * 0.94, 2))
            self.assertLessEqual(item["unit_price"], round(high * 1.06, 2))
            self.assertEqual(item["total_price"], round(self.billed_quantity(item) * item["unit_price"], 2))

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
            lambda: self.fake.grocery_department_name(99),
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
        self.assertIn(fake["fr_FR"].grocery_department_name(16), {self.provider.departments["16"]["fr"]})
        self.assertIn(fake["en_US"].grocery_department_name(16), {self.provider.departments["16"]["en"]})


    # -- currency -----------------------------------------------------------------

    def _faker(self, locale):
        fake = Faker(locale)
        fake.add_provider(GroceryStoreProvider)
        return fake

    def test_currency_follows_locale_country(self):
        expected = {"fr_FR": "EUR", "de_DE": "EUR", "en_US": "USD", "en_GB": "GBP",
                    "fr_CA": "CAD", "fr_CH": "CHF", "ja_JP": "JPY"}
        for locale, currency in expected.items():
            self.assertEqual(self._faker(locale).grocery_currency(), currency, msg=locale)

    def test_unlisted_country_falls_back_to_base_currency(self):
        self.assertEqual(self._faker("en_PH").grocery_currency(), "EUR")

    def test_grocery_currency_symbol(self):
        self.assertEqual(self.fake.grocery_currency(symbol=True), "€")
        self.assertEqual(self._faker("en_GB").grocery_currency(symbol=True), "£")

    def test_faker_currency_code_is_not_shadowed(self):
        # Faker's own currency_code() returns a random currency; the provider
        # must not override it with its fixed locale currency.
        codes = {self.fake.currency_code() for _ in range(50)}
        self.assertGreater(len(codes), 1)

    def test_prices_are_converted_from_the_eur_catalog(self):
        fake = self._faker("en_US")
        factor = self.price_factor("USD")
        base_price_col = self.provider._data["base_price_col"]
        for _ in range(30):
            record = fake.product_record()
            eur_base = self.provider._data["by_id"][record["id"]][base_price_col]
            self.assertEqual(record["currency"], "USD")
            self.assertEqual(record["base_price"], round(eur_base * factor, 2))
            self.assertGreaterEqual(record["price"], round(record["base_price"] * 0.95, 2) - 0.01)
            self.assertLessEqual(record["price"], round(record["base_price"] * 1.05, 2) + 0.01)

    def test_department_price_range_is_converted(self):
        fake = self._faker("en_GB")
        factor = self.price_factor("GBP")
        low, high = self.provider._data["price_ranges"]["5"]  # alcohol, 4-40 EUR
        for _ in range(30):
            price = fake.price(department=5)
            self.assertGreaterEqual(price, round(low * factor, 2))
            self.assertLessEqual(price, round(high * factor, 2))

    def test_custom_price_range_is_not_converted(self):
        fake = self._faker("ja_JP")
        for _ in range(30):
            price = fake.price(min_price=100, max_price=200)
            self.assertGreaterEqual(price, 100)
            self.assertLessEqual(price, 200)

    def test_zero_decimal_currency_gives_whole_prices(self):
        fake = self._faker("ja_JP")
        shopping_list = fake.grocery_list()
        self.assertEqual(shopping_list["currency"], "JPY")
        self.assertIsInstance(shopping_list["total"], int)
        for item in shopping_list["items"]:
            self.assertIsInstance(item["unit_price"], int)
            self.assertEqual(item["total_price"], round(self.billed_quantity(item, lang="en") * item["unit_price"]))
        self.assertEqual(shopping_list["total"], sum(i["total_price"] for i in shopping_list["items"]))

    def test_currency_field_in_items_and_lists(self):
        self.assertEqual(self.fake.grocery_item()["currency"], "EUR")
        self.assertEqual(self.fake.grocery_list(min_items=1, max_items=1)["currency"], "EUR")

    def test_set_grocery_currency_overrides_and_resets(self):
        fake = self._faker("fr_FR")
        fake.set_grocery_currency("usd")
        self.assertEqual(fake.grocery_currency(), "USD")
        self.assertEqual(fake.grocery_item()["currency"], "USD")
        fake.set_grocery_currency(None)
        self.assertEqual(fake.grocery_currency(), "EUR")

    def test_set_unsupported_currency_raises(self):
        with self.assertRaises(ValueError):
            self.fake.set_grocery_currency("XYZ")


    # -- price levels ---------------------------------------------------------------

    def test_price_level_makes_switzerland_dearer_than_a_plain_conversion(self):
        fake = self._faker("fr_CH")
        info = self.provider._data["currencies"]["CHF"]
        base_price_col = self.provider._data["base_price_col"]
        for _ in range(20):
            record = fake.product_record()
            eur_base = self.provider._data["by_id"][record["id"]][base_price_col]
            self.assertEqual(record["base_price"], round(eur_base * info["rate"] * info["price_level"], 2))
            if eur_base >= 1:
                self.assertGreater(record["base_price"], round(eur_base * info["rate"], 2))

    def test_country_price_level_varies_within_the_eurozone(self):
        # Same EUR currency, different countries: Portugal cheaper, Ireland dearer.
        levels = self.provider._data["country_price_levels"]
        base_price_col = self.provider._data["base_price_col"]
        for locale, country in [("pt_PT", "PT"), ("en_IE", "IE"), ("fr_FR", "FR")]:
            fake = self._faker(locale)
            self.assertEqual(fake.grocery_currency(), "EUR")
            record = fake.product_record()
            eur_base = self.provider._data["by_id"][record["id"]][base_price_col]
            self.assertEqual(record["base_price"], round(eur_base * levels[country], 2), msg=locale)

    def test_overridden_currency_uses_its_own_price_level(self):
        # A Portuguese locale priced in USD gets US prices, not Portuguese ones.
        fake = self._faker("pt_PT")
        fake.set_grocery_currency("USD")
        base_price_col = self.provider._data["base_price_col"]
        record = fake.product_record()
        eur_base = self.provider._data["by_id"][record["id"]][base_price_col]
        self.assertEqual(record["base_price"], round(eur_base * self.price_factor("USD"), 2))

    def test_every_currency_has_a_positive_price_level(self):
        for code, info in self.provider._data["currencies"].items():
            self.assertGreater(info["price_level"], 0, msg=code)
        self.assertEqual(self.provider._data["currencies"]["EUR"]["price_level"], 1.0)

    # -- measured quantities --------------------------------------------------------

    def _items_with_unit(self, unit_key, aisle, family_size=None, n=200):
        label = self.provider._data["unit_labels"][unit_key]["fr"]
        items = [self.fake.grocery_item(aisle=aisle, family_size=family_size) for _ in range(n)]
        return [item for item in items if item["unit"] == label]

    def test_weight_quantities_are_realistic_and_priced_per_kg(self):
        spec = self.provider._data["measured_units"]["kg"]
        items = self._items_with_unit("kg", aisle=24, family_size=2)  # fresh fruits
        self.assertTrue(items)
        for item in items:
            self.assertIsInstance(item["quantity"], float)
            self.assertGreaterEqual(item["quantity"], spec["min"])
            self.assertLessEqual(item["quantity"], spec["base"] + spec["per_person"] * 2 + 1e-9)
            self.assertEqual(item["price_per"], "kg")
            self.assertEqual(item["total_price"], round(item["quantity"] * item["unit_price"], 2))

    def test_gram_quantities_are_whole_steps_priced_per_kg(self):
        spec = self.provider._data["measured_units"]["g"]
        items = self._items_with_unit("g", aisle=96)  # lunch meat
        self.assertTrue(items)
        for item in items:
            self.assertIsInstance(item["quantity"], int)
            self.assertEqual(item["quantity"] % spec["step"], 0)
            self.assertEqual(item["price_per"], "kg")
            self.assertEqual(item["total_price"], round(item["quantity"] / 1000 * item["unit_price"], 2))

    def test_volume_quantities_are_priced_per_litre(self):
        items = self._items_with_unit("l", aisle=84)  # milk
        self.assertTrue(items)
        for item in items:
            self.assertEqual(item["price_per"], "L")
            self.assertEqual(item["total_price"], round(item["quantity"] * item["unit_price"], 2))

    def test_per_kg_prices_are_realistic_for_their_aisle(self):
        # 200 g of seafood is priced from a seafood per-kg range, not as a
        # fraction of an arbitrary per-article price.
        low, high = self.provider._data["measured_price_ranges"]["39"]  # seafood counter
        for item in self._items_with_unit("kg", aisle=39) + self._items_with_unit("g", aisle=39):
            self.assertGreaterEqual(item["unit_price"], round(low * 0.94, 2))
            self.assertLessEqual(item["unit_price"], round(high * 1.06, 2))

    def test_counted_items_are_priced_per_article(self):
        for _ in range(30):
            item = self.fake.grocery_item(department=21)  # piece/pack only
            self.assertIsInstance(item["quantity"], int)
            self.assertEqual(item["price_per"], item["unit"])

    def test_measured_quantities_scale_with_family_size(self):
        small = [i["quantity"] for i in self._items_with_unit("kg", aisle=24, family_size=1, n=300)]
        big = [i["quantity"] for i in self._items_with_unit("kg", aisle=24, family_size=8, n=300)]
        self.assertLess(max(small), max(big))

    # -- popularity weighting -----------------------------------------------------

    def test_weighted_picks_favour_popular_products(self):
        # Banana (id 24852) is by far the most ordered product in the source data.
        Faker.seed(7)
        weighted = sum(self.fake.product_record()["id"] == 24852 for _ in range(2000))
        Faker.seed(7)
        uniform = sum(self.fake.product_record(weighted=False)["id"] == 24852 for _ in range(2000))
        self.assertGreater(weighted, 5)
        self.assertLessEqual(uniform, 2)

    def test_weighted_picks_respect_filters(self):
        for _ in range(50):
            self.assertEqual(self.fake.product_record(aisle=84)["aisle_id"], 84)
            self.assertEqual(self.fake.product_record(department=16)["department_id"], 16)

    def test_cumulative_weights_match_their_row_lists(self):
        data = self.provider._data
        self.assertEqual(len(data["cum_weights"]), len(data["products"]))
        for key, rows in data["by_aisle"].items():
            self.assertEqual(len(data["cum_weights_by_aisle"][key]), len(rows))
        for key, rows in data["by_department"].items():
            self.assertEqual(len(data["cum_weights_by_department"][key]), len(rows))

    # -- realistic shopping times -----------------------------------------------------

    def test_shopping_patterns_shape(self):
        for name, weights in self.provider._data["shopping_patterns"].items():
            self.assertEqual(len(weights), 7, msg=name)
            for hours in weights:
                self.assertEqual(len(hours), 24, msg=name)

    def test_shopping_pattern_follows_locale_country(self):
        expected = {"fr_FR": "sunday_morning", "es_ES": "sunday_morning", "de_DE": "sunday_closed",
                    "de_CH": "sunday_closed", "en_US": "instacart_us", "en_GB": "instacart_us"}
        for locale, pattern in expected.items():
            self.assertEqual(self._faker(locale).grocery_shopping_pattern(), pattern, msg=locale)

    def test_set_grocery_shopping_pattern_overrides_and_resets(self):
        self.fake.set_grocery_shopping_pattern("sunday_closed")
        self.assertEqual(self.fake.grocery_shopping_pattern(), "sunday_closed")
        self.fake.set_grocery_shopping_pattern(None)
        self.assertEqual(self.fake.grocery_shopping_pattern(), "sunday_morning")
        with self.assertRaises(ValueError):
            self.fake.set_grocery_shopping_pattern("nope")

    def test_sunday_closed_pattern_never_shops_on_sunday(self):
        fake = self._faker("de_DE")
        for _ in range(500):
            self.assertNotEqual(fake.shopping_datetime().weekday(), 6)

    def test_sunday_morning_pattern_never_shops_on_sunday_afternoon(self):
        sundays = [dt for dt in (self.fake.shopping_datetime() for _ in range(2000)) if dt.weekday() == 6]
        self.assertTrue(sundays)
        self.assertTrue(all(dt.hour < 13 for dt in sundays))

    def test_sunday_morning_pattern_busiest_on_saturday(self):
        weekdays = [self.fake.shopping_datetime().weekday() for _ in range(3000)]
        self.assertEqual(max(range(7), key=weekdays.count), 5)

    def test_forced_closed_day_falls_back_to_opening_hours(self):
        fake = self._faker("de_DE")
        sunday = datetime.date(2025, 6, 1)
        for _ in range(50):
            dt = fake.shopping_datetime(date=sunday)
            self.assertEqual(dt.date(), sunday)
            self.assertTrue(8 <= dt.hour < 20)

    def test_weighted_shopping_hours_avoid_quiet_opening_time(self):
        # Instacart orders are much rarer at 8h than mid-afternoon.
        self.fake.set_grocery_shopping_pattern("instacart_us")
        hours = [self.fake.shopping_datetime(date=datetime.date(2025, 6, 1)).hour for _ in range(2000)]
        self.assertGreater(hours.count(14), hours.count(8))
        for hour in hours:
            self.assertGreaterEqual(hour, 8)
            self.assertLess(hour, 20)

    def test_weighted_shopping_days_follow_the_weekly_pattern(self):
        self.fake.set_grocery_shopping_pattern("instacart_us")
        weights = self.provider._data["shopping_patterns"]["instacart_us"]
        day_totals = [sum(hours[8:20]) for hours in weights]
        busiest, quietest = day_totals.index(max(day_totals)), day_totals.index(min(day_totals))
        weekdays = [self.fake.shopping_datetime().weekday() for _ in range(3000)]
        self.assertGreater(weekdays.count(busiest), weekdays.count(quietest))

    def test_unweighted_shopping_datetime_still_within_hours(self):
        for _ in range(50):
            dt = self.fake.shopping_datetime(open_hour=9, close_hour=12, weighted=False)
            self.assertIn(dt.hour, (9, 10, 11))


    # -- name clash with Faker's administrative departments -------------------------

    def test_fr_fr_keeps_fakers_administrative_departments(self):
        # Faker's fr_FR address provider has department() -> ("18", "Cher")
        # and department_name() -> "Sarthe"; adding the grocery provider must
        # not replace them.
        from faker.providers.address.fr_FR import Provider as FrAddressProvider

        expected_departments = set(FrAddressProvider.departments)  # (code, name) tuples
        dept = self.fake.department()
        self.assertIsInstance(dept, tuple)
        self.assertIn(dept, expected_departments)
        self.assertIn(self.fake.department_name(), {name for _, name in expected_departments})

    def test_es_co_keeps_fakers_administrative_departments(self):
        from faker.providers.address.es_CO import Provider as CoAddressProvider

        fake = self._faker("es_CO")
        self.assertIn(fake.department(), CoAddressProvider.departments.values())

    def test_grocery_department_names_work_in_every_locale(self):
        for locale in ["fr_FR", "es_CO", "en_US", "de_DE"]:
            fake = self._faker(locale)
            lang = GroceryStoreProvider(fake).language
            names = {info[lang] for info in self.provider.departments.values()}
            self.assertIn(fake.grocery_department(), names, msg=locale)
            self.assertEqual(fake.grocery_department_name(16), self.provider.departments["16"][lang], msg=locale)

    def test_deprecated_aliases_still_work_without_a_clash(self):
        fake = self._faker("en_US")  # no administrative departments in en_US
        with self.assertWarns(DeprecationWarning):
            dept = fake.department()
        self.assertIn(dept, {info["en"] for info in self.provider.departments.values()})
        with self.assertWarns(DeprecationWarning):
            self.assertEqual(fake.department_name(16), self.provider.departments["16"]["en"])

    def test_deprecated_aliases_still_work_on_the_provider_itself(self):
        # Even in fr_FR, calling the provider directly still reaches the alias.
        with self.assertWarns(DeprecationWarning):
            self.assertEqual(self.provider.department_name(16), self.provider.departments["16"]["fr"])

    def test_aliases_hidden_only_when_they_would_clash(self):
        self.assertNotIn("department", dir(self.provider))
        self.assertNotIn("department_name", dir(self.provider))
        self.assertIn("grocery_department", dir(self.provider))
        en_provider = GroceryStoreProvider(self._faker("en_US"))
        self.assertIn("department", dir(en_provider))
        self.assertIn("department_name", dir(en_provider))

    def test_adding_the_provider_twice_keeps_the_aliases(self):
        # A second GroceryStoreProvider must not count as a clashing provider.
        fake = self._faker("en_US")
        fake.add_provider(GroceryStoreProvider)
        with self.assertWarns(DeprecationWarning):
            self.assertIsInstance(fake.department(), str)

    def test_multi_locale_faker_keeps_each_locales_departments(self):
        fake = Faker(["fr_FR", "en_US"])
        for locale in ("fr_FR", "en_US"):
            fake[locale].add_provider(GroceryStoreProvider)
        self.assertIsInstance(fake["fr_FR"].department(), tuple)
        self.assertEqual(fake["fr_FR"].grocery_department_name(16), self.provider.departments["16"]["fr"])
        self.assertEqual(fake["en_US"].grocery_department_name(16), self.provider.departments["16"]["en"])

    # -- robustness ---------------------------------------------------------------------

    def test_invariants_over_many_draws(self):
        # Broad randomized sweep (but seeded, so reproducible): many baskets
        # across locales, currencies and patterns must all stay internally
        # consistent. Catches rare edge cases (rounding, empty ranges...)
        # that a handful of draws would miss.
        data = self.provider._data
        for locale in ["fr_FR", "en_US", "de_DE", "ja_JP", "pt_PT", "fr_CH"]:
            fake = self._faker(locale)
            provider = GroceryStoreProvider(fake)
            lang, decimals = provider.language, data["currencies"][provider.currency]["decimals"]
            pattern = data["shopping_patterns"][fake.grocery_shopping_pattern()]
            for seed in range(40):
                Faker.seed(seed)
                basket = fake.grocery_list(family_size=1 + seed % 6, with_datetime=True)
                self.assertEqual(basket["total"], round(sum(i["total_price"] for i in basket["items"]), decimals))
                dt = basket["shopping_datetime"]
                self.assertTrue(8 <= dt.hour < 20)
                self.assertGreater(pattern[dt.weekday()][dt.hour], 0, msg=(locale, dt))
                for item in basket["items"]:
                    row = data["by_id"][item["product_id"]]
                    unit_key = row[data["unit_col"]]
                    self.assertEqual(item["unit"], data["unit_labels"][unit_key][lang])
                    self.assertIn(unit_key, data["aisle_units"][str(row[1])])
                    measure = data["measured_units"].get(unit_key)
                    billed = round(item["quantity"] * measure["factor"], 6) if measure else item["quantity"]
                    self.assertGreater(item["quantity"], 0)
                    self.assertGreater(item["unit_price"], 0)
                    self.assertEqual(item["total_price"], round(billed * item["unit_price"], decimals))


if __name__ == "__main__":
    unittest.main()
