import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts/spatial"))
SPEC = importlib.util.spec_from_file_location(
    "city", ROOT / "scripts/spatial/fetch_bangkok_network.py"
)
city = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(city)

CONFIG = {
    "bbox_wgs84": {"min_lon": 100.3, "min_lat": 13.4, "max_lon": 100.9, "max_lat": 14.0},
    "network": {
        "include_highway_classes": ["motorway", "primary", "secondary", "tertiary"],
        "tile_rows": 3,
        "tile_cols": 3,
        "min_group_length_m_strategic": 300,
        "min_group_length_m_urban": 1200,
        "max_nonpriority_roads": 0,
        "exclude_name_patterns": ["service road"],
    },
    "roads": [],
}


class CitywideNetworkTests(unittest.TestCase):
    def test_tiles(self):
        tiles = city.tile_bboxes(CONFIG)
        self.assertEqual(len(tiles), 9)
        self.assertAlmostEqual(tiles[0]["min_lon"], 100.3)
        self.assertAlmostEqual(tiles[-1]["max_lat"], 14.0)

    def test_tiers(self):
        self.assertEqual(city.network_tier("primary"), "STRATEGIC")
        self.assertEqual(city.network_tier("secondary"), "STRATEGIC")
        self.assertEqual(city.network_tier("tertiary"), "URBAN")

    def test_query_has_motorway_and_names(self):
        q = city.build_query(CONFIG, city.tile_bboxes(CONFIG)[0])
        self.assertIn("motorway", q)
        self.assertIn('"name"', q)


if __name__ == "__main__":
    unittest.main()
