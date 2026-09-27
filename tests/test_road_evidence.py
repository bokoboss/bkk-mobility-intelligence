import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]

MATCH_SPEC = importlib.util.spec_from_file_location(
    "match",
    ROOT / "scripts/spatial/match_events_to_network.py",
)
match = importlib.util.module_from_spec(MATCH_SPEC)
MATCH_SPEC.loader.exec_module(match)

CLUSTER_SPEC = importlib.util.spec_from_file_location(
    "cluster",
    ROOT / "scripts/spatial/cluster_network_events.py",
)
cluster = importlib.util.module_from_spec(CLUSTER_SPEC)
CLUSTER_SPEC.loader.exec_module(cluster)


class RoadEvidenceTests(unittest.TestCase):
    def test_thai_highway_ref(self):
        event = {
            "title": "น้ำท่วมทางหลวง 351 ช่วงมหาวิทยาลัยเกษตรศาสตร์ - คันนายาว"
        }
        self.assertEqual(match.event_route_refs(event), {"351"})

    def test_route_and_geometry_confirm(self):
        event = {
            "title": "น้ำท่วมทางหลวง 351",
            "road_title_matches": [],
        }
        out = match.classify(
            event,
            [{"road_id": "prasert_manukitch", "distance_m": 12.0}],
            80,
            150,
            {"prasert_manukitch": {"351"}},
        )
        self.assertTrue(out["network_confirmed"])
        self.assertEqual(
            out["network_match_class"],
            "GEOMETRY+ROUTE_CONFIRMED",
        )

    def test_geometry_without_identity_is_candidate(self):
        event = {
            "title": "น้ำท่วม ถนนแจ้งวัฒนะ",
            "road_title_matches": [],
        }
        out = match.classify(
            event,
            [{"road_id": "ram_inthra", "distance_m": 5.0}],
            80,
            150,
            {"ram_inthra": {"304"}},
        )
        self.assertFalse(out["network_confirmed"])
        self.assertEqual(
            out["network_match_class"],
            "GEOMETRY_ONLY_CANDIDATE",
        )

    def test_cluster_collapses_duplicate_records(self):
        rows = [
            {
                "network_confirmed": True,
                "confirmed_road_id": "ram_inthra",
                "type": "6",
                "title": "น้ำท่วมทางหลวง 304 ช่วงคันนายาว - แยกเข้ามีนบุรี",
                "latitude": "13.82286667",
                "longitude": "100.67882479",
                "start": "2026-09-25 00:00:20",
                "stop": "2026-09-27 21:30:20",
                "eid": "1",
                "network_match_class": "GEOMETRY+ROUTE_CONFIRMED",
                "event_route_refs": ["304"],
            },
            {
                "network_confirmed": True,
                "confirmed_road_id": "ram_inthra",
                "type": "6",
                "title": "น้ำท่วมทางหลวง 304 ช่วงคันนายาว - แยกเข้ามีนบุรี",
                "latitude": "13.82286667",
                "longitude": "100.67882479",
                "start": "2026-09-25 00:00:56",
                "stop": "2026-09-28 13:11:48",
                "eid": "2",
                "network_match_class": "GEOMETRY+ROUTE_CONFIRMED",
                "event_route_refs": ["304"],
            },
        ]
        result = cluster.build_clusters(rows, 5)
        self.assertEqual(result["summary"]["confirmed_record_count"], 2)
        self.assertEqual(result["summary"]["confirmed_cluster_count"], 1)
        self.assertEqual(result["clusters"][0]["record_count"], 2)


if __name__ == "__main__":
    unittest.main()
