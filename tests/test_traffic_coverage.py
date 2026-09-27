import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "traffic_coverage",
    ROOT / "scripts/analysis/build_traffic_coverage.py",
)
coverage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(coverage)


class TrafficCoverageTests(unittest.TestCase):
    def candidates(self):
        return [
            {"road_id":"a","network_tier":"STRATEGIC","district_id":"01","road_total_length_m":5000},
            {"road_id":"b","network_tier":"URBAN","district_id":"01","road_total_length_m":3000},
            {"road_id":"c","network_tier":"STRATEGIC","district_id":"02","road_total_length_m":4000},
            {"road_id":"d","network_tier":"URBAN","district_id":"03","road_total_length_m":3500},
            {"road_id":"e","network_tier":"STRATEGIC","district_id":"04","road_total_length_m":2500},
            {"road_id":"f","network_tier":"URBAN","district_id":"05","road_total_length_m":2000},
        ]

    def test_plan_respects_budget_and_unique_roads(self):
        rows = coverage.choose_plan(self.candidates(), 4, 0.5, "2026-09-27")
        self.assertEqual(len(rows), 4)
        self.assertEqual(len({x["road_id"] for x in rows}), 4)
        self.assertEqual([x["plan_rank"] for x in rows], [1,2,3,4])

    def test_plan_is_deterministic_for_slot(self):
        a = coverage.choose_plan(self.candidates(), 3, 0.67, "slot-a")
        b = coverage.choose_plan(self.candidates(), 3, 0.67, "slot-a")
        self.assertEqual(a, b)

    def test_pct_zero_denominator(self):
        self.assertEqual(coverage.pct(1, 0), 0.0)
        self.assertEqual(coverage.pct(1, 4), 0.25)


if __name__ == "__main__":
    unittest.main()
