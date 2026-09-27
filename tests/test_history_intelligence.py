import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "history",
    ROOT / "scripts/history/build_recent_incident_intelligence.py",
)
history = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(history)


class HistoryIntelligenceTests(unittest.TestCase):
    def test_canonical_title_removes_update_prefix(self):
        self.assertEqual(
            history.canonical_title("คืบหน้าอุบัติเหตุ ถนนรามอินทรา"),
            "อุบัติเหตุ ถนนรามอินทรา",
        )
        self.assertEqual(
            history.canonical_title("Update: Accident Ram Inthra Road"),
            "accident ram inthra road",
        )

    def test_overlapping_updates_form_one_episode(self):
        rows = [
            {
                "network_confirmed": True,
                "confirmed_road_id": "r1",
                "confirmed_road_name": "ถนนทดสอบ",
                "type": "3",
                "title": "อุบัติเหตุ ถนนทดสอบ",
                "latitude": "13.8",
                "longitude": "100.6",
                "start": "2026-09-20 08:00:00",
                "stop": "2026-09-20 10:00:00",
                "eid": "1",
                "event_route_refs": [],
            },
            {
                "network_confirmed": True,
                "confirmed_road_id": "r1",
                "confirmed_road_name": "ถนนทดสอบ",
                "type": "3",
                "title": "คืบหน้าอุบัติเหตุ ถนนทดสอบ",
                "latitude": "13.8",
                "longitude": "100.6",
                "start": "2026-09-20 09:00:00",
                "stop": "2026-09-20 11:00:00",
                "eid": "2",
                "event_route_refs": [],
            },
        ]
        clusters = history.build_episode_clusters(rows)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0]["record_count"], 2)

    def test_separate_day_recurrence_is_new_episode(self):
        rows = [
            {
                "network_confirmed": True,
                "confirmed_road_id": "r1",
                "confirmed_road_name": "ถนนทดสอบ",
                "type": "6",
                "title": "น้ำท่วม ถนนทดสอบ",
                "latitude": "13.8",
                "longitude": "100.6",
                "start": "2026-09-20 08:00:00",
                "stop": "2026-09-20 10:00:00",
                "eid": "1",
                "event_route_refs": [],
            },
            {
                "network_confirmed": True,
                "confirmed_road_id": "r1",
                "confirmed_road_name": "ถนนทดสอบ",
                "type": "6",
                "title": "น้ำท่วม ถนนทดสอบ",
                "latitude": "13.8",
                "longitude": "100.6",
                "start": "2026-09-22 08:00:00",
                "stop": "2026-09-22 10:00:00",
                "eid": "2",
                "event_route_refs": [],
            },
        ]
        clusters = history.build_episode_clusters(rows)
        self.assertEqual(len(clusters), 2)

    def test_delta_pct(self):
        self.assertEqual(history.delta_pct(12, 10), 20.0)
        self.assertEqual(history.delta_pct(0, 0), None)


if __name__ == "__main__":
    unittest.main()
