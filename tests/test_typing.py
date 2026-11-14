"""
Typing checks for the public API.

Run by pytest (the TypedDicts must describe exactly the keys the provider
really returns) and by mypy in CI (the documented ways of getting typed
results must type-check, see the README's "Type hints" section).
"""
import datetime
import unittest
from typing import assert_type

from faker import Faker

from faker_grocery import (
    CustomerProfile,
    GroceryItem,
    GroceryList,
    GroceryStore,
    GroceryStoreProvider,
    ProductRecord,
    Receipt,
    ReceiptLine,
    TaxLine,
)


def make_faker() -> Faker:
    fake = Faker("fr_FR")
    fake.add_provider(GroceryStoreProvider)
    return fake


class TestTypedDictsMatchRuntime(unittest.TestCase):
    def setUp(self) -> None:
        Faker.seed(1)
        self.fake = make_faker()

    def test_product_record_keys(self) -> None:
        self.assertEqual(set(self.fake.product_record()), set(ProductRecord.__annotations__))

    def test_grocery_item_keys(self) -> None:
        self.assertEqual(set(self.fake.grocery_item()), set(GroceryItem.__annotations__))

    def test_grocery_list_keys(self) -> None:
        self.assertEqual(set(self.fake.grocery_list()), GroceryList.__required_keys__)
        self.assertEqual(set(self.fake.grocery_list(with_datetime=True)) - GroceryList.__required_keys__,
                         {"shopping_datetime"})
        history = self.fake.customer_history(trips=1)
        self.assertEqual(set(history[0]) - GroceryList.__required_keys__, GroceryList.__optional_keys__)

    def test_new_typed_dicts_keys(self) -> None:
        self.assertEqual(set(self.fake.customer_profile()), set(CustomerProfile.__annotations__))
        self.assertEqual(set(self.fake.grocery_store()), set(GroceryStore.__annotations__))
        receipt = self.fake.receipt()
        self.assertEqual(set(receipt), Receipt.__required_keys__)
        self.assertEqual(set(receipt["lines"][0]), set(ReceiptLine.__annotations__))
        self.assertEqual(set(receipt["taxes"][0]), set(TaxLine.__annotations__))


class TestDocumentedTypedUsage(unittest.TestCase):
    """The two ways of getting typed results documented in the README.
    assert_type() is a no-op at runtime; mypy checks it statically."""

    def test_annotating_the_result_of_a_faker_call(self) -> None:
        fake = make_faker()
        item: GroceryItem = fake.grocery_item()
        assert_type(item["total_price"], float)
        assert_type(item["unit"], str)

    def test_calling_the_provider_directly(self) -> None:
        grocery = GroceryStoreProvider(make_faker())
        assert_type(grocery.product_record(), ProductRecord)
        assert_type(grocery.grocery_item(), GroceryItem)
        basket = grocery.grocery_list(with_datetime=True)
        assert_type(basket, GroceryList)
        assert_type(basket["items"], list[GroceryItem])
        assert_type(grocery.shopping_datetime(), datetime.datetime)
        assert_type(grocery.grocery_department(), str)
        assert_type(grocery.department_id(), int)
        assert_type(grocery.receipt(basket), Receipt)
        assert_type(grocery.customer_profile(), CustomerProfile)
        assert_type(grocery.customer_history(trips=2), list[GroceryList])


if __name__ == "__main__":
    unittest.main()
