#!/usr/bin/env python3
"""
Basic usage example for the GroceryStoreProvider.
Demonstrates all features with the supported locales.
"""
from faker import Faker

from faker_grocery import GroceryStoreProvider


def print_section(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def demo_locale(locale_name):
    print_section(f"Locale: {locale_name}")

    fake = Faker(locale_name)
    fake.add_provider(GroceryStoreProvider)

    print("\n--- 5 Random Departments ---")
    for i in range(5):
        print(f"  {i + 1}. {fake.department()}")

    print("\n--- 5 Random Aisles ---")
    for i in range(5):
        print(f"  {i + 1}. {fake.aisle()}")

    department = fake.department()
    print(f"\n--- 5 Aisles restricted to department '{department}' ---")
    for i in range(5):
        print(f"  {i + 1}. {fake.aisle(department=department)}")

    print("\n--- 10 Random Products ---")
    for i in range(10):
        print(f"  {i + 1}. {fake.product()}")

    print("\n--- 5 Product Records (id, name, aisle, department) ---")
    for i in range(5):
        record = fake.product_record()
        print(f"  {i + 1}. #{record['id']} {record['name']} "
              f"[{record['aisle']} / {record['department']}]")

    print("\n--- 5 Prices, quantities and units ---")
    for _ in range(5):
        print(f"  {fake.quantity()} {fake.unit()} - {fake.price():.2f}")

    print("\n--- Complete shopping list (default: couple, family_size=2) ---")
    shopping_list = fake.grocery_list()
    for item in shopping_list["items"]:
        print(f"  - {item['quantity']} {item['unit']} x {item['product']} "
              f"({item['aisle']} / {item['department']}): "
              f"{item['unit_price']:.2f}/{item['price_per']} = {item['total_price']:.2f}")
    print(f"\nFamily size: {shopping_list['family_size']}")
    print(f"Item count: {shopping_list['item_count']}")
    print(f"Total: {shopping_list['total']:.2f} {shopping_list['currency']}")

    print("\n--- Shopping list for a family of 5, with a shopping date/time ---")
    shopping_list = fake.grocery_list(family_size=5, with_datetime=True)
    print(f"Shopping trip: {shopping_list['shopping_datetime']}")
    for item in shopping_list["items"]:
        print(f"  - {item['quantity']} {item['unit']} x {item['product']}: {item['total_price']:.2f}")
    print(f"Total: {shopping_list['total']:.2f} {shopping_list['currency']}")

    print("\n--- Shopping list restricted to one department ---")
    department = fake.department()
    shopping_list = fake.grocery_list(min_items=3, max_items=5, department=department)
    print(f"Department: {department}")
    for item in shopping_list["items"]:
        print(f"  - {item['quantity']} {item['unit']} x {item['product']}: {item['total_price']:.2f}")
    print(f"Total: {shopping_list['total']:.2f} {shopping_list['currency']}")

    print("\n--- Same product priced twice: base_price vs jittered price (+/-5%) ---")
    record = fake.product_record()
    print(f"  {record['name']}: base_price={record['base_price']:.2f}, price now={record['price']:.2f}")
    for _ in range(3):
        print(f"    price(product={record['id']}) -> {fake.price(product=record['id']):.2f}")


def main():
    print_section("Faker Grocery Store Provider - Complete Demo")
    for locale in ["en_US", "fr_FR"]:
        demo_locale(locale)

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
