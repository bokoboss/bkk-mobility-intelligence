import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]

MATCH_SPEC = importlib.util.spec_from_file_location(
    "match", ROOT / "scripts/spatial/match_events_to_network.py"
)
match = importlib.util.module_from_spec(MATCH_SPEC)
MATCH_SPEC.loader.exec_module(match)

CLUSTER_SPEC = importlib.util.spec_from_file_location(
    "cluster", ROOT / "scripts/spatial/cluster_network_events.py"
)
cluster = importlib.util.module_from_spec(CLUSTER_SPEC)
CLUSTER_SPEC.loader.exec_module(cluster)


class RoadEvidenceTests(unittest.TestCase):
    def test_thai_highway_ref(self):
        event = {"title": "น้ำท่วมทางหลวง 351 ช่วงมหาวิทยาลัยเกษตรศาสตร์ - คันนายาว"}
        self.assertEqual(match.event_route_refs(event), {"351"})

    def test_route_and_geometry_confirm(self):
        event = {"title": "น้ำท่วมทางหลวง 351", "road_title_matches": []}
        candidate = {
            "road_id": "prasert_manukitch",
            "display_name": "ถนนประเสริฐมนูกิจ",
            "distance_m": 12.0,
            "aliases": ["ถนนประเสริฐมนูกิจ"],
            "route_refs": ["351"],
        }
        out = match.classify(event, [candidate], 80, 150)
        self.assertTrue(out["network_confirmed"])
        self.assertEqual(out["network_match_class"], "GEOMETRY+ROUTE_CONFIRMED")

    def test_dynamic_title_and_geometry_confirm(self):
        event = {"title": "น้ำท่วม ถนนนวมินทร์ ขาเข้า"}
        candidate = {
            "road_id": "osm_abc",
            "display_name": "ถนนนวมินทร์",
            "distance_m": 30.0,
            "aliases": ["ถนนนวมินทร์"],
            "route_refs": [],
        }
        out = match.classify(event, [candidate], 80, 150)
        self.assertTrue(out["network_confirmed"])
        self.assertTrue(out["title_support"])


    def test_soi_name_does_not_confirm_main_road(self):
        event = {"title": "น้ำท่วม ซอยนวมินทร์ 38"}
        candidate = {
            "road_id": "osm_abc",
            "display_name": "ถนนนวมินทร์",
            "distance_m": 20.0,
            "aliases": ["ถนนนวมินทร์", "นวมินทร์"],
            "route_refs": [],
        }
        out = match.classify(event, [candidate], 80, 150)
        self.assertFalse(out["network_confirmed"])
        self.assertFalse(out["title_support"])
        self.assertEqual(out["network_match_class"], "GEOMETRY_ONLY_CANDIDATE")

    def test_geometry_without_identity_is_candidate(self):
        event = {"title": "น้ำท่วม ถนนแจ้งวัฒนะ", "road_title_matches": []}
        candidate = {
            "road_id": "ram_inthra",
            "display_name": "ถนนรามอินทรา",
            "distance_m": 5.0,
            "aliases": ["ถนนรามอินทรา"],
            "route_refs": ["304"],
        }
        out = match.classify(event, [candidate], 80, 150)
        self.assertFalse(out["network_confirmed"])
        self.assertEqual(out["network_match_class"], "GEOMETRY_ONLY_CANDIDATE")


    def test_route_segment_clusters_across_multiple_coordinates(self):
        rows = [
            {
                "network_confirmed": True,
                "confirmed_road_id": "ram_inthra",
                "type": "6",
                "title": "น้ำท่วมทางหลวง 304 ช่วงคันนายาว - แยกเข้ามีนบุรี (ผ่านได้)",
                "latitude": "13.812891",
                "longitude": "100.707488",
                "start": "2026-09-26 03:30:07",
                "stop": "2026-09-27 20:00:00",
                "eid": "10",
                "network_match_class": "GEOMETRY+ROUTE_CONFIRMED",
                "event_route_refs": ["304"],
            },
            {
                "network_confirmed": True,
                "confirmed_road_id": "ram_inthra",
                "type": "6",
                "title": "น้ำท่วมทางหลวง 304 ช่วงคันนายาว - แยกเข้ามีนบุรี (ผ่านได้)",
                "latitude": "13.822866",
                "longitude": "100.678824",
                "start": "2026-09-25 00:00:56",
                "stop": "2026-09-28 13:11:48",
                "eid": "11",
                "network_match_class": "GEOMETRY+ROUTE_CONFIRMED",
                "event_route_refs": ["304"],
            },
        ]
        result = cluster.build_clusters(rows, 5)
        self.assertEqual(result["summary"]["confirmed_cluster_count"], 1)
        self.assertEqual(result["clusters"][0]["cluster_scope"], "ROUTE_SEGMENT")
        self.assertEqual(result["clusters"][0]["location_count"], 2)

    def test_local_same_title_different_coordinates_stay_distinct(self):
        rows = [
            {
                "network_confirmed": True,
                "confirmed_road_id": "osm_x",
                "type": "6",
                "title": "น้ำท่วม ถนนนวมินทร์",
                "latitude": "13.80",
                "longitude": "100.64",
                "start": "2026-09-27 00:00:00",
                "eid": "20",
                "network_match_class": "GEOMETRY+TITLE_CONFIRMED",
                "event_route_refs": [],
            },
            {
                "network_confirmed": True,
                "confirmed_road_id": "osm_x",
                "type": "6",
                "title": "น้ำท่วม ถนนนวมินทร์",
                "latitude": "13.81",
                "longitude": "100.65",
                "start": "2026-09-27 00:00:00",
                "eid": "21",
                "network_match_class": "GEOMETRY+TITLE_CONFIRMED",
                "event_route_refs": [],
            },
        ]
        result = cluster.build_clusters(rows, 5)
        self.assertEqual(result["summary"]["confirmed_cluster_count"], 2)

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


if __name__ == "__main__":
    unittest.main()
