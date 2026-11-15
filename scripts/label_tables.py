"""
Product labels and diets, used by build_data.py.

- Labels are what a product's (English) name claims: "Organic", "Gluten
  Free", "Vegan"... (plus a few implied ones: a vegan or plant-based milk is
  lactose free). Read from the name only: a product that doesn't say it is
  gluten free isn't labelled gluten free, even when it naturally is.
- Diets say which products a customer following that diet may buy: some
  aisles are excluded (meat, seafood), some only allowed for products
  carrying the right label (bread, pasta and cereal for gluten free; dairy
  for lactose free), and names mentioning e.g. chicken or bacon are
  excluded for vegetarians wherever they are shelved (soups, frozen meals,
  pizza).

Approximate, "faker-grade" data built from product names: fine for test
data, never to be relied on for real dietary or allergy information.
"""
import re

# Label keys, in bit order (bit 0 = first key) of the products' `labels` mask.
LABELS = ["organic", "gluten_free", "vegan", "lactose_free", "sugar_free", "low_fat", "whole_grain", "kosher",
          "non_gmo"]

PLANT_MILK = r"(?:almond|soy|soya|oat|coconut|rice|cashew|hemp|pea|macadamia) ?(?:milk|beverage|creamer|yogurt|yoghurt)"

LABEL_PATTERNS = {
    "organic": r"\borganic\b",
    "gluten_free": r"\bgluten[- ]?free\b|\bno gluten\b|\bwithout gluten\b",
    "vegan": r"\bvegan\b",
    "lactose_free": rf"\blactose[- ]?free\b|\bdairy[- ]?free\b|\bnon[- ]?dairy\b|\bvegan\b|\b{PLANT_MILK}\b",
    "sugar_free": r"\bsugar[- ]?free\b|\bno sugar added\b|\bno added sugar\b|\bzero sugar\b",
    "low_fat": r"\blow[- ]?fat\b|\bfat[- ]?free\b|\breduced[- ]fat\b|\bnon[- ]?fat\b|\bskim\b",
    "whole_grain": r"\bwhole[- ]grains?\b|\bwhole[- ]wheat\b",
    "kosher": r"\bkosher\b",
    "non_gmo": r"\bnon[- ]?gmo\b",
}
_LABEL_RES = {key: re.compile(pattern, re.IGNORECASE) for key, pattern in LABEL_PATTERNS.items()}
# The "soy lactosefree" aisle only holds lactose-free products.
LABEL_AISLES = {"lactose_free": {91}}

# Diet keys, in bit order of the products' `diets` mask.
DIETS = ["vegetarian", "vegan", "gluten_free", "lactose_free"]

MEAT_AISLES = {7, 15, 34, 35, 39, 49, 95, 96, 106, 122}
DAIRY_AISLES = {2, 21, 36, 37, 53, 71, 84, 108, 119, 120}
GLUTEN_AISLES = {3, 4, 8, 12, 13, 17, 27, 38, 43, 48, 52, 57, 58, 61, 78, 79, 93, 105, 112, 121, 128, 129, 130, 131}
# Non-food aisles: no diet concern (pets, household, personal care, babies' non-food).
NON_FOOD_DEPARTMENTS = {2, 8, 11, 17}  # other, pets, personal care, household

MEAT_RE = re.compile(
    r"\b(?:chicken|beef|pork|turkey|bacon|ham|hams|sausages?|salami|pepperoni|prosciutto|chorizo|jerky|veal|lamb|"
    r"duck|meat ?balls?|meatloaf|hot ?dogs?|bratwurst|brisket|steak|carnitas|pastrami|bologna|"
    r"fish|salmon|tuna|cod|tilapia|shrimps?|prawns?|crab|lobster|anchov(?:y|ies)|sardines?|clams?|oysters?|"
    r"mussels?|scallops?|calamari|gelatin|lard|bone broth)\b",
    re.IGNORECASE,
)
# Meat words used for vegetarian versions ("Meatless Chicken Strips"), and
# fish-free uses of the words above ("Fish Sauce" stays excluded).
MEAT_FREE_RE = re.compile(r"\b(?:meatless|meat[- ]?free|vegetarian|veggie|vegan|plant[- ]based|tofurky|chik'n|"
                          r"chick'n|beefless|soy ?rizo)\b", re.IGNORECASE)
GLUTEN_RE = re.compile(
    r"\b(?:wheat|flour|barley|rye|spelt|semolina|couscous|bulgur|seitan|malt|noodles?|pasta|spaghetti|macaroni|"
    r"penne|lasagna|ravioli|tortellini|gnocchi|bread|breaded|breadcrumbs?|croutons?|crackers?|cookies?|cakes?|"
    r"brownies?|muffins?|bagels?|croissants?|pretzels?|pastr(?:y|ies)|pie|pies|pizza|dumplings?|wafers?|"
    r"waffles?|pancakes?|biscuits?|beer|ale|lager|stout)\b",
    re.IGNORECASE,
)
ANIMAL_RE = re.compile(
    r"\b(?:honey|eggs?|cheeses?|cheddar|mozzarella|parmesan|ricotta|feta|brie|gouda|whey|yogh?urts?|"
    r"butter|buttermilk|milk|cream|ghee|kefir|custard|mayonnaise|mayo)\b",
    re.IGNORECASE,
)
PLANT_RE = re.compile(rf"\b{PLANT_MILK}\b|\b(?:peanut|almond|cashew|sunflower|cocoa|shea|apple|nut|seed|soy) butter\b|"
                      r"\bcoconut cream\b|\bcream of tartar\b|\bvegan (?:mayo|mayonnaise|cheese|butter)\b",
                      re.IGNORECASE)


def labels_mask(name, aisle_id):
    """Bit mask of the LABELS a product's English name claims."""
    mask = 0
    for bit, key in enumerate(LABELS):
        if _LABEL_RES[key].search(name) or aisle_id in LABEL_AISLES.get(key, ()):
            mask |= 1 << bit
    return mask


def _has(mask, label):
    return bool(mask & (1 << LABELS.index(label)))


def diets_mask(name, aisle_id, department_id, labels):
    """Bit mask of the DIETS a product is compatible with."""
    if department_id in NON_FOOD_DEPARTMENTS:
        return (1 << len(DIETS)) - 1
    vegan_label = _has(labels, "vegan")
    meat = (aisle_id in MEAT_AISLES or bool(MEAT_RE.search(name))) and not MEAT_FREE_RE.search(name)
    vegetarian = not meat or vegan_label
    lactose_free = _has(labels, "lactose_free") or (aisle_id not in DAIRY_AISLES and not (
        ANIMAL_RE.search(name) and re.search(r"\b(?:milk|cream|cheeses?|butter|yogh?urts?|whey|buttermilk|kefir)\b",
                                             name, re.IGNORECASE) and not PLANT_RE.search(name)))
    plant = bool(PLANT_RE.search(name))
    vegan = vegan_label or (vegetarian and (aisle_id not in DAIRY_AISLES | {86} or plant) and not (
        ANIMAL_RE.search(name) and not plant))
    gluten_free = _has(labels, "gluten_free") or (aisle_id not in GLUTEN_AISLES and not GLUTEN_RE.search(name))
    mask = 0
    for bit, ok in enumerate((vegetarian, vegan, gluten_free, lactose_free)):
        if ok:
            mask |= 1 << bit
    return mask


# Localized names, for display ("Bio", "sans gluten"...).
LABEL_NAMES = {
    "organic": {"en": "organic", "fr": "bio", "it": "biologico", "es": "ecológico", "pt": "biológico", "de": "Bio"},
    "gluten_free": {"en": "gluten free", "fr": "sans gluten", "it": "senza glutine", "es": "sin gluten",
                    "pt": "sem glúten", "de": "glutenfrei"},
    "vegan": {"en": "vegan", "fr": "végan", "it": "vegano", "es": "vegano", "pt": "vegano", "de": "vegan"},
    "lactose_free": {"en": "lactose free", "fr": "sans lactose", "it": "senza lattosio", "es": "sin lactosa",
                     "pt": "sem lactose", "de": "laktosefrei"},
    "sugar_free": {"en": "sugar free", "fr": "sans sucre", "it": "senza zucchero", "es": "sin azúcar",
                   "pt": "sem açúcar", "de": "zuckerfrei"},
    "low_fat": {"en": "low fat", "fr": "allégé", "it": "magro", "es": "bajo en grasa", "pt": "magro",
                "de": "fettarm"},
    "whole_grain": {"en": "whole grain", "fr": "complet", "it": "integrale", "es": "integral", "pt": "integral",
                    "de": "Vollkorn"},
    "kosher": {"en": "kosher", "fr": "casher", "it": "kosher", "es": "kosher", "pt": "kosher", "de": "koscher"},
    "non_gmo": {"en": "non-GMO", "fr": "sans OGM", "it": "senza OGM", "es": "sin OGM", "pt": "sem OGM",
                "de": "gentechnikfrei"},
}
DIET_NAMES = {
    "vegetarian": {"en": "vegetarian", "fr": "végétarien", "it": "vegetariano", "es": "vegetariano",
                   "pt": "vegetariano", "de": "vegetarisch"},
    "vegan": LABEL_NAMES["vegan"],
    "gluten_free": LABEL_NAMES["gluten_free"],
    "lactose_free": LABEL_NAMES["lactose_free"],
}
# Share of customers following each diet in customer_profile(diet="random"):
# rough orders of magnitude for Western Europe / North America.
DIET_SHARES = {"vegetarian": 0.05, "vegan": 0.02, "gluten_free": 0.02, "lactose_free": 0.04}
