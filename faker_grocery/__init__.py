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
import itertools
import json
import os
import warnings
from typing import Any, NotRequired, TypedDict

from faker.providers import BaseProvider

__version__ = "0.5.0"

_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "grocery_data.json")
_data_cache: dict[str, Any] | None = None

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


class GroceryItem(TypedDict):
    """A shopping list line, as returned by `GroceryStoreProvider.grocery_item()`.

    `quantity` is an int for counted units (and g), a float for kg/L.
    """

    product: str
    product_id: int
    aisle: str
    department: str
    quantity: float
    unit: str
    unit_price: float
    price_per: str
    total_price: float
    currency: str


class GroceryList(TypedDict):
    """A shopping basket, as returned by `GroceryStoreProvider.grocery_list()`.

    `shopping_datetime` is only present with `with_datetime=True` or `date=`.
    """

    items: list[GroceryItem]
    item_count: int
    family_size: int
    total: float
    currency: str
    shopping_datetime: NotRequired[_datetime.datetime]


def _load_data() -> dict[str, Any]:
    global _data_cache
    if _data_cache is None:
        with open(_DATA_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        _data_cache = _build_index(raw)
    return _data_cache


def _build_index(raw: dict[str, Any]) -> dict[str, Any]:
    languages = raw["meta"]["languages"]
    # products rows are [id, aisle_id, department_id, base_price, order_count, unit, name_<lang0>, ...]
    fields = raw["meta"]["product_fields"]
    base_price_col = fields.index("base_price")
    order_count_col = fields.index("order_count")
    unit_col = fields.index("unit")
    name_col = {lang: fields.index(f"name_{lang}") for lang in languages}

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

    return {
        "meta": raw["meta"],
        "languages": languages,
        "name_col": name_col,
        "base_price_col": base_price_col,
        "unit_col": unit_col,
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
        "shopping_patterns": raw["shopping_patterns"],
        "country_shopping_patterns": raw["country_shopping_patterns"],
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
    return isinstance(value, int) or (isinstance(value, str) and value.isdigit())


class GroceryStoreProvider(BaseProvider):
    """Provider for generating supermarket / hypermarket related data.

    This provider can generate:
    - Departments and aisles (localized names)
    - Products, optionally filtered by aisle and/or department
    - Prices, quantities and units
    - Single grocery items and full randomized shopping lists
    """

    def __init__(self, generator: Any) -> None:
        super().__init__(generator)
        self._provider_locale = _generator_locale(generator)

        data = _load_data()
        lang = self._provider_locale.split("_")[0].lower()
        self._lang = lang if lang in data["languages"] else data["meta"]["default_language"]
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
        """The catalog language actually used ('en' or 'fr'), resolved from the locale."""
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

    def grocery_department(self) -> str:
        """Return a random (store) department name in the current language."""
        dept_id = self.random_element(list(self.departments.keys()))
        return self.departments[dept_id][self._lang]

    def department_id(self) -> int:
        """Return a random department id."""
        return int(self.random_element(list(self.departments.keys())))

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

    def aisle(self, department: IdOrName | None = None) -> str:
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

    def aisle_id(self, department: IdOrName | None = None) -> int:
        """Return a random aisle id, optionally restricted to a given department."""
        dept_id = self._resolve_department_id(department)
        if dept_id is None:
            return int(self.random_element(list(self.aisles.keys())))
        candidates = [int(a) for a, info in self.aisles.items() if info["department_id"] == dept_id]
        if not candidates:
            raise ValueError(f"No aisle found for department: {department!r}")
        return self.random_element(candidates)

    def aisle_name(self, aisle_id: int | str) -> str:
        """Return the localized name of a given aisle id."""
        if not _is_id(aisle_id) or str(int(aisle_id)) not in self.aisles:
            raise ValueError(f"Unknown aisle id: {aisle_id!r}")
        return self.aisles[str(int(aisle_id))][self._lang]

    # -- products -----------------------------------------------------------

    def _pick_product_row(
        self, aisle: IdOrName | None = None, department: IdOrName | None = None, weighted: bool = True
    ) -> list[Any]:
        aisle_id = self._resolve_aisle_id(aisle)
        dept_id = self._resolve_department_id(department)

        if aisle_id is not None:
            rows = self._data["by_aisle"].get(aisle_id)
            if not rows:
                raise ValueError(f"No product found for aisle: {aisle!r}")
            if dept_id is not None and self.aisles[str(aisle_id)]["department_id"] != dept_id:
                raise ValueError(f"Aisle {aisle!r} does not belong to department {department!r}")
            cum_weights = self._data["cum_weights_by_aisle"][aisle_id]
        elif dept_id is not None:
            rows = self._data["by_department"].get(dept_id)
            if not rows:
                raise ValueError(f"No product found for department: {department!r}")
            cum_weights = self._data["cum_weights_by_department"][dept_id]
        else:
            rows = self._data["products"]
            cum_weights = self._data["cum_weights"]

        # random.choice(s) rather than random_element: the latter scans the
        # whole sequence on every call, which is slow on the ~50k-row catalog.
        if weighted:
            return self.generator.random.choices(rows, cum_weights=cum_weights)[0]
        return self.generator.random.choice(rows)

    def product(
        self, aisle: IdOrName | None = None, department: IdOrName | None = None, weighted: bool = True
    ) -> str:
        """Return a random product name in the current language, optionally
        filtered by aisle and/or department (id or localized name).

        By default products are picked in proportion to how often they were
        ordered in the Instacart data (bananas and milk come up far more
        often than niche items); `weighted=False` picks uniformly."""
        row = self._pick_product_row(aisle=aisle, department=department, weighted=weighted)
        return row[self._data["name_col"][self._lang]]

    def product_record(
        self, aisle: IdOrName | None = None, department: IdOrName | None = None, weighted: bool = True
    ) -> ProductRecord:
        """Return a full dict describing a random product: id, localized
        product/aisle/department names and their ids, its stable catalog
        'base_price' and a 'price' jittered +/-5% around it (see `price`),
        its 'unit' and what the prices are for ('price_per': one article,
        or one kg/L for products sold by weight/volume). `weighted` works as
        in `product`."""
        row = self._pick_product_row(aisle=aisle, department=department, weighted=weighted)
        return self._row_to_record(row)

    def _row_to_record(self, row: list[Any]) -> ProductRecord:
        product_id, aisle_id, department_id = row[0], row[1], row[2]
        base_price = self._convert_price(row[self._data["base_price_col"]])
        unit_key = row[self._data["unit_col"]]
        return {
            "id": product_id,
            "name": row[self._data["name_col"][self._lang]],
            "aisle_id": aisle_id,
            "aisle": self.aisles[str(aisle_id)][self._lang],
            "department_id": department_id,
            "department": self.departments[str(department_id)][self._lang],
            "base_price": base_price,
            "price": self._jitter_price(base_price),
            "currency": self._currency,
            "unit": self._unit_label(unit_key),
            "price_per": self._unit_label(self._price_basis(unit_key)),
        }

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
        - Otherwise returns a uniform random price within the given
          department's typical range (or a random department's range if
          none is given)."""
        if product is not None:
            row = self._find_product_row(product)
            return self._jitter_price(self._convert_price(row[self._data["base_price_col"]]))
        if (min_price is None) != (max_price is None):
            raise ValueError("min_price and max_price must be given together")
        if min_price is not None and max_price is not None and min_price > max_price:
            raise ValueError(f"min_price ({min_price}) is greater than max_price ({max_price})")
        if min_price is None:
            dept_id = self._resolve_department_id(department)
            if dept_id is None:
                dept_id = int(self.random_element(list(self._data["price_ranges"].keys())))
            min_price, max_price = (p * self._price_factor for p in self._data["price_ranges"][str(dept_id)])
        return self._round_price(self.generator.random.uniform(min_price, max_price))

    def quantity(self, max_quantity: int = 10) -> int:
        """Return a random quantity for a shopping list item (1 to `max_quantity`)."""
        return self.random_int(min=1, max=max_quantity)

    def unit(self, department: IdOrName | None = None, aisle: IdOrName | None = None) -> str:
        """Return a random unit of measure in the current language.

        If `aisle` or `department` (id or localized name) is given, the unit
        is picked among the ones plausible for it (e.g. 'L'/'bottle' for the
        milk aisle, 'jar' for spices), instead of any unit at all. Generated
        products themselves always come with their own fixed unit (see
        `product_record`)."""
        aisle_id = self._resolve_aisle_id(aisle)
        if aisle_id is not None:
            return self._unit_label(self.random_element(self._data["aisle_units"][str(aisle_id)]))
        dept_id = self._resolve_department_id(department)
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
    ) -> GroceryItem:
        """Return a single random grocery list line item as a dict, with a
        unit price jittered +/-5% around the product's base price and a unit
        of measure plausible for the product's department (see `unit`).

        The unit is the product's own (fixed) unit. Items sold by weight or
        volume (kg, g, L) get a realistic measured quantity (e.g. 0.85 kg,
        350 g) and are priced per kg or per L ('price_per'); other items are
        counted (1, 2, 3... articles) and priced per article.

        `family_size` (if given) scales up the plausible quantity range
        (bigger households buy more of a given item at once). `weighted`
        works as in `product`."""
        row = self._pick_product_row(aisle=aisle, department=department, weighted=weighted)
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
            "aisle": record["aisle"],
            "department": record["department"],
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

    def shopping_datetime(
        self,
        date: _datetime.date | None = None,
        open_hour: int = 8,
        close_hour: int = 20,
        weighted: bool = True,
    ) -> _datetime.datetime:
        """Return a random datetime plausible for a shopping trip: a random
        day (within the last year) unless `date` (a date or datetime) is
        given, combined with a random time within store opening hours
        (`open_hour` inclusive, `close_hour` exclusive, 0 <= open < close <= 24).

        By default days and hours follow the locale's weekly shopping pattern
        (see `set_grocery_shopping_pattern`): busier days and hours come up
        more often, and days a pattern has shops closed never come up unless
        `date` forces one (its time is then uniform within opening hours).
        `weighted=False` picks days and hours uniformly."""
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
                day = rng.choices(days, weights=[sum(hour_weights[d.weekday()]) for d in days])[0]
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

    def grocery_list(
        self,
        min_items: int | None = None,
        max_items: int | None = None,
        family_size: int = 2,
        department: IdOrName | None = None,
        with_datetime: bool = False,
        date: _datetime.date | None = None,
        weighted: bool = True,
    ) -> GroceryList:
        """Return a randomized shopping basket as a dict with 'items',
        'item_count', 'family_size', 'total' and 'currency'.

        - `family_size` (default 2, a couple) scales the default item-count
          range and how much of each item is bought, when `min_items` /
          `max_items` are not given explicitly.
        - `department` optionally restricts every item to one department
          (id or localized name).
        - `with_datetime=True` (or passing `date`) adds a 'shopping_datetime'
          field: a plausible date/time for the trip (see `shopping_datetime`).
        - `weighted` (default True) picks popular products more often and
          busy shopping days/hours more often (see `product` and
          `shopping_datetime`); False makes both uniform.
        """
        _check_family_size(family_size)
        if min_items is None:
            min_items = max(3, 4 + 3 * (family_size - 1))
        if max_items is None:
            max_items = max(min_items + 3, 10 + 5 * (family_size - 1))
        if min_items < 0 or min_items > max_items:
            raise ValueError(f"Invalid item-count range: min_items={min_items!r}, max_items={max_items!r}")

        # Resolve once (and fail fast on an unknown department) rather than
        # re-resolving a department name for every item.
        dept_id = self._resolve_department_id(department)
        item_count = self.random_int(min=min_items, max=max_items)
        items = [
            self.grocery_item(department=dept_id, family_size=family_size, weighted=weighted)
            for _ in range(item_count)
        ]
        total = self._round_price(sum(item["total_price"] for item in items))
        result: GroceryList = {
            "items": items,
            "item_count": item_count,
            "family_size": family_size,
            "total": total,
            "currency": self._currency,
        }
        if with_datetime or date is not None:
            result["shopping_datetime"] = self.shopping_datetime(date=date, weighted=weighted)
        return result
