import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]

INDEX_SPEC = importlib.util.spec_from_file_location(
    "traffic_index",
    ROOT / "scripts/live/fetch_longdo_traffic_index.py",
)
traffic_index = importlib.util.module_from_spec(INDEX_SPEC)
INDEX_SPEC.loader.exec_module(traffic_index)

CAM_SPEC = importlib.util.spec_from_file_location(
    "cameras",
    ROOT / "scripts/live/fetch_itic_cameras.py",
)
cameras = importlib.util.module_from_spec(CAM_SPEC)
CAM_SPEC.loader.exec_module(cameras)


class CurrentContextTests(unittest.TestCase):
    def test_jsonp(self):
        parsed = traffic_index.unwrap_jsonp('cb({"index":5.2,"time":123})')
        self.assertEqual(parsed["index"], 5.2)

    def test_plain_json(self):
        parsed = traffic_index.unwrap_jsonp('{"index":3,"time":123}')
        self.assertEqual(parsed["index"], 3)

    def test_camera_coordinate_filter(self):
        cfg = {
            "bbox_wgs84": {
                "min_lon": 100.5,
                "min_lat": 13.7,
                "max_lon": 100.8,
                "max_lat": 13.9,
            }
        }
        self.assertTrue(cameras.in_bbox(13.8, 100.6, cfg))
        self.assertFalse(cameras.in_bbox(14.0, 100.6, cfg))

    def test_camera_id(self):
        self.assertEqual(cameras.camera_id({"camid": "abc"}), "abc")
        self.assertEqual(cameras.camera_id({"id": 42}), "42")


if __name__ == "__main__":
    unittest.main()
