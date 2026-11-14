#!/usr/bin/env python3
"""
Aggregate the (large, unversioned) Instacart order files into the two small
statistics files versioned in DATAS/ and used by build_data.py:

- DATAS/order_times.csv: number of orders per (order_dow, order_hour_of_day)
  slot, from orders.csv (~3.4M orders) - drives realistic shopping
  days/hours.
- DATAS/product_popularity.csv: number of times each product was ordered
  (and re-ordered by the same customer), from order_products__prior.csv
  (~32M rows) - drives popularity-weighted product picking and customers'
  favorite products.
- DATAS/basket_sizes.csv: number of orders per basket size (items per order).
- DATAS/aisle_orders.csv / DATAS/aisle_pairs.csv: number of orders containing
  each aisle / each pair of aisles - drives complementary products in
  coherent baskets (aisles bought together more often than by chance).
- DATAS/customer_intervals.csv: number of customers per median number of
  days between their orders (Instacart caps it at 30).
- DATAS/customer_reorder_rates.csv: number of customers per share (in 5%
  steps) of their items that are re-orders of products they bought before.

The raw files come from the same Kaggle dataset as DATAS/*.csv (see the
README) and are only needed to regenerate these statistics:

    python scripts/build_order_stats.py path/to/orders.csv path/to/order_products__prior.csv
"""
import csv
import itertools
import os
import statistics
import sys
from collections import Counter, defaultdict

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


def write_csv(name, header, rows):
    out = os.path.join(DATAS_DIR, name)
    with open(out, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    return out


def load_orders(orders_path):
    """order_id -> (user_id, order_number), and per-user lists of days
    since the previous order, for the prior orders."""
    orders = {}
    intervals = defaultdict(list)
    with open(orders_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["eval_set"] != "prior":
                continue
            orders[int(row["order_id"])] = (int(row["user_id"]), int(row["order_number"]))
            if row["days_since_prior_order"]:
                intervals[int(row["user_id"])].append(float(row["days_since_prior_order"]))
    return orders, intervals


def load_product_aisles():
    with open(os.path.join(DATAS_DIR, "products.csv"), encoding="utf-8") as f:
        return {int(row["product_id"]): int(row["aisle_id"]) for row in csv.DictReader(f)}


def basket_statistics(order_products_path, orders, product_aisles):
    """One pass over order_products (sorted by order_id): products ordered /
    re-ordered, basket sizes, aisle and aisle-pair order counts, and per-user
    re-ordered / re-orderable item counts."""
    product_orders, product_reorders = Counter(), Counter()
    basket_sizes = Counter()
    aisle_orders = Counter()
    pair_counts = [[0] * 135 for _ in range(135)]
    user_items, user_reordered = Counter(), Counter()

    def flush(order_id, items):
        basket_sizes[len(items)] += 1
        aisles = sorted({product_aisles[product_id] for product_id, _ in items})
        for aisle in aisles:
            aisle_orders[aisle] += 1
        for a, b in itertools.combinations(aisles, 2):
            pair_counts[a][b] += 1
        user, number = orders.get(order_id, (None, 1))
        if user is not None and number > 1:
            user_items[user] += len(items)
            user_reordered[user] += sum(reordered for _, reordered in items)

    with open(order_products_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        order_col, product_col, reordered_col = (header.index(c) for c in ("order_id", "product_id", "reordered"))
        current, items = None, []
        for row in reader:
            order_id, product_id, reordered = int(row[order_col]), int(row[product_col]), int(row[reordered_col])
            if order_id != current:
                if items:
                    flush(current, items)
                current, items = order_id, []
            items.append((product_id, reordered))
            product_orders[product_id] += 1
            product_reorders[product_id] += reordered
        if items:
            flush(current, items)
    pairs = [(a, b, pair_counts[a][b]) for a in range(135) for b in range(a + 1, 135) if pair_counts[a][b]]
    return product_orders, product_reorders, basket_sizes, aisle_orders, pairs, user_items, user_reordered


def main(orders_path, order_products_path):
    times = order_times(orders_path)
    out = write_csv("order_times.csv", ["order_dow", "order_hour_of_day", "order_count"],
                    ([dow, hour, times.get((dow, hour), 0)] for dow in range(7) for hour in range(24)))
    print(f"Wrote {out} ({sum(times.values())} orders)")

    orders, intervals = load_orders(orders_path)
    stats = basket_statistics(order_products_path, orders, load_product_aisles())
    product_orders, product_reorders, basket_sizes, aisle_orders, pairs, user_items, user_reordered = stats

    out = write_csv("product_popularity.csv", ["product_id", "order_count", "reorder_count"],
                    ([p, product_orders[p], product_reorders[p]] for p in sorted(product_orders)))
    print(f"Wrote {out} ({len(product_orders)} products, {sum(product_orders.values())} order lines)")

    out = write_csv("basket_sizes.csv", ["item_count", "order_count"], sorted(basket_sizes.items()))
    print(f"Wrote {out} ({sum(basket_sizes.values())} orders)")

    out = write_csv("aisle_orders.csv", ["aisle_id", "order_count"], sorted(aisle_orders.items()))
    print(f"Wrote {out}")
    out = write_csv("aisle_pairs.csv", ["aisle_id", "other_aisle_id", "order_count"], pairs)
    print(f"Wrote {out} ({len(pairs)} pairs)")

    medians = Counter(min(30, round(statistics.median(days))) for days in intervals.values() if days)
    out = write_csv("customer_intervals.csv", ["median_days", "customer_count"], sorted(medians.items()))
    print(f"Wrote {out} ({sum(medians.values())} customers)")

    rates = Counter(
        5 * round(20 * user_reordered[user] / user_items[user]) for user in user_items if user_items[user]
    )
    out = write_csv("customer_reorder_rates.csv", ["reorder_pct", "customer_count"], sorted(rates.items()))
    print(f"Wrote {out} ({sum(rates.values())} customers)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
