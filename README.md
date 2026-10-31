# Faker Grocery Store Provider

**A custom [Faker](https://faker.readthedocs.io/) provider for generating realistic fake data for supermarkets and hypermarkets: departments, aisles, products, prices and randomized shopping lists.**

The catalog is built from the [Instacart Market Basket Analysis](https://www.kaggle.com/c/instacart-market-basket-analysis) open dataset: **21 departments**, **134 aisles** and **~49,700 real products**.

---

## 🌍 Supported languages

| Language | Locale examples | Departments / Aisles | Product names |
|----------|------------------|-----------------------|----------------|
| `en` | `en_US` | Original English names | Original English names |
| `fr` | `fr_FR` | Hand-translated | Approximate word-substitution translation |

> **Default language**: `en` (used for any locale not listed above, e.g. as a fallback).

Planned extensions (data not built yet): `it`, `es`, `pt`, `de`. See [Adding a new language](#-adding-a-new-language) below.

Product names in `fr` are translated word-by-word from the source English names using a curated ~700-word grocery vocabulary dictionary (see `scripts/translations/word_dict_fr.json`). Words missing from the dictionary (mostly brand names) are left untranslated, and grammar/word order is not reordered. This is approximate, "faker-grade" data meant for tests and demos, not a professional localization.

---

## 📦 Installation

Requires Python 3.9+ and Faker 20+.

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

fake["fr_FR"].department()              # "produits laitiers et œufs"
```

Unknown ids/names and invalid arguments (e.g. `min_items > max_items`,
`family_size < 1`, `open_hour >= close_hour`, only one of
`min_price`/`max_price`) raise `ValueError`.

### 🏬 Departments & aisles

```python
fake.department()                       # "produits laitiers et œufs"
fake.department_id()                    # 16
fake.department_name(16)                # "produits laitiers et œufs"

fake.aisle()                            # "yaourt"
fake.aisle(department="produits laitiers et œufs")   # restricted to that department
fake.aisle(department=16)               # same, by id
fake.aisle_id(department=16)            # 120
fake.aisle_name(120)                    # "yaourt"
```

### 🛒 Products

```python
fake.product()                          # "Yaourt Grec Vanille"
fake.product(aisle="yaourt")            # restricted to an aisle (name or id)
fake.product(department=16)             # restricted to a department (name or id)

fake.product_record()
# {
#     'id': 12345,
#     'name': 'Yaourt Grec Vanille',
#     'aisle_id': 120,
#     'aisle': 'yaourt',
#     'department_id': 16,
#     'department': 'produits laitiers et œufs',
# }

fake.product_name(12345)                # look up a specific product id
```

### 💰 Prices, quantities, units

Every product has a stable catalog **`base_price`** (its "probable price"),
generated once from its department's typical range. Any time you actually
price a product — via `price(product=...)`, `product_record()` or
`grocery_item()` — you get that base price jittered by a random **±5%**, the
way real shelf prices drift a little from one day/store to the next.

```python
fake.price()                            # 4.77  (random department's typical range)
fake.price(department=16)               # price within the dairy/eggs range
fake.price(min_price=10.0, max_price=20.0)   # both bounds are required
fake.price(product=12345)               # that product's base_price, jittered +/-5%

record = fake.product_record()
record["base_price"]                    # 2.10  (stable catalog reference)
record["price"]                         # 2.04  (this instance, +/-5% jitter)

fake.quantity()                         # 3   (1 to 10)
fake.quantity(max_quantity=5)           # 1 to 5

fake.unit()                             # "pièce(s)", "kg", "bouteille", ... (any unit)
fake.unit(department=7)                 # restricted to units plausible for that department
                                         # (e.g. "L"/"bouteille"/"canette" for beverages,
                                         # "kg"/"botte" for produce - not "9 bottle x Bread")
```

### 📝 Grocery items & shopping lists

```python
fake.grocery_item()
# {
#     'product': 'Yaourt Grec Vanille',
#     'product_id': 12345,
#     'aisle': 'yaourt',
#     'department': 'produits laitiers et œufs',
#     'quantity': 3,
#     'unit': 'pot',                # always plausible for the product's department
#     'unit_price': 2.15,           # base_price jittered +/-5%
#     'total_price': 6.45,
# }

# family_size defaults to 2 (a couple). It scales the default item-count
# range and the plausible quantity of each item (bigger households buy more).
shopping_list = fake.grocery_list()
# {
#     'items': [ ... grocery_item dicts ... ],
#     'item_count': 9,
#     'family_size': 2,
#     'total': 42.31,
# }

fake.grocery_list(family_size=5)                       # bigger default basket
fake.grocery_list(min_items=3, max_items=8)             # override the item-count range explicitly
fake.grocery_list(department="fruits et légumes")       # restrict the whole list to one department

# Optionally attach a plausible shopping date/time (random within the last
# year, during store opening hours by default 8:00-20:00):
shopping_list = fake.grocery_list(with_datetime=True)
shopping_list["shopping_datetime"]      # datetime.datetime(2026, 3, 12, 17, 42, 8)

# Or pin it to a specific date (random time on that day):
import datetime
fake.grocery_list(date=datetime.date(2025, 12, 24))

# Standalone helper used internally by grocery_list():
fake.shopping_datetime()                                # random date (last year) + time (8h-20h)
fake.shopping_datetime(date=datetime.date(2025, 12, 24))
fake.shopping_datetime(open_hour=9, close_hour=19)
```

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
- `products`: compact rows `[id, aisle_id, department_id, base_price, name_<lang0>, name_<lang1>, ...]`
- `price_ranges`: `{department_id: [min_price, max_price]}`
- `unit_labels`: `{unit_key: {language: label}}` (e.g. `"bottle": {"en": "bottle", "fr": "bouteille"}`)
- `department_units`: `{department_id: [unit_key, ...]}` - which units are plausible for each department, so a generated item's unit always matches what the product actually is (no "9 bottle x Bread")
- `meta`: supported/default/planned languages, source, field layout

> `DATAS/*.csv` (the raw Instacart source: `aisles.csv`, `departments.csv`, `products.csv`) is **not** shipped in the installed package - only `grocery_data.json` is (see `MANIFEST.in` and `[tool.setuptools.package-data]` in `pyproject.toml`), and using the library never touches `DATAS/`. It **is** kept versioned in the repository, though: `scripts/build_data.py` always rebuilds the catalog from these CSVs (never from `grocery_data.json` itself), so they're the only way to regenerate the data at all - including to add a new language later (see below).

## 🌐 Adding a new language

The file is generated by [`scripts/build_data.py`](scripts/build_data.py) from the raw CSVs in `DATAS/` (`aisles.csv`, `departments.csv`, `products.csv`) plus the translation files in `scripts/translations/`. To add a language (e.g. `it`):

1. Create `scripts/translations/departments_it.json` and `aisles_it.json` (21 and 134 hand-translated entries).
2. Create `scripts/translations/word_dict_it.json` (a grocery vocabulary dictionary for word-substitution product name translation — see `word_dict_fr.json` for the format and scope).
3. Add `"it"` to `TRANSLATED_LANGUAGES` in `scripts/build_data.py`.
4. Re-run:
   ```bash
   python scripts/build_data.py
   ```

---

## 🧪 Tests

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

CI (`.github/workflows/ci.yml`) runs the linter, the test suite on Python
3.9-3.14 (plus the oldest supported Faker, 20.0.0) and a package build.

---

## 📊 Data source & license

The product catalog (`DATAS/*.csv`, and the `grocery_data.json` built from
it) contains only the `departments`, `aisles` and `products` tables: names
and categories, no order, customer or transaction data.

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

If you plan to redistribute the catalog data in a commercial context, check
the original Instacart terms yourself.

## 📜 License

The **code** of this project is released under the MIT License (see
[`LICENSE`](LICENSE)). The catalog data is covered by the section above.
