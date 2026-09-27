import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "geo_admin", ROOT / "scripts/spatial/geo_admin.py"
)
geo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(geo)


class GeoAdminTests(unittest.TestCase):
    def test_vendor_has_50_districts(self):
        doc = json.loads(
            (ROOT / "data/reference/bangkok_districts.geojson").read_text(encoding="utf-8")
        )
        districts = geo.prepare_districts(doc)
        self.assertEqual(len(districts), 50)
        ids = {x["district_id"] for x in districts}
        self.assertEqual(len(ids), 50)

    def test_point_in_simple_polygon(self):
        geom = {
            "type": "Polygon",
            "coordinates": [[[100, 13], [101, 13], [101, 14], [100, 14], [100, 13]]],
        }
        self.assertTrue(geo.point_in_geometry(100.5, 13.5, geom))
        self.assertFalse(geo.point_in_geometry(102, 13.5, geom))

    def test_bbox_matches_staging_source(self):
        doc = json.loads(
            (ROOT / "data/reference/bangkok_districts.geojson").read_text(encoding="utf-8")
        )
        self.assertEqual(len(doc.get("bbox") or []), 4)
        self.assertAlmostEqual(doc["bbox"][0], 100.32618858616179, places=6)
        self.assertAlmostEqual(doc["bbox"][3], 13.95198557600562, places=6)


if __name__ == "__main__":
    unittest.main()
