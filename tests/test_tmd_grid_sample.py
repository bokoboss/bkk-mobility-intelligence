import importlib.util
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sample_tmd",
    ROOT / "scripts/live/sample_tmd_precip_grid.py",
)
sample = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sample)


class TmdGridSampleTests(unittest.TestCase):
    def test_choose_first_forecast_after_init(self):
        init = sample.parse_init("2026092700")
        idx, valid = sample.choose_next_24h_column(
            [
                "lat", "lon",
                "00:00Z 2026-09-27",
                "00:00Z 2026-09-28",
                "00:00Z 2026-09-29",
            ],
            init,
        )
        self.assertEqual(idx, 3)
        self.assertEqual(valid.isoformat(), "2026-09-28T00:00:00+00:00")

    def test_read_grid_filters_bbox(self):
        text = (
            "lat,lon,00:00Z 2026-09-27,00:00Z 2026-09-28\n"
            "13.80,100.60,0,12.5\n"
            "12.00,99.00,0,99.0\n"
        )
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "grid.csv"
            path.write_text(text, encoding="utf-8")
            points, valid = sample.read_grid(
                path,
                {
                    "min_lat": 13.7, "max_lat": 13.9,
                    "min_lon": 100.5, "max_lon": 100.8,
                },
                sample.parse_init("2026092700"),
            )
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["next_24h_mm"], 12.5)
        self.assertEqual(valid, "2026-09-28T00:00:00+00:00")

    def test_road_aggregate_uses_nearest_cells(self):
        points = [
            {"latitude": 13.80, "longitude": 100.60, "next_24h_mm": 10.0},
            {"latitude": 13.82, "longitude": 100.62, "next_24h_mm": 30.0},
        ]
        network = {
            "features": [
                {
                    "type": "Feature",
                    "properties": {"road_id": "r1", "display_name": "Road 1"},
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[100.6001, 13.8001], [100.6199, 13.8199]],
                    },
                }
            ]
        }
        rows = sample.road_aggregates(network, points)
        self.assertEqual(rows[0]["grid_cell_count"], 2)
        self.assertEqual(rows[0]["next_24h_mean_mm"], 20.0)
        self.assertEqual(rows[0]["next_24h_max_mm"], 30.0)


if __name__ == "__main__":
    unittest.main()
