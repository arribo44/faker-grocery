"""
Tests for the catalog build helpers (scripts/build_data.py) and for the
translated product names they produce.
"""
import gzip
import json
import os
import sys
import unittest

from faker import Faker

from faker_grocery import GroceryStoreProvider, _ensure_language

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from label_tables import DIETS, LABELS, diets_mask, labels_mask  # noqa: E402
from build_data import (  # noqa: E402
    FUNCTION_WORDS,
    TRANSLATIONS_DIR,
    fallback_translation,
    lowercase_function_words,
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

    def test_reorder_does_not_cross_linking_words(self):
        words = {**WORD_DICT, "diced": "en dés", "tomatoes": "tomates", "italian": "italiennes", "herbs": "herbes",
                 "with": "avec"}
        self.assertEqual(reorder_words("Diced Tomatoes with Italian Herbs", words),
                         "Tomatoes Diced with Herbs Italian")

    def test_function_words_are_lower_case_inside_names(self):
        self.assertEqual(lowercase_function_words("Rigatoni Avec Sauce Et Crème", FUNCTION_WORDS["fr"]),
                         "Rigatoni avec Sauce et Crème")
        self.assertEqual(lowercase_function_words("Avec Sauce", FUNCTION_WORDS["fr"]), "Avec Sauce")  # first word
        self.assertEqual(lowercase_function_words("Brot Mit Käse", FUNCTION_WORDS["de"]), "Brot mit Käse")
        words = {**WORD_DICT, "with": "avec", "sauce": "sauce"}
        self.assertEqual(fallback_translation("Beef With Sauce", words, {}, function_words=FUNCTION_WORDS["fr"]),
                         "Bœuf avec Sauce")

    def test_dictionaries_share_their_words(self):
        keys = [set(load_json(os.path.join(TRANSLATIONS_DIR, f"word_dict_{lang}.json")))
                for lang in ("fr", "it", "es", "pt", "de")]
        self.assertTrue(all(k == keys[0] for k in keys))
        self.assertGreater(len(keys[0]), 1150)

    def test_reorder_works_per_punctuation_segment(self):
        self.assertEqual(reorder_words("Balsamic Vinegar, Jennie O", WORD_DICT), "Vinegar Balsamic, Jennie O")

    def test_phrases_are_translated_and_moved_as_a_unit(self):
        self.assertEqual(fallback_translation("Organic Beef Hot Dogs", WORD_DICT, PHRASES), "Hot-dogs Bœuf Bio")

    def test_longest_phrase_wins(self):
        name, entries = protect_phrases("Extra Virgin Olive Oil", PHRASES)
        self.assertEqual(list(entries.values()), ["huile d'olive vierge extra"])

    def test_no_placeholder_leaks_into_the_catalog(self):
        provider = GroceryStoreProvider(Faker())
        for lang in provider._data["languages"]:
            _ensure_language(lang)
            name_col = provider._data["name_col"][lang]
            leaks = [row for row in provider._data["products"] if "qxphrase" in row[name_col].lower()]
            self.assertFalse(leaks, msg=lang)

    def test_reorder_can_be_disabled(self):
        # German puts the noun last, like English: no reordering.
        self.assertEqual(fallback_translation("White Balsamic Vinegar", WORD_DICT, PHRASES, reorder=False),
                         "Blanc Balsamique Vinaigre")


class TestLanguageFiles(unittest.TestCase):
    LANGS = ["fr", "it", "es", "pt", "de"]

    def test_every_language_has_complete_translation_files(self):
        fr_words = load_json(os.path.join(TRANSLATIONS_DIR, "word_dict_fr.json"))
        fr_phrases = load_json(os.path.join(TRANSLATIONS_DIR, "phrases_fr.json"))
        for lang in self.LANGS:
            departments = load_json(os.path.join(TRANSLATIONS_DIR, f"departments_{lang}.json"))
            aisles = load_json(os.path.join(TRANSLATIONS_DIR, f"aisles_{lang}.json"))
            words = load_json(os.path.join(TRANSLATIONS_DIR, f"word_dict_{lang}.json"))
            phrases = load_json(os.path.join(TRANSLATIONS_DIR, f"phrases_{lang}.json"))
            self.assertEqual(set(departments), {str(i) for i in range(1, 22)}, msg=lang)
            self.assertEqual(set(aisles), {str(i) for i in range(1, 135)}, msg=lang)
            self.assertEqual(set(words), set(fr_words), msg=lang)
            self.assertEqual(set(phrases), set(fr_phrases), msg=lang)
            for table in (departments, aisles, words, phrases):
                self.assertTrue(all(value.strip() for value in table.values()), msg=lang)

    def test_names_files_are_parallel_to_the_products(self):
        provider = GroceryStoreProvider(Faker())
        data = provider._data
        for lang in self.LANGS:
            path = os.path.join(ROOT, "faker_grocery", "data", data["meta"]["name_files"][lang])
            with gzip.open(path, "rt", encoding="utf-8") as f:
                names = json.load(f)
            self.assertEqual(len(names), len(data["products"]), msg=lang)
            self.assertTrue(all(name.strip() for name in names), msg=lang)


CURATED_LOCALES = {"fr": "fr_FR", "it": "it_IT", "es": "es_ES", "pt": "pt_PT", "de": "de_DE"}


class TestCuratedNames(unittest.TestCase):
    """Hand-checked names of the 2,000 most ordered products, per language."""

    @classmethod
    def setUpClass(cls):
        cls.curated = {
            lang: load_json(os.path.join(TRANSLATIONS_DIR, f"product_names_{lang}.json")) for lang in CURATED_LOCALES
        }
        cls.providers = {lang: GroceryStoreProvider(Faker(locale)) for lang, locale in CURATED_LOCALES.items()}

    def test_curated_names_are_used_in_the_catalog(self):
        for lang, curated in self.curated.items():
            data = self.providers[lang]._data
            name_col = data["name_col"][lang]
            for product_id, name in curated.items():
                self.assertEqual(data["by_id"][int(product_id)][name_col], name, msg=(lang, product_id))

    def test_curated_names_cover_the_most_ordered_products(self):
        data = self.providers["fr"]._data
        order_col = data["meta"]["product_fields"].index("order_count")
        top = {str(row[0]) for row in sorted(data["products"], key=lambda row: (-row[order_col], row[0]))[:2000]}
        for lang, curated in self.curated.items():
            self.assertEqual(top, set(curated), msg=lang)

    def test_curated_names_are_non_empty_clean_and_known_products(self):
        for lang, curated in self.curated.items():
            for product_id, name in curated.items():
                self.assertTrue(name.strip(), msg=(lang, product_id))
                self.assertEqual(name, " ".join(name.split()), msg=(lang, product_id))
                self.assertIn(int(product_id), self.providers[lang]._data["by_id"])

    def test_curated_names_are_translated(self):
        # Brand-only names ("Smartwater", "Cheerios Honey Nut") legitimately
        # stay the same; anything beyond a few percent means a missed batch.
        english = {str(row[0]): row[self.providers["fr"]._data["name_col"]["en"]]
                   for row in self.providers["fr"]._data["products"]}
        for lang, curated in self.curated.items():
            same = sum(1 for product_id, name in curated.items() if name == english[product_id])
            self.assertLess(same, 100, msg=lang)

    def test_known_good_translations(self):
        # Regression guard for errors a small local LLM made on these (fr),
        # and spot checks for the other languages.
        expected = {
            "fr": {"27966": "Framboises bio", "26209": "Citrons verts", "18987": "Pains à hot-dog",
                   "12442": "Liquide vaisselle au basilic", "21903": "Jeunes pousses d'épinards bio"},
            "it": {"27966": "Lamponi bio", "24852": "Banana", "18987": "Panini per hot dog"},
            "es": {"27966": "Frambuesas ecológicas", "24852": "Plátano", "12442": "Lavavajillas a mano de albahaca"},
            "pt": {"27966": "Framboesas biológicas", "26209": "Limas", "21137": "Morangos biológicos"},
            "de": {"27966": "Bio-Himbeeren", "24852": "Banane", "18987": "Hotdog-Brötchen"},
        }
        for lang, names in expected.items():
            for product_id, name in names.items():
                self.assertEqual(self.curated[lang][product_id], name, msg=lang)

    def test_curated_files_are_sorted_and_valid_json(self):
        for lang in CURATED_LOCALES:
            with open(os.path.join(TRANSLATIONS_DIR, f"product_names_{lang}.json"), encoding="utf-8") as f:
                ids = list(json.load(f))
            self.assertEqual(ids, sorted(ids, key=int), msg=lang)



def _labels(name, aisle_id=1):
    mask = labels_mask(name, aisle_id)
    return [key for bit, key in enumerate(LABELS) if mask & (1 << bit)]


def _diets(name, aisle_id, department_id=1):
    mask = diets_mask(name, aisle_id, department_id, labels_mask(name, aisle_id))
    return [key for bit, key in enumerate(DIETS) if mask & (1 << bit)]


class TestLabelTables(unittest.TestCase):
    def test_labels_from_names(self):
        self.assertEqual(_labels("Organic Gluten-Free Penne"), ["organic", "gluten_free"])
        self.assertEqual(_labels("Unsweetened Almond Milk"), ["lactose_free"])
        self.assertEqual(_labels("Vegan Mac & Cheese"), ["vegan", "lactose_free"])
        self.assertEqual(_labels("Fat Free Skim Milk"), ["low_fat"])
        self.assertEqual(_labels("100% Whole Wheat Bread"), ["whole_grain"])
        self.assertEqual(_labels("Soymilk", aisle_id=91), ["lactose_free"])  # "soy lactosefree" aisle
        self.assertEqual(_labels("Organically Grown Bananas"), [])  # whole words only

    def test_diets(self):
        all_diets = ["vegetarian", "vegan", "gluten_free", "lactose_free"]
        self.assertEqual(_diets("Banana", 24, 4), all_diets)
        self.assertEqual(_diets("Chicken Noodle Soup", 69, 15), ["lactose_free"])
        self.assertEqual(_diets("Meatless Chicken Strips", 14, 20), all_diets)
        self.assertEqual(_diets("Whole Milk", 84, 16), ["vegetarian", "gluten_free"])
        self.assertEqual(_diets("Oat Milk", 84, 16), all_diets)
        self.assertEqual(_diets("Sourdough Bread", 112, 3), ["vegetarian", "vegan", "lactose_free"])
        self.assertEqual(_diets("Gluten Free Sandwich Bread", 112, 3), all_diets)
        self.assertEqual(_diets("Clover Honey", 29, 13), ["vegetarian", "gluten_free", "lactose_free"])
        self.assertEqual(_diets("Peanut Butter", 88, 13), all_diets)
        self.assertEqual(_diets("Large Eggs", 86, 16), ["vegetarian", "gluten_free", "lactose_free"])
        self.assertEqual(_diets("Dish Soap", 74, 17), all_diets)  # non-food: no concern


if __name__ == "__main__":
    unittest.main()
