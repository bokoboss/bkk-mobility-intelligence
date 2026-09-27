import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "hii",
    ROOT / "scripts/live/fetch_hii_rain_station_registry.py",
)
hii = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hii)


class HiiRegistryTests(unittest.TestCase):
    def test_station_classification(self):
        self.assertEqual(hii.classify_station("น้ำฝน"), "RAIN")
        self.assertEqual(hii.classify_station("ระดับน้ำ"), "WATER_LEVEL")
        self.assertEqual(hii.classify_station("อื่น"), "OTHER")


if __name__ == "__main__":
    unittest.main()
