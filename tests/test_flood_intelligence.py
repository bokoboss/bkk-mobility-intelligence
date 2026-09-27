import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "flood",
    ROOT / "scripts/flood/build_flood_intelligence.py",
)
flood = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(flood)


class FloodIntelligenceTests(unittest.TestCase):
    def event(self, cid, kind, road, lat, lon, start):
        return {
            "cluster_id": cid,
            "event_type": kind,
            "road_id": road,
            "road_name": road,
            "latitude": lat,
            "longitude": lon,
            "first_start": start,
            "title": cid,
        }

    def test_haversine_zero(self):
        a = self.event("a", "6", "r", 13.8, 100.6, "2026-09-20T10:00:00+07:00")
        self.assertAlmostEqual(flood.haversine_km(a, a), 0.0, places=6)

    def test_association_prefers_same_road(self):
        history = {
            "windows": {
                "30d": {
                    "clusters": [
                        self.event("f", "6", "r1", 13.8, 100.6, "2026-09-20T12:00:00+07:00"),
                        self.event("near", "5", "r2", 13.8001, 100.6001, "2026-09-20T11:30:00+07:00"),
                        self.event("same", "5", "r1", 13.805, 100.605, "2026-09-20T11:00:00+07:00"),
                    ]
                }
            }
        }
        pairs = flood.build_associations(history)
        self.assertEqual(pairs[0]["rain_cluster_id"], "same")
        self.assertTrue(pairs[0]["same_road"])

    def test_hotspot_requires_repeat_location(self):
        a = self.event("a", "6", "r1", 13.8, 100.6, "2026-09-20T10:00:00+07:00")
        b = self.event("b", "6", "r1", 13.8005, 100.6005, "2026-09-21T10:00:00+07:00")
        c = self.event("c", "6", "r1", 13.82, 100.62, "2026-09-22T10:00:00+07:00")
        history = {
            "windows": {
                "30d": {"clusters": [a, b, c]},
                "7d": {"clusters": [a, b, c]},
            }
        }
        hotspots = flood.build_hotspots(history)
        self.assertEqual(len(hotspots), 1)
        self.assertEqual(hotspots[0]["episode_count_30d"], 2)
        self.assertEqual(hotspots[0]["distinct_flood_days_30d"], 2)


if __name__ == "__main__":
    unittest.main()
