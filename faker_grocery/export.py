"""
Bulk generation of faker_grocery records, shared by the command line
(`faker-grocery export`) and the Python API:

    from faker_grocery.export import to_dataframe, export_parquet

    df = to_dataframe("baskets", 1000, locale="fr_FR", seed=42)       # pandas, one row per item
    sales = to_dataframe("sales", 365, locale="de_DE", by="aisle")   # 365 days x 134 aisles
    export_parquet("receipts", 10000, "en_US", "receipts.parquet")

Kinds: baskets, receipts, customers, products, sales. Flat rows (CSV,
Parquet, `to_dataframe()`) have one row per basket item (baskets,
customers), per receipt line (receipts), per product or per day and
department / aisle (sales), the parent fields repeated on each row; JSON /
JSON Lines keep the nested structure.

`to_dataframe()` and Parquet need pandas / pyarrow:
`pip install "faker-grocery[data]"`.
"""
import csv
import datetime
import json
import textwrap
from collections.abc import Iterator
from typing import IO, Any

from faker import Faker

from faker_grocery import SALES_GROUPINGS, GroceryStoreProvider

EXPORT_KINDS = ("baskets", "receipts", "customers", "products", "sales")
FORMATS = ("csv", "jsonl", "json", "parquet")
DIETS = ("vegetarian", "vegan", "gluten_free", "lactose_free")

_DATA_EXTRA = 'install them with: pip install "faker-grocery[data]"'


def make_provider(locale: str = "en_US", seed: int | None = None) -> GroceryStoreProvider:
    """A provider on a new Faker(locale) generator, seeded if `seed` is given."""
    fake = Faker(locale)
    if seed is not None:
        fake.seed_instance(seed)
    return GroceryStoreProvider(fake)


def check_options(kind: str, diet: str | None = None, by: str = "department") -> None:
    """Raise ValueError for an unknown kind, diet or sales grouping."""
    if kind not in EXPORT_KINDS:
        raise ValueError(f"Unknown kind: {kind!r} (expected one of {', '.join(EXPORT_KINDS)})")
    if diet is not None and diet not in DIETS and not (diet == "random" and kind == "customers"):
        allowed = ", ".join(DIETS) + (", random" if kind == "customers" else "")
        raise ValueError(f"Unknown diet for {kind}: {diet!r} (expected one of {allowed})")
    if diet is not None and kind == "sales":
        raise ValueError("diet does not apply to sales")
    if by not in SALES_GROUPINGS:
        raise ValueError(f"Unknown sales grouping: {by!r} (expected one of {', '.join(SALES_GROUPINGS)})")


def records(
    provider: GroceryStoreProvider,
    kind: str,
    count: int,
    trips: int = 10,
    diet: str | None = None,
    start: datetime.date | None = None,
    by: str = "department",
    baskets_per_day: int = 1000,
) -> Iterator[dict[str, Any]]:
    """Nested records of `kind`, generated one at a time: `count` baskets,
    receipts, customers (with `trips` baskets each) or products, each with a
    stable id; or, for sales, `count` days from `start` (default: January
    1st of the current year) grouped `by` total, department or aisle.
    `diet` restricts baskets, receipts, customers and products to it
    ("random" for customers: see `customer_profile`)."""
    check_options(kind, diet, by)
    if kind == "sales":
        first = start if start is not None else datetime.date(datetime.date.today().year, 1, 1)
        # One month at a time, so memory doesn't grow with `count`.
        day, last = first, first + datetime.timedelta(days=count - 1)
        while day <= last:
            chunk_end = min(last, day + datetime.timedelta(days=30))
            for row in provider.sales_series(day, chunk_end, by=by, baskets_per_day=baskets_per_day):
                yield dict(row)
            day = chunk_end + datetime.timedelta(days=1)
        return
    for index in range(1, count + 1):
        if kind == "baskets":
            yield {"basket_id": index, **provider.grocery_list(with_datetime=True, diet=diet)}
        elif kind == "receipts":
            basket = provider.grocery_list(with_datetime=True, diet=diet) if diet is not None else None
            yield {"receipt_id": index, **provider.receipt(basket=basket)}
        elif kind == "customers":
            profile = provider.customer_profile(diet=diet)
            history = provider.customer_history(profile, trips=trips)
            yield {**profile, "baskets": [{"trip": n, **basket} for n, basket in enumerate(history, 1)]}
        else:
            yield dict(provider.product_record(diet=diet))


def flat_rows(kind: str, record: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Flat rows of a record: one per item / line, parent fields repeated."""
    if kind in ("products", "sales"):
        yield record
    elif kind == "baskets":
        parent = {k: v for k, v in record.items() if k != "items"}
        for item in record["items"]:
            yield {**parent, **item}
    elif kind == "receipts":
        parent = {k: v for k, v in record.items() if k not in ("lines", "taxes", "store")}
        store = {f"store_{k}": v for k, v in record["store"].items()}
        for line in record["lines"]:
            yield {**parent, **store, **{f"line_{k}" if k in parent else k: v for k, v in line.items()}}
    else:
        customer = {k: v for k, v in record.items() if k not in ("baskets", "favorite_product_ids")}
        for basket in record["baskets"]:
            parent = {k: v for k, v in basket.items() if k not in ("items", "customer_id", "family_size")}
            for item in basket["items"]:
                yield {**customer, **parent, **item}


def _json_default(value: object) -> str:
    if isinstance(value, datetime.date | datetime.datetime):
        return value.isoformat()
    raise TypeError(f"Not JSON serializable: {type(value).__name__}")


_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _csv_cell(value: Any, safe: bool) -> Any:
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, list):
        value = "|".join(str(v) for v in value)
    if safe and isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def export(kind: str, count: int, locale: str, fmt: str, out: IO[str], seed: int | None = None,
           trips: int = 10, csv_safe: bool = False, **options: Any) -> int:
    """Write `count` generated `kind` records to `out` as csv, jsonl or json
    (Parquet: see `export_parquet`); returns the number of rows / records
    written. Records are generated and written one at a time, so memory use
    doesn't grow with `count` (JSON included). `options`: diet, start, by,
    baskets_per_day (see `records`)."""
    if fmt == "parquet":
        raise ValueError("Parquet is a binary format: use export_parquet() with a file path")
    if fmt not in FORMATS:
        raise ValueError(f"Unknown format: {fmt!r} (expected one of {', '.join(FORMATS)})")
    generated = records(make_provider(locale, seed), kind, count, trips, **options)
    written = 0
    if fmt == "json":
        # Same output as json.dump(list, indent=2), without the list in memory.
        out.write("[")
        for record in generated:
            text = json.dumps(record, ensure_ascii=False, indent=2, default=_json_default)
            out.write(("," if written else "") + "\n" + textwrap.indent(text, "  "))
            written += 1
        out.write("\n]\n" if written else "]\n")
        return written
    if fmt == "jsonl":
        for record in generated:
            out.write(json.dumps(record, ensure_ascii=False, default=_json_default) + "\n")
            written += 1
        return written
    writer: csv.DictWriter[str] | None = None
    for record in generated:
        for row in flat_rows(kind, record):
            row = {k: _csv_cell(v, csv_safe) for k, v in row.items()}
            if writer is None:
                writer = csv.DictWriter(out, fieldnames=list(row), extrasaction="ignore", restval="")
                writer.writeheader()
            writer.writerow(row)
            written += 1
    return written


def _rows(kind: str, count: int, locale: str, seed: int | None, trips: int, flat: bool,
          options: dict[str, Any]) -> list[dict[str, Any]]:
    generated = records(make_provider(locale, seed), kind, count, trips, **options)
    if not flat:
        return list(generated)
    return [row for record in generated for row in flat_rows(kind, record)]


def export_parquet(kind: str, count: int, locale: str, path: str, seed: int | None = None, trips: int = 10,
                   **options: Any) -> int:
    """Write `count` generated `kind` records to a Parquet file at `path`, as
    flat rows with native types (dates, timestamps, label lists); returns the
    number of rows. Needs pyarrow. The rows are built in memory first."""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as error:
        raise ImportError(f"Parquet export needs pyarrow: {_DATA_EXTRA}") from error
    rows = _rows(kind, count, locale, seed, trips, True, options)
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path)
    return len(rows)


def to_dataframe(kind: str, count: int = 100, locale: str = "en_US", seed: int | None = None, trips: int = 10,
                 flat: bool = True, **options: Any) -> Any:
    """A pandas DataFrame of `count` generated `kind` records: flat rows
    (one per basket item / receipt line / product / day and group, as in
    CSV) by default, or one row per record with the nested fields as
    Python objects with `flat=False`. `options`: diet, start, by,
    baskets_per_day (see `records`). Needs pandas."""
    try:
        import pandas as pd
    except ImportError as error:
        raise ImportError(f"to_dataframe() needs pandas: {_DATA_EXTRA}") from error
    frame = pd.DataFrame(_rows(kind, count, locale, seed, trips, flat, options))
    for column in ("datetime", "shopping_datetime", "date"):
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column])
    return frame
