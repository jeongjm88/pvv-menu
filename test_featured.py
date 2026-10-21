import unittest
from types import SimpleNamespace
import fitz
import pvv_menu as menu


class FeaturedBadgeTests(unittest.TestCase):
    def test_real_triangle_position_overrides_displaced_text(self):
        drawing = {"type": "f", "fill": (0, .69, .941), "rect": fitz.Rect(405, 201, 444, 240),
                   "items": [("l", fitz.Point(405, 201), fitz.Point(444, 201)),
                             ("l", fitz.Point(444, 201), fitz.Point(405, 240)),
                             ("l", fitz.Point(405, 240), fitz.Point(405, 201))]}
        page = SimpleNamespace(get_drawings=lambda: [drawing])
        lines = [{"t": "이달의", "cx": 124, "cy": 340}, {"t": "메뉴", "cx": 147, "cy": 340}]
        regions = menu._featured_regions(page, lines)
        self.assertEqual(regions, [(424.5, 220.5)])

    def test_no_marker_does_not_highlight_decorative_shapes(self):
        page = SimpleNamespace(get_drawings=lambda: [])
        self.assertEqual(menu._featured_regions(page, []), [])


if __name__ == "__main__":
    unittest.main()
