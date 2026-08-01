from html.parser import HTMLParser
from pathlib import Path
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class LayoutParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.ancestors_by_id = {}

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.ancestors_by_id[element_id] = list(self.stack)
        self.stack.append((tag, attributes))

    def handle_startendtag(self, tag, attrs):
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.ancestors_by_id[element_id] = list(self.stack)

    def handle_endtag(self, tag):
        if self.stack:
            self.stack.pop()


class AdvisorGuiTests(unittest.TestCase):
    def test_save_control_is_in_the_visible_hero_actions(self):
        html = (PLUGIN_ROOT / "assets" / "index.html").read_text(encoding="utf-8")
        parser = LayoutParser()
        parser.feed(html)

        save_ancestors = parser.ancestors_by_id["save"]
        ancestor_classes = {
            class_name
            for _, attributes in save_ancestors
            for class_name in attributes.get("class", "").split()
        }

        self.assertIn("hero-actions", ancestor_classes)
        self.assertNotIn("actions", ancestor_classes)
        self.assertIn("enabled", parser.ancestors_by_id)
        enabled_ancestors = parser.ancestors_by_id["enabled"]
        enabled_classes = {
            class_name
            for _, attributes in enabled_ancestors
            for class_name in attributes.get("class", "").split()
        }
        self.assertIn("hero-actions", enabled_classes)


if __name__ == "__main__":
    unittest.main()
