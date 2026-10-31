"""
Main module for faker_grocery
Allows running the package as a module: python -m faker_grocery
"""
from collections.abc import Collection
from typing import TypeVar

from faker import Faker

from faker_grocery import GroceryStoreProvider

T = TypeVar("T")


def distinct_sample(fake: Faker, elements: Collection[T], k: int = 5) -> list[T]:
    """k distinct elements (or all of them if there are fewer than k) -
    plain independent draws like `fake.department()` can repeat by design,
    which is correct for actual generation but makes a "look, here are 5
    examples" demo section misleading."""
    return list(fake.random_elements(elements=list(elements), length=min(k, len(elements)), unique=True))


def demo(locale: str) -> None:
    fake = Faker(locale)
    fake.add_provider(GroceryStoreProvider)
    # Typed handle on the provider: fake.department_name() & co. are added
    # dynamically by Faker, so type checkers can't see their signatures.
    provider = GroceryStoreProvider(fake)

    print("=" * 60)
    print(f"Faker Grocery Store Provider - Demo ({locale})")
    print("=" * 60)

    print("\n--- Departments (5 distinct examples) ---")
    for dept_key in distinct_sample(fake, provider.departments.keys()):
        print(f"  - {provider.department_name(dept_key)}")

    print("\n--- Aisles (5 distinct examples) ---")
    for aisle_id in distinct_sample(fake, provider.aisles.keys()):
        print(f"  - {fake.aisle_name(aisle_id)}")

    dept_id = provider.department_id()
    dept_name = provider.department_name(dept_id)
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


def main() -> None:
    for locale in ["en_US", "fr_FR"]:
        demo(locale)


if __name__ == "__main__":
    main()
