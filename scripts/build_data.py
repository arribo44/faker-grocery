#!/usr/bin/env python3
"""
Build faker_grocery/data/grocery_data.json from the raw CSV dataset in DATAS/
(aisles.csv, departments.csv, products.csv - Instacart Market Basket Analysis
open dataset) plus the hand-curated translation files in scripts/translations/.

Re-run this script whenever DATAS/ changes, or when adding a new locale:
add scripts/translations/word_dict_<lang>.json (+ departments_<lang>.json and
aisles_<lang>.json) and add <lang> to LANGUAGES below.
"""
import csv
import json
import os
import random
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATAS_DIR = os.path.join(ROOT, "DATAS")
TRANSLATIONS_DIR = os.path.join(ROOT, "scripts", "translations")
OUTPUT_PATH = os.path.join(ROOT, "faker_grocery", "data", "grocery_data.json")

# Source language of the raw dataset.
SOURCE_LANG = "en"

# Additional languages to generate via word-substitution translation.
# Each needs scripts/translations/word_dict_<lang>.json,
# departments_<lang>.json and aisles_<lang>.json.
TRANSLATED_LANGUAGES = ["fr"]

# Locales planned for future extension (not yet built).
PLANNED_LANGUAGES = ["it", "es", "pt", "de"]

TOKEN_RE = re.compile(r"[A-Za-z']+|[^A-Za-z']+")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def translate_name(name, word_dict):
    """Word-by-word substitution translation, preserving punctuation/spacing
    and the original capitalization style of each translated word. Words
    absent from the dictionary (brand names, units, acronyms...) are kept
    unchanged - this is a deliberately approximate 'faker-grade' translation,
    not a linguistically accurate one."""
    parts = TOKEN_RE.findall(name)
    out = []
    for part in parts:
        lower = part.lower()
        translation = word_dict.get(lower)
        if translation is None:
            out.append(part)
            continue
        if part.isupper() and len(part) > 1:
            out.append(translation.upper())
        elif part[0].isupper():
            out.append(translation[0].upper() + translation[1:])
        else:
            out.append(translation)
    return "".join(out)


# Typical price range (min, max) in EUR per department, used both as the
# fallback range for GroceryStoreProvider.price() and to derive each
# product's stable "probable price" (base_price) at build time.
PRICE_RANGES = {
    "1": [2.0, 12.0],
    "2": [1.0, 15.0],
    "3": [0.8, 8.0],
    "4": [0.5, 6.0],
    "5": [4.0, 40.0],
    "6": [1.5, 10.0],
    "7": [0.5, 6.0],
    "8": [2.0, 25.0],
    "9": [0.5, 5.0],
    "10": [0.3, 8.0],
    "11": [1.5, 15.0],
    "12": [3.0, 30.0],
    "13": [0.5, 8.0],
    "14": [1.5, 8.0],
    "15": [0.5, 5.0],
    "16": [0.5, 6.0],
    "17": [1.0, 15.0],
    "18": [2.0, 20.0],
    "19": [0.5, 6.0],
    "20": [2.0, 15.0],
    "21": [0.5, 10.0],
}


# Localized labels for each unit of measure, keyed by a stable internal key
# (not by language) so departments can reference plausible units without
# duplicating strings per language.
UNIT_LABELS = {
    "kg": {"en": "kg", "fr": "kg"},
    "g": {"en": "g", "fr": "g"},
    "l": {"en": "L", "fr": "L"},
    "ml": {"en": "mL", "fr": "mL"},
    "piece": {"en": "piece(s)", "fr": "pièce(s)"},
    "pack": {"en": "pack", "fr": "paquet"},
    "box": {"en": "box", "fr": "boîte"},
    "bag": {"en": "bag", "fr": "sachet"},
    "bottle": {"en": "bottle", "fr": "bouteille"},
    "jar": {"en": "jar", "fr": "pot"},
    "bunch": {"en": "bunch", "fr": "botte"},
    "slice": {"en": "slice(s)", "fr": "tranche(s)"},
    "tray": {"en": "tray", "fr": "barquette"},
    "can": {"en": "can", "fr": "canette"},
    "tube": {"en": "tube", "fr": "tube"},
}

# Which unit keys are plausible for each department, so a generated grocery
# item's unit matches what the product actually is (no more "9 bottle x
# Bread" or "10 jar x Trash Bags"). Deliberately at department granularity,
# like PRICE_RANGES, rather than per-aisle - coarse but keeps the mapping
# maintainable, and department is already the axis GroceryStoreProvider
# reasons about for pricing.
#
# Instacart departments are themselves a grouping of quite varied aisles
# (e.g. department 9 "dry goods pasta" contains both dry pasta AND pasta
# sauce; department 13 "pantry" mixes oils, honey, spices and pickles), so
# each list below is deliberately a superset covering every aisle actually
# filed under that department - see the comment for the aisle breakdown.
DEPARTMENT_UNITS = {
    # frozen meat/seafood, ice cream, meals, pizza, juice, produce, dessert, appetizers
    "1": ["kg", "g", "piece", "pack", "box", "bag", "tray", "can"],
    "2": ["piece", "pack", "box", "bottle", "bag", "jar", "can"],  # other (catch-all)
    "3": ["piece", "pack", "slice", "bag", "box"],  # bakery desserts, buns, bread, tortillas
    "4": ["kg", "g", "bunch", "piece", "tray", "bag", "pack"],  # herbs, fruits, vegetables
    "5": ["bottle", "can", "pack", "box"],  # beers, wines, spirits, champagnes
    "6": ["pack", "box", "jar", "bag", "piece", "can", "bottle"],  # latino/kosher/asian/indian foods
    "7": ["l", "ml", "bottle", "can", "pack", "box", "bag"],  # coffee, tea, sodas, juice, water
    "8": ["kg", "g", "pack", "box", "bag", "piece", "can"],  # dog/cat food & care
    "9": ["kg", "g", "pack", "box", "bag", "jar", "bottle", "can"],  # dry pasta AND pasta sauce
    "10": ["kg", "g", "bag"],  # bulk dried fruits/grains/rice
    "11": ["piece", "pack", "box", "bottle", "tube", "jar", "can"],  # personal care (very varied)
    "12": ["kg", "g", "piece", "tray", "pack", "box"],  # meat, seafood, hot dogs/bacon/sausage
    "13": ["kg", "g", "pack", "box", "jar", "bottle", "bag", "can"],  # oils, honey, spreads, condiments, spices
    "14": ["kg", "g", "pack", "box", "bag", "piece"],  # bars/pastries, granola, cereal, pancake mixes
    "15": ["can", "jar", "box", "pack", "bottle"],  # canned meals/soup/veg/meat/fruit
    "16": ["piece", "pack", "box", "bottle", "jar", "tray", "bag"],  # cheese, butter, milk, eggs, yogurt
    "17": ["piece", "pack", "box", "bottle", "bag", "jar", "can"],  # kitchen/paper/cleaning/candles
    "18": ["piece", "pack", "box", "bag", "bottle", "jar"],  # diapers, accessories, baby food/formula
    "19": ["kg", "g", "pack", "box", "bag", "piece", "jar", "bottle"],  # snacks, candy, chips, toppings
    "20": ["kg", "g", "piece", "slice", "tray", "pack", "box"],  # prepared meals/salads, deli, lunch meat
    "21": ["piece", "pack"],  # missing
}


# Quantities for units sold by weight or volume, instead of by the piece.
# Items in these units are priced per `price_per` unit (per kg or per L,
# `factor` converting a quantity to it: 350 g -> 0.35 kg) and get a
# quantity in [min, base + per_person * family size], in multiples of
# `step` - e.g. 0.85 kg of apples or 1.5 L of milk rather than "7 kg of
# basil". Every other unit is counted (1, 2, 3... articles).
MEASURED_UNITS = {
    "kg": {"min": 0.2, "base": 0.3, "per_person": 0.35, "step": 0.05, "price_per": "kg", "factor": 1},
    "g": {"min": 100, "base": 150, "per_person": 150, "step": 50, "price_per": "kg", "factor": 0.001},
    "l": {"min": 0.5, "base": 0.5, "per_person": 0.5, "step": 0.5, "price_per": "l", "factor": 1},
    "ml": {"min": 250, "base": 250, "per_person": 250, "step": 250, "price_per": "l", "factor": 0.001},
}

# Currency the catalog prices (PRICE_RANGES and every base_price) are
# expressed in.
BASE_CURRENCY = "EUR"

# Currencies prices can be converted to. `rate` is a fixed, approximate
# EUR -> currency conversion factor (deliberately not a live exchange rate:
# the data must stay stable and offline), `price_level` the approximate
# grocery price level of the currency's country relative to the eurozone
# (exchange rates alone would make a basket cost the same everywhere, which
# it doesn't: groceries are much dearer in Switzerland, much cheaper in
# India), `decimals` the number of minor units prices are rounded to.
CURRENCIES = {
    "EUR": {"symbol": "€", "rate": 1.0, "price_level": 1.0, "decimals": 2},
    "USD": {"symbol": "$", "rate": 1.1, "price_level": 1.15, "decimals": 2},
    "GBP": {"symbol": "£", "rate": 0.85, "price_level": 0.95, "decimals": 2},
    "CHF": {"symbol": "CHF", "rate": 0.95, "price_level": 1.6, "decimals": 2},
    "CAD": {"symbol": "$", "rate": 1.5, "price_level": 1.1, "decimals": 2},
    "AUD": {"symbol": "$", "rate": 1.65, "price_level": 1.15, "decimals": 2},
    "NZD": {"symbol": "$", "rate": 1.8, "price_level": 1.15, "decimals": 2},
    "SEK": {"symbol": "kr", "rate": 11.5, "price_level": 1.0, "decimals": 2},
    "NOK": {"symbol": "kr", "rate": 11.7, "price_level": 1.3, "decimals": 2},
    "DKK": {"symbol": "kr", "rate": 7.46, "price_level": 1.15, "decimals": 2},
    "PLN": {"symbol": "zł", "rate": 4.3, "price_level": 0.65, "decimals": 2},
    "CZK": {"symbol": "Kč", "rate": 25.0, "price_level": 0.75, "decimals": 2},
    "HUF": {"symbol": "Ft", "rate": 400.0, "price_level": 0.7, "decimals": 0},
    "JPY": {"symbol": "¥", "rate": 160.0, "price_level": 0.85, "decimals": 0},
    "INR": {"symbol": "₹", "rate": 92.0, "price_level": 0.3, "decimals": 2},
    "BRL": {"symbol": "R$", "rate": 6.0, "price_level": 0.6, "decimals": 2},
    "MXN": {"symbol": "$", "rate": 20.0, "price_level": 0.65, "decimals": 2},
}

# Default currency for the country part of a Faker locale (e.g. "US" in
# "en_US"). Countries not listed here (including every eurozone country)
# use BASE_CURRENCY.
COUNTRY_CURRENCIES = {
    "US": "USD",
    "GB": "GBP",
    "CH": "CHF",
    "CA": "CAD",
    "AU": "AUD",
    "NZ": "NZD",
    "SE": "SEK",
    "NO": "NOK",
    "DK": "DKK",
    "PL": "PLN",
    "CZ": "CZK",
    "HU": "HUF",
    "JP": "JPY",
    "IN": "INR",
    "BR": "BRL",
    "MX": "MXN",
}


def base_price_for(product_id, department_id):
    """Deterministically derive a stable 'probable price' for a product from
    its department's typical price range, skewed towards the cheaper end
    (most grocery items are inexpensive, a few are premium). Seeded on the
    product id so the catalog is stable across rebuilds."""
    low, high = PRICE_RANGES[str(department_id)]
    mode = low + (high - low) * 0.35
    rng = random.Random(product_id)
    return round(rng.triangular(low, high, mode), 2)


def load_order_time_weights():
    """7x24 order counts, rows indexed like `datetime.date.weekday()`
    (0 = Monday). Instacart doesn't document its `order_dow` encoding; it is
    commonly read as 0 = Sunday (the two busiest days, 0 and 1, then being
    Sunday and Monday), which is the assumption made here."""
    weights = [[0] * 24 for _ in range(7)]
    with open(os.path.join(DATAS_DIR, "order_times.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            weekday = (int(row["order_dow"]) + 6) % 7
            weights[weekday][int(row["order_hour_of_day"])] = int(row["order_count"])
    return weights


def load_product_popularity():
    """product_id -> number of times it was ordered (absent: never ordered)."""
    with open(os.path.join(DATAS_DIR, "product_popularity.csv"), encoding="utf-8") as f:
        return {int(row["product_id"]): int(row["order_count"]) for row in csv.DictReader(f)}


def main():
    aisles = {}
    with open(os.path.join(DATAS_DIR, "aisles.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            aisles[row["aisle_id"]] = {"en": row["aisle"]}

    departments = {}
    with open(os.path.join(DATAS_DIR, "departments.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            departments[row["department_id"]] = {"en": row["department"]}

    products = []
    with open(os.path.join(DATAS_DIR, "products.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            products.append(
                {
                    "id": int(row["product_id"]),
                    "aisle_id": int(row["aisle_id"]),
                    "department_id": int(row["department_id"]),
                    "name": {"en": row["product_name"]},
                }
            )

    # Every aisle maps to exactly one department in the source data - store
    # that link on the aisle record for convenient filtering.
    for product in products:
        aisles[str(product["aisle_id"])]["department_id"] = product["department_id"]

    popularity = load_product_popularity()
    for product in products:
        product["base_price"] = base_price_for(product["id"], product["department_id"])
        product["order_count"] = popularity.get(product["id"], 0)

    for lang in TRANSLATED_LANGUAGES:
        word_dict = load_json(os.path.join(TRANSLATIONS_DIR, f"word_dict_{lang}.json"))
        dept_translations = load_json(os.path.join(TRANSLATIONS_DIR, f"departments_{lang}.json"))
        aisle_translations = load_json(os.path.join(TRANSLATIONS_DIR, f"aisles_{lang}.json"))

        for dept_id, translation in dept_translations.items():
            departments[dept_id][lang] = translation
        for aisle_id, translation in aisle_translations.items():
            aisles[aisle_id][lang] = translation
        for product in products:
            product["name"][lang] = translate_name(product["name"]["en"], word_dict)

    languages = [SOURCE_LANG] + TRANSLATED_LANGUAGES

    # Compact array format for products to keep the JSON file a reasonable
    # size: [id, aisle_id, department_id, base_price, order_count, name_lang1, name_lang2, ...]
    products_compact = [
        [p["id"], p["aisle_id"], p["department_id"], p["base_price"], p["order_count"]]
        + [p["name"][lang] for lang in languages]
        for p in products
    ]

    price_ranges = PRICE_RANGES
    unit_labels = UNIT_LABELS
    department_units = DEPARTMENT_UNITS

    # Every department must resolve to at least one known unit key.
    assert set(department_units) == set(price_ranges), "department_units / price_ranges department ids mismatch"
    for dept_id, keys in department_units.items():
        unknown = set(keys) - set(unit_labels)
        assert not unknown, f"department {dept_id} references unknown unit keys: {unknown}"
    assert BASE_CURRENCY in CURRENCIES and CURRENCIES[BASE_CURRENCY]["rate"] == 1.0
    unknown = set(COUNTRY_CURRENCIES.values()) - set(CURRENCIES)
    assert not unknown, f"COUNTRY_CURRENCIES references unknown currencies: {unknown}"
    for unit_key, spec in MEASURED_UNITS.items():
        assert unit_key in unit_labels and spec["price_per"] in unit_labels, unit_key

    data = {
        "meta": {
            "languages": languages,
            "default_language": SOURCE_LANG,
            "base_currency": BASE_CURRENCY,
            "planned_languages": PLANNED_LANGUAGES,
            "source": "Instacart Market Basket Analysis dataset (aisles.csv, departments.csv, products.csv, "
            "plus order statistics aggregated from orders.csv and order_products__prior.csv)",
            "product_count": len(products_compact),
            "product_fields": ["id", "aisle_id", "department_id", "base_price", "order_count"]
            + [f"name_{lang}" for lang in languages],
        },
        "departments": departments,
        "aisles": aisles,
        "price_ranges": price_ranges,
        "currencies": CURRENCIES,
        "country_currencies": COUNTRY_CURRENCIES,
        "unit_labels": unit_labels,
        "department_units": department_units,
        "measured_units": MEASURED_UNITS,
        "order_time_weights": load_order_time_weights(),
        "products": products_compact,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        # Compact separators: indentation would roughly double the file size
        # for no benefit (nobody reads a 50k-row JSON by hand).
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    print(f"Wrote {OUTPUT_PATH} ({size_mb:.2f} MB, {len(products_compact)} products)")


if __name__ == "__main__":
    main()
