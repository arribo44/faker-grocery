# Faker Grocery Store Provider

**A custom [Faker](https://faker.readthedocs.io/) provider for generating realistic fake data for supermarkets and hypermarkets: departments, aisles, products (with package sizes and EAN-13 barcodes), prices, seasonal and coherent shopping lists, recurring customers and till receipts with VAT and promotions.**

The catalog is built from the [Instacart Market Basket Analysis](https://www.kaggle.com/c/instacart-market-basket-analysis) open dataset: **21 departments**, **134 aisles** and **~49,700 real products**.

---

## 🌍 Supported languages

| Language | Locale examples | Departments / Aisles | Product names |
|----------|------------------|-----------------------|----------------|
| `en` | `en_US` | Original English names | Original English names |
| `fr` | `fr_FR`, `fr_CA`, `fr_BE`... | Hand-translated | Natural translation for the 2,000 most ordered products (~2/3 of generated products); approximate automatic translation for the rest |
| `it` | `it_IT` | Hand-translated | Same as French |
| `es` | `es_ES`, `es_MX`... | Hand-translated | Same as French |
| `pt` | `pt_PT`, `pt_BR` | Hand-translated (European Portuguese) | Same as French (European Portuguese) |
| `de` | `de_DE`, `de_AT`, `de_CH` | Hand-translated | Same as French (automatic part keeps the English word order, see below) |

> **Default language**: `en` (used for any locale not listed above, e.g. as a fallback).

Unit labels are translated in every language ("bouteille", "bottiglia",
"botella", "garrafa", "Flasche"). Only the product names of the language(s)
you actually use are loaded (one `names_<lang>.json.gz` file per language).

Translated product names come from two sources:

- **The 2,000 most ordered products** have a natural, checked translation in
  every language (`scripts/translations/product_names_<lang>.json`), in
  shelf-label style, brands kept as is: "Organic Raspberries" -> "Framboises
  bio", "Lamponi bio", "Frambuesas ecológicas", "Framboesas biológicas",
  "Bio-Himbeeren". Since products are picked by popularity, they make up
  about **two thirds** of generated products.
- **All other products** are translated automatically: common expressions
  first ("gluten free" -> "sans gluten", `phrases_<lang>.json`), then the
  word order of fully known segments is reversed for the Romance languages
  (they put the noun first; segments are split at punctuation and linking
  words such as "with" or "and"), then word-by-word substitution with a
  ~1,200-word grocery dictionary (`word_dict_<lang>.json`), with function
  words in lower case inside the name ("Rigatoni avec Sauce"). Brand names
  stay untranslated. This is approximate, "faker-grade" output ("Tomates en
  dés Bio avec Herbes Italien"), fine for tests and demos but not a
  professional localization. German keeps the English word order, since it
  also puts the noun last ("Glutenfrei Schokoladenstückchen Kekse").

Overall, 1.4% (es) to 2.9% (it) of generated product names stay identical
to the English name, mostly brand names ("Cheerios Honey Nut", "Smartwater").

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
fake.grocery_department(weighted=False) # uniform pick (default: popular departments more often)
fake.grocery_department_name(16)        # "produits laitiers et œufs"

fake.aisle()                            # "yaourt"
fake.aisle(department="produits laitiers et œufs")   # restricted to that department
fake.aisle(department=16)               # same, by id
fake.aisle_id(department=16)            # 120
fake.aisle(weighted=False)              # uniform pick (default: popular aisles more often)
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
#     'ean': '2000000123455',       # stable, valid EAN-13 (in-store prefix 20)
#     'size': '500 g',              # package size: '6 x 330 mL', '12 pièce(s)', or None
#     'reference_price': 4.08,      # price per kg or L ("prix au kilo"), None if unknown
#     'reference_unit': 'kg',
# }

fake.product_ean(12345)                 # "2000000123455", always the same for this product
fake.product(aisle=24, month=6)         # seasonal pick: strawberries in June, clementines in December

fake.product_name(12345)                # look up a specific product id
```

**Package sizes** come from the product name when it states one ("12 oz" ->
340 g, "16 fl oz" -> 475 mL, "6 ct" -> 6 pieces), otherwise from sizes
typical of the aisle and unit (a jar of spices 30-80 g, a pack of beer 6 to
24 x 330 mL, a box of eggs 6 to 12...). The dearer a product is within its
price range, the bigger its package, so prices per kg stay plausible.
Products sold by weight or volume have no size (the quantity bought is).

**Seasonality**: with a `month` (1-12), or in a `grocery_list()` with a date,
fresh fruits and vegetables in season come up about twice as often and
out-of-season ones less (strawberries, asparagus, clementines, squash...),
with seasons shifted by six months in the southern hemisphere (AU, NZ, AR,
CL, ZA, BR...).

Products are picked **in proportion to their popularity**: how many times
each one was ordered in the ~32M order lines of the Instacart data. Bananas,
strawberries, milk or avocados come up far more often than niche items, as
in a real basket. Pass `weighted=False` to `product()`, `product_record()`,
`grocery_item()` or `grocery_list()` for a uniform pick across the catalog.

### 💰 Prices, quantities, units

Every product has a stable catalog **`base_price`** (its "probable price"),
organic and premium products ("Organic", "Premium", "Artisan", "Grass-Fed"...)
costing 25% more than their plain equivalent,
generated once from its department's typical range (or a finer per-aisle
and per-unit range where one is needed: a can of beer is not priced like a
bottle of spirits) - or, for products sold
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
fake.price(department=16)               # price within the dairy/eggs range (skewed towards cheap, like the catalog)
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
`en_GB` → GBP, `fr_CA` → CAD, `fr_CH` → CHF, `ja_JP` → JPY, `es_AR` → ARS,
`ko_KR` → KRW, `zh_CN` → CNY, `tr_TR` → TRY, etc.: **56 currencies**, covering
the country of every Faker locale except Iran (`fa_IR`, no stable rate) and
the generic `ar_AA`. Eurozone countries (Bulgaria included since 2026), and
any country not in the list, use EUR (the catalog's base currency). Prices are converted from EUR with **fixed approximate rates**
(not live exchange rates), then adjusted to the country's approximate
**grocery price level**: a plain conversion would make a basket cost the
same everywhere, whereas groceries are much dearer in Switzerland and much
cheaper in India. Within the eurozone the level is per country too
(Portugal cheaper, Ireland dearer). Average default basket: ~85 EUR in
France, ~69 EUR in Portugal, ~93 EUR in Ireland, ~107 USD in the US,
~128 CHF in Switzerland. Prices are rounded to the currency's minor unit
(whole numbers for JPY, HUF, KRW, CLP, VND...; 3 decimals for BHD/JOD). Every priced dict carries a `currency` field.

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
#     'ean': '2000000123455',
#     'aisle': 'yaourt',
#     'department': 'produits laitiers et œufs',
#     'size': '4 x 125 g',
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

# The number of items follows the distribution of the ~3.2M Instacart baskets
# (many small baskets, a few very big ones, ~10 items on average), scaled by
# family_size (default 2, a couple: x0.8 for one person, +20% per extra
# person), which also scales the plausible quantity of each item.
shopping_list = fake.grocery_list()
# {
#     'items': [ ... grocery_item dicts ... ],
#     'item_count': 9,
#     'family_size': 2,
#     'total': 42.31,
#     'currency': 'EUR',
# }

fake.grocery_list(family_size=5)                       # bigger default basket
fake.grocery_list(min_items=3, max_items=8)             # uniform item count in that range
fake.grocery_list(max_items=5)                          # measured count, capped at 5
fake.grocery_list(department="fruits et légumes")       # restrict the whole list to one department
fake.grocery_list(coherent=False)                       # no complementary products (see below)

# Baskets are coherent by default: an item sometimes brings a complementary
# one (pasta -> pasta sauce, burger buns -> sausages, granola -> yogurt,
# chips -> dip...), within the item count. The 263 pairings and their
# probabilities are measured on the ~3.2M Instacart baskets: aisles bought
# together at least twice as often as by chance.

# Optionally attach a plausible shopping date/time (within the last year,
# during the country's store opening hours, see grocery_opening_hours()).
# Days and hours follow the locale's weekly shopping pattern (see below;
# weighted=False for a uniform pick), and fresh produce follows the season:
shopping_list = fake.grocery_list(with_datetime=True)
shopping_list["shopping_datetime"]      # datetime.datetime(2026, 3, 12, 17, 42, 8)

# Or pin it to a specific date (random time on that day):
import datetime
fake.grocery_list(date=datetime.date(2025, 12, 24))

# Standalone helper used internally by grocery_list():
fake.grocery_opening_hours()                            # (8, 21) in France, (7, 23) in the US, (8, 20) by default
fake.shopping_datetime()                                # random date (last year) + time within those hours
fake.shopping_datetime(date=datetime.date(2025, 12, 24))
fake.shopping_datetime(open_hour=9, close_hour=19)
fake.shopping_datetime(weighted=False)                  # uniform day and hour
```

### 👤 Recurring customers

```python
customer = fake.customer_profile()      # or customer_profile(family_size=4)
# {'customer_id': 106053, 'name': 'Théophile Gosselin', 'family_size': 3,
#  'favorite_product_ids': [10246, 49044, ...],   # 8 + 4 per person, often re-ordered products
#  'shopping_interval_days': 7,                    # 1 to 30, weekly and monthly most often
#  'reorder_rate': 0.54}                           # share of items re-ordered from favorites

history = fake.customer_history(customer, trips=12)    # 12 baskets, oldest first
history = fake.customer_history(trips=12, end_date=datetime.date(2026, 6, 30))
# Each basket is a grocery_list() dict with 'shopping_datetime' and
# 'customer_id'; trips are spaced by the shopping interval (give or take a
# third) and each item is a re-order of a favorite with probability reorder_rate.
```

Measured on the ~206,000 Instacart customers: the shopping interval follows
the distribution of their median days between orders, the re-order rate the
distribution of their share of re-ordered items (~45% on average), and
favorites are picked in proportion to how often products are re-ordered
(milk, bananas, eggs rather than one-off purchases).

### 🧾 Receipts

```python
receipt = fake.receipt()                     # for a new grocery_list(with_datetime=True)
receipt = fake.receipt(basket)               # for a given basket (grocery_list / customer_history)
receipt = fake.receipt(promotion_rate=0.3, payment_method="cash")
# {
#     'store': {'store_id': 5830, 'name': 'Épicerie Joubert', 'address': '42, avenue Renaud, ...'},
#     'receipt_number': '5830-14-783226', 'register': 14,
#     'datetime': datetime.datetime(2026, 8, 21, 9, 25, 30),
#     'lines': [{'product': ..., 'ean': ..., 'quantity': 3, 'unit_price': 4.29, 'total_price': 12.87,
#                'promotion': '2 achetés + 1 offert', 'discount': 4.29, 'vat_rate': 0.055}, ...],
#     'item_count': 9, 'subtotal': 86.62, 'discount_total': 5.95,
#     'taxes': [{'rate': 0.055, 'base': 76.46, 'amount': 4.21}], 'tax_total': 4.21,
#     'taxes_included': True, 'total': 80.67,
#     'payment_method': 'cash', 'amount_tendered': 100.0, 'change': 19.33, 'currency': 'EUR',
# }

fake.grocery_store()                         # a fictional store: id, localized name, address
```

- **Promotions**: each line has a `promotion_rate` chance (default 15%) of
  a percentage off (10-50%), 3-for-2 or 2nd at half price (counted items
  bought in sufficient numbers), with localized labels.
- **VAT**: approximate rates of ~27 countries, a reduced rate for food and
  the standard rate for alcohol, household, personal care, pet and baby
  care products (France 5.5% / 20%, Germany 7% / 19%...). Prices include
  it, except in the US and Canada where a sales tax is added at the till
  (groceries mostly exempt). Other countries get no tax breakdown.
- **Payment**: card, cash or mobile; paying cash hands over the next
  banknote or round amount, and gets change.

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
returns are described by `TypedDict`s: `ProductRecord`, `GroceryItem`,
`GroceryList`, `CustomerProfile`, `GroceryStore`, `Receipt`, `ReceiptLine`
and `TaxLine`. Editors then autocomplete their keys, and mypy/pyright flag
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

## 🎯 Command line: demo and bulk export

The package installs a `faker-grocery` command (also `python -m faker_grocery`):

```bash
faker-grocery                                    # demo, en_US and fr_FR
faker-grocery demo --locale de_DE                # demo for one locale

# Bulk export: baskets, receipts, customers (with their shopping history) or products
faker-grocery export baskets -n 10000 --locale fr_FR --format csv -o baskets.csv
faker-grocery export receipts -n 500 --format jsonl --seed 42 > receipts.jsonl
faker-grocery export customers -n 200 --trips 12 --format json -o customers.json
faker-grocery export products -n 5000 --locale it_IT --format csv -o products.csv
```

- **Formats**: `csv` has one row per basket item (`baskets`, `customers`),
  per receipt line (`receipts`) or per product, with the basket / receipt /
  customer fields repeated on each row - ready for a spreadsheet, pandas or
  a database import. `jsonl` (one record per line) and `json` keep the
  nested structure. Dates are ISO 8601.
- `--seed` makes the output reproducible; `--locale` sets the language,
  currency, VAT, shopping hours and seasons (an unknown locale is rejected
  with the close matches); without `-o` the output goes to standard output.
- With `-o`, the file is only replaced once the export is complete: an
  interrupted or failed export never leaves a half-written file. Records
  are written as they are generated, so memory use stays flat even for
  large `json` exports.
- `--csv-safe` prefixes text cells starting with `=`, `+`, `-` or `@` with
  a `'`, so that a spreadsheet opening the file can't run them as formulas
  (CSV injection). Off by default because it also changes legitimate
  values, such as promotion labels (`-30 %` -> `'-30 %`).

For a complete demo with more examples per feature and both locales, see [`examples/basic_usage.py`](examples/basic_usage.py).

---

## 🧱 Data layout

A single gzip-compressed JSON file, `faker_grocery/data/grocery_data.json.gz`, holds the whole catalog:

- `departments`: `{department_id: {language: name}}`
- `aisles`: `{aisle_id: {language: name, department_id: int}}` (each aisle belongs to exactly one department)
- `products`: compact rows `[id, aisle_id, department_id, base_price, order_count, unit, size, season, reorder_count, name_en]` (`order_count`: popularity, see below; `unit`: the product's fixed unit key; `base_price` is per kg/L for measured units; `size`: `[count, amount, "g"|"ml"|null]` or null; `season`: 12-bit mask of the months a fresh product is in season, 0 for none)
- translated product names live in separate files, `faker_grocery/data/names_<lang>.json.gz` (a list parallel to `products`, listed in `meta.name_files`), loaded on first use of that language
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
- `aisle_unit_price_ranges`: `{aisle_id: {unit_key: [min, max]}}` - finer per-article EUR ranges (beer, fruit, vegetables, eggs)
- `premium_surcharge`, `seasonal_factors`, `southern_hemisphere_countries` - organic/premium price factor and seasonality settings
- `default_opening_hours`, `country_opening_hours`: `{country_code: [open, close]}`
- `country_vat`: `{country_code: [food_rate, standard_rate, included]}` and `aisle_tax_class`: `{aisle_id: "food"|"standard"}`
- `aisle_complements`: `[[aisle_id, complementary_aisle_id, probability], ...]` - coherent baskets, from the Instacart co-purchase statistics
- `basket_sizes`, `customer_intervals`, `customer_reorder_rates`: `[[value, count], ...]` - Instacart distributions of items per order, customers' median days between orders and re-order share (%)
- `store_name_templates`, `promotion_labels`: `{language: ...}` - receipts
- `meta`: supported/default languages, name files, base currency, source, field layout

> The store tables (sizes, seasons, VAT, opening hours, store names,
> promotions) are hand-made, in `scripts/store_tables.py`.

> `DATAS/*.csv` (the raw Instacart source: `aisles.csv`, `departments.csv`, `products.csv`, plus the aggregated order statistics `order_times.csv` and `product_popularity.csv`) is **not** shipped in the installed package - only the `faker_grocery/data/*.json.gz` files are (see `MANIFEST.in` and `[tool.setuptools.package-data]` in `pyproject.toml`), and using the library never touches `DATAS/`. It **is** kept versioned in the repository, though: `scripts/build_data.py` always rebuilds the catalog from these CSVs (never from `grocery_data.json.gz` itself), so they're the only way to regenerate the data at all - including to add a new language later (see below).

> The statistics files (`order_times.csv`, `product_popularity.csv`,
> `basket_sizes.csv`, `aisle_orders.csv`, `aisle_pairs.csv`,
> `customer_intervals.csv`, `customer_reorder_rates.csv`) are themselves aggregated from the much larger
> Instacart `orders.csv` (~109 MB) and `order_products__prior.csv` (~578 MB),
> which are **not** versioned. They only need regenerating if the source data
> changes: download them from the Kaggle dataset (see below; the anonymous
> Kaggle download no longer works, but the Hugging Face mirror
> [attik/Instacart-Market-Basket-Analysis](https://huggingface.co/datasets/attik/Instacart-Market-Basket-Analysis)
> has the same files and reproduces the versioned statistics exactly), then run
> `python scripts/build_order_stats.py path/to/orders.csv path/to/order_products__prior.csv`
> followed by `python scripts/build_data.py`. The script first checks the
> raw files' SHA-256 against the copy the statistics were built from, since
> the mirror is a third party (`--no-verify` skips the check on purpose).

## 🌐 Adding a new language

The files are generated by [`scripts/build_data.py`](scripts/build_data.py) from the raw CSVs in `DATAS/` (`aisles.csv`, `departments.csv`, `products.csv`) plus the translation files in `scripts/translations/`. To add a language (e.g. `nl`):

1. Create `scripts/translations/departments_nl.json` and `aisles_nl.json` (21 and 134 hand-translated entries).
2. Create `scripts/translations/word_dict_nl.json` and `phrases_nl.json`, with the same keys as `word_dict_fr.json` / `phrases_fr.json` (a ~1,200-word grocery vocabulary and ~90 multi-word expressions translated as a whole).
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
