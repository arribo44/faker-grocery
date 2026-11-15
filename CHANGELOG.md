# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Fixed
- `faker-grocery export ... | head` no longer prints `BrokenPipeError` when the output is small: 0.12.0 only handled a pipe closed during the export, not on the final flush of a still-buffered output.

## [0.12.0] - 2026-11-15

### Added
- `faker-grocery --locale fr_FR` (or `-l fr_FR`, `python -m faker_grocery --local fr_FR`) runs the demo for that locale, without the `demo` subcommand; repeatable.
- `faker-grocery export --csv-safe`: prefixes text cells starting with `=`, `+`, `-`, `@` (or a tab / carriage return) with `'` against spreadsheet formula injection. Off by default, since it also changes promotion labels such as `-30 %`.
- Property-based tests (`tests/test_properties.py`, hypothesis): valid EAN-13s, basket item counts and totals, receipt subtotal / discounts / taxes / total / change, product record consistency, for any seed over 8 locales (EUR, USD sales tax, JPY, BHD...). `hypothesis` joins the `test` extra.
- `scripts/build_order_stats.py` checks the SHA-256 of the raw Instacart files (from a third-party mirror) before building; `--no-verify` skips it.

### Changed
- README: new **Stability and versioning** section (public API, same values for the same seed within a minor version, data files not public); the data layout is documented as internal; the data license section states that the original Instacart terms still apply to the catalog data, which the MIT License (code only) doesn't cover.
- The deprecated `department()` / `department_name()` aliases now announce their removal in 1.0.
- `faker-grocery export -o FILE` writes to a temporary file renamed once complete: a failed or interrupted export no longer leaves a half-written file (or destroys the previous one).
- `--format json` is written record by record (same output as before) instead of building the whole list in memory.
- CI / release: actions pinned by commit SHA (updated monthly by Dependabot), read-only default token, no persisted git credentials, new `pip-audit` job.

### Fixed
- `faker-grocery` with an unknown `--locale` now exits with a usage error and the close matches instead of a traceback; an unwritable `-o` path prints an error (exit code 1) and `| head` no longer prints a `BrokenPipeError`.

## [0.11.0] - 2026-11-14

### Added
- **Bulk export from the command line**: a `faker-grocery` command (also `python -m faker_grocery`) with `export baskets|receipts|customers|products -n N --locale L --format csv|jsonl|json [-o FILE] [--seed S] [--trips T]`. CSV has one row per basket item / receipt line / product with the parent fields repeated; JSON and JSON Lines keep the nested structure. `faker-grocery demo [--locale L]` runs the demo for a given locale. 9 new tests (`tests/test_cli.py`).

### Changed
- **Coherent baskets, customers and basket sizes are now measured on the Instacart data** instead of hand-made rules:
  - **Complementary products**: 263 aisle pairings (instead of 25 hand-made ones) with their probabilities, from the co-purchases of ~3.2M baskets: aisles bought together at least twice as often as by chance and at least 3 points more often (pasta -> pasta sauce 21%, burger buns -> sausages 19%, granola -> yogurt 28%...), at most 3 per aisle.
  - **Basket sizes**: without both `min_items` and `max_items`, the item count follows the distribution of Instacart basket sizes (~10 items on average, many small baskets, a few very big ones), scaled by `family_size` (x0.8 for one person, x1 for a couple, +20% per extra person); a single bound clamps it. With both bounds, the count stays uniform between them.
  - **Customers**: `customer_profile()` draws the shopping interval from the distribution of ~206,000 customers' median days between orders, the re-order rate from their share of re-ordered items (~45% on average), and favorites in proportion to how often products are re-ordered.
- `scripts/build_order_stats.py` also writes `DATAS/basket_sizes.csv`, `aisle_orders.csv`, `aisle_pairs.csv`, `customer_intervals.csv`, `customer_reorder_rates.csv`, and a `reorder_count` column in `product_popularity.csv`; `grocery_data.json` products rows gained `reorder_count` (before `name_en`), new tables `basket_sizes`, `customer_intervals`, `customer_reorder_rates`. **Breaking for direct data access.**
- Default basket sizes changed: the same seed yields different baskets than 0.10.0.
- **Hand-checked Italian, Spanish, Portuguese and German names for the 2,000 most ordered products** (`scripts/translations/product_names_<lang>.json`, about two thirds of generated products), like the French ones: shelf-label style, brands kept ("Organic Raspberries" -> "Lamponi bio", "Frambuesas ecológicas", "Framboesas biológicas", "Bio-Himbeeren"). Generated names left in English drop from 5.9% to 2.9% (it), 4.1% to 1.4% (es), 5.1% to 2.7% (pt), 4.9% to 2.0% (de), mostly brand names.
- **Better automatic translation** of product names (all products but the 2,000 hand-checked French ones): ~350 new words in every dictionary (858 -> 1,209: wash, chip, jam, floss, ointment, lentils, chickpeas...), so ~28% fewer names stay in English (French 3,018 -> 2,148); function words in lower case inside a name ("Rigatoni avec Sauce", "Brot mit Käse"); word order reversed separately on each side of linking words ("Diced Tomatoes with Italian Herbs" -> "Tomates en dés Bio avec Herbes Italien", no longer "Herbes Italien avec Tomates en dés").
- **Catalog data files are gzip-compressed** (`grocery_data.json.gz`, `names_<lang>.json.gz`, built byte-for-byte reproducibly): the installed package takes ~5 MB on disk instead of ~13 MB. The download size is unchanged (wheels were already zip-compressed), and loading takes ~0.04 s longer. **Breaking for direct data access**: the files were renamed.
- README: the raw Instacart files are no longer downloadable anonymously from Kaggle; the Hugging Face mirror used instead reproduces the versioned statistics exactly.

---

## [0.10.0] - 2026-11-14

### Added
- **Till receipts**: `receipt(basket=None, promotion_rate=0.15, payment_method=None)` returns a fictional store (`grocery_store()`: id, localized name, address), receipt number, register, date/time, lines with promotions, VAT breakdown, total, payment method (card / cash / mobile), amount tendered and change. New `Receipt`, `ReceiptLine`, `TaxLine` and `GroceryStore` `TypedDict`s.
  - **VAT** with approximate rates for ~27 countries (`country_vat`): reduced rate for food, standard rate for alcohol, household, personal care, pet and baby care aisles; included in prices, except the US and Canada where a sales tax is added at the till. Other countries: no tax breakdown.
  - **Promotions** with localized labels: percentage off (10-50%), 3-for-2, 2nd at half price.
- **Recurring customers**: `customer_profile(family_size=None)` (favorite products, shopping interval, re-order rate) and `customer_history(customer=None, trips=10, end_date=None)`, a series of dated baskets re-ordering the customer's favorites. New `CustomerProfile` `TypedDict`; `GroceryList` gained an optional `customer_id`. Hand-coded orders of magnitude (weekly shopping, ~60% re-orders): the per-customer Instacart data isn't in the repository.
- **EAN-13 barcodes**: every product has a stable, valid EAN-13 with the in-store prefix 20 (so it can't clash with a real product); `ean` field in `product_record()` / `grocery_item()`, new `product_ean(product_id)`.
- **Package sizes and price per kg/L**: `product_record()` gained `size` ("500 g", "6 x 330 mL", "12 pièce(s)" or None), `reference_price` and `reference_unit` (the "prix au kilo"); `grocery_item()` gained `size`. Sizes come from the product name when it states one ("12 oz" -> 340 g), else from per-aisle/unit tables (`scripts/store_tables.py`), bigger for dearer products within their price range.
- **Seasonality**: `product()`, `product_record()` and `grocery_item()` take a `month`; `grocery_list()` with a date follows its month. Fresh produce in season comes up about twice as often, out of season less (25 fruits and vegetables), shifted by six months in the southern hemisphere.
- **Coherent baskets**: `grocery_list(coherent=True)` (default) sometimes adds a complementary product (pasta -> pasta sauce, cereal -> milk, chips -> dip... 25 hand-made pairings), within the item count.
- **Country opening hours**: `grocery_opening_hours()` ((8, 21) in France, (7, 23) in the US, (8, 20) by default); `shopping_datetime()` and dated baskets use them when no hours are given.
- 31 new tests (158 -> 189), in `tests/test_store_features.py`.

### Changed
- **Departments and aisles are popularity-weighted**: `grocery_department()`, `department_id()`, `aisle()` and `aisle_id()` pick in proportion to how much was ordered from them (produce and dairy far more often than bulk); `weighted=False` restores a uniform pick.
- **Organic and premium products cost 25% more** ("Organic", "Premium", "Artisan", "Grass-Fed"... in the name), so their base price may exceed their range's upper bound.
- `price()` without a product draws from the department range skewed towards cheap prices, like catalog prices, instead of uniformly.
- `shopping_datetime()`'s `open_hour` / `close_hour` default to the country's opening hours instead of 8-20.
- `grocery_list()` with a date now draws the date before the items (so they follow its season): the same seed yields different baskets than 0.9.0.
- `grocery_data.json`: products rows gained `size` and `season` columns (before `name_en`); new tables `premium_surcharge`, `seasonal_factors`, `southern_hemisphere_countries`, `default_opening_hours`, `country_opening_hours`, `country_vat`, `aisle_tax_class`, `aisle_complements`, `store_name_templates`, `promotion_labels`. **Breaking for direct data access.**

---

## [0.9.0] - 2026-11-14

### Added
- **39 new currencies** (17 -> 56), so every country of Faker's locales gets its own currency and price level instead of EUR at the French level: ARS, CLP, COP, KRW, CNY, TWD, RUB, UAH, TRY, ILS, ZAR, RON, ISK, MKD, ALL, BAM, AZN, AMD, GEL, UZS, THB, VND, IDR, PHP, MYR, PKR, BDT, LKR, NPR, SAR, AED, BHD, JOD, EGP, DZD, NGN, KES, GHS, ETB (plus CHF for `de_LI`, ILS for `ar_PS`, CAD for `fr_QC`, MYR for `en_MS`). Fixed approximate rates and rough price levels, as for the other currencies; whole-number prices where the minor unit isn't used in shops (KRW, CLP, VND...), 3 decimals for BHD/JOD. Only Iran (`fa_IR`) and the generic `ar_AA` still fall back to EUR.
- Bulgaria (`bg_BG`) uses EUR (euro since 2026-01-01) at its own price level (0.75).

### Fixed
- `shopping_datetime()` raised `ValueError: Total of weights must be greater than zero` for opening hours no shopping pattern covers (e.g. `open_hour=22, close_hour=24` or `0, 6` in `fr_FR` / `de_DE`); the day is now picked uniformly in that case.
- `grocery_list(max_items=2)` (only `max_items`, below the default minimum) raised `ValueError`; the default `min_items` now adapts to the given `max_items`.
- Aisles 32 ("packaged produce") and 123 ("packaged vegetables fruits") had the same name in fr, it, es, pt and de, so looking aisle 123 up by name always returned aisle 32. Aisle 32 is now "produits frais emballés" / "prodotti freschi confezionati" / "productos frescos envasados" / "produtos frescos embalados" / "Abgepackte Frischware". The build now fails if two aisles or departments share a name.
- `unit(aisle=..., department=...)` silently ignored the department when the aisle belongs to another one; it now raises `ValueError`, like `product()`.
- `quantity(max_quantity)` with a value below 1 (or not an integer) raised an obscure `randrange` error; it now raises `ValueError`.
- `price(min_price=..., max_price=...)` accepted negative bounds and returned negative prices; a negative `min_price` now raises `ValueError`.
- Numeric ids with surrounding spaces (`" 16 "`) are accepted; non-ASCII digits are rejected.
- The catalog's first load is now thread-safe (two threads creating their first provider at once could lose the product names of a language).
- Stale docstrings (supported languages, `language`, `grocery_item` unit).
- The English label of the `tin` unit (food can) was "can", like drink cans (`can`): it is now "tin", so every unit has a distinct label in every language.

### Changed
- **Beer is priced per container**: cans 0.80-3, bottles 1-4, packs 4-18 EUR instead of the alcohol department's 4-40 EUR (a can of beer used to cost ~19 EUR). Per-article ranges by (aisle, unit) also for fresh fruits (piece 0.20-2, tray 1.50-6), fresh vegetables (piece 0.30-3, bunch 0.80-3) and eggs (1.50-6). New `aisle_unit_price_ranges` table in `grocery_data.json`.
- **Plausible units for the most ordered products** (`PRODUCT_UNIT_OVERRIDES` in `scripts/build_data.py`): strawberries and berries by the tray, onions and carrots by the kg, garlic by the piece, kale and cilantro by the bunch... and products whose name states a pack or container ("12 Pack Soda", "Milk Gallon") are no longer sold by the litre or gram. `aisle_units` includes these forced units.
- Product names are cleaned of repeated/trailing spaces (412 English names, e.g. "TAI PEI      14OZ.SWEET & SOUR CHKN").
- Base prices and units changed for the affected products: the same seed yields different values than 0.8.0.
- Translations of aisles and departments that were left in English: "granola" (aisle 57: "granola et muesli", "Knuspermüsli"...), fr "santé digestive" (70) and "crackers et biscuits salés" (78), es "galletas saladas" (78), department "snacks" in pt/de/it ("aperitivos e doces", "Snacks und Süßwaren", "snack e dolciumi"). Names that are the correct word in their language are kept (fr "condiments", de "Butter", it "yogurt").
- 15 new tests (142 -> 157).

---

## [0.8.0] - 2026-10-31

### Added
- **Italian, Spanish, Portuguese and German** (`it`, `es`, `pt`, `de`): hand-translated department and aisle names, unit labels, and automatic product name translation (858-word dictionaries and 88-expression tables per language, word-order reversal for the Romance languages). Locales such as `it_IT`, `es_ES`, `es_MX`, `pt_PT`, `pt_BR`, `de_DE`, `de_AT`, `de_CH` now get localized data instead of the English fallback.
- 5 new tests (137 -> 142): translation files completeness, per-language names files, localized departments and units in every language.

### Changed
- **Translated product names moved to one file per language** (`faker_grocery/data/names_<lang>.json`), loaded only when a locale needs it. With six languages in one file, every import would load ~50k x 6 names (1.4 s, 70 MB); the catalog now loads in ~0.13 s (faster than 0.7.0's 0.23 s), plus ~0.07 s per additional language used. **Breaking for direct data access**: product rows only contain the English name.

---

## [0.7.0] - 2026-10-31

### Added
- **Natural French names for the 2,000 most ordered products** (`scripts/translations/product_names_fr.json`), about two thirds of generated products given popularity weighting: French shelf-label style, brands kept ("Organic Raspberries" -> "Framboises bio", "Hot Dog Buns" -> "Pains à hot-dog"). They take precedence over the automatic translation in `scripts/build_data.py`.
- **Better automatic translation for the other products**: a table of ~90 common expressions translated as a whole (`phrases_fr.json`: "gluten free" -> "sans gluten", "hot dog" -> "hot-dog"...), then word-order reversal of fully known segments (French puts the noun first; brands and numbers never move), then word substitution. 17 new dictionary entries.
- `tests/test_build_data.py`: translation helpers and curated names (11 new tests, 126 -> 137).

### Changed
- French product names changed for most products (curated or reordered); English names are unchanged.

---

## [0.6.0] - 2026-10-31

### Added
- **Fixed unit per product, chosen per aisle**: every product now has one unit, fixed at build time among the units plausible for its aisle (new `AISLE_UNITS` table, 134 aisles: milk by the litre or bottle, spices in jars, canned goods in food cans, meat counter by kg/g...). The same product is always sold the same way; `product_record()` gained `unit` and `price_per` fields.
- **Per-kg/L prices for measured products**: products sold by weight/volume (fresh produce, meat/seafood/cheese counters, deli, bulk, milk, juice, water, soft drinks) get their `base_price` as a price per kg or L from an aisle-specific range (`MEASURED_PRICE_RANGES`, e.g. seafood counter 12-45 EUR/kg), instead of reusing a per-article price.
- **Country shopping patterns**: `shopping_datetime()` follows the locale country's weekly pattern: `instacart_us` (measured, default), `sunday_morning` (FR, BE, LU, ES, IT, PT: Saturday busiest, Sunday morning only) or `sunday_closed` (DE, AT, CH, PL, NO). New `grocery_shopping_pattern()` / `set_grocery_shopping_pattern(name)`.
- **Per-country price levels**: when prices are in the locale country's own currency, the country's grocery price level is used (`COUNTRY_PRICE_LEVELS`, eurozone included: Portugal 0.82, Ireland 1.1...), instead of one level per currency.
- `unit(aisle=...)` filter.
- New `tin` unit ("can" / "boîte de conserve") for food cans, distinct from drink cans (`can`, "canette").
- Seeded, reproducible test suite plus a broad invariants sweep over 240 baskets across locales; 16 new tests (97 -> 113).
- **Type hints**: the package is fully annotated and ships a `py.typed` marker. The returned dicts are described by the new `ProductRecord`, `GroceryItem` and `GroceryList` `TypedDict`s (importable from `faker_grocery`), so editors autocomplete their keys and mypy/pyright catch typos. The README documents how to get typed results despite Faker's dynamic `fake.xxx()` methods.
- mypy (strict) in CI and in the `dev` extra; `tests/test_typing.py` checks that the `TypedDict`s match the dicts actually returned, and that the documented typed usage type-checks (5 new tests, 113 -> 118).
- **`grocery_department()` / `grocery_department_name()`**, replacing `department()` / `department_name()` (see Fixed / Deprecated).
- 8 new tests for the department name clash (118 -> 126).

### Fixed
- **Name clash with Faker's address providers**: `fr_FR` and `es_CO` already define `department()` (and `fr_FR` `department_name()`) for administrative departments ("Cher", "Sarthe", "Cesar"...). Adding `GroceryStoreProvider` used to silently replace them with store departments (since 0.1.0). The store methods are now `grocery_department()` / `grocery_department_name()`, and Faker's methods are left untouched.

### Deprecated
- `department()` / `department_name()`: deprecated aliases of `grocery_department()` / `grocery_department_name()`, emitting a `DeprecationWarning`. They are only registered on a Faker instance whose locale doesn't define these methods itself (e.g. `en_US`); in `fr_FR` / `es_CO`, `fake.department()` is Faker's own. They will be removed in a future version.

### Changed
- Grocery items no longer draw a random unit per call: they use the product's fixed unit. Per-unit quantity rules are unchanged.
- `base_price` of measured products (kg, g, L) is now a per-kg/L price; prices of all other products are unchanged in EUR.
- Default shopping days/hours for European locales listed above changed (no more US Sunday/Monday peak).
- `requires-python` raised to `>=3.11` (Python 3.10 reached end-of-life in October 2026); CI tests 3.11-3.14.
- `grocery_data.json`: products rows gained a `unit` column; new `aisle_units`, `measured_price_ranges`, `country_price_levels`, `shopping_patterns`, `country_shopping_patterns` tables; `order_time_weights` moved to `shopping_patterns["instacart_us"]`; `department_units` is now derived from aisle units. **Breaking for direct data access.**

---

## [0.5.0] - 2026-10-31

### Added
- **Popularity-weighted products**: `product()`, `product_record()`, `grocery_item()` and `grocery_list()` now pick products in proportion to how often they were ordered in the Instacart data (~32M order lines), so baskets contain bananas, milk and strawberries far more often than niche items. `weighted=False` restores a uniform pick.
- **Realistic shopping days and hours**: `shopping_datetime()` (and `grocery_list(with_datetime=True)`) follow the weekly pattern of the ~3.4M Instacart orders (busier days, quieter opening/closing hours), still within the given opening hours. `weighted=False` restores a uniform pick.
- **Measured quantities**: items sold by weight or volume (kg, g, L, mL) get realistic quantities (e.g. 0.85 kg, 350 g, 1.5 L, in fixed steps, scaled by `family_size`) and are priced per kg or per L; counted items keep integer quantities priced per article. New `price_per` field on `grocery_item()` results.
- **Grocery price levels**: currency conversion now also applies the country's approximate grocery price level (`price_level`, e.g. CHF 1.6, INR 0.3), so a basket in Switzerland costs more than a plain EUR->CHF conversion.
- `scripts/build_order_stats.py` aggregates the large, unversioned Instacart `orders.csv` / `order_products__prior.csv` into the small versioned `DATAS/order_times.csv` and `DATAS/product_popularity.csv`.
- 14 new tests (83 -> 97).

### Changed
- `grocery_item()` `quantity` is a float (kg, L) or a multiple of 50/250 (g, mL) for measured units, and `total_price` is computed from the quantity in kg/L. **Breaking** for code assuming `total_price == quantity * unit_price` for every item.
- Default product and shopping-time distributions changed (weighted by default): the same seed yields different values than 0.4.0.
- Converted prices changed for every non-EUR currency (price level now applied).
- `products` rows in `grocery_data.json` gained an `order_count` column (`[id, aisle_id, department_id, base_price, order_count, name_<lang>...]`); new `measured_units` and `order_time_weights` tables, `price_level` in `currencies`. **Breaking for direct data access**; column positions are now read from `meta.product_fields`.

---

## [0.4.0] - 2026-10-31

### Added
- **Currency support**: prices are generated in the currency of the locale's country (`en_US` -> USD, `en_GB` -> GBP, `fr_CA` -> CAD, `ja_JP` -> JPY...; eurozone and unlisted countries -> EUR), converted from the EUR catalog with fixed approximate rates and rounded to the currency's minor unit (whole numbers for JPY/HUF). 17 currencies supported.
  - `product_record()`, `grocery_item()` and `grocery_list()` results gained a `currency` field.
  - New `grocery_currency(symbol=False)` (named so as not to shadow Faker's own `currency_code()`) and `set_grocery_currency(code)` / `set_grocery_currency(None)` to override or reset the currency; `GroceryStoreProvider.currency` property.
  - New `currencies` and `country_currencies` tables and `meta.base_currency` in `grocery_data.json`, built from `scripts/build_data.py`.
- GitHub Actions CI: ruff, pytest on Python 3.10-3.14 plus Faker 20.0.0, package build check.
- `dev` extra (`pytest`, `ruff`, `build`) and a pinned ruff rule set.
- 23 new tests (60 -> 83): argument validation, currency, seed reproducibility, multi-locale usage.
- README: multi-locale usage (`fake[locale].add_provider(...)`) and error behavior.
- README: "Data source & license" section (original Instacart source, CC0 Kaggle re-upload actually used, MIT scope limited to the code).

### Fixed
- `price(min_price=...)` (or `max_price=...`) alone silently ignored the given bound and returned a price from a department range instead; passing only one bound, or `min_price > max_price`, now raises `ValueError`.
- `shopping_datetime(open_hour=20, close_hour=8)` returned a time outside opening hours; opening hours are now validated (`0 <= open_hour < close_hour <= 24`).
- `grocery_list(min_items > max_items)` raised an obscure `randrange` error; it now raises a clear `ValueError`.
- `grocery_list()` / `grocery_item()` silently accepted `family_size <= 0`; it must now be a positive integer.
- Unknown ids in `department_name()`, `aisle_name()` and `unit(department=...)` raised a bare `KeyError`; every unknown id/name now raises `ValueError`.
- `bool` values (`department=True`) were accepted as ids `1`/`0`; they are now rejected.

### Changed
- **Performance**: random product picking uses `random.choice` instead of Faker's `random_element` (which scanned the whole ~50k-row catalog on every call), and product id lookups use an index instead of a linear scan. `product()` is ~190x faster, `grocery_list()` ~60x, `price(product=...)` / `product_name()` ~1000x. Output stays reproducible with `Faker.seed()`, **but a given seed now produces different values than in 0.3.1**.
- `grocery_list(department=...)` resolves the department once instead of once per item, and fails fast on an unknown department.
- `grocery_data.json` is written without indentation (8.8 MB -> 4.2 MB, same content); the wheel shrinks from 1.9 MB to 1.6 MB.
- Packaging moved from `setup.py` to `pyproject.toml`; the version is now read from `faker_grocery.__version__` only. `requires-python` raised from `>=3.7` to `>=3.10` (Python 3.9 is end-of-life and current Faker releases require 3.10+), classifiers now list 3.10-3.14.
- The private Faker locale lookup is isolated in `_generator_locale()`.

---

## [0.3.1] - 2026-09-20

### Fixed
- `python -m faker_grocery` demo: the "Aisles" / "Aisles in department X" sections could print the same aisle twice (e.g. small departments like `pets`, with only 2 aisles, or `snacks et confiseries` with 11, have a real chance of repeats across 5 independent draws - a birthday-paradox effect, not a bug in the random generation itself). The demo now samples distinct aisles/departments (`distinct_sample()` helper using `random_elements(..., unique=True)`, capped to the pool size so it can't crash on a 1-aisle department). `fake.aisle()`/`fake.department()` themselves are unchanged: independent draws that can repeat are the correct, intended behavior for actual data generation.

---

## [0.3.0] - 2026-09-20

### Added
- Closed test coverage gaps found in an audit of `GroceryStoreProvider`'s public API: `aisle_name()`, `aisle_id()` without filter, integer (not just numeric-string) `department=`/`aisle=` filters, `product(aisle=...)`, `grocery_item(aisle=..., department=...)`, `quantity(max_quantity=...)`, `shopping_datetime(date=<datetime.datetime>)`, unknown-aisle error handling, and cross-language name resolution (e.g. filtering with an English department name while the provider language is `fr`).
- Added `departments`/`aisles` property shape checks (counts, expected keys) as regression tests for the catalog data itself.
- **Internal consistency / data integrity tests**, not just plausibility checks in isolation: every product's `base_price` falls within its department's declared price range (full 49,688-row scan), every product's `department_id` agrees with its aisle's declared department, `product_record()`'s embedded aisle/department names agree with an independent catalog lookup, and a department-restricted `grocery_list()`'s items are fully coherent (department, unit and price all agree with the requested department, `quantity * unit_price == total_price`).
- **`unit(department=...)`**: units are now tied to what's plausible for a department (e.g. `L`/bottle/can for beverages, `kg`/bunch for produce, tube for personal care) via a new `department_units` catalog table, instead of being picked from one global list independently of the product. Fixes incoherent combinations such as "9 bottle x Bread" or "10 jar x Trash Bags" that a purely random unit could previously produce.
- Added `can` and `tube` as new unit keys.
- 25 new test cases overall (35 -> 60).

### Changed
- `grocery_item()` now calls `unit(department=...)` with the product's own department, so its `unit` field is always coherent with the product instead of independently random.
- Replaced the `units: {language: [unit, ...]}` data table with `unit_labels: {unit_key: {language: label}}` + `department_units: {department_id: [unit_key, ...]}`. **Breaking for direct data access**: code reading `provider._data["units"]` directly must switch to `unit_labels`/`department_units`; the public `unit()` method is backwards compatible (still returns a localized string, now with an optional `department` filter).
- Bumped version from 0.2.0 to 0.3.0.

### Fixed
- Documented (via `test_locale_property`) that `fake.locale` on the `Faker` instance is shadowed by Faker's own built-in `locale` attribute; `GroceryStoreProvider.locale` is only reachable on the provider instance directly (`GroceryStoreProvider(fake).locale`), not through the `Faker`/`fake.*` proxy. Not a bug, but a naming collision worth knowing about.

---

## [0.2.0] - 2026-09-20

### Added
- **Probable product prices**: every product now has a stable `base_price` derived from its department's typical price range (seeded on the product id, so it stays stable across data rebuilds).
  - `price(product=<id>)` returns that product's base price jittered by a random **±5%**.
  - `product_record()` now also returns `base_price` (stable catalog reference) and `price` (this instance, jittered).
  - `grocery_item()` prices its product the same way instead of drawing a fresh uniform-random price from the whole department range.
- **Family-aware shopping baskets**: `grocery_list()` gained a `family_size` parameter (default `2`, a couple) that scales:
  - the default item-count range, when `min_items`/`max_items` are not given explicitly;
  - the plausible quantity per item (bigger households buy more of a given article), via `grocery_item(family_size=...)` and `quantity(max_quantity=...)`.
  - The returned dict now includes a `family_size` field.
- **Optional shopping date/time**: new `shopping_datetime(date=None, open_hour=8, close_hour=20)` method returning a plausible trip datetime (random day within the last year, or a given date, combined with a random time within store opening hours).
  - `grocery_list(with_datetime=True)` (or passing `date=...`) adds a `shopping_datetime` field to the result.
- 12 new test cases covering price jitter, family-size scaling and shopping date/time generation.

### Changed
- `products` rows in `faker_grocery/data/grocery_data.json` gained a `base_price` field: `[id, aisle_id, department_id, base_price, name_<lang0>, name_<lang1>, ...]`.
- `scripts/build_data.py` now derives each product's `base_price` from its department's price range (triangular distribution skewed towards the cheaper end).
- Bumped version from 0.1.0 to 0.2.0 in `setup.py` and `faker_grocery/__version__`.
- Updated README.md and examples with the new pricing and basket features.

---

## [0.1.0] - 2026-09-20

### Added
- Initial release of `faker-grocery`.
- `GroceryStoreProvider` built from the Instacart Market Basket Analysis open dataset: 21 departments, 134 aisles, ~49,700 products.
- Support for 2 languages: `en` (source data) and `fr` (departments/aisles hand-translated, product names translated via a curated ~700-word word-substitution dictionary).
- `department()`, `department_id()`, `department_name()`, `aisle()`, `aisle_id()`, `aisle_name()` with optional filtering by department (id or localized name).
- `product()`, `product_record()`, `product_name()` with optional filtering by aisle and/or department.
- `price()`, `quantity()`, `unit()` helpers.
- `grocery_item()` and `grocery_list(min_items, max_items, department=None)` for randomized shopping list generation.
- `scripts/build_data.py` to (re)build the single-JSON catalog from `DATAS/*.csv` and the translation files in `scripts/translations/`, designed for adding further languages (`it`, `es`, `pt`, `de` planned).
- Test suite (`tests/test_grocery_store.py`), demo (`python -m faker_grocery`) and complete usage example (`examples/basic_usage.py`).

---

## Usage Guidelines

### How to Use This Changelog

1. **Before releasing a new version**:
   - Move all changes from `[Unreleased]` section to the new version section
   - Add the release date
   - Update the version in `faker_grocery/__init__.py` (`__version__`, read by `pyproject.toml`)
   - If the catalog data changed (`DATAS/*.csv` or `scripts/translations/*.json`), re-run `python scripts/build_data.py` before releasing

2. **When making changes**:
   - Add entries to the `[Unreleased]` section under the appropriate category
   - Use past tense for entries (e.g., "Added" not "Add")
   - Group similar changes together

3. **Categories**:
   - `Added`: New features
   - `Changed`: Changes to existing functionality
   - `Fixed`: Bug fixes
   - `Removed`: Features that were removed
   - `Deprecated`: Features that will be removed in future versions
   - `Security`: Security-related changes

### Versioning Rules

Follow [Semantic Versioning](https://semver.org/):

- **MAJOR version** (X.0.0): When you make incompatible API changes
- **MINOR version** (0.X.0): When you add functionality in a backwards-compatible manner
- **PATCH version** (0.0.X): When you make backwards-compatible bug fixes

### Example Workflow

```bash
# 1. Make your changes
# 2. Update CHANGELOG.md in [Unreleased] section
# 3. Commit changes
git add .
git commit -m "Add new feature X"

# 4. When ready to release:
#    - Create new version section in CHANGELOG.md
#    - Update version in faker_grocery/__init__.py
#    - Commit
git add CHANGELOG.md faker_grocery/__init__.py
git commit -m "Bump version to 0.3.0"

# 5. Tag the release
git tag -a v0.3.0 -m "Release v0.3.0"
git push origin v0.3.0

# 6. Publish to PyPI
rm -rf dist && python -m build
twine upload dist/*
```

### Changelog Entry Examples

```markdown
## [0.3.0] - YYYY-MM-DD

### Added
- Added support for Italian catalog data (`it`)
- Added `nutriscore` field to product records

### Changed
- Widened the price range for the "alcohol" department

### Fixed
- Fixed `aisle(department=...)` raising for department ids passed as `int`
```

---

## Template for New Entries

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- 

### Changed
- 

### Fixed
- 

### Removed
- 

### Deprecated
- 

### Security
- 
```
