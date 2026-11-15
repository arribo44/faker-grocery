#!/usr/bin/env python3
"""
Local web page to try the GroceryStoreProvider methods: pick a Faker locale,
one or more methods, a few options (department, aisle, diet, labels, month,
currency...) and how many records to generate; the records are shown as JSON
at the bottom of the page. A second tab builds a dataset (baskets, receipts,
customers, products or daily sales, as in `faker-grocery export`), shown as
JSON and as a table of flat rows, downloadable as JSON, JSONL or CSV.

    python playground/app.py            # http://127.0.0.1:8000
    python playground/app.py --port 8080

Standard library only (plus faker and faker_grocery).
"""
import argparse
import datetime
import inspect
import json
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from faker import Faker  # noqa: E402
from faker.config import AVAILABLE_LOCALES  # noqa: E402

from faker_grocery import SALES_GROUPINGS, GroceryStoreProvider, _load_data  # noqa: E402
from faker_grocery.export import DIETS, EXPORT_KINDS, flat_rows, records  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_COUNT = 1000
MAX_DATASET = 5000
# Not offered as methods: deprecated aliases, setters (used through the currency /
# pattern options) and sales_series (built in the dataset tab).
EXCLUDED = {"department", "department_name", "set_grocery_currency", "set_grocery_shopping_pattern", "sales_series"}

# Form fields passed to the methods taking a parameter of that name.
OPTION_PARAMS = ("department", "aisle", "diet", "labels", "month", "family_size", "weighted", "coherent",
                 "with_datetime", "trips")
# Required parameters, filled from a form field.
REQUIRED_SOURCES = {"product_id": "product_id", "aisle_id": "aisle", "department_id": "department",
                    "diet": "diet", "label": "labels"}
FIELD_NAMES = {"product_id": "Identifiant produit", "aisle": "Sous-rayon", "department": "Rayon",
               "diet": "Régime", "labels": "Labels"}

# Languages, currencies and shopping patterns have no public listing: read
# them from the (internal) data file. Departments and aisles use the public
# grocery_departments() / grocery_aisles().
DATA = _load_data()


def locale_groups():
    """[(group label, locales)]: the locales of each catalog language, then every other Faker locale."""
    groups = []
    seen = set()
    for lang in DATA["languages"]:
        locales = sorted(loc for loc in AVAILABLE_LOCALES if loc.split("_")[0] == lang)
        groups.append((f"Catalogue « {lang} »", locales))
        seen.update(locales)
    groups.append(("Autres locales (catalogue en anglais)", sorted(set(AVAILABLE_LOCALES) - seen)))
    return groups


LOCALE_GROUPS = locale_groups()
LOCALES = {locale for _, group in LOCALE_GROUPS for locale in group}


def methods():
    """{name: {doc, options, required}} of the provider's own public methods."""
    found = {}
    for name, member in inspect.getmembers(GroceryStoreProvider, inspect.isfunction):
        if name.startswith("_") or name in EXCLUDED or member.__qualname__.split(".")[0] != "GroceryStoreProvider":
            continue
        params = list(inspect.signature(member).parameters.values())[1:]
        required = [p.name for p in params if p.default is inspect.Parameter.empty]
        if any(p not in REQUIRED_SOURCES for p in required):
            continue
        doc = inspect.getdoc(member) or ""
        found[name] = {
            "doc": " ".join(doc.split("\n\n")[0].split()),
            "options": [p.name for p in params if p.name in OPTION_PARAMS and p.name not in required],
            "required": required,
        }
    return found


METHODS = methods()

_providers: dict[str, GroceryStoreProvider] = {}


def provider_of(locale, seed, currency=None, pattern=None):
    if locale not in _providers:
        _providers[locale] = GroceryStoreProvider(Faker(locale))
    provider = _providers[locale]
    provider.generator.seed_instance(seed)
    provider.set_grocery_currency(currency or None)
    provider.set_grocery_shopping_pattern(pattern or None)
    return provider


def locale_options(locale):
    """Departments and aisles named in the locale's catalog language."""
    provider = provider_of(locale, None)
    by_name = lambda entry: entry["name"].lower()  # noqa: E731
    departments = sorted(provider.grocery_departments(), key=by_name)
    aisles = sorted(provider.grocery_aisles(), key=by_name)
    return {
        "language": provider.language,
        "currency": provider.grocery_currency(),
        "pattern": provider.grocery_shopping_pattern(),
        "departments": departments,
        "aisles": aisles,
        "labels": {key: provider.grocery_label_name(key) for key in provider.grocery_labels()},
        "diets": {key: provider.grocery_diet_name(key) for key in provider.grocery_diets()},
    }


def read_options(query):
    """The method options of the form, typed, empty ones left out."""
    options = {}
    for key in ("department", "aisle", "month", "family_size", "trips", "product_id"):
        if query.get(key) not in (None, ""):
            options[key] = int(query[key])
    if query.get("diet"):
        if query["diet"] not in DIETS:
            raise ValueError(f"unknown diet {query['diet']!r}")
        options["diet"] = query["diet"]
    if query.get("labels"):
        options["labels"] = list(query["labels"])
    for key in ("weighted", "coherent", "with_datetime"):
        if key in query:
            options[key] = bool(query[key])
    if "month" in options and not 1 <= options["month"] <= 12:
        raise ValueError("month must be between 1 and 12")
    return options


def call(provider, name, options):
    info = METHODS[name]
    kwargs = {key: options[key] for key in info["options"] if key in options}
    for param in info["required"]:
        source = REQUIRED_SOURCES[param]
        if source not in options:
            raise ValueError(f"{name}() a besoin du champ « {FIELD_NAMES[source]} »")
        value = options[source]
        kwargs[param] = value[0] if source == "labels" else value
    return getattr(provider, name)(**kwargs)


def generate(provider, names, count, options):
    out = []
    for _ in range(count):
        record = {}
        for name in names:
            try:
                record[name] = call(provider, name, options)
            except Exception as error:  # show the error in place of the value
                record[name] = {"error": f"{type(error).__name__}: {error}"}
        out.append(record)
    return out


def dataset(provider, kind, count, options):
    if kind not in EXPORT_KINDS:
        raise ValueError(f"unknown kind {kind!r}")
    by = options.get("by") or "department"
    if by not in SALES_GROUPINGS:
        raise ValueError(f"unknown grouping {by!r}")
    start = datetime.date.fromisoformat(options["start"]) if options.get("start") else None
    generated = list(records(provider, kind, count, trips=int(options.get("trips") or 10),
                             diet=options.get("diet") or None, start=start, by=by,
                             baskets_per_day=int(options.get("baskets_per_day") or 1000)))
    rows = [row for record in generated for row in flat_rows(kind, record)]
    return {"records": generated, "rows": rows}


def read_query(handler):
    length = int(handler.headers.get("Content-Length", 0))
    query = json.loads(handler.rfile.read(length) or b"{}")
    locale = query.get("locale")
    if locale not in LOCALES:
        raise ValueError(f"unknown locale {locale!r}")
    seed = query.get("seed")
    seed = None if seed in (None, "") else int(seed)
    currency = query.get("currency") or None
    if currency and currency not in DATA["currencies"]:
        raise ValueError(f"unknown currency {currency!r}")
    pattern = query.get("pattern") or None
    if pattern and pattern not in DATA["shopping_patterns"]:
        raise ValueError(f"unknown shopping pattern {pattern!r}")
    return query, provider_of(locale, seed, currency, pattern)


def to_json(value):
    return json.dumps(value, ensure_ascii=False, default=lambda v: v.isoformat() if hasattr(v, "isoformat") else str(v))


class Handler(BaseHTTPRequestHandler):
    def send(self, status, body, content_type="application/json; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, status, value):
        self.send(status, to_json(value))

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            with open(os.path.join(HERE, "index.html"), encoding="utf-8") as f:
                self.send(HTTPStatus.OK, f.read(), "text/html; charset=utf-8")
        elif url.path == "/api/options":
            self.send_json(HTTPStatus.OK, {
                "locale_groups": LOCALE_GROUPS, "methods": METHODS, "currencies": sorted(DATA["currencies"]),
                "patterns": sorted(DATA["shopping_patterns"]), "kinds": EXPORT_KINDS, "groupings": SALES_GROUPINGS,
                "max_count": MAX_COUNT, "max_dataset": MAX_DATASET,
            })
        elif url.path == "/api/locale":
            locale = parse_qs(url.query).get("locale", [""])[0]
            if locale not in LOCALES:
                return self.send_json(HTTPStatus.BAD_REQUEST, {"error": f"unknown locale {locale!r}"})
            self.send_json(HTTPStatus.OK, locale_options(locale))
        else:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            query, provider = read_query(self)
            count = int(query.get("count", 1))
            if path == "/api/generate":
                names = query.get("methods") or []
                unknown = [name for name in names if name not in METHODS]
                if not names or unknown:
                    raise ValueError(f"pick at least one known method (unknown: {unknown})")
                if not 1 <= count <= MAX_COUNT:
                    raise ValueError(f"count must be between 1 and {MAX_COUNT}")
                result = generate(provider, names, count, read_options(query))
            elif path == "/api/dataset":
                if not 1 <= count <= MAX_DATASET:
                    raise ValueError(f"count must be between 1 and {MAX_DATASET}")
                result = dataset(provider, query.get("kind"), count, query)
            else:
                return self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except (ValueError, TypeError) as error:
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        self.send_json(HTTPStatus.OK, result)

    def log_message(self, format, *args):
        sys.stderr.write(f"{self.command} {self.path} {args[1] if len(args) > 1 else ''}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = HTTPServer((args.host, args.port), Handler)
    print(f"faker-grocery playground: http://{args.host}:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
