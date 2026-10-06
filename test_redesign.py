import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from build import Parser, certificate_parts, content_text, load_content, travel_parts, walk

ROOT = Path(__file__).resolve().parent


class RedesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sections, cls.evidence = load_content()
        cls.items = [item for section in cls.sections
                     for item in walk(section["blocks"])]

    def test_source_content_and_order(self):
        saved = json.loads(ROOT.joinpath("content.json").read_text())
        self.assertEqual(saved, self.sections)
        self.assertEqual(len(self.evidence), 23)
        self.assertTrue(all(not row["missing"] for row in self.evidence))

    def test_business_content_counts(self):
        counts = {}
        for item in self.items:
            variant = item.get("variant")
            if variant:
                counts[variant] = counts.get(variant, 0) + 1
        self.assertEqual(counts["sec1-box1"], 7)
        self.assertEqual(counts["sec5-box1"], 12)
        self.assertEqual(counts["sec10-boxs"], 18)
        self.assertEqual(counts["sec9a-box"], 2)
        self.assertEqual(counts["sec12-box-1"], 4)
        self.assertEqual(sum(item["kind"] == "detail" for item in self.items), 18)

    def test_html_assets_and_anchor_targets(self):
        parser = Parser()
        parser.feed(ROOT.joinpath("index.html").read_text())

        def nodes(node):
            yield node
            for child in node.children:
                if hasattr(child, "tag"):
                    yield from nodes(child)

        elements = list(nodes(parser.root))
        ids = [node.attrs["id"] for node in elements if node.attrs.get("id")]
        self.assertEqual(len(ids), len(set(ids)))
        for node in elements:
            href = node.attrs.get("href", "")
            if href.startswith("#"):
                self.assertIn(href[1:], ids)
            if node.tag == "img":
                self.assertTrue(ROOT.joinpath(node.attrs["src"]).is_file())
        self.assertEqual(sum(node.tag == "details" for node in elements), 18)
        self.assertFalse(any(node.tag == "iframe" for node in elements))

    def test_certificate_and_travel_structure(self):
        certificate = next(section for section in self.sections
                           if "section-9b" in section["class"].split())
        _, copy, collage, logos, document = certificate_parts(certificate["blocks"])
        self.assertEqual(len(copy), 6)
        self.assertIn("yoga-logos.svg", logos["src"])
        self.assertIn("certificate.webp", document["src"])
        self.assertNotEqual(collage["src"], document["src"])
        travel = next(section for section in self.sections
                      if "section-13" in section["class"].split())
        _, cards, _ = travel_parts(travel["blocks"])
        self.assertEqual([card["children"][0]["text"] for card in cards], [
            "BEFORE YOU FLY", "ARRIVAL IN GOA", "DURING YOUR STAY", "GOING HOME"])
        self.assertFalse(any(item["kind"] == "image" for item in travel["blocks"]))
        page = ROOT.joinpath("index.html").read_text()
        self.assertIn('class="certificate-layout"', page)
        self.assertEqual(page.count('class="travel-step"'), 4)

    def test_svg_shapes_and_all_content(self):
        ns = {"s": "http://www.w3.org/2000/svg"}
        for filename, width in (("desktop-1440.svg", "1440"),
                                ("mobile-390.svg", "390")):
            root = ET.parse(ROOT / filename).getroot()
            self.assertEqual(root.attrib["width"], width)
            labels = [node.attrib.get("aria-label", "")
                      for node in root.findall(".//s:text", ns)]
            for text in content_text([item for section in self.sections
                                      for item in section["blocks"]]):
                self.assertTrue(text in labels or text + "  −" in labels,
                                f"{filename}: {text}")
            self.assertGreater(len(root.findall(".//s:rect", ns)), 50)
            self.assertGreater(len(root.findall(".//s:image", ns)), 50)
            for image in root.findall(".//s:image", ns):
                self.assertTrue(image.attrib[
                    "{http://www.w3.org/1999/xlink}href"].startswith("data:image/"))


if __name__ == "__main__":
    unittest.main()
