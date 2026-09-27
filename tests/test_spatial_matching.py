import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "match",
    ROOT / "scripts/spatial/match_events_to_network.py",
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

    def test_geometry_and_title_strong(self):
        event = {"road_title_matches": ["ram_inthra"]}
        out = match.classify(
            event,
            [{"road_id": "ram_inthra", "distance_m": 25.0}],
            80,
            150,
            {"ram_inthra": {"304"}},
        )
        self.assertEqual(
            out["network_match_class"],
            "GEOMETRY+TITLE_CONFIRMED",
        )
        self.assertTrue(out["network_confirmed"])

    def test_far_event_is_context_only(self):
        event = {"road_title_matches": ["ram_inthra"]}
        out = match.classify(
            event,
            [{"road_id": "ram_inthra", "distance_m": 450.0}],
            80,
            150,
            {"ram_inthra": {"304"}},
        )
        self.assertEqual(out["network_match_class"], "NETWORK_CONTEXT_ONLY")
        self.assertIsNone(out["network_road_id"])


if __name__ == "__main__":
    unittest.main()
