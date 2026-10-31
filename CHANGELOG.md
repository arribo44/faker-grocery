# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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
- Packaging moved from `setup.py` to `pyproject.toml`; the version is now read from `faker_grocery.__version__` only. `requires-python` raised from `>=3.7` to `>=3.9` (Faker 20+ already required 3.8+), classifiers now list 3.9-3.14.
- The private Faker locale lookup is isolated in `_generator_locale()`.

### Added
- GitHub Actions CI: ruff, pytest on Python 3.9-3.14 plus Faker 20.0.0, package build check.
- `dev` extra (`pytest`, `ruff`, `build`) and a pinned ruff rule set.
- 12 new tests (60 -> 72): argument validation, seed reproducibility, multi-locale usage.
- README: multi-locale usage (`fake[locale].add_provider(...)`) and error behavior.
- README: "Data source & license" section (original Instacart source, CC0 Kaggle re-upload actually used, MIT scope limited to the code).

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
