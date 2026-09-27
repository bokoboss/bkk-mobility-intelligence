import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]

BASE_SPEC = importlib.util.spec_from_file_location(
    "baseline",
    ROOT / "scripts/analysis/analyze_longdo_traffic_index.py",
)
baseline = importlib.util.module_from_spec(BASE_SPEC)
BASE_SPEC.loader.exec_module(baseline)

CAM_SPEC = importlib.util.spec_from_file_location(
    "cameras",
    ROOT / "scripts/live/fetch_itic_cameras.py",
)
cameras = importlib.util.module_from_spec(CAM_SPEC)
CAM_SPEC.loader.exec_module(cameras)


class NowContextAnalysisTests(unittest.TestCase):
    def test_percentile_classification(self):
        self.assertEqual(baseline.classify_percentile(97), "VERY_HIGH_FOR_TIME")
        self.assertEqual(baseline.classify_percentile(85), "HIGH_FOR_TIME")
        self.assertEqual(baseline.classify_percentile(50), "TYPICAL_FOR_TIME")

    def test_percentile(self):
        self.assertEqual(baseline.percentile([1, 2, 3], 0.5), 2)

    def test_distance_inside_bbox_zero(self):
        cfg = {
            "bbox_wgs84": {
                "min_lon": 100.5,
                "min_lat": 13.7,
                "max_lon": 100.8,
                "max_lat": 13.9,
            }
        }
        self.assertAlmostEqual(cameras.distance_to_bbox_m(13.8, 100.6, cfg), 0.0)

    def test_distance_outside_bbox_positive(self):
        cfg = {
            "bbox_wgs84": {
                "min_lon": 100.5,
                "min_lat": 13.7,
                "max_lon": 100.8,
                "max_lat": 13.9,
            }
        }
        self.assertGreater(cameras.distance_to_bbox_m(14.0, 100.6, cfg), 10000)


if __name__ == "__main__":
    unittest.main()
