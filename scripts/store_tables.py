"""
Hand-made store tables used by build_data.py: package sizes, seasonality,
premium surcharge, VAT, opening hours, complementary aisles, store names and
promotion labels. Approximate, "faker-grade" data: plausible orders of
magnitude, not a reference.

Sizes are [count, amount, unit]: [1, 500, "g"] is "500 g", [6, 330, "ml"]
"6 x 330 mL", [12, None, None] "12 pieces" (a count without weight/volume).
"""
import re

# -- package sizes ---------------------------------------------------------------

# Default sizes per unit key, for food products. Listed from smallest to
# largest: a product gets the size matching where its price falls in its
# price range (cheap -> small), so a 1 kg box doesn't cost less than a 250 g one.
UNIT_DEFAULT_SIZES = {
    "pack": [[1, 125, "g"], [1, 200, "g"], [1, 250, "g"], [1, 400, "g"], [1, 500, "g"]],
    "box": [[1, 250, "g"], [1, 375, "g"], [1, 500, "g"], [1, 750, "g"], [1, 1000, "g"]],
    "bag": [[1, 100, "g"], [1, 150, "g"], [1, 250, "g"], [1, 500, "g"], [1, 1000, "g"]],
    "bottle": [[1, 330, "ml"], [1, 500, "ml"], [1, 750, "ml"], [1, 1000, "ml"], [1, 1500, "ml"]],
    "jar": [[1, 90, "g"], [1, 180, "g"], [1, 250, "g"], [1, 350, "g"], [1, 500, "g"]],
    "tin": [[1, 140, "g"], [1, 200, "g"], [1, 400, "g"], [1, 800, "g"]],
    "can": [[1, 250, "ml"], [1, 330, "ml"], [1, 500, "ml"]],
    "tube": [[1, 50, "ml"], [1, 75, "ml"], [1, 100, "ml"], [1, 150, "ml"]],
    "tray": [[1, 250, "g"], [1, 400, "g"], [1, 500, "g"], [1, 750, "g"], [1, 1000, "g"]],
    # piece, bunch, slice: no size by default (one article); kg, g, L: sold
    # by weight/volume, the quantity is the size.
}


def _count(*counts):
    return [[n, None, None] for n in counts]


def _ml(*amounts):
    return [[1, a, "ml"] for a in amounts]


def _g(*amounts):
    return [[1, a, "g"] for a in amounts]


_CARE = {"tube": _ml(50, 75, 100, 200), "bottle": _ml(200, 250, 400, 500)}

# Per-aisle sizes, overriding UNIT_DEFAULT_SIZES for the units listed (None:
# no size). Non-food aisles mostly count articles or hold millilitres.
AISLE_SIZES = {
    "2": {"piece": _g(150, 200, 250)},  # specialty cheeses
    "3": {"box": [[5, 40, "g"], [6, 35, "g"], [8, 30, "g"]], "pack": _g(40, 50)},  # energy granola bars
    "6": {"piece": None, "pack": _count(2, 4, 6), "box": _count(2, 4, 6)},  # other
    "9": {"jar": _g(350, 400, 500, 700)},  # pasta sauce
    "10": {"piece": None, "pack": _count(2, 3, 5)},  # kitchen supplies
    "11": {"box": _count(10, 16, 20, 30), "bottle": _ml(100, 150, 250)},  # cold flu allergy
    "19": {"bottle": _ml(250, 500, 750, 1000)},  # oils vinegars
    "20": {"tube": _ml(50, 75, 100), "bottle": _ml(250, 500), "piece": None},  # oral hygiene
    "21": {"pack": _g(150, 200, 250, 400)},  # packaged cheese
    "22": {"bottle": _ml(250, 300, 400, 500), "tube": _ml(150, 200)},  # hair care
    "25": {"bottle": _ml(250, 300, 500), "piece": _g(100, 125, 150)},  # soap
    "26": {"pack": _g(250, 500, 1000), "bag": _g(250, 500, 1000), "jar": _g(100, 200)},  # coffee
    "27": {  # beers coolers
        "can": _ml(330, 500), "bottle": _ml(250, 330, 750),
        "pack": [[6, 250, "ml"], [6, 330, "ml"], [12, 330, "ml"], [24, 330, "ml"]],
    },
    "28": {"bottle": _ml(750)},  # red wines
    "36": {"pack": _g(125, 250, 500)},  # butter
    "37": {"box": _ml(500, 750, 1000)},  # ice cream ice
    "38": {"box": _g(300, 350, 400, 450)},  # frozen meals
    "40": {"bag": _g(1500, 3000, 7500), "tin": _g(400, 800), "box": [[12, 85, "g"], [12, 100, "g"]]},  # dog food
    "41": {"bag": _g(1500, 3000, 7500), "tin": _g(85, 400), "box": [[12, 85, "g"], [12, 100, "g"]]},  # cat food
    "43": {"bag": _count(4, 6, 8), "pack": _count(4, 6, 8)},  # buns rolls
    "44": {"bottle": _ml(10, 15, 30), "box": _count(10, 30)},  # eye ear care
    "45": {"bag": _g(100, 150, 250), "piece": _g(40, 50, 100), "box": _g(150, 250, 400)},  # candy chocolate
    "46": {"pack": _count(10, 14)},  # mint gum
    "47": {"bottle": _count(30, 60, 90), "box": _count(30, 60, 90)},  # vitamins supplements
    "53": {"bottle": _ml(200, 500, 1000), "jar": _ml(200, 400)},  # cream
    "54": {"pack": _count(4, 6, 8, 12, 24)},  # paper goods
    "55": {"piece": None, "pack": _count(3, 4, 5), "tube": _ml(100, 200)},  # shave needs
    "56": {"pack": _count(24, 40, 60, 80)},  # diapers wipes
    "60": {"box": _count(10, 20, 30, 50), "pack": _count(10, 20, 30, 50)},  # trash bags liners
    "62": {"bottle": _ml(750)},  # white wines
    "63": {"bag": _g(500, 1000, 2000), "box": _g(500, 1000, 2000)},  # grains rice dried goods
    "64": {"can": _ml(250, 500), "bottle": _ml(500, 750)},  # energy sports drinks
    "70": {"box": _count(10, 20, 30), "bottle": _ml(150, 250)},  # digestion
    "73": _CARE,  # facial care
    "74": {"bottle": _ml(500, 750, 1000), "box": _count(30, 50, 80)},  # dish detergents
    "75": {"bottle": _ml(1500, 2000, 3000), "box": _count(20, 30, 50)},  # laundry
    "77": {  # soft drinks
        "can": _ml(330), "bottle": _ml(500, 1500, 2000),
        "pack": [[6, 330, "ml"], [12, 330, "ml"], [6, 1500, "ml"]],
    },
    "79": {"box": _g(350, 400, 450)},  # frozen pizza
    "80": {"piece": _ml(50, 150, 200)},  # deodorants
    "82": {"piece": None},  # baby accessories
    "84": {"bottle": _ml(500, 1000, 2000)},  # milk
    "85": {"box": _count(20, 50, 100), "pack": _count(20, 50, 100)},  # food storage
    "86": {"box": _count(6, 10, 12)},  # eggs
    "87": {"piece": None, "pack": _count(2, 4, 6)},  # more household
    "91": {"bottle": _ml(1000), "pack": [[3, 200, "ml"], [1, 1000, "ml"]]},  # soy lactosefree
    "92": {"box": _g(400, 800), "jar": _g(130, 200), "bag": _g(500)},  # baby food formula
    "94": {"box": _count(20, 25, 40, 100)},  # tea
    "98": {"bottle": _ml(1000, 1500), "pack": [[6, 200, "ml"], [4, 1000, "ml"]]},  # juice nectars
    "100": {"piece": None, "pack": _count(2, 4, 6)},  # missing
    "101": {"piece": None},  # air fresheners candles
    "102": _CARE,  # baby bath body care
    "104": {"jar": _g(30, 40, 50, 80)},  # spices seasonings
    "106": {"pack": _g(150, 200, 250, 400)},  # hot dogs bacon sausage
    "107": {"bag": _g(125, 150, 200, 300)},  # chips pretzels
    "109": _CARE,  # skin care
    "111": {"pack": _count(10, 20, 50)},  # plates bowls cups flatware
    "112": {"piece": _g(400, 500, 800), "bag": _g(500, 800)},  # bread
    "114": {"bottle": _ml(500, 750, 1000)},  # cleaning products
    "115": {"bottle": _ml(500, 1000, 1500), "pack": [[6, 500, "ml"], [6, 1500, "ml"]]},  # water
    "118": {"box": _count(10, 20, 40)},  # first aid
    "119": {"box": [[4, 100, "ml"], [1, 500, "ml"], [1, 1000, "ml"]]},  # frozen dessert
    "120": {"pack": [[4, 125, "g"], [6, 100, "g"], [8, 125, "g"]], "jar": _g(450, 500, 1000)},  # yogurt
    "121": {"box": _g(375, 500, 750)},  # cereal
    "124": {"bottle": _ml(500, 700, 1000)},  # spirits
    "126": {"box": _count(16, 20, 32), "pack": _count(16, 20, 32)},  # feminine care
    "127": _CARE,  # body lotions soap
    "128": {"pack": _count(6, 8, 10)},  # tortillas flat bread
    "131": {"pack": _g(500, 1000), "box": _g(500, 1000)},  # dry pasta
    "132": {"tube": _ml(15, 30, 50, 75)},  # beauty
    "133": {"box": _count(10, 20, 30), "tube": _ml(50, 100)},  # muscles joints pain relief
    "134": {"bottle": _ml(375, 750, 1500)},  # specialty wines champagnes
}

# Departments whose "oz" are fluid ounces (beverages), plus liquid dairy aisles.
_LIQUID_DEPARTMENTS = {7}
_LIQUID_AISLES = {53, 84, 91}

_SIZE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(fl\.?\s*oz|floz|oz|lbs?|gallons?|gal|ml|liters?|litres?|l|kg|g)\b", re.IGNORECASE
)
_COUNT_RE = re.compile(r"(\d+)\s*(ct|count|pk|pack|pc|pcs)\b", re.IGNORECASE)


def _nice(amount):
    """Round a converted amount to what a label would show (340 g, 473 mL)."""
    return int(round(amount / 5.0) * 5) if amount >= 50 else int(round(amount))


def parse_size(name, aisle_id, department_id):
    """The package size stated in an (English) product name, converted to
    metric ("12 oz" -> 340 g, "16 fl oz" -> 475 mL, "6 ct" -> 6 pieces), or
    None. "oz" alone means fluid ounces for beverages and liquid dairy."""
    liquid = department_id in _LIQUID_DEPARTMENTS or aisle_id in _LIQUID_AISLES
    amount = unit = None
    match = _SIZE_RE.search(name)
    if match:
        value, symbol = float(match.group(1)), match.group(2).lower().replace(" ", "").replace(".", "")
        if symbol in ("floz",) or (symbol == "oz" and liquid):
            amount, unit = value * 29.57, "ml"
        elif symbol == "oz":
            amount, unit = value * 28.35, "g"
        elif symbol.startswith("lb"):
            amount, unit = value * 453.6, "g"
        elif symbol.startswith("gal"):
            amount, unit = value * 3785.0, "ml"
        elif symbol == "ml":
            amount, unit = value, "ml"
        elif symbol.startswith("lit") or symbol == "l":
            amount, unit = value * 1000, "ml"
        elif symbol == "kg":
            amount, unit = value * 1000, "g"
        elif symbol == "g":
            amount, unit = value, "g"
        if amount is not None and not 1 <= amount <= 20000:
            amount = unit = None
    elif re.search(r"\bhalf gallon\b", name, re.IGNORECASE):
        amount, unit = 1890.0, "ml"
    elif re.search(r"\bgallon\b", name, re.IGNORECASE):
        amount, unit = 3785.0, "ml"
    count_match = _COUNT_RE.search(name)
    count = int(count_match.group(1)) if count_match and 1 < int(count_match.group(1)) <= 500 else 1
    if amount is not None:
        # "12 Pk ... 12 Floz": 12 x 355 mL; a count alone with a total weight
        # ("Goldfish 9ct") stays the total.
        return [count, _nice(amount), unit] if count > 1 and amount < 1000 else [1, _nice(amount), unit]
    if count > 1:
        return [count, None, None]
    return None


# -- premium products ------------------------------------------------------------

# Organic / premium products cost more than their plain equivalent: their
# base price gets this surcharge (applied after the draw in the product's
# price range, so they may exceed its upper bound).
PREMIUM_SURCHARGE = 1.25
PREMIUM_RE = re.compile(
    r"\b(organic|premium|artisan|artisanal|gourmet|grass[- ]fed|wild caught|free range|pasture raised)\b",
    re.IGNORECASE,
)

# -- seasonality -----------------------------------------------------------------

# Fresh produce aisles where seasonality applies (fresh fruits, fresh
# vegetables, packaged vegetables fruits, packaged produce, fresh herbs).
SEASONAL_AISLES = {24, 83, 123, 32, 16}

# (pattern on the English name, months in season in the northern hemisphere).
SEASONS = [
    (r"strawberr", [5, 6, 7]),
    (r"\bcherr(y|ies)\b", [6, 7]),
    (r"\b(peach|peaches|nectarines?|apricots?)\b", [6, 7, 8]),
    (r"\b(melons?|watermelons?|cantaloupes?|honeydew)\b", [6, 7, 8]),
    (r"\basparagus\b", [4, 5, 6]),
    (r"\b(pumpkins?|butternut|acorn squash|spaghetti squash)\b", [9, 10, 11, 12]),
    (r"\b(clementines?|mandarins?|tangerines?|satsumas?|cuties)\b", [11, 12, 1, 2]),
    (r"\bcorn\b", [7, 8, 9]),
    (r"\btomato(es)?\b", [6, 7, 8, 9]),
    (r"\bzucchini\b", [6, 7, 8, 9]),
    (r"\bgrapes?\b", [8, 9, 10]),
    (r"\bblueberr", [6, 7, 8]),
    (r"\braspberr", [6, 7, 8, 9]),
    (r"\bblackberr", [7, 8, 9]),
    (r"\bpears?\b", [9, 10, 11, 12, 1]),
    (r"\bbrussels\b", [10, 11, 12, 1, 2]),
    (r"\bkale\b", [10, 11, 12, 1, 2, 3]),
    (r"\bcranberr", [10, 11, 12]),
    (r"\bpomegranates?\b", [10, 11, 12, 1]),
    (r"\bfigs?\b", [8, 9, 10]),
    (r"\brhubarb\b", [4, 5, 6]),
    (r"\bplums?\b", [7, 8, 9]),
    (r"\bapples?\b", [9, 10, 11, 12, 1, 2, 3]),
    (r"\bleeks?\b", [10, 11, 12, 1, 2, 3]),
    (r"\b(eggplants?|aubergines?)\b", [6, 7, 8, 9]),
]

# Pick weight multipliers for seasonal products, in / out of season.
SEASONAL_FACTORS = {"in": 2.0, "out": 0.4}

# Countries in the southern hemisphere: seasons shifted by six months.
SOUTHERN_HEMISPHERE_COUNTRIES = ["AU", "NZ", "AR", "CL", "ZA", "BR", "UY", "PY"]


def season_mask(name, aisle_id):
    """12-bit mask of the months a fresh product is in season (bit 0 =
    January), 0 if it has no season or isn't fresh produce."""
    if aisle_id not in SEASONAL_AISLES:
        return 0
    for pattern, months in SEASONS:
        if re.search(pattern, name, re.IGNORECASE):
            return sum(1 << (month - 1) for month in months)
    return 0


# -- opening hours ---------------------------------------------------------------

DEFAULT_OPENING_HOURS = [8, 20]
COUNTRY_OPENING_HOURS = {
    "FR": [8, 21], "BE": [8, 20], "LU": [8, 20], "NL": [8, 22], "DE": [8, 20], "AT": [8, 19],
    "CH": [8, 19], "IT": [8, 21], "ES": [9, 22], "PT": [8, 22], "GB": [7, 22], "IE": [8, 22],
    "US": [7, 23], "CA": [7, 23], "AU": [7, 22], "NZ": [7, 22], "PL": [6, 22], "NO": [7, 23],
    "SE": [8, 22], "DK": [8, 22], "FI": [7, 22], "JP": [9, 22], "KR": [10, 22], "MX": [7, 23],
    "BR": [7, 22],
}

# -- VAT -------------------------------------------------------------------------

# [food rate, standard rate, prices include the tax]. Approximate rates: many
# countries have more brackets (e.g. sweets or soft drinks at the standard
# rate); here food aisles get the food rate, non-food aisles (alcohol,
# household, personal care, pets, baby care) the standard rate. In the US
# and Canada, shelf prices exclude a sales tax added at checkout (the US
# rate is an average of state + local rates; groceries are mostly exempt).
COUNTRY_VAT = {
    "FR": [0.055, 0.20, True], "DE": [0.07, 0.19, True], "AT": [0.10, 0.20, True], "BE": [0.06, 0.21, True],
    "NL": [0.09, 0.21, True], "LU": [0.03, 0.17, True], "IE": [0.0, 0.23, True], "IT": [0.10, 0.22, True],
    "ES": [0.10, 0.21, True], "PT": [0.06, 0.23, True], "GR": [0.13, 0.24, True], "FI": [0.135, 0.255, True],
    "CH": [0.026, 0.081, True], "GB": [0.0, 0.20, True], "PL": [0.05, 0.23, True], "SE": [0.12, 0.25, True],
    "NO": [0.15, 0.25, True], "DK": [0.25, 0.25, True], "CZ": [0.12, 0.21, True], "HU": [0.18, 0.27, True],
    "JP": [0.08, 0.10, True], "AU": [0.0, 0.10, True], "NZ": [0.15, 0.15, True], "MX": [0.0, 0.16, True],
    "IN": [0.05, 0.18, True], "US": [0.0, 0.07, False], "CA": [0.0, 0.13, False],
}

# Departments taxed at the standard rate: other, alcohol, pets, personal
# care, household; plus non-food baby aisles (diapers, accessories, bath).
STANDARD_RATE_DEPARTMENTS = {2, 5, 8, 11, 17}
STANDARD_RATE_AISLES = {56, 82, 102}

# -- complementary aisles --------------------------------------------------------

# [aisle, complementary aisle, probability]: after an item from `aisle`, a
# coherent basket adds an item from the complementary aisle with that
# probability (pasta -> pasta sauce, cereal -> milk...). Hand-made: the
# Instacart co-purchase data isn't in this repository.
AISLE_COMPLEMENTS = [
    [131, 9, 0.5], [9, 131, 0.4], [121, 84, 0.4], [107, 67, 0.25], [107, 51, 0.15],
    [43, 106, 0.3], [106, 43, 0.3], [128, 30, 0.3], [78, 21, 0.25], [78, 2, 0.15],
    [112, 36, 0.2], [112, 88, 0.2], [26, 53, 0.3], [94, 29, 0.2], [130, 29, 0.4],
    [79, 77, 0.2], [27, 107, 0.25], [28, 2, 0.25], [37, 103, 0.2], [59, 128, 0.15],
    [63, 66, 0.2], [66, 63, 0.2], [105, 86, 0.3], [105, 17, 0.3], [17, 86, 0.25],
]

# -- store names / promotions ----------------------------------------------------

# Templates for fictional store names, filled with a Faker city / last name.
STORE_NAME_TEMPLATES = {
    "en": ["{city} Fresh Market", "{last_name}'s Grocery", "{city} Supermarket", "{last_name} Foods"],
    "fr": ["Supermarché de {city}", "Marché {last_name}", "Hyper {city}", "Épicerie {last_name}"],
    "it": ["Supermercato {city}", "Alimentari {last_name}", "Market {city}"],
    "es": ["Supermercado {city}", "Mercado {last_name}", "Ultramarinos {last_name}"],
    "pt": ["Supermercado {city}", "Mercearia {last_name}", "Mercado {city}"],
    "de": ["{last_name} Markt", "Supermarkt {city}", "Frischemarkt {last_name}"],
}

# Promotion labels per language; {pct} is replaced by the percentage.
PROMOTION_LABELS = {
    "percent": {"en": "-{pct}%", "fr": "-{pct} %", "it": "-{pct}%", "es": "-{pct}%", "pt": "-{pct}%",
                "de": "-{pct} %"},
    "buy2get1": {"en": "Buy 2, get 1 free", "fr": "2 achetés + 1 offert", "it": "Prendi 3 paghi 2",
                 "es": "3x2", "pt": "Leve 3 pague 2", "de": "3 für 2"},
    "second_half": {"en": "2nd at half price", "fr": "2e à -50 %", "it": "2° a metà prezzo",
                    "es": "2ª unidad a mitad de precio", "pt": "2.ª unidade a metade do preço",
                    "de": "2. Artikel -50 %"},
}
