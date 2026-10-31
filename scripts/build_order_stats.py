#!/usr/bin/env python3
"""
Aggregate the (large, unversioned) Instacart order files into the two small
statistics files versioned in DATAS/ and used by build_data.py:

- DATAS/order_times.csv: number of orders per (order_dow, order_hour_of_day)
  slot, from orders.csv (~3.4M orders) - drives realistic shopping
  days/hours.
- DATAS/product_popularity.csv: number of times each product was ordered,
  from order_products__prior.csv (~32M rows) - drives popularity-weighted
  product picking.

The raw files come from the same Kaggle dataset as DATAS/*.csv (see the
README) and are only needed to regenerate these statistics:

    python scripts/build_order_stats.py path/to/orders.csv path/to/order_products__prior.csv
"""
import csv
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATAS_DIR = os.path.join(ROOT, "DATAS")


def order_times(orders_path):
    counts = Counter()
    with open(orders_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            counts[(int(row["order_dow"]), int(row["order_hour_of_day"]))] += 1
    return counts


def product_popularity(order_products_path):
    counts = Counter()
    with open(order_products_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        product_col = next(reader).index("product_id")
        for row in reader:
            counts[int(row[product_col])] += 1
    return counts


def main(orders_path, order_products_path):
    times = order_times(orders_path)
    out = os.path.join(DATAS_DIR, "order_times.csv")
    with open(out, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["order_dow", "order_hour_of_day", "order_count"])
        for dow in range(7):
            for hour in range(24):
                writer.writerow([dow, hour, times.get((dow, hour), 0)])
    print(f"Wrote {out} ({sum(times.values())} orders)")

    popularity = product_popularity(order_products_path)
    out = os.path.join(DATAS_DIR, "product_popularity.csv")
    with open(out, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["product_id", "order_count"])
        for product_id in sorted(popularity):
            writer.writerow([product_id, popularity[product_id]])
    print(f"Wrote {out} ({len(popularity)} products, {sum(popularity.values())} order lines)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
