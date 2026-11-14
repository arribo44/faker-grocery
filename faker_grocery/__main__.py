"""
Command line for faker_grocery: `python -m faker_grocery` (or the
`faker-grocery` script).

    faker-grocery                          # demo (en_US and fr_FR)
    faker-grocery demo --locale de_DE      # demo for one locale
    faker-grocery export baskets -n 1000 --locale fr_FR --format csv -o baskets.csv
    faker-grocery export receipts -n 500 --format jsonl --seed 42
    faker-grocery export customers -n 50 --trips 12 --format csv
    faker-grocery export products -n 2000 --format json

CSV has one row per basket item (baskets, customers), per receipt line
(receipts) or per product (products), the basket/receipt fields repeated on
each row; JSON / JSON Lines keep the nested structure.
"""
import argparse
import csv
import datetime
import json
import sys
from collections.abc import Collection, Iterator
from typing import IO, Any, TypeVar

from faker import Faker

from faker_grocery import GroceryStoreProvider

T = TypeVar("T")


def distinct_sample(fake: Faker, elements: Collection[T], k: int = 5) -> list[T]:
    """k distinct elements (or all of them if there are fewer than k) -
    plain independent draws like `fake.grocery_department()` can repeat by design,
    which is correct for actual generation but makes a "look, here are 5
    examples" demo section misleading."""
    return list(fake.random_elements(elements=list(elements), length=min(k, len(elements)), unique=True))


def demo(locale: str) -> None:
    fake = Faker(locale)
    fake.add_provider(GroceryStoreProvider)
    # Typed handle on the provider: fake.grocery_department_name() & co. are added
    # dynamically by Faker, so type checkers can't see their signatures.
    provider = GroceryStoreProvider(fake)

    print("=" * 60)
    print(f"Faker Grocery Store Provider - Demo ({locale})")
    print("=" * 60)

    print("\n--- Departments (5 distinct examples) ---")
    for dept_key in distinct_sample(fake, provider.departments.keys()):
        print(f"  - {provider.grocery_department_name(dept_key)}")

    print("\n--- Aisles (5 distinct examples) ---")
    for aisle_id in distinct_sample(fake, provider.aisles.keys()):
        print(f"  - {fake.aisle_name(aisle_id)}")

    dept_id = provider.department_id()
    dept_name = provider.grocery_department_name(dept_id)
    dept_aisle_ids = [a for a, info in provider.aisles.items() if info["department_id"] == dept_id]
    print(f"\n--- Aisles in department '{dept_name}' (distinct examples) ---")
    for aisle_id in distinct_sample(fake, dept_aisle_ids):
        print(f"  - {fake.aisle_name(aisle_id)}")

    print("\n--- Products ---")
    for _ in range(5):
        print(f"  - {fake.product()}")

    print("\n--- Product record ---")
    print(f"  {fake.product_record()}")

    print("\n--- Prices / quantities / units ---")
    print(f"  price: {fake.price()} {fake.grocery_currency()}")
    print(f"  quantity: {fake.quantity()}")
    print(f"  unit: {fake.unit()}")

    print("\n--- Grocery item ---")
    print(f"  {fake.grocery_item()}")

    print("\n--- Grocery list (default: couple) ---")
    shopping_list = fake.grocery_list(min_items=3, max_items=6, with_datetime=True)
    print(f"  Shopping trip: {shopping_list['shopping_datetime']}")
    for item in shopping_list["items"]:
        print(f"  {item['quantity']} {item['unit']} x {item['product']} "
              f"({item['aisle']} / {item['department']}): {item['total_price']} {shopping_list['currency']}")
    print(f"  Family size: {shopping_list['family_size']}  Total: {shopping_list['total']} {shopping_list['currency']}")

    print("\n--- Grocery list for a family of 4 ---")
    shopping_list = fake.grocery_list(family_size=4)
    print(f"  Item count: {shopping_list['item_count']}  Total: {shopping_list['total']} {shopping_list['currency']}")

    print("\n--- Receipt ---")
    receipt = provider.receipt(promotion_rate=0.3)
    print(f"  {receipt['store']['name']} - {receipt['store']['address']}")
    print(f"  No {receipt['receipt_number']}  {receipt['datetime']:%Y-%m-%d %H:%M}")
    for line in receipt["lines"]:
        promotion = f"  [{line['promotion']} -{line['discount']}]" if line["promotion"] else ""
        print(f"  {line['quantity']} {line['unit']} x {line['product']}: {line['total_price']}{promotion}")
    for tax in receipt["taxes"]:
        print(f"  VAT {tax['rate']:.1%}: {tax['amount']} on {tax['base']}")
    print(f"  Total: {receipt['total']} {receipt['currency']} ({receipt['payment_method']}, "
          f"tendered {receipt['amount_tendered']}, change {receipt['change']})")


# -- export -----------------------------------------------------------------------

EXPORT_KINDS = ("baskets", "receipts", "customers", "products")
FORMATS = ("csv", "jsonl", "json")


def _records(provider: GroceryStoreProvider, kind: str, count: int, trips: int) -> Iterator[dict[str, Any]]:
    """`count` nested records of `kind`, each with a stable id."""
    for index in range(1, count + 1):
        if kind == "baskets":
            yield {"basket_id": index, **provider.grocery_list(with_datetime=True)}
        elif kind == "receipts":
            yield {"receipt_id": index, **provider.receipt()}
        elif kind == "customers":
            profile = provider.customer_profile()
            history = provider.customer_history(profile, trips=trips)
            yield {**profile, "baskets": [{"trip": n, **basket} for n, basket in enumerate(history, 1)]}
        else:
            yield dict(provider.product_record())


def _flat_rows(kind: str, record: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """CSV rows of a record: one per item / line, parent fields repeated."""
    if kind == "products":
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


def export(kind: str, count: int, locale: str, fmt: str, out: IO[str], seed: int | None = None,
           trips: int = 10) -> int:
    """Write `count` generated `kind` records to `out`; returns the number of
    rows / records written."""
    fake = Faker(locale)
    if seed is not None:
        fake.seed_instance(seed)
    provider = GroceryStoreProvider(fake)
    records = _records(provider, kind, count, trips)
    written = 0
    if fmt == "json":
        json.dump(list(records), out, ensure_ascii=False, indent=2, default=_json_default)
        out.write("\n")
        return count
    if fmt == "jsonl":
        for record in records:
            out.write(json.dumps(record, ensure_ascii=False, default=_json_default) + "\n")
            written += 1
        return written
    writer: csv.DictWriter[str] | None = None
    for record in records:
        for row in _flat_rows(kind, record):
            row = {k: v.isoformat() if isinstance(v, datetime.date) else v for k, v in row.items()}
            if writer is None:
                writer = csv.DictWriter(out, fieldnames=list(row), extrasaction="ignore", restval="")
                writer.writeheader()
            writer.writerow(row)
            written += 1
    return written


def _positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {value}")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="faker-grocery", description="Fake supermarket data: demo or bulk export.")
    commands = parser.add_subparsers(dest="command")
    demo_parser = commands.add_parser("demo", help="print examples of every generator")
    demo_parser.add_argument("--locale", action="append", help="Faker locale (repeatable; default: en_US and fr_FR)")
    export_parser = commands.add_parser("export", help="generate many records to CSV / JSON / JSON Lines")
    export_parser.add_argument("kind", choices=EXPORT_KINDS)
    export_parser.add_argument("-n", "--count", type=_positive, default=100, help="number of records (default 100)")
    export_parser.add_argument("--locale", default="en_US", help="Faker locale (default en_US)")
    export_parser.add_argument("--format", choices=FORMATS, default="csv", help="output format (default csv)")
    export_parser.add_argument("-o", "--output", help="output file (default: standard output)")
    export_parser.add_argument("--seed", type=int, help="seed, for reproducible output")
    export_parser.add_argument("--trips", type=_positive, default=10,
                               help="baskets per customer, for 'customers' (default 10)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "export":
        if args.output:
            with open(args.output, "w", encoding="utf-8", newline="") as out:
                written = export(args.kind, args.count, args.locale, args.format, out, args.seed, args.trips)
            print(f"Wrote {written} {'rows' if args.format == 'csv' else 'records'} to {args.output}", file=sys.stderr)
        else:
            export(args.kind, args.count, args.locale, args.format, sys.stdout, args.seed, args.trips)
        return 0
    for locale in (args.locale if args.command == "demo" and args.locale else ["en_US", "fr_FR"]):
        demo(locale)
    return 0


if __name__ == "__main__":
    sys.exit(main())
