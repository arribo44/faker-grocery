"""
Faker Grocery Store Provider

A custom Faker provider for simulating a supermarket / hypermarket catalog:
departments, aisles and products, plus helpers for prices, quantities, units,
single grocery items and full randomized shopping lists.

The catalog data comes from the Instacart Market Basket Analysis open
dataset (21 departments, 134 aisles, ~49,700 real products). Department and
aisle names are available in multiple languages; product names are
translated from English via a curated word-substitution dictionary, so
translated names are approximate rather than grammatically perfect - this is
fake/test data, not a professional localization.

Supported languages: en, fr.
Planned (data not yet built): it, es, pt, de.
"""
import datetime as _datetime
import json
import os

from faker.providers import BaseProvider

__version__ = "0.3.1"

_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "grocery_data.json")
_data_cache = None


def _load_data():
    global _data_cache
    if _data_cache is None:
        with open(_DATA_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        _data_cache = _build_index(raw)
    return _data_cache


def _build_index(raw):
    languages = raw["meta"]["languages"]
    # products rows are [id, aisle_id, department_id, base_price, name_<lang0>, name_<lang1>, ...]
    base_price_col = 3
    name_offset = 4
    name_col = {lang: name_offset + i for i, lang in enumerate(languages)}

    products = raw["products"]

    by_department = {}
    by_aisle = {}
    for row in products:
        aisle_id, department_id = row[1], row[2]
        by_aisle.setdefault(aisle_id, []).append(row)
        by_department.setdefault(department_id, []).append(row)

    return {
        "meta": raw["meta"],
        "languages": languages,
        "name_col": name_col,
        "base_price_col": base_price_col,
        "departments": raw["departments"],
        "aisles": raw["aisles"],
        "price_ranges": raw["price_ranges"],
        "unit_labels": raw["unit_labels"],
        "department_units": raw["department_units"],
        "products": products,
        "by_department": by_department,
        "by_aisle": by_aisle,
    }


class GroceryStoreProvider(BaseProvider):
    """Provider for generating supermarket / hypermarket related data.

    This provider can generate:
    - Departments and aisles (localized names)
    - Products, optionally filtered by aisle and/or department
    - Prices, quantities and units
    - Single grocery items and full randomized shopping lists
    """

    def __init__(self, generator):
        super().__init__(generator)
        if hasattr(generator, "_Generator__config") and isinstance(generator._Generator__config, dict):
            self._provider_locale = generator._Generator__config.get("locale", "en_US")
        else:
            self._provider_locale = "en_US"

        data = _load_data()
        lang = self._provider_locale.split("_")[0].lower()
        self._lang = lang if lang in data["languages"] else data["meta"]["default_language"]

    @property
    def locale(self):
        """The Faker locale this provider instance was created with (e.g. 'fr_FR')."""
        return self._provider_locale

    @property
    def language(self):
        """The catalog language actually used ('en' or 'fr'), resolved from the locale."""
        return self._lang

    @property
    def _data(self):
        return _load_data()

    @property
    def departments(self):
        """dict: department_id (str) -> {language: name}."""
        return self._data["departments"]

    @property
    def aisles(self):
        """dict: aisle_id (str) -> {language: name, 'department_id': int}."""
        return self._data["aisles"]

    # -- id resolution helpers -------------------------------------------------

    def _resolve_department_id(self, department):
        """Accept a department id (int/str) or a localized name and return the int id."""
        if department is None:
            return None
        if isinstance(department, int) or (isinstance(department, str) and department.isdigit()):
            return int(department)
        needle = str(department).strip().lower()
        for dept_id, names in self.departments.items():
            for lang in self._data["languages"]:
                if names.get(lang, "").lower() == needle:
                    return int(dept_id)
        raise ValueError(f"Unknown department: {department!r}")

    def _resolve_aisle_id(self, aisle):
        """Accept an aisle id (int/str) or a localized name and return the int id."""
        if aisle is None:
            return None
        if isinstance(aisle, int) or (isinstance(aisle, str) and aisle.isdigit()):
            return int(aisle)
        needle = str(aisle).strip().lower()
        for aisle_id, names in self.aisles.items():
            for lang in self._data["languages"]:
                if names.get(lang, "").lower() == needle:
                    return int(aisle_id)
        raise ValueError(f"Unknown aisle: {aisle!r}")

    # -- departments / aisles ---------------------------------------------------

    def department(self):
        """Return a random department name in the current language."""
        dept_id = self.random_element(list(self.departments.keys()))
        return self.departments[dept_id][self._lang]

    def department_id(self):
        """Return a random department id."""
        return int(self.random_element(list(self.departments.keys())))

    def department_name(self, department_id):
        """Return the localized name of a given department id."""
        return self.departments[str(department_id)][self._lang]

    def aisle(self, department=None):
        """Return a random aisle name in the current language, optionally
        restricted to a given department (id or localized name)."""
        dept_id = self._resolve_department_id(department)
        if dept_id is None:
            aisle_id = self.random_element(list(self.aisles.keys()))
        else:
            candidates = [a for a, info in self.aisles.items() if info["department_id"] == dept_id]
            if not candidates:
                raise ValueError(f"No aisle found for department: {department!r}")
            aisle_id = self.random_element(candidates)
        return self.aisles[aisle_id][self._lang]

    def aisle_id(self, department=None):
        """Return a random aisle id, optionally restricted to a given department."""
        dept_id = self._resolve_department_id(department)
        if dept_id is None:
            return int(self.random_element(list(self.aisles.keys())))
        candidates = [int(a) for a, info in self.aisles.items() if info["department_id"] == dept_id]
        if not candidates:
            raise ValueError(f"No aisle found for department: {department!r}")
        return self.random_element(candidates)

    def aisle_name(self, aisle_id):
        """Return the localized name of a given aisle id."""
        return self.aisles[str(aisle_id)][self._lang]

    # -- products -----------------------------------------------------------

    def _pick_product_row(self, aisle=None, department=None):
        aisle_id = self._resolve_aisle_id(aisle)
        dept_id = self._resolve_department_id(department)

        if aisle_id is not None:
            rows = self._data["by_aisle"].get(aisle_id)
            if not rows:
                raise ValueError(f"No product found for aisle: {aisle!r}")
            if dept_id is not None and self.aisles[str(aisle_id)]["department_id"] != dept_id:
                raise ValueError(f"Aisle {aisle!r} does not belong to department {department!r}")
        elif dept_id is not None:
            rows = self._data["by_department"].get(dept_id)
            if not rows:
                raise ValueError(f"No product found for department: {department!r}")
        else:
            rows = self._data["products"]

        return self.random_element(rows)

    def product(self, aisle=None, department=None):
        """Return a random product name in the current language, optionally
        filtered by aisle and/or department (id or localized name)."""
        row = self._pick_product_row(aisle=aisle, department=department)
        return row[self._data["name_col"][self._lang]]

    def product_record(self, aisle=None, department=None):
        """Return a full dict describing a random product: id, localized
        product/aisle/department names and their ids, its stable catalog
        'base_price' and a 'price' jittered +/-5% around it (see `price`)."""
        row = self._pick_product_row(aisle=aisle, department=department)
        return self._row_to_record(row)

    def _row_to_record(self, row):
        product_id, aisle_id, department_id = row[0], row[1], row[2]
        base_price = row[self._data["base_price_col"]]
        return {
            "id": product_id,
            "name": row[self._data["name_col"][self._lang]],
            "aisle_id": aisle_id,
            "aisle": self.aisles[str(aisle_id)][self._lang],
            "department_id": department_id,
            "department": self.departments[str(department_id)][self._lang],
            "base_price": base_price,
            "price": self._jitter_price(base_price),
        }

    def product_name(self, product_id):
        """Return the localized name of a given product id. O(n) lookup."""
        for row in self._data["products"]:
            if row[0] == int(product_id):
                return row[self._data["name_col"][self._lang]]
        raise ValueError(f"Unknown product id: {product_id!r}")

    def _find_product_row(self, product_id):
        for row in self._data["products"]:
            if row[0] == int(product_id):
                return row
        raise ValueError(f"Unknown product id: {product_id!r}")

    # -- price / quantity / unit ---------------------------------------------

    def _jitter_price(self, base_price, variation=0.05):
        """Apply a random +/-`variation` fraction (default 5%) around a base
        price, so the same article's 'probable price' fluctuates a little
        each time it is priced, like real shelf prices do from day to day."""
        factor = 1 + self.generator.random.uniform(-variation, variation)
        return round(max(0.01, base_price * factor), 2)

    def price(self, product=None, department=None, min_price=None, max_price=None):
        """Return a price (float, 2 decimals).

        - If `product` (a product id) is given, returns that product's
          catalog base price jittered by +/-5% (its "probable price" today).
        - Elif a custom (min_price, max_price) range is given, returns a
          uniform random price in that range.
        - Otherwise returns a uniform random price within the given
          department's typical range (or a random department's range if
          none is given)."""
        if product is not None:
            row = self._find_product_row(product)
            return self._jitter_price(row[self._data["base_price_col"]])
        if min_price is None or max_price is None:
            dept_id = self._resolve_department_id(department)
            if dept_id is None:
                dept_id = int(self.random_element(list(self._data["price_ranges"].keys())))
            min_price, max_price = self._data["price_ranges"][str(dept_id)]
        return round(self.generator.random.uniform(min_price, max_price), 2)

    def quantity(self, max_quantity=10):
        """Return a random quantity for a shopping list item (1 to `max_quantity`)."""
        return self.random_int(min=1, max=max_quantity)

    def unit(self, department=None):
        """Return a random unit of measure in the current language.

        If `department` (id or localized name) is given, the unit is picked
        among the ones plausible for that department (e.g. 'kg'/'bunch' for
        produce, 'bottle'/'L' for beverages), instead of any unit at all -
        this avoids incoherent combinations like "9 bottle x Bread"."""
        dept_id = self._resolve_department_id(department)
        if dept_id is None:
            unit_key = self.random_element(list(self._data["unit_labels"].keys()))
        else:
            unit_key = self.random_element(self._data["department_units"][str(dept_id)])
        return self._data["unit_labels"][unit_key][self._lang]

    # -- grocery items / shopping lists ---------------------------------------

    @staticmethod
    def _max_quantity_for_family(family_size):
        """Bigger households tend to buy more of a given article at once."""
        return max(2, family_size + 1)

    def grocery_item(self, aisle=None, department=None, family_size=None):
        """Return a single random grocery list line item as a dict, with a
        unit price jittered +/-5% around the product's base price and a unit
        of measure plausible for the product's department (see `unit`).

        `family_size` (if given) scales up the plausible quantity range
        (bigger households buy more of a given item at once)."""
        record = self.product_record(aisle=aisle, department=department)
        max_quantity = self._max_quantity_for_family(family_size) if family_size else 10
        quantity = self.quantity(max_quantity=max_quantity)
        unit = self.unit(department=record["department_id"])
        unit_price = record["price"]
        return {
            "product": record["name"],
            "product_id": record["id"],
            "aisle": record["aisle"],
            "department": record["department"],
            "quantity": quantity,
            "unit": unit,
            "unit_price": unit_price,
            "total_price": round(quantity * unit_price, 2),
        }

    def shopping_datetime(self, date=None, open_hour=8, close_hour=20):
        """Return a random datetime plausible for a shopping trip: a random
        day (within the last year) unless `date` (a date or datetime) is
        given, combined with a random time within store opening hours."""
        if date is None:
            day = self.generator.date_between(start_date="-1y", end_date="today")
        elif isinstance(date, _datetime.datetime):
            day = date.date()
        else:
            day = date
        hour = self.random_int(min=open_hour, max=max(open_hour, close_hour - 1))
        minute = self.random_int(min=0, max=59)
        second = self.random_int(min=0, max=59)
        return _datetime.datetime.combine(day, _datetime.time(hour, minute, second))

    def grocery_list(self, min_items=None, max_items=None, family_size=2, department=None,
                      with_datetime=False, date=None):
        """Return a randomized shopping basket as a dict with 'items',
        'item_count', 'family_size' and 'total'.

        - `family_size` (default 2, a couple) scales the default item-count
          range and how much of each item is bought, when `min_items` /
          `max_items` are not given explicitly.
        - `department` optionally restricts every item to one department
          (id or localized name).
        - `with_datetime=True` (or passing `date`) adds a 'shopping_datetime'
          field: a plausible date/time for the trip (see `shopping_datetime`).
        """
        if min_items is None:
            min_items = max(3, 4 + 3 * (family_size - 1))
        if max_items is None:
            max_items = max(min_items + 3, 10 + 5 * (family_size - 1))

        item_count = self.random_int(min=min_items, max=max_items)
        items = [
            self.grocery_item(department=department, family_size=family_size)
            for _ in range(item_count)
        ]
        total = round(sum(item["total_price"] for item in items), 2)
        result = {
            "items": items,
            "item_count": item_count,
            "family_size": family_size,
            "total": total,
        }
        if with_datetime or date is not None:
            result["shopping_datetime"] = self.shopping_datetime(date=date)
        return result
