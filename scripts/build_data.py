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

from store_tables import (
    AISLE_COMPLEMENTS,
    AISLE_SIZES,
    COUNTRY_OPENING_HOURS,
    COUNTRY_VAT,
    DEFAULT_OPENING_HOURS,
    PREMIUM_RE,
    PREMIUM_SURCHARGE,
    PROMOTION_LABELS,
    SEASONAL_FACTORS,
    SOUTHERN_HEMISPHERE_COUNTRIES,
    STANDARD_RATE_AISLES,
    STANDARD_RATE_DEPARTMENTS,
    STORE_NAME_TEMPLATES,
    UNIT_DEFAULT_SIZES,
    parse_size,
    season_mask,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATAS_DIR = os.path.join(ROOT, "DATAS")
TRANSLATIONS_DIR = os.path.join(ROOT, "scripts", "translations")
OUTPUT_PATH = os.path.join(ROOT, "faker_grocery", "data", "grocery_data.json")

# Source language of the raw dataset.
SOURCE_LANG = "en"

# Additional languages to generate via word-substitution translation.
# Each needs scripts/translations/word_dict_<lang>.json,
# departments_<lang>.json and aisles_<lang>.json.
TRANSLATED_LANGUAGES = ["fr", "it", "es", "pt", "de"]

# Locales planned for future extension (not yet built).
PLANNED_LANGUAGES = []

# Languages whose noun phrases put the noun first ("vinaigre balsamique
# blanc"), so reorder_words applies. German, like English, puts it last.
NOUN_FIRST_LANGUAGES = {"fr", "it", "es", "pt"}

TOKEN_RE = re.compile(r"[A-Za-z']+|[^A-Za-z']+")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# Punctuation that splits a product name into independently reorderable
# segments ("Napkins, Dinner, Ultra White" -> 3 segments).
SEGMENT_SPLIT_RE = re.compile(r"(\s*[,;/&()\-]\s*)")


def protect_phrases(name, phrases):
    """Swap known multi-word expressions ("gluten free", "hot dog") for
    single placeholder words, so they are translated as a whole and moved
    as a unit by reorder_words - instead of becoming "Gluten Sans" or, once
    reversed, "Chien Chaud". Returns the new name and the placeholder ->
    translation entries to add to the word dictionary."""
    entries = {}
    # Longest expressions first, so "extra virgin olive oil" wins over "olive oil".
    for index, (expression, translation) in enumerate(sorted(phrases.items(), key=lambda kv: -len(kv[0]))):
        placeholder = "qxphrase" + "".join(chr(ord("a") + int(d)) for d in str(index))

        def substitute(match, placeholder=placeholder, translation=translation):
            entries[placeholder] = translation
            return placeholder.capitalize() if match.group(0)[0].isupper() else placeholder

        name = re.sub(r"\b" + re.escape(expression) + r"\b", substitute, name, flags=re.IGNORECASE)
    return name, entries


def fallback_translation(name, word_dict, phrases, reorder=True):
    """Translation for products without a hand-checked one: known
    expressions first, then word-order reversal (for noun-first languages),
    then word substitution."""
    name, entries = protect_phrases(name, phrases)
    words = {**word_dict, **entries}
    if reorder:
        name = reorder_words(name, words)
    return translate_name(name, words)


def reorder_words(name, word_dict):
    """English puts modifiers before the noun ("White Balsamic Vinegar"),
    French mostly after it ("Vinaigre balsamique blanc"): reverse the word
    order of each segment - but only when every word of the segment is a
    known dictionary word, so brand names, numbers and sizes never move."""
    out = []
    for segment in SEGMENT_SPLIT_RE.split(name):
        words = segment.split()
        if len(words) > 1 and all(re.fullmatch(r"[A-Za-z']+", w) and w.lower() in word_dict for w in words):
            segment = " ".join(reversed(words))
        out.append(segment)
    return "".join(out)


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
    "kg": {"en": "kg", "fr": "kg", "it": "kg", "es": "kg", "pt": "kg", "de": "kg"},
    "g": {"en": "g", "fr": "g", "it": "g", "es": "g", "pt": "g", "de": "g"},
    "l": {"en": "L", "fr": "L", "it": "L", "es": "L", "pt": "L", "de": "L"},
    "ml": {"en": "mL", "fr": "mL", "it": "mL", "es": "mL", "pt": "mL", "de": "mL"},
    "piece": {
        "en": "piece(s)",
        "fr": "pièce(s)",
        "it": "pezzo/i",
        "es": "unidad(es)",
        "pt": "unidade(s)",
        "de": "Stück",
    },
    "pack": {"en": "pack", "fr": "paquet", "it": "confezione", "es": "paquete", "pt": "embalagem", "de": "Packung"},
    "box": {"en": "box", "fr": "boîte", "it": "scatola", "es": "caja", "pt": "caixa", "de": "Schachtel"},
    "bag": {"en": "bag", "fr": "sachet", "it": "sacchetto", "es": "bolsa", "pt": "saco", "de": "Beutel"},
    "bottle": {"en": "bottle", "fr": "bouteille", "it": "bottiglia", "es": "botella", "pt": "garrafa", "de": "Flasche"},
    "jar": {"en": "jar", "fr": "pot", "it": "vasetto", "es": "tarro", "pt": "frasco", "de": "Glas"},
    "bunch": {"en": "bunch", "fr": "botte", "it": "mazzo", "es": "manojo", "pt": "molho", "de": "Bund"},
    "slice": {
        "en": "slice(s)",
        "fr": "tranche(s)",
        "it": "fetta/e",
        "es": "loncha(s)",
        "pt": "fatia(s)",
        "de": "Scheibe(n)",
    },
    "tray": {"en": "tray", "fr": "barquette", "it": "vaschetta", "es": "bandeja", "pt": "cuvete", "de": "Schale"},
    "can": {"en": "can", "fr": "canette", "it": "lattina", "es": "lata", "pt": "lata", "de": "Dose"},  # drink can
    "tin": {  # food can (not "can": that's the drink can's English label)
        "en": "tin",
        "fr": "boîte de conserve",
        "it": "scatoletta",
        "es": "lata de conserva",
        "pt": "lata de conserva",
        "de": "Konservendose",
    },
    "tube": {"en": "tube", "fr": "tube", "it": "tubetto", "es": "tubo", "pt": "tubo", "de": "Tube"},
}

# Which unit keys are plausible for each aisle. Every product gets ONE of
# its aisle's units, fixed at build time (see unit_for), so a given product
# is always sold the same way - "Organic Whole Milk" is always by the litre
# or always by the bottle, never "450 g" one day and "3 bottles" the next.
# Measured units (kg, g, L) are only used where products really are sold by
# weight/volume: fresh produce, counters, bulk and drinks.
AISLE_UNITS = {
    "1": ["g", "tray"],  # prepared soups salads
    "2": ["g", "piece"],  # specialty cheeses
    "3": ["box", "pack"],  # energy granola bars
    "4": ["pack", "box", "jar"],  # instant foods
    "5": ["bottle", "jar", "bag"],  # marinades meat preparation
    "6": ["piece", "pack", "box"],  # other
    "7": ["pack", "tray"],  # packaged meat
    "8": ["piece", "box"],  # bakery desserts
    "9": ["jar"],  # pasta sauce
    "10": ["piece", "pack"],  # kitchen supplies
    "11": ["box", "bottle"],  # cold flu allergy
    "12": ["pack", "tray"],  # fresh pasta
    "13": ["tray", "box"],  # prepared meals
    "14": ["pack"],  # tofu meat alternatives
    "15": ["pack", "tray"],  # packaged seafood
    "16": ["bunch", "pack"],  # fresh herbs
    "17": ["bag", "box", "jar"],  # baking ingredients
    "18": ["g", "kg"],  # bulk dried fruits vegetables
    "19": ["bottle"],  # oils vinegars
    "20": ["tube", "piece", "bottle"],  # oral hygiene
    "21": ["pack", "piece"],  # packaged cheese
    "22": ["bottle", "tube"],  # hair care
    "23": ["bag"],  # popcorn jerky
    "24": ["kg", "piece"],  # fresh fruits
    "25": ["piece", "bottle"],  # soap
    "26": ["pack", "bag", "jar"],  # coffee
    "27": ["can", "bottle", "pack"],  # beers coolers
    "28": ["bottle"],  # red wines
    "29": ["jar", "bottle"],  # honeys syrups nectars
    "30": ["tin", "pack", "jar", "bag"],  # latino foods
    "31": ["bottle"],  # refrigerated (drinks)
    "32": ["pack", "bag", "tray"],  # packaged produce
    "33": ["pack", "box", "jar"],  # kosher foods
    "34": ["bag", "pack"],  # frozen meat seafood
    "35": ["kg"],  # poultry counter
    "36": ["pack"],  # butter
    "37": ["box"],  # ice cream ice
    "38": ["box"],  # frozen meals
    "39": ["kg", "g"],  # seafood counter
    "40": ["bag", "tin", "box"],  # dog food care
    "41": ["bag", "tin", "box"],  # cat food care
    "42": ["box", "bag"],  # frozen vegan vegetarian
    "43": ["bag", "pack"],  # buns rolls
    "44": ["bottle", "box"],  # eye ear care
    "45": ["bag", "piece", "box"],  # candy chocolate
    "46": ["pack"],  # mint gum
    "47": ["bottle", "box"],  # vitamins supplements
    "48": ["box"],  # breakfast bars pastries
    "49": ["pack", "tray"],  # packaged poultry
    "50": ["bag", "pack"],  # fruit vegetable snacks
    "51": ["jar"],  # preserved dips spreads
    "52": ["box"],  # frozen breakfast
    "53": ["bottle", "jar"],  # cream
    "54": ["pack"],  # paper goods
    "55": ["piece", "pack", "tube"],  # shave needs
    "56": ["pack"],  # diapers wipes
    "57": ["bag", "box"],  # granola
    "58": ["bag", "box"],  # frozen breads doughs
    "59": ["tin"],  # canned meals beans
    "60": ["box", "pack"],  # trash bags liners
    "61": ["pack", "box"],  # cookies cakes
    "62": ["bottle"],  # white wines
    "63": ["bag", "box"],  # grains rice dried goods
    "64": ["can", "bottle"],  # energy sports drinks
    "65": ["box", "bottle", "jar"],  # protein meal replacements
    "66": ["pack", "jar", "bottle", "bag"],  # asian foods
    "67": ["jar", "tray"],  # fresh dips tapenades
    "68": ["kg", "g"],  # bulk grains rice dried goods
    "69": ["tin", "box"],  # soup broth bouillon
    "70": ["box", "bottle"],  # digestion
    "71": ["pack", "jar"],  # refrigerated pudding desserts
    "72": ["bottle", "jar"],  # condiments
    "73": ["tube", "bottle"],  # facial care
    "74": ["bottle", "box"],  # dish detergents
    "75": ["bottle", "box"],  # laundry
    "76": ["pack", "jar", "box"],  # indian foods
    "77": ["l", "can", "bottle", "pack"],  # soft drinks
    "78": ["box", "pack"],  # crackers
    "79": ["box"],  # frozen pizza
    "80": ["piece"],  # deodorants
    "81": ["tin", "jar"],  # canned jarred vegetables
    "82": ["piece"],  # baby accessories
    "83": ["kg", "piece", "bunch"],  # fresh vegetables
    "84": ["l", "bottle"],  # milk
    "85": ["box", "pack"],  # food storage
    "86": ["box"],  # eggs
    "87": ["piece", "pack"],  # more household
    "88": ["jar"],  # spreads
    "89": ["bottle", "jar"],  # salad dressing toppings
    "90": ["box", "jar"],  # cocoa drink mixes
    "91": ["bottle", "pack"],  # soy lactosefree
    "92": ["jar", "box", "bag"],  # baby food formula
    "93": ["pack", "piece"],  # breakfast bakery
    "94": ["box"],  # tea
    "95": ["tin"],  # canned meat seafood
    "96": ["g", "slice", "pack"],  # lunch meat
    "97": ["jar", "pack"],  # baking supplies decor
    "98": ["l", "bottle"],  # juice nectars
    "99": ["tin", "jar"],  # canned fruit applesauce
    "100": ["piece", "pack"],  # missing
    "101": ["piece"],  # air fresheners candles
    "102": ["bottle", "tube"],  # baby bath body care
    "103": ["jar", "bottle"],  # ice cream toppings
    "104": ["jar"],  # spices seasonings
    "105": ["box", "pack"],  # doughs gelatins bake mixes
    "106": ["pack"],  # hot dogs bacon sausage
    "107": ["bag"],  # chips pretzels
    "108": ["jar", "pack"],  # other creams cheeses
    "109": ["tube", "bottle"],  # skin care
    "110": ["jar"],  # pickled goods olives
    "111": ["pack"],  # plates bowls cups flatware
    "112": ["piece", "bag"],  # bread
    "113": ["can", "bottle"],  # frozen juice
    "114": ["bottle"],  # cleaning products
    "115": ["l", "bottle", "pack"],  # water seltzer sparkling water
    "116": ["bag"],  # frozen produce
    "117": ["bag", "jar"],  # nuts seeds dried fruit
    "118": ["box"],  # first aid
    "119": ["box"],  # frozen dessert
    "120": ["jar", "pack"],  # yogurt
    "121": ["box"],  # cereal
    "122": ["kg", "g"],  # meat counter
    "123": ["bag", "pack", "tray"],  # packaged vegetables fruits
    "124": ["bottle"],  # spirits
    "125": ["bag"],  # trail mix snack mix
    "126": ["box", "pack"],  # feminine care
    "127": ["bottle", "tube"],  # body lotions soap
    "128": ["pack"],  # tortillas flat bread
    "129": ["box", "bag"],  # frozen appetizers sides
    "130": ["box"],  # hot cereal pancake mixes
    "131": ["pack", "box"],  # dry pasta
    "132": ["piece", "tube"],  # beauty
    "133": ["box", "tube"],  # muscles joints pain relief
    "134": ["bottle"],  # specialty wines champagnes
}

# Price range (min, max) in EUR per kg or per L for the aisles whose
# products can be sold by weight/volume. A product given a measured unit
# (kg, g, L) gets its base_price from here, as a price per kg/L, instead of
# a per-article price from its department's PRICE_RANGES - so 200 g of
# seafood costs what 200 g of seafood costs, not 1/5 of an arbitrary
# article price.
MEASURED_PRICE_RANGES = {
    "1": [8.0, 25.0],  # prepared soups salads
    "2": [12.0, 40.0],  # specialty cheeses
    "18": [6.0, 25.0],  # bulk dried fruits vegetables
    "24": [1.5, 8.0],  # fresh fruits
    "35": [6.0, 20.0],  # poultry counter
    "39": [12.0, 45.0],  # seafood counter
    "68": [1.5, 8.0],  # bulk grains rice dried goods
    "77": [0.8, 3.0],  # soft drinks (per L)
    "83": [1.0, 6.0],  # fresh vegetables
    "84": [0.9, 2.5],  # milk (per L)
    "96": [10.0, 35.0],  # lunch meat
    "98": [1.5, 5.0],  # juice nectars (per L)
    "115": [0.2, 1.2],  # water (per L)
    "122": [9.0, 40.0],  # meat counter
}


# Per-article price range (min, max) in EUR for some (aisle, unit) pairs,
# overriding the department's PRICE_RANGES where one range per department is
# too coarse: a can of beer is not priced like a bottle of spirits, nor a
# lime like a bunch of asparagus.
AISLE_UNIT_PRICE_RANGES = {
    "24": {"piece": [0.2, 2.0], "tray": [1.5, 6.0]},  # fresh fruits
    "27": {"can": [0.8, 3.0], "bottle": [1.0, 4.0], "pack": [4.0, 18.0]},  # beers coolers
    "83": {"piece": [0.3, 3.0], "bunch": [0.8, 3.0]},  # fresh vegetables
    "86": {"box": [1.5, 6.0]},  # eggs
}

# Fixed unit for some of the most ordered products, whose unit drawn among
# their aisle's would be implausible ("Organic Yellow Onion" by the bunch,
# "Strawberries" by the piece). These products come up in most baskets, so
# their oddities would too. Units not already in the aisle's AISLE_UNITS are
# added to its plausible units in the generated data.
PRODUCT_UNIT_OVERRIDES = {
    13176: "bag",  # Bag of Organic Bananas
    21137: "tray",  # Organic Strawberries
    16797: "tray",  # Strawberries
    26604: "tray",  # Organic Blackberries
    27966: "tray",  # Organic Raspberries
    39275: "tray",  # Organic Blueberries
    43352: "tray",  # Raspberries
    37646: "kg",  # Organic Gala Apples
    22935: "kg",  # Organic Yellow Onion
    8518: "kg",  # Organic Red Onion
    17794: "kg",  # Carrots
    24964: "piece",  # Organic Garlic
    28985: "bunch",  # Michigan Organic Kale
    31717: "bunch",  # Organic Cilantro
    49235: "bottle",  # Organic Half & Half
    35951: "bottle",  # Organic Unsweetened Almond Milk
    # Names stating a count, pack or container size, not sold by weight/volume.
    31808: "pack",  # Lemon-Lime 12 Pack Soda
    10510: "pack",  # Black Cherry Soda 6 Ct
    35543: "pack",  # Sparkling Cranberry 6 Pack
    48496: "pack",  # All Natural Kiwi Strawberry - 6 CT
    31408: "pack",  # Fruit Pnc 12 Floz 12 Pk 144 Floz
    21866: "bottle",  # 2% Milk Gallon
    3355: "piece",  # Goldfish 9ct Wg Cheddar
    17042: "piece",  # 8 oz Dofino Havarti Light
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
# grocery price level of the currency's main country relative to France
# (1.0; see COUNTRY_PRICE_LEVELS for finer per-country levels)
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
    # Other countries of Faker's locales (approximate 2025-2026 rates; price
    # levels are rough orders of magnitude, from food price comparisons).
    # Currencies whose minor unit isn't used in shops are rounded to whole
    # numbers (CLP, COP, KRW, ISK, TWD, VND, IDR, UZS).
    "ARS": {"symbol": "$", "rate": 1500.0, "price_level": 0.75, "decimals": 2},
    "CLP": {"symbol": "$", "rate": 1050.0, "price_level": 0.8, "decimals": 0},
    "COP": {"symbol": "$", "rate": 4500.0, "price_level": 0.55, "decimals": 0},
    "KRW": {"symbol": "₩", "rate": 1550.0, "price_level": 1.3, "decimals": 0},
    "CNY": {"symbol": "¥", "rate": 8.0, "price_level": 0.6, "decimals": 2},
    "TWD": {"symbol": "NT$", "rate": 36.0, "price_level": 0.85, "decimals": 0},
    "RUB": {"symbol": "₽", "rate": 95.0, "price_level": 0.5, "decimals": 2},
    "UAH": {"symbol": "₴", "rate": 46.0, "price_level": 0.5, "decimals": 2},
    "TRY": {"symbol": "₺", "rate": 46.0, "price_level": 0.45, "decimals": 2},
    "ILS": {"symbol": "₪", "rate": 4.0, "price_level": 1.3, "decimals": 2},
    "ZAR": {"symbol": "R", "rate": 20.0, "price_level": 0.5, "decimals": 2},
    "RON": {"symbol": "lei", "rate": 5.0, "price_level": 0.65, "decimals": 2},
    "ISK": {"symbol": "kr", "rate": 145.0, "price_level": 1.45, "decimals": 0},
    "MKD": {"symbol": "ден", "rate": 61.5, "price_level": 0.6, "decimals": 2},
    "ALL": {"symbol": "L", "rate": 98.0, "price_level": 0.65, "decimals": 2},
    "BAM": {"symbol": "KM", "rate": 1.96, "price_level": 0.7, "decimals": 2},
    "AZN": {"symbol": "₼", "rate": 1.9, "price_level": 0.5, "decimals": 2},
    "AMD": {"symbol": "֏", "rate": 440.0, "price_level": 0.6, "decimals": 2},
    "GEL": {"symbol": "₾", "rate": 3.0, "price_level": 0.6, "decimals": 2},
    "UZS": {"symbol": "soʻm", "rate": 14000.0, "price_level": 0.4, "decimals": 0},
    "THB": {"symbol": "฿", "rate": 38.0, "price_level": 0.55, "decimals": 2},
    "VND": {"symbol": "₫", "rate": 28000.0, "price_level": 0.45, "decimals": 0},
    "IDR": {"symbol": "Rp", "rate": 18000.0, "price_level": 0.5, "decimals": 0},
    "PHP": {"symbol": "₱", "rate": 64.0, "price_level": 0.55, "decimals": 2},
    "MYR": {"symbol": "RM", "rate": 4.9, "price_level": 0.55, "decimals": 2},
    "PKR": {"symbol": "Rs", "rate": 310.0, "price_level": 0.3, "decimals": 2},
    "BDT": {"symbol": "৳", "rate": 130.0, "price_level": 0.35, "decimals": 2},
    "LKR": {"symbol": "Rs", "rate": 340.0, "price_level": 0.4, "decimals": 2},
    "NPR": {"symbol": "Rs", "rate": 155.0, "price_level": 0.35, "decimals": 2},
    "SAR": {"symbol": "SAR", "rate": 4.1, "price_level": 0.8, "decimals": 2},
    "AED": {"symbol": "AED", "rate": 4.0, "price_level": 0.95, "decimals": 2},
    "BHD": {"symbol": "BD", "rate": 0.41, "price_level": 0.85, "decimals": 3},
    "JOD": {"symbol": "JD", "rate": 0.78, "price_level": 0.75, "decimals": 3},
    "EGP": {"symbol": "E£", "rate": 55.0, "price_level": 0.3, "decimals": 2},
    "DZD": {"symbol": "DA", "rate": 150.0, "price_level": 0.4, "decimals": 2},
    "NGN": {"symbol": "₦", "rate": 1700.0, "price_level": 0.4, "decimals": 2},
    "KES": {"symbol": "KSh", "rate": 145.0, "price_level": 0.5, "decimals": 2},
    "GHS": {"symbol": "GH₵", "rate": 13.0, "price_level": 0.5, "decimals": 2},
    "ETB": {"symbol": "Br", "rate": 160.0, "price_level": 0.4, "decimals": 2},
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
    "AR": "ARS", "CL": "CLP", "CO": "COP", "KR": "KRW", "CN": "CNY", "TW": "TWD",
    "RU": "RUB", "UA": "UAH", "TR": "TRY", "IL": "ILS", "PS": "ILS", "ZA": "ZAR",
    "RO": "RON", "IS": "ISK", "MK": "MKD", "AL": "ALL", "BA": "BAM", "AZ": "AZN",
    "AM": "AMD", "GE": "GEL", "UZ": "UZS", "TH": "THB", "VN": "VND", "ID": "IDR",
    "PH": "PHP", "MY": "MYR", "PK": "PKR", "BD": "BDT", "LK": "LKR", "NP": "NPR",
    "SA": "SAR", "AE": "AED", "BH": "BHD", "JO": "JOD", "EG": "EGP", "DZ": "DZD",
    "NG": "NGN", "KE": "KES", "GH": "GHS", "ET": "ETB", "LI": "CHF",
    # Faker locale suffixes that aren't ISO country codes: fr_QC (Quebec),
    # en_MS (Malaysian English, not Montserrat).
    "QC": "CAD", "MS": "MYR",
}

# Approximate grocery price level per country, relative to France (1.0),
# loosely based on Eurostat food price level indices. Used instead of the
# currency's own price_level when prices are in the locale country's own
# currency - so the eurozone isn't one flat price level (Portugal cheaper,
# Ireland dearer...). Countries not listed use their currency's level.
COUNTRY_PRICE_LEVELS = {
    "FR": 1.0, "DE": 0.95, "AT": 1.05, "BE": 1.0, "NL": 0.9, "LU": 1.1,
    "IE": 1.1, "IT": 0.95, "ES": 0.85, "PT": 0.82, "GR": 0.9, "FI": 1.05,
    "EE": 0.95, "LV": 0.9, "LT": 0.85, "SK": 0.85, "SI": 0.9, "HR": 0.9,
    "CY": 0.95, "MT": 0.95, "BG": 0.75,  # Bulgaria joined the euro on 2026-01-01
}

# Typical weekly shopping-time profiles, as 7x24 weights indexed
# [weekday][hour] (weekday 0 = Monday). "instacart_us" is measured (US online
# orders, see load_order_time_weights); the others are hand-made heuristics
# for countries whose trading hours differ markedly: busy Saturday, quiet
# early week, lunchtime and after-work peaks, and Sunday either closed or
# morning-only.
DEFAULT_SHOPPING_PATTERN = "instacart_us"
_EU_HOUR_WEIGHTS = [0, 0, 0, 0, 0, 0, 0, 0.3, 0.5, 0.8, 1.0, 1.1, 0.9, 0.7,
                    0.7, 0.8, 1.0, 1.3, 1.3, 0.9, 0.4, 0.15, 0, 0]


def _weekly_pattern(day_weights, hour_weights, sunday_until=24):
    pattern = [[round(d * h, 3) for h in hour_weights] for d in day_weights]
    pattern[6] = [w if hour < sunday_until else 0 for hour, w in enumerate(pattern[6])]
    return pattern


SYNTHETIC_SHOPPING_PATTERNS = {
    # Sunday morning opening only (France, Belgium, southern Europe).
    "sunday_morning": _weekly_pattern([0.85, 0.8, 0.9, 0.9, 1.1, 1.5, 0.6], _EU_HOUR_WEIGHTS, sunday_until=13),
    # Shops closed on Sunday (Germany, Austria, Switzerland, Poland, Norway).
    "sunday_closed": _weekly_pattern([0.9, 0.85, 0.9, 0.95, 1.2, 1.6, 0], _EU_HOUR_WEIGHTS),
}

# Shopping pattern for the country part of a Faker locale; unlisted countries
# use DEFAULT_SHOPPING_PATTERN.
COUNTRY_SHOPPING_PATTERNS = {
    "FR": "sunday_morning", "BE": "sunday_morning", "LU": "sunday_morning",
    "ES": "sunday_morning", "IT": "sunday_morning", "PT": "sunday_morning",
    "DE": "sunday_closed", "AT": "sunday_closed", "CH": "sunday_closed",
    "PL": "sunday_closed", "NO": "sunday_closed",
}


def triangular_price(seed, low, high):
    """A stable price in [low, high], skewed towards the cheaper end (most
    grocery items are inexpensive, a few are premium). Seeded on the product
    id so the catalog is stable across rebuilds."""
    mode = low + (high - low) * 0.35
    return round(random.Random(seed).triangular(low, high, mode), 2)


def unit_for(product):
    """The product's fixed unit, among its aisle's plausible units. Seeded on
    a string (not the bare id) so it is independent of the price draw.
    PRODUCT_UNIT_OVERRIDES wins over the draw."""
    if product["id"] in PRODUCT_UNIT_OVERRIDES:
        return PRODUCT_UNIT_OVERRIDES[product["id"]]
    return random.Random(f"unit:{product['id']}").choice(AISLE_UNITS[str(product["aisle_id"])])


def price_range_for(aisle_id, department_id, unit):
    """The EUR range a product's base_price is drawn from: per kg/L from the
    aisle's MEASURED_PRICE_RANGES for measured units, else per article from
    AISLE_UNIT_PRICE_RANGES if the (aisle, unit) pair has one, else from the
    department's PRICE_RANGES."""
    if unit in MEASURED_UNITS:
        return MEASURED_PRICE_RANGES[str(aisle_id)]
    specific = AISLE_UNIT_PRICE_RANGES.get(str(aisle_id), {}).get(unit)
    return specific or PRICE_RANGES[str(department_id)]


def base_price_for(product):
    """A product's stable price, from its range (see price_range_for), with
    PREMIUM_SURCHARGE for organic / premium products."""
    low, high = price_range_for(product["aisle_id"], product["department_id"], product["unit"])
    price = triangular_price(product["id"], low, high)
    if PREMIUM_RE.search(product["name"][SOURCE_LANG]):
        price = round(price * PREMIUM_SURCHARGE, 2)
    return price


def size_for(product):
    """The product's package size ([count, amount, unit], see store_tables),
    or None: the size stated in its name if any, else one of its (aisle,
    unit)'s sizes - the larger the dearer the product is within its price
    range, so price and size stay consistent. Products sold by weight or
    volume have no size (the quantity bought is the size)."""
    unit = product["unit"]
    if unit in MEASURED_UNITS:
        return None
    stated = parse_size(product["name"][SOURCE_LANG], product["aisle_id"], product["department_id"])
    if stated is not None:
        return stated
    aisle_sizes = AISLE_SIZES.get(str(product["aisle_id"]), {})
    options = aisle_sizes[unit] if unit in aisle_sizes else UNIT_DEFAULT_SIZES.get(unit)
    if not options:
        return None
    low, high = price_range_for(product["aisle_id"], product["department_id"], unit)
    quantile = (triangular_price(product["id"], low, high) - low) / (high - low)
    return options[min(len(options) - 1, int(quantile * len(options)))]


def clean_name(name):
    """Collapse runs of whitespace ("TAI PEI      14OZ.SWEET") and trim."""
    return " ".join(name.split())


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
                    "name": {"en": clean_name(row["product_name"])},
                }
            )

    # Every aisle maps to exactly one department in the source data - store
    # that link on the aisle record for convenient filtering.
    for product in products:
        aisles[str(product["aisle_id"])]["department_id"] = product["department_id"]

    popularity = load_product_popularity()
    for product in products:
        product["unit"] = unit_for(product)
        product["base_price"] = base_price_for(product)
        product["order_count"] = popularity.get(product["id"], 0)
        product["size"] = size_for(product)
        product["season"] = season_mask(product["name"][SOURCE_LANG], product["aisle_id"])

    for lang in TRANSLATED_LANGUAGES:
        word_dict = load_json(os.path.join(TRANSLATIONS_DIR, f"word_dict_{lang}.json"))
        dept_translations = load_json(os.path.join(TRANSLATIONS_DIR, f"departments_{lang}.json"))
        aisle_translations = load_json(os.path.join(TRANSLATIONS_DIR, f"aisles_{lang}.json"))

        for dept_id, translation in dept_translations.items():
            departments[dept_id][lang] = translation
        for aisle_id, translation in aisle_translations.items():
            aisles[aisle_id][lang] = translation
        # Hand-checked translations of the most ordered products (see
        # product_names_<lang>.json) take precedence; every other product
        # falls back to word-order reversal + word-by-word substitution.
        names_path = os.path.join(TRANSLATIONS_DIR, f"product_names_{lang}.json")
        curated_names = load_json(names_path) if os.path.exists(names_path) else {}
        phrases_path = os.path.join(TRANSLATIONS_DIR, f"phrases_{lang}.json")
        phrases = load_json(phrases_path) if os.path.exists(phrases_path) else {}
        for product in products:
            curated = curated_names.get(str(product["id"]))
            product["name"][lang] = clean_name(curated or fallback_translation(
                product["name"]["en"], word_dict, phrases, reorder=lang in NOUN_FIRST_LANGUAGES
            ))

    languages = [SOURCE_LANG] + TRANSLATED_LANGUAGES

    # Compact array format for products to keep the JSON file a reasonable
    # size: [id, aisle_id, department_id, base_price, order_count, unit, name_<source lang>].
    # Translated names go to one names_<lang>.json file per language (a list
    # parallel to "products"), loaded only when a locale needs it: keeping
    # all languages in the main file would make every import load ~50k x 6
    # names.
    products_compact = [
        [p["id"], p["aisle_id"], p["department_id"], p["base_price"], p["order_count"], p["unit"],
         p["size"], p["season"], p["name"][SOURCE_LANG]]
        for p in products
    ]
    # Tax class of each aisle: food (reduced rate) or standard.
    aisle_tax_class = {
        aisle_id: "standard"
        if info["department_id"] in STANDARD_RATE_DEPARTMENTS or int(aisle_id) in STANDARD_RATE_AISLES
        else "food"
        for aisle_id, info in aisles.items()
    }

    price_ranges = PRICE_RANGES
    unit_labels = UNIT_LABELS
    # An aisle's plausible units: AISLE_UNITS plus any unit forced on one of
    # its products by PRODUCT_UNIT_OVERRIDES (appended, so the seeded unit
    # draw of the other products is unchanged).
    aisle_units = {aisle_id: list(units) for aisle_id, units in AISLE_UNITS.items()}
    by_id = {p["id"]: p for p in products}
    for product_id, unit in PRODUCT_UNIT_OVERRIDES.items():
        assert product_id in by_id, f"PRODUCT_UNIT_OVERRIDES: unknown product {product_id}"
        units = aisle_units[str(by_id[product_id]["aisle_id"])]
        if unit not in units:
            units.append(unit)
    # A department's plausible units are those of its aisles.
    department_units = {}
    for aisle_id in sorted(aisles, key=int):
        dept_units = department_units.setdefault(str(aisles[aisle_id]["department_id"]), [])
        dept_units.extend(u for u in aisle_units[aisle_id] if u not in dept_units)

    assert set(AISLE_UNITS) == set(aisles), "AISLE_UNITS / aisles ids mismatch"
    assert set(department_units) == set(price_ranges), "department_units / price_ranges department ids mismatch"
    for aisle_id, ranges in AISLE_UNIT_PRICE_RANGES.items():
        for unit, (low, high) in ranges.items():
            assert unit in aisle_units[aisle_id] and unit not in MEASURED_UNITS and 0 < low < high, (aisle_id, unit)
    # Names must identify one aisle / department: name lookups search every
    # language, so a name shared by two ids would always resolve to the first.
    for kind, table in (("aisle", aisles), ("department", departments)):
        owners = {}
        for item_id, names in table.items():
            for lang in [SOURCE_LANG] + TRANSLATED_LANGUAGES:
                owner = owners.setdefault(names[lang].lower(), item_id)
                assert owner == item_id, f"{kind}s {owner} and {item_id} share the name {names[lang]!r}"
    for aisle_id, keys in aisle_units.items():
        unknown = set(keys) - set(unit_labels)
        assert not unknown, f"aisle {aisle_id} references unknown unit keys: {unknown}"
        if set(keys) & set(MEASURED_UNITS):
            assert aisle_id in MEASURED_PRICE_RANGES, f"aisle {aisle_id} has measured units but no per-kg/L range"
    assert BASE_CURRENCY in CURRENCIES and CURRENCIES[BASE_CURRENCY]["rate"] == 1.0
    unknown = set(COUNTRY_CURRENCIES.values()) - set(CURRENCIES)
    assert not unknown, f"COUNTRY_CURRENCIES references unknown currencies: {unknown}"
    for unit_key, spec in MEASURED_UNITS.items():
        assert unit_key in unit_labels and spec["price_per"] in unit_labels, unit_key
    shopping_patterns = {DEFAULT_SHOPPING_PATTERN: load_order_time_weights(), **SYNTHETIC_SHOPPING_PATTERNS}
    unknown = set(COUNTRY_SHOPPING_PATTERNS.values()) - set(shopping_patterns)
    assert not unknown, f"COUNTRY_SHOPPING_PATTERNS references unknown patterns: {unknown}"
    for aisle_id, sizes in AISLE_SIZES.items():
        assert aisle_id in aisles, f"AISLE_SIZES: unknown aisle {aisle_id}"
        for unit in sizes:
            assert unit in aisle_units[aisle_id], f"AISLE_SIZES: aisle {aisle_id} has no unit {unit}"
    for aisle_id, complement, probability in AISLE_COMPLEMENTS:
        assert str(aisle_id) in aisles and str(complement) in aisles and 0 < probability <= 1
    for country, hours in COUNTRY_OPENING_HOURS.items():
        assert 0 <= hours[0] < hours[1] <= 24, country
    for lang in languages:
        assert lang in STORE_NAME_TEMPLATES, lang
        assert all(lang in labels for labels in PROMOTION_LABELS.values()), lang

    data = {
        "meta": {
            "languages": languages,
            "default_language": SOURCE_LANG,
            "base_currency": BASE_CURRENCY,
            "default_shopping_pattern": DEFAULT_SHOPPING_PATTERN,
            "planned_languages": PLANNED_LANGUAGES,
            "source": "Instacart Market Basket Analysis dataset (aisles.csv, departments.csv, products.csv, "
            "plus order statistics aggregated from orders.csv and order_products__prior.csv)",
            "product_count": len(products_compact),
            "product_fields": ["id", "aisle_id", "department_id", "base_price", "order_count", "unit",
                               "size", "season", f"name_{SOURCE_LANG}"],
            "name_files": {lang: f"names_{lang}.json" for lang in TRANSLATED_LANGUAGES},
        },
        "departments": departments,
        "aisles": aisles,
        "price_ranges": price_ranges,
        "currencies": CURRENCIES,
        "country_currencies": COUNTRY_CURRENCIES,
        "country_price_levels": COUNTRY_PRICE_LEVELS,
        "unit_labels": unit_labels,
        "aisle_units": aisle_units,
        "department_units": department_units,
        "measured_units": MEASURED_UNITS,
        "measured_price_ranges": MEASURED_PRICE_RANGES,
        "aisle_unit_price_ranges": AISLE_UNIT_PRICE_RANGES,
        "shopping_patterns": shopping_patterns,
        "country_shopping_patterns": COUNTRY_SHOPPING_PATTERNS,
        "premium_surcharge": PREMIUM_SURCHARGE,
        "seasonal_factors": SEASONAL_FACTORS,
        "southern_hemisphere_countries": SOUTHERN_HEMISPHERE_COUNTRIES,
        "default_opening_hours": DEFAULT_OPENING_HOURS,
        "country_opening_hours": COUNTRY_OPENING_HOURS,
        "country_vat": COUNTRY_VAT,
        "aisle_tax_class": aisle_tax_class,
        "aisle_complements": AISLE_COMPLEMENTS,
        "store_name_templates": STORE_NAME_TEMPLATES,
        "promotion_labels": PROMOTION_LABELS,
        "products": products_compact,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        # Compact separators: indentation would roughly double the file size
        # for no benefit (nobody reads a 50k-row JSON by hand).
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    print(f"Wrote {OUTPUT_PATH} ({size_mb:.2f} MB, {len(products_compact)} products)")

    for lang in TRANSLATED_LANGUAGES:
        names_path = os.path.join(os.path.dirname(OUTPUT_PATH), data["meta"]["name_files"][lang])
        with open(names_path, "w", encoding="utf-8") as f:
            json.dump([p["name"][lang] for p in products], f, ensure_ascii=False, separators=(",", ":"))
        print(f"Wrote {names_path} ({os.path.getsize(names_path) / (1024 * 1024):.2f} MB)")


if __name__ == "__main__":
    main()
