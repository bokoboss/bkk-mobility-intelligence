import importlib.util
import json
from pathlib import Path
import unittest

MODULE_PATH = (
    Path(__file__).parents[1] / "scripts" / "live" / "fetch_current_bundle.py"
)
spec = importlib.util.spec_from_file_location("fetch_current_bundle", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

CONFIG = {
    "bbox_wgs84": {
        "min_lon": 100.575,
        "min_lat": 13.785,
        "max_lon": 100.700,
        "max_lat": 13.895,
    },
    "roads": [
        {
            "id": "ram_inthra",
            "aliases": ["รามอินทรา", "ramintra", "ram inthra"],
        },
        {"id": "nuan_chan", "aliases": ["นวลจันทร์", "nuan chan"]},
    ],
}


class CurrentPipelineTests(unittest.TestCase):
    def test_event_area_and_road_match(self):
        feed = [
            {
                "eid": "1",
                "title": "รถเสีย ถนนรามอินทรา",
                "latitude": "13.85",
                "longitude": "100.64",
                "start": "2026-09-27 12:00:00",
            },
            {
                "eid": "2",
                "title": "Other",
                "latitude": "13.70",
                "longitude": "100.50",
                "start": "2026-09-27 12:10:00",
            },
        ]
        audit, rows = mod.audit_events(
            json.dumps(feed, ensure_ascii=False).encode(),
            CONFIG,
            "2026-09-27T06:00:00+00:00",
        )
        self.assertEqual(audit["study_area_event_count"], 1)
        self.assertEqual(rows[0]["road_title_matches"], ["ram_inthra"])
        self.assertEqual(rows[0]["road_match_confidence"], "TITLE_STRONG")

    def test_event_provider_mention_is_context_only(self):
        feed = [
            {
                "eid": "3",
                "title": "น้ำท่วม ทางหลวง 351",
                "description": "เจ้าหน้าที่หมวดทางหลวงรามอินทราเข้าอำนวยการจราจร",
                "latitude": "13.83",
                "longitude": "100.61",
                "start": "2026-09-27 11:00:00",
            }
        ]
        _, rows = mod.audit_events(
            json.dumps(feed, ensure_ascii=False).encode(),
            CONFIG,
            "2026-09-27T06:00:00+00:00",
        )
        self.assertEqual(rows[0]["road_title_matches"], [])
        self.assertEqual(rows[0]["road_description_matches"], ["ram_inthra"])
        self.assertEqual(rows[0]["road_match_confidence"], "DESCRIPTION_CONTEXT")

    def test_xml_traffic_coordinate_match(self):
        xml = b"""<feed><item><road>Ramintra</road><lat>13.85</lat><lon>100.64</lon><status>red</status></item><item><road>Elsewhere</road><lat>13.70</lat><lon>100.50</lon></item></feed>"""
        audit, rows = mod.audit_traffic(xml, "application/xml", CONFIG)
        self.assertEqual(audit["format"], "xml")
        self.assertEqual(audit["study_area_record_count"], 1)
        self.assertEqual(rows[0]["road_text_matches"], ["ram_inthra"])

    def test_xml_name_match_without_coordinates_is_provisional(self):
        xml = b"""<feed><item><road>nuan chan</road><status>yellow</status></item></feed>"""
        audit, rows = mod.audit_traffic(xml, "application/xml", CONFIG)
        self.assertEqual(audit["study_area_road_name_match_count"], 1)
        self.assertEqual(rows[0]["study_area_match_method"], "road_name")

    def test_bbox_rejects_missing_coordinate(self):
        self.assertFalse(mod.in_bbox(None, 100.64, CONFIG))


if __name__ == "__main__":
    unittest.main()
