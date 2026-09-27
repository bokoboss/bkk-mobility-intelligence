import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "osm",
    ROOT / "scripts/spatial/fetch_osm_network.py",
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
    "roads": [
        {
            "id": "ram_inthra",
            "osm_exact_names": ["ถนนรามอินทรา"],
        },
        {
            "id": "nuan_chan",
            "osm_exact_names": ["ถนนนวลจันทร์"],
        },
    ],
}


class OsmNetworkTests(unittest.TestCase):
    def test_regex_is_anchored(self):
        regex = osm.build_name_regex(CONFIG)
        self.assertTrue(regex.startswith("^("))
        self.assertTrue(regex.endswith(")$"))

    def test_exact_main_road_classifies(self):
        self.assertEqual(
            osm.classify_road(
                {"name": "ถนนรามอินทรา"},
                CONFIG,
            ),
            "ram_inthra",
        )

    def test_soi_does_not_classify(self):
        self.assertIsNone(
            osm.classify_road(
                {"name": "ซอยรามอินทรา 64"},
                CONFIG,
            )
        )

    def test_similarly_named_road_does_not_classify(self):
        self.assertIsNone(
            osm.classify_road(
                {"name": "ถนนรัชดา-รามอินทรา"},
                CONFIG,
            )
        )


if __name__ == "__main__":
    unittest.main()
