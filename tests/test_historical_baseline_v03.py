import importlib.util
import io
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


processor = load_module(
    "probe_processor",
    ROOT / "scripts/history/process_probe_archive.py",
)
baseline = load_module(
    "probe_baseline",
    ROOT / "scripts/history/build_historical_road_baseline.py",
)


class ProbeBaselineV03Tests(unittest.TestCase):
    def simple_network(self):
        return {
            "type": "FeatureCollection",
            "properties": {
                "road_catalog": [
                    {
                        "road_id": "road_a",
                        "display_name": "Road A",
                        "network_tier": "STRATEGIC",
                        "district_ids": ["01"],
                        "district_names": ["Test"],
                    },
                    {
                        "road_id": "road_b",
                        "display_name": "Road B",
                        "network_tier": "URBAN",
                        "district_ids": ["01"],
                        "district_names": ["Test"],
                    },
                ]
            },
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "road_id": "road_a",
                        "display_name": "Road A",
                        "network_tier": "STRATEGIC",
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[100.0, 13.0], [100.01, 13.0]],
                    },
                },
                {
                    "type": "Feature",
                    "properties": {
                        "road_id": "road_b",
                        "display_name": "Road B",
                        "network_tier": "URBAN",
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[100.0, 13.01], [100.01, 13.01]],
                    },
                },
            ],
        }

    def test_parse_probe_row(self):
        row = ["veh1", "1", "13.0001", "100.005", "2025-01-06 08:05:00", "32.5", "1", "1"]
        parsed = processor.parse_probe_row(row)
        self.assertEqual(parsed["vehicle_id"], "veh1")
        self.assertAlmostEqual(parsed["speed_kmh"], 32.5)
        self.assertIsNone(processor.parse_probe_row(["veh1", "0", "13", "100", "2025-01-06 08:05:00", "20"]))

    def test_road_matcher(self):
        matcher = processor.RoadMatcher(
            self.simple_network(),
            max_distance_m=80,
            ambiguity_margin_m=5,
        )
        result = matcher.match(100.005, 13.0001)
        self.assertEqual(result["status"], "MATCHED")
        self.assertEqual(result["road_id"], "road_a")

    def test_baseline_readiness(self):
        network = self.simple_network()
        config = {
            "historical_baseline": {
                "time_bin_minutes": 30,
                "min_days_per_weekday_bin": 2,
                "min_total_vehicles_per_bin": 4,
                "min_ready_bins_per_road": 1,
            }
        }
        docs = [
            {
                "date": "2025-01-06",
                "rows": [{
                    "road_id": "road_a",
                    "weekday": 0,
                    "time_bin_index": 16,
                    "daily_median_speed_kmh": 30,
                    "vehicle_count": 2,
                    "probe_count": 10,
                }],
            },
            {
                "date": "2025-01-13",
                "rows": [{
                    "road_id": "road_a",
                    "weekday": 0,
                    "time_bin_index": 16,
                    "daily_median_speed_kmh": 40,
                    "vehicle_count": 2,
                    "probe_count": 12,
                }],
            },
        ]
        result = baseline.build_baseline(docs, network, config, reference_year=2025)
        self.assertEqual(result["summary"]["ready_road_count"], 1)
        self.assertEqual(result["baseline_bins"][0]["quality"], "BASELINE_READY")
        self.assertEqual(result["baseline_bins"][0]["median_speed_kmh"], 35.0)
        self.assertEqual(result["direction_state"], "NOT_AVAILABLE_IN_PUBLISHED_RAW_FORMAT")


if __name__ == "__main__":
    unittest.main()
