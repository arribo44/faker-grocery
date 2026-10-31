# Faker Grocery Store Provider

**A custom [Faker](https://faker.readthedocs.io/) provider for generating realistic fake data for supermarkets and hypermarkets: departments, aisles, products, prices and randomized shopping lists.**

The catalog is built from the [Instacart Market Basket Analysis](https://www.kaggle.com/c/instacart-market-basket-analysis) open dataset: **21 departments**, **134 aisles** and **~49,700 real products**.

---

## 🌍 Supported languages

| Language | Locale examples | Departments / Aisles | Product names |
|----------|------------------|-----------------------|----------------|
| `en` | `en_US` | Original English names | Original English names |
| `fr` | `fr_FR`, `fr_CA`, `fr_BE`... | Hand-translated | Natural translation for the 2,000 most ordered products (~2/3 of generated products); approximate automatic translation for the rest |
| `it` | `it_IT` | Hand-translated | Approximate automatic translation |
| `es` | `es_ES`, `es_MX`... | Hand-translated | Approximate automatic translation |
| `pt` | `pt_PT`, `pt_BR` | Hand-translated (European Portuguese) | Approximate automatic translation |
| `de` | `de_DE`, `de_AT`, `de_CH` | Hand-translated | Approximate automatic translation (word order kept, see below) |

> **Default language**: `en` (used for any locale not listed above, e.g. as a fallback).

Unit labels are translated in every language ("bouteille", "bottiglia",
"botella", "garrafa", "Flasche"). Only the product names of the language(s)
you actually use are loaded (one `names_<lang>.json` file per language).

French product names come from two sources:

- **The 2,000 most ordered products** have a natural, checked translation
  (`scripts/translations/product_names_fr.json`): French shelf-label style,
  brands kept as is - "Organic Raspberries" -> "Framboises bio", "White
  Balsamic Vinegar" -> "Vinaigre balsamique blanc". Since products are picked
  by popularity, they make up about **two thirds** of generated products.
- **All other products** are translated automatically: common expressions
  first ("gluten free" -> "sans gluten", `phrases_fr.json`), then the word
  order of fully known segments is reversed (French puts the noun first),
  then word-by-word substitution with a ~860-word grocery dictionary
  (`word_dict_fr.json`). Brand names stay untranslated. This is approximate,
  "faker-grade" output ("Hot-dogs Bœuf Bio"), fine for tests and demos but
  not a professional localization.

Italian, Spanish, Portuguese and German product names use that same
automatic translation (with their own `word_dict_<lang>.json` and
`phrases_<lang>.json`): "Biscotti Gocce di cioccolato Senza glutine",
"Galletas Pepitas de chocolate Sin gluten". German keeps the English word
order, since it also puts the noun last ("Glutenfrei Schokoladenstückchen
Kekse"). They don't have hand-checked names for popular products yet.

---

## 📦 Installation

Requires Python 3.11+ and Faker 20+.

```bash
cd faker_grocery
pip install -e .
```

---

## 🚀 Usage

```python
from faker import Faker
from faker_grocery import GroceryStoreProvider

fake = Faker("fr_FR")          # or "en_US"
fake.add_provider(GroceryStoreProvider)
```

With a multi-locale `Faker([...])`, Faker's proxy does not support
`add_provider()`: add the provider to each locale's generator instead.

```python
fake = Faker(["fr_FR", "en_US"])
for locale in ("fr_FR", "en_US"):
    fake[locale].add_provider(GroceryStoreProvider)

fake["fr_FR"].grocery_department()      # "produits laitiers et œufs"
```

Unknown ids/names and invalid arguments (e.g. `min_items > max_items`,
`family_size < 1`, `open_hour >= close_hour`, only one of
`min_price`/`max_price`) raise `ValueError`.

### 🏬 Departments & aisles

```python
fake.grocery_department()               # "produits laitiers et œufs"
fake.department_id()                    # 16
fake.grocery_department_name(16)        # "produits laitiers et œufs"

fake.aisle()                            # "yaourt"
fake.aisle(department="produits laitiers et œufs")   # restricted to that department
fake.aisle(department=16)               # same, by id
fake.aisle_id(department=16)            # 120
fake.aisle_name(120)                    # "yaourt"
```

> **Why `grocery_department()`?** Faker's own address providers already use
> `department()` / `department_name()` for administrative departments
> (`fr_FR`: `("18", "Cher")`, `"Sarthe"`; `es_CO`: `"Cesar"`). The store
> methods are therefore named `grocery_department()` /
> `grocery_department_name()`, and adding `GroceryStoreProvider` leaves
> Faker's methods untouched:
>
> ```python
> fake = Faker("fr_FR")
> fake.add_provider(GroceryStoreProvider)
> fake.department()                # ("18", "Cher")  - Faker's, unchanged
> fake.grocery_department()        # "produits laitiers et œufs"
> ```
>
> The former names `department()` / `department_name()` still work as
> deprecated aliases (with a `DeprecationWarning`) in locales where they
> don't clash, e.g. `en_US`, and will be removed in a future version.

### 🛒 Products

```python
fake.product()                          # "Yaourt Grec Vanille"
fake.product(aisle="yaourt")            # restricted to an aisle (name or id)
fake.product(department=16)             # restricted to a department (name or id)
fake.product(weighted=False)            # uniform pick instead of popularity-weighted (see below)

fake.product_record()
# {
#     'id': 12345,
#     'name': 'Yaourt Grec Vanille',
#     'aisle_id': 120,
#     'aisle': 'yaourt',
#     'department_id': 16,
#     'department': 'produits laitiers et œufs',
#     'base_price': 2.10,
#     'price': 2.04,
#     'currency': 'EUR',
#     'unit': 'pot',                # the product's own, fixed unit
#     'price_per': 'pot',           # what the prices are for: one article, or one kg/L
# }

fake.product_name(12345)                # look up a specific product id
```

Products are picked **in proportion to their popularity**: how many times
each one was ordered in the ~32M order lines of the Instacart data. Bananas,
strawberries, milk or avocados come up far more often than niche items, as
in a real basket. Pass `weighted=False` to `product()`, `product_record()`,
`grocery_item()` or `grocery_list()` for a uniform pick across the catalog.

### 💰 Prices, quantities, units

Every product has a stable catalog **`base_price`** (its "probable price"),
generated once from its department's typical range - or, for products sold
by weight or volume, as a **price per kg or per L** from its aisle's own
range (fresh fruit 1.50-8 EUR/kg, seafood counter 12-45 EUR/kg, milk
0.90-2.50 EUR/L...). Any time you actually price a product — via
`price(product=...)`, `product_record()` or `grocery_item()` — you get that
base price jittered by a random **±5%**, the way real shelf prices drift a
little from one day/store to the next.

Every product also has **one fixed unit**, chosen among the units plausible
for its aisle: milk is sold by the litre or the bottle, spices in jars,
canned beans in food cans, meat at the counter by the kg or g... A given
product is always sold the same way.

```python
fake.price()                            # 4.77  (random department's typical range)
fake.price(department=16)               # price within the dairy/eggs range
fake.price(min_price=10.0, max_price=20.0)   # both bounds are required
fake.price(product=12345)               # that product's base_price, jittered +/-5%

record = fake.product_record()
record["base_price"]                    # 2.10  (stable catalog reference)
record["price"]                         # 2.04  (this instance, +/-5% jitter)

fake.quantity()                         # 3   (1 to 10, a count of articles)
fake.quantity(max_quantity=5)           # 1 to 5

fake.unit()                             # "pièce(s)", "kg", "bouteille", ... (any unit)
fake.unit(aisle=104)                    # "pot" - units plausible for that aisle (spices)
fake.unit(department=7)                 # units plausible for that department
                                         # (e.g. "L"/"bouteille"/"canette" for beverages)
```

### 💱 Currency

Prices are generated in the currency of the locale's country: `en_US` → USD,
`en_GB` → GBP, `fr_CA` → CAD, `fr_CH` → CHF, `ja_JP` → JPY, etc. Eurozone
countries, and any country not in the list, use EUR (the catalog's base
currency). Prices are converted from EUR with **fixed approximate rates**
(not live exchange rates), then adjusted to the country's approximate
**grocery price level**: a plain conversion would make a basket cost the
same everywhere, whereas groceries are much dearer in Switzerland and much
cheaper in India. Within the eurozone the level is per country too
(Portugal cheaper, Ireland dearer). Average default basket: ~85 EUR in
France, ~69 EUR in Portugal, ~93 EUR in Ireland, ~107 USD in the US,
~128 CHF in Switzerland. Prices are rounded to the currency's minor unit
(whole numbers for JPY/HUF). Every priced dict carries a `currency` field.

```python
fake = Faker("en_US")
fake.add_provider(GroceryStoreProvider)

fake.grocery_currency()                 # "USD"
fake.grocery_currency(symbol=True)      # "$"
fake.product_record()["currency"]       # "USD"

fake.set_grocery_currency("GBP")        # override the locale's currency
fake.set_grocery_currency(None)         # back to the locale's default
```

`price(min_price=..., max_price=...)` takes its bounds as already in the
current currency. The method is named `grocery_currency()` rather than
`currency_code()` so it doesn't shadow Faker's own `currency_code()`. When
you override the currency, prices follow that currency's main country
(a `pt_PT` faker set to USD gets US prices).
Supported currencies: EUR, USD, GBP, CHF, CAD, AUD, NZD, SEK, NOK, DKK, PLN,
CZK, HUF, JPY, INR, BRL, MXN.

### 📝 Grocery items & shopping lists

```python
fake.grocery_item()
# {
#     'product': 'Yaourt Grec Vanille',
#     'product_id': 12345,
#     'aisle': 'yaourt',
#     'department': 'produits laitiers et œufs',
#     'quantity': 3,
#     'unit': 'pot',                # the product's own unit (always the same for it)
#     'unit_price': 2.15,           # base_price jittered +/-5%
#     'price_per': 'pot',           # what unit_price is for (here: one article)
#     'total_price': 6.45,
#     'currency': 'EUR',
# }

# Items sold by weight or volume get a realistic measured quantity and are
# priced per kg or per L (no more "7 kg of basil"):
# {'product': 'Non traité Lent Cuit Jambon', 'quantity': 100, 'unit': 'g',
#  'unit_price': 17.53, 'price_per': 'kg', 'total_price': 1.75, ...}
# kg: 0.2 kg upwards in 0.05 kg steps; g: 100 g upwards in 50 g steps;
# L: 0.5 L steps - the upper bound grows with family_size. Only fresh
# produce, counters (meat, seafood, cheese, deli), bulk goods and drinks
# are sold this way; everything else is counted.

# family_size defaults to 2 (a couple). It scales the default item-count
# range and the plausible quantity of each item (bigger households buy more).
shopping_list = fake.grocery_list()
# {
#     'items': [ ... grocery_item dicts ... ],
#     'item_count': 9,
#     'family_size': 2,
#     'total': 42.31,
#     'currency': 'EUR',
# }

fake.grocery_list(family_size=5)                       # bigger default basket
fake.grocery_list(min_items=3, max_items=8)             # override the item-count range explicitly
fake.grocery_list(department="fruits et légumes")       # restrict the whole list to one department

# Optionally attach a plausible shopping date/time (within the last year,
# during store opening hours, by default 8:00-20:00). Days and hours follow
# the locale's weekly shopping pattern (see below; weighted=False for a
# uniform pick):
shopping_list = fake.grocery_list(with_datetime=True)
shopping_list["shopping_datetime"]      # datetime.datetime(2026, 3, 12, 17, 42, 8)

# Or pin it to a specific date (random time on that day):
import datetime
fake.grocery_list(date=datetime.date(2025, 12, 24))

# Standalone helper used internally by grocery_list():
fake.shopping_datetime()                                # random date (last year) + time (8h-20h)
fake.shopping_datetime(date=datetime.date(2025, 12, 24))
fake.shopping_datetime(open_hour=9, close_hour=19)
fake.shopping_datetime(weighted=False)                  # uniform day and hour
```

#### 🕒 Shopping patterns

The weekly pattern of shopping days and hours depends on the locale's country:

| Pattern | Countries | Shape |
|---|---|---|
| `instacart_us` (default) | all others (US, GB, ...) | measured on ~3.4M US online orders: Sunday/Monday busiest, quiet at opening time |
| `sunday_morning` | FR, BE, LU, ES, IT, PT | Saturday busiest, lunchtime and after-work peaks, Sunday morning only |
| `sunday_closed` | DE, AT, CH, PL, NO | Saturday busiest, shops closed on Sunday |

```python
fake.grocery_shopping_pattern()                     # "sunday_morning" for fr_FR
fake.set_grocery_shopping_pattern("instacart_us")   # override
fake.set_grocery_shopping_pattern(None)             # back to the locale's default
```

Days a pattern has shops closed never come up, unless you force one with
`date=` (its time is then uniform within opening hours). The two European
patterns are hand-made heuristics, not measured data. Instacart's
day-of-week encoding is undocumented and read as 0 = Sunday.

---

### 🔤 Type hints

The package is fully typed (it ships a `py.typed` marker), and the dicts it
returns are described by `TypedDict`s: `ProductRecord`, `GroceryItem` and
`GroceryList`. Editors then autocomplete their keys, and mypy/pyright flag
typos and type errors:

```text
error: TypedDict "GroceryItem" has no key "totl_price"
note: Did you mean "total_price"?
```

Faker attaches provider methods to `fake` at runtime, so type checkers
can't see the signature of `fake.grocery_item()` & co. by themselves. Two
ways to get typed results:

```python
from faker_grocery import GroceryItem, GroceryStoreProvider

# 1. Annotate the result of a call on the Faker instance
item: GroceryItem = fake.grocery_item()

# 2. Or call the provider directly: everything is then typed automatically
grocery = GroceryStoreProvider(fake)
basket = grocery.grocery_list()          # GroceryList
basket["items"][0]["unit_price"]         # float
```

Prices are typed `float`; they are ints for currencies without minor units
(JPY, HUF), which type checkers accept wherever a float is expected.

---

## 🎯 Demo

```bash
python -m faker_grocery
```

For a complete demo with more examples per feature and both locales, see [`examples/basic_usage.py`](examples/basic_usage.py).

---

## 🧱 Data layout

A single JSON file, `faker_grocery/data/grocery_data.json`, holds the whole catalog:

- `departments`: `{department_id: {language: name}}`
- `aisles`: `{aisle_id: {language: name, department_id: int}}` (each aisle belongs to exactly one department)
- `products`: compact rows `[id, aisle_id, department_id, base_price, order_count, unit, name_en]` (`order_count`: popularity, see below; `unit`: the product's fixed unit key; `base_price` is per kg/L for measured units)
- translated product names live in separate files, `faker_grocery/data/names_<lang>.json` (a list parallel to `products`, listed in `meta.name_files`), loaded on first use of that language
- `price_ranges`: `{department_id: [min_price, max_price]}` (in the base currency, EUR)
- `currencies`: `{code: {symbol, rate, price_level, decimals}}` - fixed approximate EUR -> currency rates and grocery price levels
- `country_currencies`: `{country_code: currency_code}` - default currency per locale country (unlisted countries use EUR)
- `country_price_levels`: `{country_code: level}` - grocery price level relative to France, used when prices are in the country's own currency
- `unit_labels`: `{unit_key: {language: label}}` (e.g. `"bottle": {"en": "bottle", "fr": "bouteille"}`)
- `aisle_units`: `{aisle_id: [unit_key, ...]}` - units plausible for each aisle; each product's fixed unit is one of them
- `department_units`: `{department_id: [unit_key, ...]}` - union of the department's aisle units (used by `unit(department=...)`)
- `measured_units`: `{unit_key: {min, base, per_person, step, price_per, factor}}` - quantity ranges and pricing basis of units sold by weight/volume
- `measured_price_ranges`: `{aisle_id: [min, max]}` - EUR per kg/L for aisles with measured units
- `shopping_patterns`: `{name: [weekday][hour] weights}` (weekday 0 = Monday) and `country_shopping_patterns`: `{country_code: name}` - realistic shopping days/hours
- `meta`: supported/default languages, name files, base currency, source, field layout

> `DATAS/*.csv` (the raw Instacart source: `aisles.csv`, `departments.csv`, `products.csv`, plus the aggregated order statistics `order_times.csv` and `product_popularity.csv`) is **not** shipped in the installed package - only `grocery_data.json` is (see `MANIFEST.in` and `[tool.setuptools.package-data]` in `pyproject.toml`), and using the library never touches `DATAS/`. It **is** kept versioned in the repository, though: `scripts/build_data.py` always rebuilds the catalog from these CSVs (never from `grocery_data.json` itself), so they're the only way to regenerate the data at all - including to add a new language later (see below).

> The two statistics files are themselves aggregated from the much larger
> Instacart `orders.csv` (~109 MB) and `order_products__prior.csv` (~578 MB),
> which are **not** versioned. They only need regenerating if the source data
> changes: download them from the Kaggle dataset (see below), then run
> `python scripts/build_order_stats.py path/to/orders.csv path/to/order_products__prior.csv`
> followed by `python scripts/build_data.py`.

## 🌐 Adding a new language

The files are generated by [`scripts/build_data.py`](scripts/build_data.py) from the raw CSVs in `DATAS/` (`aisles.csv`, `departments.csv`, `products.csv`) plus the translation files in `scripts/translations/`. To add a language (e.g. `nl`):

1. Create `scripts/translations/departments_nl.json` and `aisles_nl.json` (21 and 134 hand-translated entries).
2. Create `scripts/translations/word_dict_nl.json` and `phrases_nl.json`, with the same keys as `word_dict_fr.json` / `phrases_fr.json` (a ~860-word grocery vocabulary and ~90 multi-word expressions translated as a whole).
3. Optionally, create `scripts/translations/product_names_nl.json` (`{product_id: name}`) with natural translations of the most ordered products - they take precedence over the automatic translation. See `product_names_fr.json`.
4. Add `"nl"` to `TRANSLATED_LANGUAGES`, and a `"nl"` label to every entry of `UNIT_LABELS`, in `scripts/build_data.py`. If the language puts the noun first (like French, Italian, Spanish, Portuguese), also add it to `NOUN_FIRST_LANGUAGES` so word order is reversed.
5. Re-run:
   ```bash
   python scripts/build_data.py
   ```

---

## 🧪 Tests

```bash
pip install -e ".[dev]"
pytest
ruff check .
mypy faker_grocery tests/test_typing.py
```

CI (`.github/workflows/ci.yml`) runs the linter, the type checker, the test
suite on Python 3.11-3.14 (plus the oldest supported Faker, 20.0.0) and a
package build.

---

## 📊 Data source & license

The product catalog (`DATAS/*.csv`, and the `grocery_data.json` built from
it) contains the `departments`, `aisles` and `products` tables (names and
categories) plus anonymous aggregate counts derived from the order tables:
number of orders per weekday/hour slot and number of orders per product. No
individual order, customer or transaction data is included.

- **Original source**: the [Instacart Market Basket Analysis](https://www.kaggle.com/c/instacart-market-basket-analysis/data)
  Kaggle competition (2017), released by Instacart as
  *"3 Million Instacart Orders, Open Sourced"*. The original data is subject
  to the terms set by Instacart and the competition rules.
- **Copy used here**: the Kaggle re-upload
  [InstaCart Online Grocery Basket Analysis Dataset](https://www.kaggle.com/datasets/yasserh/instacart-online-grocery-basket-analysis-dataset)
  (by M Yasser H), published under **CC0: Public Domain**. That license is
  the one declared by the re-uploader.
- **Derived data**: French names, prices, units and price ranges are
  generated by this project (`scripts/build_data.py`, `scripts/translations/`).
  The French names of the 2,000 most ordered products were translated with
  Claude (Anthropic) and spot-checked.

If you plan to redistribute the catalog data in a commercial context, check
the original Instacart terms yourself.

## 📜 License

The **code** of this project is released under the MIT License (see
[`LICENSE`](LICENSE)). The catalog data is covered by the section above.
