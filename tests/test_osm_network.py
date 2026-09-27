import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "osm", ROOT / "scripts/spatial/fetch_osm_network.py"
)
osm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(osm)

CONFIG = {
    "bbox_wgs84": {
        "min_lon": 100.5,
        "min_lat": 13.7,
        "max_lon": 100.8,
        "max_lat": 13.9,
    },
    "network": {
        "include_highway_classes": ["primary", "secondary", "tertiary"],
        "min_group_length_m": 500,
        "max_nonpriority_roads": 10,
        "exclude_name_patterns": ["ทางบริการ", "service road", "frontage road"],
    },
    "roads": [
        {
            "id": "ram_inthra",
            "display_name": "ถนนรามอินทรา",
            "aliases": ["รามอินทรา"],
            "osm_exact_names": ["ถนนรามอินทรา"],
            "route_refs": ["304"],
        }
    ],
}


class OsmNetworkTests(unittest.TestCase):
    def test_query_contains_dynamic_classes_and_priority(self):
        q = osm.build_query(CONFIG)
        self.assertIn("primary", q)
        self.assertIn("secondary", q)
        self.assertIn("ถนนรามอินทรา", q)

    def test_priority_keeps_stable_id(self):
        p = osm.priority_for_tags({"name": "ถนนรามอินทรา"}, CONFIG)
        self.assertEqual(p["id"], "ram_inthra")

    def test_dynamic_id_is_stable(self):
        a = osm.dynamic_road_id("ถนนนวมินทร์")
        b = osm.dynamic_road_id(" ถนนนวมินทร์ ")
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("osm_"))


    def test_service_road_name_is_excluded(self):
        self.assertTrue(osm.excluded_name("ทางบริการด้านขวา", CONFIG))
        self.assertTrue(osm.excluded_name("Frontage Road A", CONFIG))
        self.assertFalse(osm.excluded_name("ถนนนวมินทร์", CONFIG))

    def test_selection_keeps_priority_and_long_dynamic(self):
        features = [
            {
                "type": "Feature",
                "properties": {
                    "road_id": "ram_inthra",
                    "priority": True,
                    "length_m": 100,
                },
                "geometry": {"type": "LineString", "coordinates": [[0,0],[1,1]]},
            },
            {
                "type": "Feature",
                "properties": {
                    "road_id": "osm_long",
                    "priority": False,
                    "length_m": 700,
                },
                "geometry": {"type": "LineString", "coordinates": [[0,0],[1,1]]},
            },
            {
                "type": "Feature",
                "properties": {
                    "road_id": "osm_short",
                    "priority": False,
                    "length_m": 100,
                },
                "geometry": {"type": "LineString", "coordinates": [[0,0],[1,1]]},
            },
        ]
        selected = osm.select_network_features(features, CONFIG)
        ids = {x["properties"]["road_id"] for x in selected}
        self.assertIn("ram_inthra", ids)
        self.assertIn("osm_long", ids)
        self.assertNotIn("osm_short", ids)


if __name__ == "__main__":
    unittest.main()
