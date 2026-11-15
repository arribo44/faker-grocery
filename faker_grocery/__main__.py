"""
Command line for faker_grocery: `python -m faker_grocery` (or the
`faker-grocery` script).

    faker-grocery                          # demo (en_US and fr_FR)
    faker-grocery demo --locale de_DE      # demo for one locale
    faker-grocery --locale fr_FR           # same, without "demo" (or -l fr_FR)
    faker-grocery export baskets -n 1000 --locale fr_FR --format csv -o baskets.csv
    faker-grocery export receipts -n 500 --format jsonl --seed 42
    faker-grocery export customers -n 50 --trips 12 --format csv
    faker-grocery export products -n 2000 --format json
    faker-grocery export products -n 500 --format csv --csv-safe -o products.csv
    faker-grocery export customers -n 200 --diet random --format parquet -o customers.parquet
    faker-grocery export sales -n 365 --start 2026-01-01 --by aisle --locale de_DE -o sales.csv

CSV and Parquet have one row per basket item (baskets, customers), per
receipt line (receipts), per product (products) or per day and department /
aisle (sales: -n is a number of days), the basket/receipt fields repeated on
each row; JSON / JSON Lines keep the nested structure. Parquet needs
pyarrow (pip install "faker-grocery[data]") and -o. `--csv-safe` prefixes
text cells starting with = + - @ (or a tab / carriage return) with a quote,
so that spreadsheet software opening the file doesn't run them as formulas.

With `-o`, the file is written next to its destination under a temporary
name and only renamed once complete: an interrupted export leaves no
half-written file behind.
"""
import argparse
import contextlib
import datetime
import os
import sys
import tempfile
from collections.abc import Collection
from typing import Any, TypeVar

from faker import Faker
from faker.config import AVAILABLE_LOCALES

from faker_grocery import SALES_GROUPINGS, GroceryStoreProvider
from faker_grocery.export import (  # noqa: F401 - _csv_cell re-exported for tests
    DIETS,
    EXPORT_KINDS,
    FORMATS,
    _csv_cell,
    export,
    export_parquet,
)

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

    print("\n--- Labels and diets ---")
    for label in ("organic", "gluten_free", "vegan"):
        print(f"  {provider.grocery_label_name(label)}: {fake.product(labels=label)}")
    vegan_basket = provider.grocery_list(diet="vegan", min_items=3, max_items=3)
    print(f"  {provider.grocery_diet_name('vegan')} basket: {', '.join(i['product'] for i in vegan_basket['items'])}")

    print("\n--- Sales (last 7 days, whole store) ---")
    for row in provider.sales_series(datetime.date.today() - datetime.timedelta(days=6), by="total"):
        print(f"  {row['date']:%a %Y-%m-%d}: {row['baskets']} baskets, {row['items']} items, "
              f"{row['revenue']} {row['currency']}")

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


def _positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {value}")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="faker-grocery", description="Fake supermarket data: demo or bulk export.")
    # `faker-grocery --locale fr_FR` = `faker-grocery demo --locale fr_FR`
    # (argparse also accepts the unambiguous prefix `--local`).
    parser.add_argument("-l", "--locale", action="append", dest="main_locales", metavar="LOCALE",
                        help="demo for this Faker locale (repeatable; default: en_US and fr_FR)")
    commands = parser.add_subparsers(dest="command")
    demo_parser = commands.add_parser("demo", help="print examples of every generator")
    demo_parser.add_argument("--locale", action="append", help="Faker locale (repeatable; default: en_US and fr_FR)")
    export_parser = commands.add_parser("export", help="generate many records to CSV / JSON / JSON Lines / Parquet")
    export_parser.add_argument("kind", choices=EXPORT_KINDS)
    export_parser.add_argument("-n", "--count", type=_positive, default=100,
                               help="number of records, or of days for 'sales' (default 100)")
    export_parser.add_argument("--locale", default="en_US", help="Faker locale (default en_US)")
    export_parser.add_argument("--format", choices=FORMATS, default="csv", help="output format (default csv)")
    export_parser.add_argument("-o", "--output", help="output file (default: standard output)")
    export_parser.add_argument("--seed", type=int, help="seed, for reproducible output")
    export_parser.add_argument("--trips", type=_positive, default=10,
                               help="baskets per customer, for 'customers' (default 10)")
    export_parser.add_argument("--csv-safe", action="store_true",
                               help="quote text cells starting with = + - @ (spreadsheet formula injection)")
    export_parser.add_argument("--diet", choices=[*DIETS, "random"],
                               help="only products fitting this diet (baskets, receipts, customers, products); "
                                    "'random': a few customers follow one")
    export_parser.add_argument("--start", type=datetime.date.fromisoformat,
                               help="first day, YYYY-MM-DD, for 'sales' (default: January 1st of this year)")
    export_parser.add_argument("--by", choices=SALES_GROUPINGS, default="department",
                               help="sales grouping, for 'sales' (default department)")
    export_parser.add_argument("--baskets-per-day", type=_positive, default=1000,
                               help="store traffic on an average day, for 'sales' (default 1000)")
    return parser


def _check_locale(parser: argparse.ArgumentParser, locale: str) -> None:
    if locale not in AVAILABLE_LOCALES:
        close = sorted(name for name in AVAILABLE_LOCALES if name.split("_")[0] == locale.split("_")[0])
        hint = f" (did you mean {', '.join(close)}?)" if close else ""
        parser.error(f"unknown Faker locale: {locale!r}{hint}")


def _options(args: argparse.Namespace) -> dict[str, Any]:
    return {"diet": args.diet, "start": args.start, "by": args.by, "baskets_per_day": args.baskets_per_day}


def _export_to_file(args: argparse.Namespace) -> int:
    """Write to a temporary file in the destination directory, renamed to
    the destination only once the export is complete."""
    path = os.path.abspath(args.output)
    descriptor, temporary = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".faker-grocery-", suffix=".tmp")
    try:
        if args.format == "parquet":
            os.close(descriptor)
            written = export_parquet(args.kind, args.count, args.locale, temporary, args.seed, args.trips,
                                     **_options(args))
        else:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as out:
                written = export(args.kind, args.count, args.locale, args.format, out, args.seed, args.trips,
                                 args.csv_safe, **_options(args))
        os.chmod(temporary, 0o666 & ~_umask())
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temporary)
        raise
    return written


def _umask() -> int:
    mask = os.umask(0)
    os.umask(mask)
    return mask


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "export" and args.main_locales:
        parser.error("put --locale after 'export': faker-grocery export KIND --locale LOCALE")
    demo_locales = args.locale if args.command == "demo" else None
    locales = demo_locales or args.main_locales or ["en_US", "fr_FR"]
    if args.command == "export":
        locales = [args.locale]
    for locale in locales:
        _check_locale(parser, locale)
    if args.command == "export":
        if args.format == "parquet" and not args.output:
            parser.error("--format parquet needs an output file (-o FILE)")
        if args.diet == "random" and args.kind != "customers":
            parser.error("--diet random only applies to customers")
        if args.diet and args.kind == "sales":
            parser.error("--diet does not apply to sales")
        try:
            if args.output:
                written = _export_to_file(args)
                unit = "rows" if args.format in ("csv", "parquet") or args.kind == "sales" else "records"
                print(f"Wrote {written} {unit} to {args.output}", file=sys.stderr)
            else:
                export(args.kind, args.count, args.locale, args.format, sys.stdout, args.seed, args.trips,
                       args.csv_safe, **_options(args))
                # Flush here: a small output is still buffered, and a broken
                # pipe would otherwise only surface at interpreter exit.
                sys.stdout.flush()
        except BrokenPipeError:
            # `faker-grocery export ... | head`: the reader left, not an error.
            # Point stdout at devnull so the interpreter's final flush is quiet.
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
            return 0
        except (OSError, ImportError) as error:
            print(f"faker-grocery: error: {error}", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            print("faker-grocery: interrupted", file=sys.stderr)
            return 130
        return 0
    for locale in locales:
        demo(locale)
    return 0


if __name__ == "__main__":
    sys.exit(main())
