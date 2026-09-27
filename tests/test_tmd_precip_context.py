import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "tmd",
    ROOT / "scripts/live/fetch_tmd_precip_context.py",
)
tmd = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tmd)


class TmdContextTests(unittest.TestCase):
    def test_choose_init_time(self):
        html = '''
        <select id="download-init-time">
          <option value="2026092700">00Z</option>
          <option value="2026092706" selected>06Z</option>
        </select>
        '''
        self.assertEqual(tmd.choose_init_time(html), "2026092706")

    def test_discover_named_products(self):
        files = [
            {
                "filename": "p24h.d02.2026092700.csv",
                "format": "CSV",
                "domain_code": "d02",
                "url": "/static/csv/2026092700/p24h.d02.2026092700.csv",
            },
            {
                "filename": "p1h.d02.2026092700.csv",
                "format": "CSV",
                "domain_code": "d02",
                "url": "/static/csv/2026092700/p1h.d02.2026092700.csv",
            },
        ]
        products = tmd.discover_products(files)
        self.assertIn("p24h_d02_csv", products)
        self.assertIn("p1h_d02_csv", products)
        self.assertTrue(products["p24h_d02_csv"]["download_url"].startswith("https://"))


if __name__ == "__main__":
    unittest.main()
