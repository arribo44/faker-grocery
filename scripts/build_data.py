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


def base_price_for(product_id, department_id):
    """Deterministically derive a stable 'probable price' for a product from
    its department's typical price range, skewed towards the cheaper end
    (most grocery items are inexpensive, a few are premium). Seeded on the
    product id so the catalog is stable across rebuilds."""
    low, high = PRICE_RANGES[str(department_id)]
    mode = low + (high - low) * 0.35
    rng = random.Random(product_id)
    return round(rng.triangular(low, high, mode), 2)


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

    for product in products:
        product["base_price"] = base_price_for(product["id"], product["department_id"])

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
    # size: [id, aisle_id, department_id, base_price, name_lang1, name_lang2, ...]
    products_compact = [
        [p["id"], p["aisle_id"], p["department_id"], p["base_price"]]
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

    data = {
        "meta": {
            "languages": languages,
            "default_language": SOURCE_LANG,
            "planned_languages": PLANNED_LANGUAGES,
            "source": "Instacart Market Basket Analysis dataset (aisles.csv, departments.csv, products.csv)",
            "product_count": len(products_compact),
            "product_fields": ["id", "aisle_id", "department_id", "base_price"]
            + [f"name_{lang}" for lang in languages],
        },
        "departments": departments,
        "aisles": aisles,
        "price_ranges": price_ranges,
        "unit_labels": unit_labels,
        "department_units": department_units,
        "products": products_compact,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    print(f"Wrote {OUTPUT_PATH} ({size_mb:.2f} MB, {len(products_compact)} products)")


if __name__ == "__main__":
    main()
