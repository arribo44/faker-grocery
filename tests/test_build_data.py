"""
Tests for the catalog build helpers (scripts/build_data.py) and for the
translated product names they produce.
"""
import json
import os
import sys
import unittest

from faker import Faker

from faker_grocery import GroceryStoreProvider

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from build_data import (  # noqa: E402
    TRANSLATIONS_DIR,
    fallback_translation,
    load_json,
    protect_phrases,
    reorder_words,
)

WORD_DICT = {"white": "blanc", "balsamic": "balsamique", "vinegar": "vinaigre", "organic": "bio", "beef": "bœuf"}
PHRASES = {"hot dogs": "hot-dogs", "gluten free": "sans gluten", "olive oil": "huile d'olive",
           "extra virgin olive oil": "huile d'olive vierge extra"}


class TestTranslationHelpers(unittest.TestCase):
    def test_reorder_puts_the_noun_first(self):
        self.assertEqual(reorder_words("White Balsamic Vinegar", WORD_DICT), "Vinegar Balsamic White")

    def test_reorder_never_moves_unknown_words(self):
        # "Jennie" is a brand (not in the dictionary): the segment stays as is.
        self.assertEqual(reorder_words("Organic Jennie Beef", WORD_DICT), "Organic Jennie Beef")

    def test_reorder_works_per_punctuation_segment(self):
        self.assertEqual(reorder_words("Balsamic Vinegar, Jennie O", WORD_DICT), "Vinegar Balsamic, Jennie O")

    def test_phrases_are_translated_and_moved_as_a_unit(self):
        self.assertEqual(fallback_translation("Organic Beef Hot Dogs", WORD_DICT, PHRASES), "Hot-dogs Bœuf Bio")

    def test_longest_phrase_wins(self):
        name, entries = protect_phrases("Extra Virgin Olive Oil", PHRASES)
        self.assertEqual(list(entries.values()), ["huile d'olive vierge extra"])

    def test_no_placeholder_leaks_into_the_catalog(self):
        provider = GroceryStoreProvider(Faker())
        name_col = provider._data["name_col"]["fr"]
        self.assertFalse([row for row in provider._data["products"] if "qxphrase" in row[name_col].lower()])


class TestCuratedFrenchNames(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.curated = load_json(os.path.join(TRANSLATIONS_DIR, "product_names_fr.json"))
        cls.provider = GroceryStoreProvider(Faker("fr_FR"))

    def test_curated_names_are_used_in_the_catalog(self):
        name_col = self.provider._data["name_col"]["fr"]
        for product_id, name in self.curated.items():
            self.assertEqual(self.provider._data["by_id"][int(product_id)][name_col], name)

    def test_curated_names_cover_the_most_ordered_products(self):
        data = self.provider._data
        order_col = data["meta"]["product_fields"].index("order_count")
        top = sorted(data["products"], key=lambda row: (-row[order_col], row[0]))[:2000]
        self.assertEqual({str(row[0]) for row in top}, set(self.curated))

    def test_curated_names_are_non_empty_and_known_products(self):
        for product_id, name in self.curated.items():
            self.assertTrue(name.strip(), msg=product_id)
            self.assertIn(int(product_id), self.provider._data["by_id"])

    def test_known_good_translations(self):
        # Regression guard for errors a small local LLM made on these.
        expected = {"27966": "Framboises bio", "26209": "Citrons verts", "18987": "Pains à hot-dog",
                    "12442": "Liquide vaisselle au basilic", "21903": "Jeunes pousses d'épinards bio"}
        for product_id, name in expected.items():
            self.assertEqual(self.curated[product_id], name)

    def test_curated_file_is_sorted_and_valid_json(self):
        with open(os.path.join(TRANSLATIONS_DIR, "product_names_fr.json"), encoding="utf-8") as f:
            ids = list(json.load(f))
        self.assertEqual(ids, sorted(ids, key=int))


if __name__ == "__main__":
    unittest.main()
