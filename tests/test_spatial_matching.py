import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "match", ROOT / "scripts/spatial/match_events_to_network.py"
)
match = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(match)


class SpatialMatchingTests(unittest.TestCase):
    def test_point_on_line_is_zero(self):
        distance = match.point_line_distance_m(
            100.0, 13.0, [[99.999, 13.0], [100.001, 13.0]]
        )
        self.assertLess(distance, 0.5)

    def test_point_about_111m_north(self):
        distance = match.point_line_distance_m(
            100.0, 13.001, [[99.999, 13.0], [100.001, 13.0]]
        )
        self.assertTrue(109 <= distance <= 113)

    def test_far_event_is_context_only(self):
        event = {"title": "ถนนรามอินทรา"}
        candidate = {
            "road_id": "ram_inthra",
            "display_name": "ถนนรามอินทรา",
            "distance_m": 450.0,
            "aliases": ["ถนนรามอินทรา"],
            "route_refs": ["304"],
        }
        out = match.classify(event, [candidate], 80, 150)
        self.assertEqual(out["network_match_class"], "NETWORK_CONTEXT_ONLY")
        self.assertIsNone(out["network_road_id"])


if __name__ == "__main__":
    unittest.main()
