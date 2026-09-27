import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]

SPEC = importlib.util.spec_from_file_location(
    "traffic_state",
    ROOT / "scripts/analysis/build_traffic_state.py",
)
traffic_state = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(traffic_state)


class TrafficStateTests(unittest.TestCase):
    def network(self):
        return {
            "properties": {
                "road_catalog": [
                    {
                        "road_id": "road_a",
                        "display_name": "Road A",
                        "network_tier": "STRATEGIC",
                        "priority": False,
                        "district_ids": ["10"],
                        "district_names": ["Example"],
                    },
                    {
                        "road_id": "road_b",
                        "display_name": "Road B",
                        "network_tier": "URBAN",
                        "priority": False,
                        "district_ids": ["11"],
                        "district_names": ["Example 2"],
                    },
                ]
            }
        }

    def test_movement_bands(self):
        self.assertEqual(traffic_state.movement_class(7), "STOP_AND_GO")
        self.assertEqual(traffic_state.movement_class(15), "SLOW")
        self.assertEqual(traffic_state.movement_class(30), "MOVING")
        self.assertEqual(traffic_state.movement_class(50), "FREE_FLOW_LIKE")

    def test_build_aggregates_speed_mps_to_kmh(self):
        speed_doc = {
            "provider": "test",
            "status": "OK",
            "samples": [
                {
                    "road_id": "road_a",
                    "lon": 100.5,
                    "lat": 13.7,
                    "response": {"road": "Road A", "dir": "N", "speed": 5, "source": "r"},
                },
                {
                    "road_id": "road_a",
                    "lon": 100.6,
                    "lat": 13.8,
                    "response": {"road": "Road A", "dir": "S", "speed": 10, "source": "p"},
                },
            ],
            "errors": [],
        }
        result = traffic_state.build(self.network(), speed_doc)
        self.assertEqual(result["access_state"], "PARTIAL_EXPERIMENTAL")
        self.assertEqual(result["summary"]["sampled_road_count"], 1)
        self.assertEqual(result["roads"]["road_a"]["sample_count"], 2)
        self.assertEqual(result["roads"]["road_a"]["median_speed_kmh"], 27.0)
        self.assertEqual(result["roads"]["road_a"]["movement_class"], "MOVING")
        self.assertEqual(result["roads"]["road_b"]["status"], "NO_SAMPLE")
        self.assertEqual(result["roads"]["road_a"]["abnormality_state"], "NOT_EVALUATED")

    def test_missing_key_is_explicit(self):
        result = traffic_state.build(
            self.network(),
            {"provider": "test", "status": "BLOCKED_MISSING_API_KEY", "samples": [], "errors": []},
        )
        self.assertEqual(result["access_state"], "BLOCKED_MISSING_API_KEY")
        self.assertEqual(result["summary"]["usable_observation_count"], 0)


if __name__ == "__main__":
    unittest.main()
