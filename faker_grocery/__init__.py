"""
Faker Grocery Store Provider

A custom Faker provider for simulating a supermarket / hypermarket catalog:
departments, aisles and products, plus helpers for prices, quantities, units,
package sizes, barcodes, single grocery items, full randomized shopping
lists, recurring customers and till receipts (VAT, promotions, payment).

The catalog data comes from the Instacart Market Basket Analysis open
dataset (21 departments, 134 aisles, ~49,700 real products). Department and
aisle names are hand-translated; product names are translated from English
(hand-checked for the 2,000 most ordered products in French, automatic
word-substitution otherwise), so most translated names are approximate rather
than grammatically perfect - this is fake/test data, not a professional
localization.

Supported languages: en, fr, it, es, pt, de.
"""
import datetime as _datetime
import gzip
import itertools
import json
import math
import os
import threading
import warnings
from typing import Any, NotRequired, TypedDict

from faker.providers import BaseProvider

__version__ = "0.11.0"

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_DATA_PATH = os.path.join(_DATA_DIR, "grocery_data.json.gz")
_data_cache: dict[str, Any] | None = None
_data_lock = threading.Lock()
_language_lock = threading.Lock()

# An id (int or numeric string) or a localized name, as accepted by the
# `department=` / `aisle=` filters.
IdOrName = int | str


class ProductRecord(TypedDict):
    """A product, as returned by `GroceryStoreProvider.product_record()`.

    Prices are floats, or ints for currencies without minor units (JPY, HUF).
    """

    id: int
    name: str
    aisle_id: int
    aisle: str
    department_id: int
    department: str
    base_price: float
    price: float
    currency: str
    unit: str
    price_per: str
    ean: str
    size: str | None
    reference_price: float | None
    reference_unit: str | None


class GroceryItem(TypedDict):
    """A shopping list line, as returned by `GroceryStoreProvider.grocery_item()`.

    `quantity` is an int for counted units (and g), a float for kg/L.
    """

    product: str
    product_id: int
    ean: str
    aisle: str
    department: str
    size: str | None
    quantity: float
    unit: str
    unit_price: float
    price_per: str
    total_price: float
    currency: str


class GroceryList(TypedDict):
    """A shopping basket, as returned by `GroceryStoreProvider.grocery_list()`.

    `shopping_datetime` is only present with `with_datetime=True` or `date=`
    (always in `customer_history()` baskets), `customer_id` only in
    `customer_history()` baskets.
    """

    items: list[GroceryItem]
    item_count: int
    family_size: int
    total: float
    currency: str
    shopping_datetime: NotRequired[_datetime.datetime]
    customer_id: NotRequired[int]


class CustomerProfile(TypedDict):
    """A recurring customer, as returned by `GroceryStoreProvider.customer_profile()`."""

    customer_id: int
    name: str
    family_size: int
    favorite_product_ids: list[int]
    shopping_interval_days: int
    reorder_rate: float


class GroceryStore(TypedDict):
    """A (fictional) store, as returned by `GroceryStoreProvider.grocery_store()`."""

    store_id: int
    name: str
    address: str


class ReceiptLine(TypedDict):
    """A receipt line: a grocery item plus its promotion and VAT rate."""

    product: str
    product_id: int
    ean: str
    quantity: float
    unit: str
    unit_price: float
    price_per: str
    total_price: float
    promotion: str | None
    discount: float
    vat_rate: float | None


class TaxLine(TypedDict):
    """VAT / sales tax for one rate: taxable base and tax amount."""

    rate: float
    base: float
    amount: float


class Receipt(TypedDict):
    """A till receipt, as returned by `GroceryStoreProvider.receipt()`.

    `total` is what the customer pays: the lines minus discounts, plus the
    tax when `taxes_included` is false (US / Canadian sales tax).
    """

    store: GroceryStore
    receipt_number: str
    register: int
    datetime: _datetime.datetime
    lines: list[ReceiptLine]
    item_count: int
    subtotal: float
    discount_total: float
    taxes: list[TaxLine]
    tax_total: float
    taxes_included: bool
    total: float
    payment_method: str
    amount_tendered: float
    change: float
    currency: str
    customer_id: NotRequired[int]


def _load_data() -> dict[str, Any]:
    global _data_cache
    if _data_cache is None:
        # Locked so two threads creating their first provider at the same
        # time share one cache (a second one would silently drop the product
        # names another thread already added to the first).
        with _data_lock:
            if _data_cache is None:
                with gzip.open(_DATA_PATH, "rt", encoding="utf-8") as f:
                    raw = json.load(f)
                _data_cache = _build_index(raw)
    return _data_cache


def _ensure_language(lang: str) -> None:
    """Load the product names of `lang` (names_<lang>.json.gz, a list parallel
    to the products) on first use, appending them as a new column to every
    product row. Languages nobody asks for are never loaded."""
    data = _load_data()
    if lang in data["name_col"]:
        return
    with _language_lock:
        if lang in data["name_col"]:
            return
        with gzip.open(os.path.join(_DATA_DIR, data["meta"]["name_files"][lang]), "rt", encoding="utf-8") as f:
            names = json.load(f)
        products = data["products"]
        if len(names) != len(products):
            raise RuntimeError(f"names_{lang}.json.gz has {len(names)} names for {len(products)} products")
        column = len(products[0]) if products else 0
        for row, name in zip(products, names, strict=True):
            row.append(name)
        data["name_col"][lang] = column


def _build_index(raw: dict[str, Any]) -> dict[str, Any]:
    languages = raw["meta"]["languages"]
    # products rows are [id, aisle_id, department_id, base_price, order_count, unit, size, season,
    # name_<lang0>, ...]
    fields = raw["meta"]["product_fields"]
    base_price_col = fields.index("base_price")
    order_count_col = fields.index("order_count")
    unit_col = fields.index("unit")
    size_col = fields.index("size")
    season_col = fields.index("season")
    reorder_count_col = fields.index("reorder_count")
    # Only the source language is in the main file; the others are added by
    # _ensure_language() on first use.
    name_col = {lang: fields.index(f"name_{lang}") for lang in languages if f"name_{lang}" in fields}

    products = raw["products"]

    by_id: dict[int, list[Any]] = {}
    by_department: dict[int, list[list[Any]]] = {}
    by_aisle: dict[int, list[list[Any]]] = {}
    for row in products:
        aisle_id, department_id = row[1], row[2]
        by_id[row[0]] = row
        by_aisle.setdefault(aisle_id, []).append(row)
        by_department.setdefault(department_id, []).append(row)

    def cum_weights(rows: list[list[Any]]) -> list[int]:
        # Popularity weight = number of times the product was ordered in the
        # Instacart data, +1 so never-ordered products can still come up.
        return list(itertools.accumulate(row[order_count_col] + 1 for row in rows))

    complements: dict[int, list[tuple[int, float]]] = {}
    for aisle_id, complement, probability in raw["aisle_complements"]:
        complements.setdefault(aisle_id, []).append((complement, probability))

    return {
        "meta": raw["meta"],
        "languages": languages,
        "name_col": name_col,
        "base_price_col": base_price_col,
        "order_count_col": order_count_col,
        "unit_col": unit_col,
        "size_col": size_col,
        "season_col": season_col,
        "reorder_count_col": reorder_count_col,
        "departments": raw["departments"],
        "aisles": raw["aisles"],
        "price_ranges": raw["price_ranges"],
        "currencies": raw["currencies"],
        "country_currencies": raw["country_currencies"],
        "country_price_levels": raw["country_price_levels"],
        "unit_labels": raw["unit_labels"],
        "aisle_units": raw["aisle_units"],
        "department_units": raw["department_units"],
        "measured_units": raw["measured_units"],
        "measured_price_ranges": raw["measured_price_ranges"],
        "aisle_unit_price_ranges": raw["aisle_unit_price_ranges"],
        "shopping_patterns": raw["shopping_patterns"],
        "country_shopping_patterns": raw["country_shopping_patterns"],
        "premium_surcharge": raw["premium_surcharge"],
        "seasonal_factors": raw["seasonal_factors"],
        "southern_hemisphere_countries": set(raw["southern_hemisphere_countries"]),
        "default_opening_hours": raw["default_opening_hours"],
        "country_opening_hours": raw["country_opening_hours"],
        "country_vat": raw["country_vat"],
        "aisle_tax_class": raw["aisle_tax_class"],
        "complements": complements,
        "basket_sizes": raw["basket_sizes"],
        "customer_intervals": raw["customer_intervals"],
        "customer_reorder_rates": raw["customer_reorder_rates"],
        "store_name_templates": raw["store_name_templates"],
        "promotion_labels": raw["promotion_labels"],
        # Total popularity of each department / aisle, for weighted picks.
        "department_weights": {str(k): sum(r[order_count_col] + 1 for r in v) for k, v in by_department.items()},
        "aisle_weights": {str(k): sum(r[order_count_col] + 1 for r in v) for k, v in by_aisle.items()},
        # Seasonal cumulative weights, computed on first use per (scope, month).
        "seasonal_cum_weights": {},
        "products": products,
        "by_id": by_id,
        "by_department": by_department,
        "by_aisle": by_aisle,
        # Cumulative popularity weights, parallel to the row lists above, for
        # O(log n) weighted picks with random.choices(cum_weights=...).
        "cum_weights": cum_weights(products),
        "cum_weights_by_department": {k: cum_weights(v) for k, v in by_department.items()},
        "cum_weights_by_aisle": {k: cum_weights(v) for k, v in by_aisle.items()},
    }


def _generator_locale(generator: Any, default: str = "en_US") -> str:
    """Best-effort lookup of the locale a Faker generator was created with.

    Faker has no public API for this: the locale lives in the name-mangled
    private `Generator.__config` dict. Kept in one place so a future Faker
    change only needs fixing here; falls back to `default` if it moves."""
    config = getattr(generator, "_Generator__config", None)
    if isinstance(config, dict) and config.get("locale"):
        return config["locale"]
    return default


def _check_family_size(family_size: object) -> None:
    if isinstance(family_size, bool) or not isinstance(family_size, int) or family_size < 1:
        raise ValueError(f"family_size must be a positive integer, got {family_size!r}")


def _is_id(value: object) -> bool:
    """True for an int id or a numeric string id (bools are rejected, even
    though `bool` is a subclass of `int`)."""
    if isinstance(value, bool):
        return False
    return isinstance(value, int) or (isinstance(value, str) and value.strip().isascii() and value.strip().isdigit())


class GroceryStoreProvider(BaseProvider):
    """Provider for generating supermarket / hypermarket related data.

    This provider can generate:
    - Departments and aisles (localized names)
    - Products, optionally filtered by aisle and/or department
    - Prices, quantities, units, package sizes and EAN-13 barcodes
    - Single grocery items and full randomized shopping lists (seasonal,
      with complementary products)
    - Recurring customers and their shopping history
    - Stores and till receipts (VAT, promotions, payment)
    """

    def __init__(self, generator: Any) -> None:
        super().__init__(generator)
        self._provider_locale = _generator_locale(generator)

        data = _load_data()
        lang = self._provider_locale.split("_")[0].lower()
        self._lang = lang if lang in data["languages"] else data["meta"]["default_language"]
        _ensure_language(self._lang)
        self._country = self._provider_locale.split("_")[-1].upper()
        self.set_grocery_currency(None)
        self.set_grocery_shopping_pattern(None)

    @property
    def locale(self) -> str:  # type: ignore[override]
        """The Faker locale this provider instance was created with (e.g. 'fr_FR').

        NB: this property shadows BaseProvider.locale(), a method returning a
        random locale string. Kept for backwards compatibility; on a Faker
        instance, `fake.locale` is Faker's own attribute either way."""
        return self._provider_locale

    @property
    def language(self) -> str:
        """The catalog language actually used ('en', 'fr', 'it', 'es', 'pt' or 'de'),
        resolved from the locale ('en' for unsupported languages)."""
        return self._lang

    @property
    def currency(self) -> str:
        """The ISO 4217 code of the currency prices are generated in (e.g. 'EUR')."""
        return self._currency

    @property
    def _data(self) -> dict[str, Any]:
        return _load_data()

    @property
    def departments(self) -> dict[str, dict[str, str]]:
        """dict: department_id (str) -> {language: name}."""
        return self._data["departments"]

    @property
    def aisles(self) -> dict[str, dict[str, Any]]:
        """dict: aisle_id (str) -> {language: name, 'department_id': int}."""
        return self._data["aisles"]

    # -- id resolution helpers -------------------------------------------------

    def _resolve_department_id(self, department: IdOrName | None) -> int | None:
        """Accept a department id (int/str) or a localized name and return the int id."""
        if department is None:
            return None
        if _is_id(department):
            if str(int(department)) not in self.departments:
                raise ValueError(f"Unknown department: {department!r}")
            return int(department)
        if not isinstance(department, str):
            raise ValueError(f"Unknown department: {department!r}")
        needle = str(department).strip().lower()
        for dept_id, names in self.departments.items():
            for lang in self._data["languages"]:
                if names.get(lang, "").lower() == needle:
                    return int(dept_id)
        raise ValueError(f"Unknown department: {department!r}")

    def _resolve_aisle_id(self, aisle: IdOrName | None) -> int | None:
        """Accept an aisle id (int/str) or a localized name and return the int id."""
        if aisle is None:
            return None
        if _is_id(aisle):
            if str(int(aisle)) not in self.aisles:
                raise ValueError(f"Unknown aisle: {aisle!r}")
            return int(aisle)
        if not isinstance(aisle, str):
            raise ValueError(f"Unknown aisle: {aisle!r}")
        needle = str(aisle).strip().lower()
        for aisle_id, names in self.aisles.items():
            for lang in self._data["languages"]:
                if names.get(lang, "").lower() == needle:
                    return int(aisle_id)
        raise ValueError(f"Unknown aisle: {aisle!r}")

    # -- departments / aisles ---------------------------------------------------

    def _pick_weighted_key(self, keys: list[str], weights: dict[str, int], weighted: bool) -> str:
        if weighted:
            return self.generator.random.choices(keys, weights=[weights.get(k, 1) for k in keys])[0]
        return self.generator.random.choice(keys)

    def grocery_department(self, weighted: bool = True) -> str:
        """Return a random (store) department name in the current language.

        Departments are picked in proportion to how much was ordered from
        them (produce and dairy far more often than bulk); `weighted=False`
        picks uniformly."""
        return self.departments[str(self.department_id(weighted=weighted))][self._lang]

    def department_id(self, weighted: bool = True) -> int:
        """Return a random department id (popularity-weighted unless `weighted=False`)."""
        keys = list(self.departments.keys())
        return int(self._pick_weighted_key(keys, self._data["department_weights"], weighted))

    def grocery_department_name(self, department_id: int | str) -> str:
        """Return the localized name of a given (store) department id."""
        if not _is_id(department_id) or str(int(department_id)) not in self.departments:
            raise ValueError(f"Unknown department id: {department_id!r}")
        return self.departments[str(int(department_id))][self._lang]

    # -- deprecated aliases -----------------------------------------------------
    #
    # department() / department_name() clash with Faker's own address
    # providers, which use them for administrative departments (fr_FR:
    # "Cher", "Sarthe"...; es_CO). Faker's add_provider() registers every
    # public callable that dir(provider) lists, so these aliases used to
    # silently replace Faker's methods. They are now hidden from dir() -
    # hence not registered - whenever another provider of the same generator
    # already defines them, and warn when called.

    _DEPRECATED_ALIASES = {"department": "grocery_department", "department_name": "grocery_department_name"}

    def __dir__(self) -> list[str]:
        return [name for name in super().__dir__() if not self._alias_would_clash(name)]

    def _alias_would_clash(self, name: str) -> bool:
        if name not in self._DEPRECATED_ALIASES:
            return False
        providers = getattr(self.generator, "providers", [])
        return any(
            not isinstance(provider, GroceryStoreProvider) and callable(getattr(provider, name, None))
            for provider in providers
        )

    def _warn_deprecated(self, name: str) -> None:
        warnings.warn(
            f"GroceryStoreProvider.{name}() is deprecated and will be removed in a future version, "
            f"use {self._DEPRECATED_ALIASES[name]}() instead (the old name clashes with Faker's "
            f"own address providers, e.g. administrative departments in fr_FR).",
            DeprecationWarning,
            stacklevel=3,
        )

    def department(self) -> str:
        """Deprecated alias of `grocery_department`."""
        self._warn_deprecated("department")
        return self.grocery_department()

    def department_name(self, department_id: int | str) -> str:
        """Deprecated alias of `grocery_department_name`."""
        self._warn_deprecated("department_name")
        return self.grocery_department_name(department_id)

    def aisle(self, department: IdOrName | None = None, weighted: bool = True) -> str:
        """Return a random aisle name in the current language, optionally
        restricted to a given department (id or localized name). Popular
        aisles come up more often unless `weighted=False`."""
        return self.aisles[str(self.aisle_id(department=department, weighted=weighted))][self._lang]

    def aisle_id(self, department: IdOrName | None = None, weighted: bool = True) -> int:
        """Return a random aisle id, optionally restricted to a given department
        (popularity-weighted unless `weighted=False`)."""
        dept_id = self._resolve_department_id(department)
        candidates = [a for a, info in self.aisles.items() if dept_id is None or info["department_id"] == dept_id]
        if not candidates:
            raise ValueError(f"No aisle found for department: {department!r}")
        return int(self._pick_weighted_key(candidates, self._data["aisle_weights"], weighted))

    def aisle_name(self, aisle_id: int | str) -> str:
        """Return the localized name of a given aisle id."""
        if not _is_id(aisle_id) or str(int(aisle_id)) not in self.aisles:
            raise ValueError(f"Unknown aisle id: {aisle_id!r}")
        return self.aisles[str(int(aisle_id))][self._lang]

    # -- products -----------------------------------------------------------

    @staticmethod
    def _check_month(month: object) -> None:
        if month is not None and (isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12):
            raise ValueError(f"month must be an integer from 1 to 12, got {month!r}")

    def _seasonal_cum_weights(self, scope: Any, rows: list[list[Any]], month: int) -> list[float]:
        """Cumulative popularity weights of `rows` for `month` (1-12): fresh
        produce in season (for the locale's hemisphere) gets a boost, out of
        season a penalty. Cached per (scope, month)."""
        data = self._data
        if self._country in data["southern_hemisphere_countries"]:
            month = (month + 5) % 12 + 1
        key = (scope, month)
        cache = data["seasonal_cum_weights"]
        if key not in cache:
            bit = 1 << (month - 1)
            order_col, season_col = data["order_count_col"], data["season_col"]
            boost, penalty = data["seasonal_factors"]["in"], data["seasonal_factors"]["out"]

            def weight(row: list[Any]) -> float:
                base = row[order_col] + 1
                mask = row[season_col]
                if not mask:
                    return base
                return base * (boost if mask & bit else penalty)

            cache[key] = list(itertools.accumulate(weight(row) for row in rows))
        return cache[key]

    def _pick_product_row(
        self,
        aisle: IdOrName | None = None,
        department: IdOrName | None = None,
        weighted: bool = True,
        month: int | None = None,
    ) -> list[Any]:
        self._check_month(month)
        aisle_id = self._resolve_aisle_id(aisle)
        dept_id = self._resolve_department_id(department)

        scope: Any
        if aisle_id is not None:
            rows = self._data["by_aisle"].get(aisle_id)
            if not rows:
                raise ValueError(f"No product found for aisle: {aisle!r}")
            if dept_id is not None and self.aisles[str(aisle_id)]["department_id"] != dept_id:
                raise ValueError(f"Aisle {aisle!r} does not belong to department {department!r}")
            cum_weights = self._data["cum_weights_by_aisle"][aisle_id]
            scope = ("aisle", aisle_id)
        elif dept_id is not None:
            rows = self._data["by_department"].get(dept_id)
            if not rows:
                raise ValueError(f"No product found for department: {department!r}")
            cum_weights = self._data["cum_weights_by_department"][dept_id]
            scope = ("department", dept_id)
        else:
            rows = self._data["products"]
            cum_weights = self._data["cum_weights"]
            scope = "all"

        # random.choice(s) rather than random_element: the latter scans the
        # whole sequence on every call, which is slow on the ~50k-row catalog.
        if weighted:
            if month is not None:
                cum_weights = self._seasonal_cum_weights(scope, rows, month)
            return self.generator.random.choices(rows, cum_weights=cum_weights)[0]
        return self.generator.random.choice(rows)

    def product(
        self,
        aisle: IdOrName | None = None,
        department: IdOrName | None = None,
        weighted: bool = True,
        month: int | None = None,
    ) -> str:
        """Return a random product name in the current language, optionally
        filtered by aisle and/or department (id or localized name).

        By default products are picked in proportion to how often they were
        ordered in the Instacart data (bananas and milk come up far more
        often than niche items); `weighted=False` picks uniformly. With a
        `month` (1-12), fresh fruits and vegetables in season come up more
        often and out-of-season ones less (strawberries in June, clementines
        in December; shifted by six months in the southern hemisphere)."""
        row = self._pick_product_row(aisle=aisle, department=department, weighted=weighted, month=month)
        return row[self._data["name_col"][self._lang]]

    def product_record(
        self,
        aisle: IdOrName | None = None,
        department: IdOrName | None = None,
        weighted: bool = True,
        month: int | None = None,
    ) -> ProductRecord:
        """Return a full dict describing a random product: id, EAN-13
        barcode, localized product/aisle/department names and their ids, its
        stable catalog 'base_price' and a 'price' jittered +/-5% around it
        (see `price`), its 'unit' and what the prices are for ('price_per':
        one article, or one kg/L for products sold by weight/volume), its
        package 'size' ('500 g', '6 x 330 mL', or None) and the price per kg
        or L ('reference_price' / 'reference_unit', None when the size is a
        count or unknown). `weighted` and `month` work as in `product`."""
        row = self._pick_product_row(aisle=aisle, department=department, weighted=weighted, month=month)
        return self._row_to_record(row)

    def _row_to_record(self, row: list[Any]) -> ProductRecord:
        product_id, aisle_id, department_id = row[0], row[1], row[2]
        base_price = self._convert_price(row[self._data["base_price_col"]])
        unit_key = row[self._data["unit_col"]]
        price = self._jitter_price(base_price)
        size = row[self._data["size_col"]]
        reference_price, reference_unit = self._reference_price(price, unit_key, size)
        return {
            "id": product_id,
            "name": row[self._data["name_col"][self._lang]],
            "aisle_id": aisle_id,
            "aisle": self.aisles[str(aisle_id)][self._lang],
            "department_id": department_id,
            "department": self.departments[str(department_id)][self._lang],
            "base_price": base_price,
            "price": price,
            "currency": self._currency,
            "unit": self._unit_label(unit_key),
            "price_per": self._unit_label(self._price_basis(unit_key)),
            "ean": self._ean13(product_id),
            "size": self._size_label(size),
            "reference_price": reference_price,
            "reference_unit": reference_unit,
        }

    # -- package sizes / barcodes ---------------------------------------------

    def _format_amount(self, value: float) -> str:
        text = f"{value:.2f}".rstrip("0").rstrip(".")
        return text if self._lang == "en" else text.replace(".", ",")

    def _size_label(self, size: list[Any] | None) -> str | None:
        """'500 g', '1,5 L', '6 x 330 mL', '12 pièce(s)'... or None."""
        if size is None:
            return None
        count, amount, unit = size
        if amount is None:
            return f"{count} {self._unit_label('piece')}"
        if amount >= 1000:
            label = f"{self._format_amount(amount / 1000)} {self._unit_label('kg' if unit == 'g' else 'l')}"
        else:
            label = f"{self._format_amount(amount)} {self._unit_label(unit)}"
        return f"{count} x {label}" if count > 1 else label

    def _reference_price(self, price: float, unit_key: str, size: list[Any] | None) -> tuple[float | None, str | None]:
        """Price per kg or per L (the 'prix au kilo' shelf labels show)."""
        measure = self._data["measured_units"].get(unit_key)
        if measure is not None:
            return price, self._unit_label(measure["price_per"])
        if size is None or size[1] is None:
            return None, None
        count, amount, unit = size
        total = count * amount / 1000
        return self._round_price(price / total), self._unit_label("kg" if unit == "g" else "l")

    @staticmethod
    def _ean13(product_id: int) -> str:
        """A stable, valid EAN-13 for a product: GS1 prefix 20 ("restricted
        circulation", i.e. in-store numbering, so it can't clash with a real
        product's barcode), the zero-padded product id, and the check digit."""
        body = f"20{int(product_id):010d}"
        total = sum(int(digit) * (3 if index % 2 else 1) for index, digit in enumerate(body))
        return body + str((10 - total % 10) % 10)

    def product_ean(self, product_id: int | str) -> str:
        """Return the (stable) EAN-13 barcode of a given product id."""
        return self._ean13(self._find_product_row(product_id)[0])

    def product_name(self, product_id: int | str) -> str:
        """Return the localized name of a given product id."""
        row = self._find_product_row(product_id)
        return row[self._data["name_col"][self._lang]]

    def _find_product_row(self, product_id: int | str) -> list[Any]:
        row = self._data["by_id"].get(int(product_id)) if _is_id(product_id) else None
        if row is None:
            raise ValueError(f"Unknown product id: {product_id!r}")
        return row

    # -- currency -------------------------------------------------------------

    def set_grocery_currency(self, currency: str | None = None) -> None:
        """Set the currency prices are generated in (an ISO 4217 code such as
        'USD'), or reset it to the locale's default with `None`.

        By default the currency follows the country of the Faker locale
        ('en_US' -> USD, 'en_GB' -> GBP, 'fr_CA' -> CAD...), falling back to
        EUR, the catalog's base currency. Prices are converted from EUR with
        fixed approximate rates (not live exchange rates), then adjusted to
        the approximate grocery price level of the locale's country when the
        currency is that country's own (e.g. Portugal cheaper than Ireland,
        both in EUR), or else of the currency's main country (e.g. CHF prices
        are higher than a plain conversion would give)."""
        data = self._data
        local_currency = data["country_currencies"].get(self._country, data["meta"]["base_currency"])
        code = local_currency if currency is None else str(currency).upper()
        if code not in data["currencies"]:
            raise ValueError(f"Unsupported currency: {currency!r} (supported: {sorted(data['currencies'])})")
        currency_info = data["currencies"][code]
        price_level = currency_info["price_level"]
        if code == local_currency:
            price_level = data["country_price_levels"].get(self._country, price_level)
        self._currency = code
        self._price_factor = currency_info["rate"] * price_level
        self._decimals = currency_info["decimals"]

    def grocery_currency(self, symbol: bool = False) -> str:
        """Return the currency prices are generated in: its ISO 4217 code
        (e.g. 'EUR'), or its symbol (e.g. '€') if `symbol` is true.

        Not named `currency_code` so as not to shadow Faker's own
        `currency_code()` (a random currency, unrelated to this provider)."""
        if symbol:
            return self._data["currencies"][self._currency]["symbol"]
        return self._currency

    def _round_price(self, amount: float) -> float:
        return round(amount, self._decimals) if self._decimals else int(round(amount))

    def _convert_price(self, eur_amount: float) -> float:
        """Convert a catalog (EUR) amount to the current currency and its
        country's price level."""
        return self._round_price(eur_amount * self._price_factor)

    # -- price / quantity / unit ---------------------------------------------

    def _jitter_price(self, base_price: float, variation: float = 0.05) -> float:
        """Apply a random +/-`variation` fraction (default 5%) around a base
        price, so the same article's 'probable price' fluctuates a little
        each time it is priced, like real shelf prices do from day to day."""
        factor = 1 + self.generator.random.uniform(-variation, variation)
        smallest = 10 ** -self._decimals
        return self._round_price(max(smallest, base_price * factor))

    def price(
        self,
        product: int | str | None = None,
        department: IdOrName | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
    ) -> float:
        """Return a price in the current currency (see `grocery_currency`),
        rounded to its minor unit (2 decimals, or a whole number for e.g. JPY).

        - If `product` (a product id) is given, returns that product's
          catalog base price jittered by +/-5% (its "probable price" today).
        - Elif a custom (min_price, max_price) range is given, returns a
          uniform random price in that range (both bounds are required, and
          taken as already in the current currency).
        - Otherwise returns a random price within the given department's
          typical range (or a random department's range if none is given),
          skewed towards the cheaper end like catalog prices (most grocery
          items are inexpensive, a few are premium)."""
        if product is not None:
            row = self._find_product_row(product)
            return self._jitter_price(self._convert_price(row[self._data["base_price_col"]]))
        if (min_price is None) != (max_price is None):
            raise ValueError("min_price and max_price must be given together")
        if min_price is not None and max_price is not None:
            if min_price < 0:
                raise ValueError(f"min_price must not be negative, got {min_price!r}")
            if min_price > max_price:
                raise ValueError(f"min_price ({min_price}) is greater than max_price ({max_price})")
        if min_price is None:
            dept_id = self._resolve_department_id(department)
            if dept_id is None:
                dept_id = int(self.random_element(list(self._data["price_ranges"].keys())))
            low, high = (p * self._price_factor for p in self._data["price_ranges"][str(dept_id)])
            mode = low + (high - low) * 0.35
            return self._round_price(self.generator.random.triangular(low, high, mode))
        return self._round_price(self.generator.random.uniform(min_price, max_price))

    def quantity(self, max_quantity: int = 10) -> int:
        """Return a random quantity for a shopping list item (1 to `max_quantity`)."""
        if isinstance(max_quantity, bool) or not isinstance(max_quantity, int) or max_quantity < 1:
            raise ValueError(f"max_quantity must be a positive integer, got {max_quantity!r}")
        return self.random_int(min=1, max=max_quantity)

    def unit(self, department: IdOrName | None = None, aisle: IdOrName | None = None) -> str:
        """Return a random unit of measure in the current language.

        If `aisle` or `department` (id or localized name) is given, the unit
        is picked among the ones plausible for it (e.g. 'L'/'bottle' for the
        milk aisle, 'jar' for spices), instead of any unit at all. Generated
        products themselves always come with their own fixed unit (see
        `product_record`). If both are given, the aisle must belong to the
        department."""
        aisle_id = self._resolve_aisle_id(aisle)
        dept_id = self._resolve_department_id(department)
        if aisle_id is not None:
            if dept_id is not None and self.aisles[str(aisle_id)]["department_id"] != dept_id:
                raise ValueError(f"Aisle {aisle!r} does not belong to department {department!r}")
            return self._unit_label(self.random_element(self._data["aisle_units"][str(aisle_id)]))
        if dept_id is not None:
            return self._unit_label(self.random_element(self._data["department_units"][str(dept_id)]))
        return self._unit_label(self.random_element(list(self._data["unit_labels"].keys())))

    def _unit_label(self, unit_key: str) -> str:
        return self._data["unit_labels"][unit_key][self._lang]

    def _price_basis(self, unit_key: str) -> str:
        """The unit a price applies to: kg/L for measured units, else the unit itself."""
        measure = self._data["measured_units"].get(unit_key)
        return measure["price_per"] if measure else unit_key

    # -- grocery items / shopping lists ---------------------------------------

    @staticmethod
    def _max_quantity_for_family(family_size: int) -> int:
        """Bigger households tend to buy more of a given article at once."""
        _check_family_size(family_size)
        return max(2, family_size + 1)

    def _measured_quantity(self, spec: dict[str, Any], family_size: int | None) -> float:
        """A quantity for a unit sold by weight/volume (e.g. 0.85 kg, 350 g,
        1.5 L): a multiple of spec['step'] in [min, base + per_person * family
        size]. Without a family size, assumes a 3-person household."""
        if family_size is not None:
            _check_family_size(family_size)
        people = family_size if family_size is not None else 3
        maximum = spec["base"] + spec["per_person"] * people
        steps = int(round((maximum - spec["min"]) / spec["step"]))
        quantity = round(spec["min"] + spec["step"] * self.random_int(min=0, max=steps), 3)
        return int(quantity) if isinstance(spec["step"], int) else quantity

    def grocery_item(
        self,
        aisle: IdOrName | None = None,
        department: IdOrName | None = None,
        family_size: int | None = None,
        weighted: bool = True,
        month: int | None = None,
    ) -> GroceryItem:
        """Return a single random grocery list line item as a dict, with a
        unit price jittered +/-5% around the product's base price.

        The unit is the product's own (fixed) unit (see `product_record`). Items sold by weight or
        volume (kg, g, L) get a realistic measured quantity (e.g. 0.85 kg,
        350 g) and are priced per kg or per L ('price_per'); other items are
        counted (1, 2, 3... articles) and priced per article.

        `family_size` (if given) scales up the plausible quantity range
        (bigger households buy more of a given item at once). `weighted`
        and `month` work as in `product`."""
        row = self._pick_product_row(aisle=aisle, department=department, weighted=weighted, month=month)
        return self._item_from_row(row, family_size)

    def _item_from_row(self, row: list[Any], family_size: int | None) -> GroceryItem:
        record = self._row_to_record(row)
        measure = self._data["measured_units"].get(row[self._data["unit_col"]])
        quantity: float
        if measure is None:
            max_quantity = self._max_quantity_for_family(family_size) if family_size is not None else 10
            quantity = self.quantity(max_quantity=max_quantity)
            billed_quantity = quantity
        else:
            quantity = self._measured_quantity(measure, family_size)
            # Rounded so e.g. 450 g -> 0.45 kg exactly, not 0.45000000000000001
            # (which could tip a half-cent total the other way).
            billed_quantity = round(quantity * measure["factor"], 6)
        unit_price = record["price"]
        return {
            "product": record["name"],
            "product_id": record["id"],
            "ean": record["ean"],
            "aisle": record["aisle"],
            "department": record["department"],
            "size": record["size"],
            "quantity": quantity,
            "unit": record["unit"],
            "unit_price": unit_price,
            "price_per": record["price_per"],
            "total_price": self._round_price(billed_quantity * unit_price),
            "currency": self._currency,
        }

    def set_grocery_shopping_pattern(self, pattern: str | None = None) -> None:
        """Set the weekly shopping-time pattern used by `shopping_datetime`,
        or reset it to the locale's default with `None`.

        Patterns: 'instacart_us' (measured on ~3.4M US online orders; the
        default for most locales), 'sunday_morning' (shops open on Sunday
        morning only: fr_FR, fr_BE, es_ES, it_IT...) and 'sunday_closed'
        (de_DE, de_AT, de_CH, pl_PL...)."""
        data = self._data
        if pattern is None:
            pattern = data["country_shopping_patterns"].get(self._country, data["meta"]["default_shopping_pattern"])
        if pattern not in data["shopping_patterns"]:
            raise ValueError(f"Unknown shopping pattern: {pattern!r} (known: {sorted(data['shopping_patterns'])})")
        self._shopping_pattern = pattern

    def grocery_shopping_pattern(self) -> str:
        """Return the name of the weekly shopping-time pattern in use."""
        return self._shopping_pattern

    def grocery_opening_hours(self) -> tuple[int, int]:
        """Return the typical (opening, closing) hours of a supermarket in
        the locale's country, e.g. (8, 21) for France, (7, 23) for the US,
        (8, 20) by default. Used by `shopping_datetime` when no hours are given."""
        data = self._data
        hours = data["country_opening_hours"].get(self._country, data["default_opening_hours"])
        return hours[0], hours[1]

    def shopping_datetime(
        self,
        date: _datetime.date | None = None,
        open_hour: int | None = None,
        close_hour: int | None = None,
        weighted: bool = True,
    ) -> _datetime.datetime:
        """Return a random datetime plausible for a shopping trip: a random
        day (within the last year) unless `date` (a date or datetime) is
        given, combined with a random time within store opening hours
        (`open_hour` inclusive, `close_hour` exclusive, 0 <= open < close <= 24;
        by default the country's, see `grocery_opening_hours`).

        By default days and hours follow the locale's weekly shopping pattern
        (see `set_grocery_shopping_pattern`): busier days and hours come up
        more often, and days a pattern has shops closed never come up unless
        `date` forces one (its time is then uniform within opening hours).
        `weighted=False` picks days and hours uniformly."""
        default_open, default_close = self.grocery_opening_hours()
        open_hour = default_open if open_hour is None else open_hour
        close_hour = default_close if close_hour is None else close_hour
        if not 0 <= open_hour < close_hour <= 24:
            raise ValueError(
                f"Invalid opening hours: open_hour={open_hour!r}, close_hour={close_hour!r} "
                "(expected 0 <= open_hour < close_hour <= 24)"
            )
        rng = self.generator.random
        # pattern[weekday][hour], restricted to opening hours.
        pattern = self._data["shopping_patterns"][self._shopping_pattern]
        hour_weights = [hours[open_hour:close_hour] for hours in pattern]
        if date is None:
            if weighted:
                today = _datetime.date.today()
                days = [today - _datetime.timedelta(days=n) for n in range(366)]
                day_weights = [sum(hour_weights[d.weekday()]) for d in days]
                # Opening hours the pattern never sees anyone shopping in
                # (e.g. 22-24 in a European pattern): no day is likelier than
                # another, pick uniformly rather than fail.
                day = rng.choices(days, weights=day_weights)[0] if sum(day_weights) else rng.choice(days)
            else:
                day = self.generator.date_between(start_date="-1y", end_date="today")
        elif isinstance(date, _datetime.datetime):
            day = date.date()
        else:
            day = date
        if weighted and sum(hour_weights[day.weekday()]):
            hour = rng.choices(range(open_hour, close_hour), weights=hour_weights[day.weekday()])[0]
        else:
            hour = self.random_int(min=open_hour, max=close_hour - 1)
        minute = self.random_int(min=0, max=59)
        second = self.random_int(min=0, max=59)
        return _datetime.datetime.combine(day, _datetime.time(hour, minute, second))

    def _item_count(self, family_size: int, min_items: int | None, max_items: int | None) -> int:
        """Number of items in a basket. With both bounds given: uniform in
        [min_items, max_items]. Otherwise drawn from the distribution of
        Instacart basket sizes (many small baskets, a few very big ones;
        ~10 items on average), scaled by household size (x0.8 for one
        person, x1 for a couple, +20% per extra person), then clamped to
        the bound given, if any."""
        for name, bound in (("min_items", min_items), ("max_items", max_items)):
            if bound is not None and (isinstance(bound, bool) or not isinstance(bound, int) or bound < 0):
                raise ValueError(f"{name} must be a non-negative integer, got {bound!r}")
        if min_items is not None and max_items is not None:
            if min_items > max_items:
                raise ValueError(f"Invalid item-count range: min_items={min_items!r}, max_items={max_items!r}")
            return self.random_int(min=min_items, max=max_items)
        sizes = self._data["basket_sizes"]
        drawn = self.generator.random.choices([s for s, _ in sizes], weights=[w for _, w in sizes])[0]
        count = max(1, round(drawn * (0.6 + 0.2 * family_size)))
        if min_items is not None:
            count = max(count, min_items)
        if max_items is not None:
            count = min(count, max_items)
        return count

    def _basket_items(
        self,
        item_count: int,
        family_size: int,
        dept_id: int | None,
        weighted: bool,
        month: int | None,
        coherent: bool,
        favorites: list[list[Any]] | None = None,
        reorder_rate: float = 0.0,
    ) -> list[GroceryItem]:
        """`item_count` items; with `coherent`, an item may pull in one from a
        complementary aisle (pasta -> pasta sauce); with `favorites`, each
        item is a re-order of one of them with probability `reorder_rate`."""
        rng = self.generator.random
        complements = self._data["complements"]
        favorite_weights = (
            list(itertools.accumulate(row[self._data["order_count_col"]] + 1 for row in favorites))
            if favorites else None
        )
        items: list[GroceryItem] = []
        while len(items) < item_count:
            if favorites and rng.random() < reorder_rate:
                row = rng.choices(favorites, cum_weights=favorite_weights)[0]
            else:
                row = self._pick_product_row(department=dept_id, weighted=weighted, month=month)
            items.append(self._item_from_row(row, family_size))
            if not coherent:
                continue
            for complement, probability in complements.get(row[1], []):
                if len(items) >= item_count:
                    break
                if dept_id is not None and self.aisles[str(complement)]["department_id"] != dept_id:
                    continue
                if rng.random() < probability:
                    extra = self._pick_product_row(aisle=complement, weighted=weighted, month=month)
                    items.append(self._item_from_row(extra, family_size))
        return items

    def grocery_list(
        self,
        min_items: int | None = None,
        max_items: int | None = None,
        family_size: int = 2,
        department: IdOrName | None = None,
        with_datetime: bool = False,
        date: _datetime.date | None = None,
        weighted: bool = True,
        coherent: bool = True,
    ) -> GroceryList:
        """Return a randomized shopping basket as a dict with 'items',
        'item_count', 'family_size', 'total' and 'currency'.

        - The number of items follows the distribution of real (Instacart)
          basket sizes, scaled by `family_size` (default 2, a couple), which
          also scales how much of each item is bought. `min_items` /
          `max_items` clamp it; with both, the count is uniform between them.
        - `department` optionally restricts every item to one department
          (id or localized name).
        - `with_datetime=True` (or passing `date`) adds a 'shopping_datetime'
          field: a plausible date/time for the trip (see `shopping_datetime`),
          and makes fresh produce follow the season of that date.
        - `weighted` (default True) picks popular products more often and
          busy shopping days/hours more often (see `product` and
          `shopping_datetime`); False makes both uniform.
        - `coherent` (default True) adds complementary products now and then
          (pasta and pasta sauce, cereal and milk, chips and dip...), within
          the item count.
        """
        _check_family_size(family_size)
        item_count = self._item_count(family_size, min_items, max_items)

        # Resolve once (and fail fast on an unknown department) rather than
        # re-resolving a department name for every item.
        dept_id = self._resolve_department_id(department)
        shopping_dt = (
            self.shopping_datetime(date=date, weighted=weighted) if with_datetime or date is not None else None
        )
        month = shopping_dt.month if shopping_dt is not None else None
        items = self._basket_items(item_count, family_size, dept_id, weighted, month, coherent)
        result: GroceryList = {
            "items": items,
            "item_count": item_count,
            "family_size": family_size,
            "total": self._round_price(sum(item["total_price"] for item in items)),
            "currency": self._currency,
        }
        if shopping_dt is not None:
            result["shopping_datetime"] = shopping_dt
        return result

    # -- customers --------------------------------------------------------------

    def customer_profile(self, family_size: int | None = None) -> CustomerProfile:
        """Return a recurring customer: id, name, household size, favorite
        products, how often they shop (in days) and the share of their
        basket that is re-orders of their favorites.

        Measured on the Instacart customers: the shopping interval follows
        the distribution of customers' median days between orders (weekly
        and monthly most common), the re-order share the distribution of
        their re-ordered items (~45% on average), and favorites are picked
        in proportion to how often products are re-ordered (milk, bananas
        and eggs rather than one-off purchases)."""
        rng = self.generator.random
        if family_size is None:
            family_size = rng.choices([1, 2, 3, 4, 5], weights=[30, 35, 15, 15, 5])[0]
        _check_family_size(family_size)
        data = self._data
        if "reorder_cum_weights" not in data:
            data["reorder_cum_weights"] = list(
                itertools.accumulate(row[data["reorder_count_col"]] + 1 for row in data["products"])
            )
        favorites: list[int] = []
        target = 8 + 4 * family_size
        for _ in range(target * 10):
            product_id = rng.choices(data["products"], cum_weights=data["reorder_cum_weights"])[0][0]
            if product_id not in favorites:
                favorites.append(product_id)
            if len(favorites) == target:
                break
        intervals, reorder_rates = data["customer_intervals"], data["customer_reorder_rates"]
        interval = rng.choices([d for d, _ in intervals], weights=[w for _, w in intervals])[0]
        reorder_pct = rng.choices([p for p, _ in reorder_rates], weights=[w for _, w in reorder_rates])[0]
        reorder_rate = min(1.0, max(0.0, reorder_pct / 100 + rng.uniform(-0.025, 0.025)))
        return {
            "customer_id": self.random_int(min=100000, max=999999),
            "name": self.generator.name(),
            "family_size": family_size,
            "favorite_product_ids": favorites,
            "shopping_interval_days": max(1, interval),
            "reorder_rate": round(reorder_rate, 2),
        }

    def customer_history(
        self,
        customer: CustomerProfile | None = None,
        trips: int = 10,
        end_date: _datetime.date | None = None,
        weighted: bool = True,
        coherent: bool = True,
    ) -> list[GroceryList]:
        """Return `trips` shopping baskets of one customer (a new
        `customer_profile()` unless given), oldest first, spaced by their
        shopping interval (give or take a third) and ending on `end_date`
        (default: today). Each basket re-orders the customer's favorite
        products with probability `reorder_rate` per item, and carries
        'shopping_datetime' and 'customer_id'."""
        if isinstance(trips, bool) or not isinstance(trips, int) or trips < 1:
            raise ValueError(f"trips must be a positive integer, got {trips!r}")
        if customer is None:
            customer = self.customer_profile()
        if isinstance(end_date, _datetime.datetime):
            end_date = end_date.date()
        day = end_date if end_date is not None else _datetime.date.today()
        interval = customer["shopping_interval_days"]
        days = []
        for _ in range(trips):
            days.append(day)
            jitter = self.random_int(min=-(interval // 3), max=interval // 3)
            day -= _datetime.timedelta(days=max(1, interval + jitter))
        favorites = [self._find_product_row(product_id) for product_id in customer["favorite_product_ids"]]
        family_size = customer["family_size"]
        baskets: list[GroceryList] = []
        for day in reversed(days):
            shopping_dt = self.shopping_datetime(date=day, weighted=weighted)
            item_count = self._item_count(family_size, None, None)
            items = self._basket_items(
                item_count, family_size, None, weighted, shopping_dt.month, coherent,
                favorites=favorites, reorder_rate=customer["reorder_rate"],
            )
            baskets.append({
                "items": items,
                "item_count": item_count,
                "family_size": family_size,
                "total": self._round_price(sum(item["total_price"] for item in items)),
                "currency": self._currency,
                "shopping_datetime": shopping_dt,
                "customer_id": customer["customer_id"],
            })
        return baskets

    # -- stores / receipts ------------------------------------------------------

    def grocery_store(self) -> GroceryStore:
        """Return a fictional store: id, name in the locale's language
        ("Supermarché de Lyon", "Miller's Grocery"...) and address."""
        template = self.generator.random.choice(self._data["store_name_templates"][self._lang])
        city = self.generator.city() if hasattr(self.generator, "city") else self.generator.last_name()
        name = template.format(city=city, last_name=self.generator.last_name())
        address = self.generator.address().replace("\n", ", ") if hasattr(self.generator, "address") else city
        return {"store_id": self.random_int(min=1, max=9999), "name": name, "address": address}

    def _promotion(self, item: GroceryItem, counted: bool, rate: float) -> tuple[str | None, float]:
        """A random promotion for a receipt line (with probability `rate`):
        a percentage off, 3-for-2 or 2nd at half price for counted items
        bought in sufficient numbers. Returns (label, discount)."""
        rng = self.generator.random
        if rate <= 0 or rng.random() >= rate:
            return None, self._round_price(0.0)
        quantity = int(item["quantity"]) if counted else 0
        kinds = ["percent"] + (["buy2get1"] if quantity >= 3 else []) + (["second_half"] if quantity >= 2 else [])
        kind = rng.choice(kinds)
        labels = self._data["promotion_labels"][kind]
        if kind == "percent":
            pct = rng.choice([10, 20, 25, 30, 50])
            return labels[self._lang].format(pct=pct), self._round_price(item["total_price"] * pct / 100)
        if kind == "buy2get1":
            return labels[self._lang], self._round_price(item["unit_price"] * (quantity // 3))
        return labels[self._lang], self._round_price(item["unit_price"] * 0.5 * (quantity // 2))

    def _cash_tendered(self, total: float) -> float:
        """What a customer paying cash hands over: the next banknote, or the
        next round amount, at or above `total`."""
        rate = self._data["currencies"][self._currency]["rate"]
        scale = 10 ** max(0, math.floor(math.log10(rate)))
        notes = [n * scale for n in (5, 10, 20, 50, 100, 200, 500)]
        candidates = [next((n for n in notes if n >= total), math.ceil(total / (100 * scale)) * 100 * scale)]
        candidates.append(math.ceil(total / scale) * scale)
        return self._round_price(float(self.generator.random.choice(candidates)))

    def receipt(
        self,
        basket: GroceryList | None = None,
        promotion_rate: float = 0.15,
        payment_method: str | None = None,
    ) -> Receipt:
        """Return a till receipt for `basket` (a `grocery_list()` /
        `customer_history()` basket; a new `grocery_list(with_datetime=True)`
        if not given): store, receipt number, register, date/time, lines
        with promotions (each line has a `promotion_rate` chance of one),
        VAT per rate, total, payment method ('card', 'cash' or 'mobile';
        random unless given) and change.

        VAT uses approximate rates of the locale's country: a reduced rate
        for food, the standard rate for alcohol, household, personal care,
        pet and baby care products. Prices include it, except in the US and
        Canada where a sales tax is added at the till. Countries without
        known rates get no tax breakdown (`taxes` empty, `vat_rate` None)."""
        if not 0 <= promotion_rate <= 1:
            raise ValueError(f"promotion_rate must be between 0 and 1, got {promotion_rate!r}")
        if payment_method not in (None, "card", "cash", "mobile"):
            raise ValueError(f"Unknown payment method: {payment_method!r} (expected 'card', 'cash' or 'mobile')")
        rng = self.generator.random
        if basket is None:
            basket = self.grocery_list(with_datetime=True)
        when = basket.get("shopping_datetime") or self.shopping_datetime()
        data = self._data
        vat = data["country_vat"].get(self._country)

        lines: list[ReceiptLine] = []
        groups: dict[float, float] = {}
        for item in basket["items"]:
            row = self._find_product_row(item["product_id"])
            counted = row[data["unit_col"]] not in data["measured_units"]
            promotion, discount = self._promotion(item, counted, promotion_rate)
            rate = None
            if vat is not None:
                rate = vat[1] if data["aisle_tax_class"][str(row[1])] == "standard" else vat[0]
                groups[rate] = groups.get(rate, 0) + item["total_price"] - discount
            lines.append({
                "product": item["product"],
                "product_id": item["product_id"],
                "ean": item["ean"],
                "quantity": item["quantity"],
                "unit": item["unit"],
                "unit_price": item["unit_price"],
                "price_per": item["price_per"],
                "total_price": item["total_price"],
                "promotion": promotion,
                "discount": discount,
                "vat_rate": rate,
            })

        subtotal = self._round_price(sum(line["total_price"] for line in lines))
        discount_total = self._round_price(sum(line["discount"] for line in lines))
        net = self._round_price(subtotal - discount_total)
        included = vat[2] if vat is not None else True
        taxes: list[TaxLine] = []
        for rate, gross in sorted(groups.items()):
            gross = self._round_price(gross)
            if included:
                base = self._round_price(gross / (1 + rate))
                taxes.append({"rate": rate, "base": base, "amount": self._round_price(gross - base)})
            else:
                taxes.append({"rate": rate, "base": gross, "amount": self._round_price(gross * rate)})
        tax_total = self._round_price(sum(tax["amount"] for tax in taxes))
        total = net if included else self._round_price(net + tax_total)

        method = payment_method or rng.choices(["card", "cash", "mobile"], weights=[55, 25, 20])[0]
        tendered = self._cash_tendered(total) if method == "cash" else total
        store = self.grocery_store()
        register = self.random_int(min=1, max=20)
        result: Receipt = {
            "store": store,
            "receipt_number": f"{store['store_id']:04d}-{register:02d}-{self.random_int(min=0, max=999999):06d}",
            "register": register,
            "datetime": when,
            "lines": lines,
            "item_count": len(lines),
            "subtotal": subtotal,
            "discount_total": discount_total,
            "taxes": taxes,
            "tax_total": tax_total,
            "taxes_included": included,
            "total": total,
            "payment_method": method,
            "amount_tendered": tendered,
            "change": self._round_price(tendered - total),
            "currency": self._currency,
        }
        if "customer_id" in basket:
            result["customer_id"] = basket["customer_id"]
        return result
