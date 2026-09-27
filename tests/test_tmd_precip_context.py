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

    def test_choose_precip_file(self):
        files = [
            {"filename": "t2m.d02.2026092706.csv"},
            {"filename": "prec1hr.d02.2026092706.csv"},
        ]
        item = tmd.choose_precip_file(files)
        self.assertEqual(item["filename"], "prec1hr.d02.2026092706.csv")


if __name__ == "__main__":
    unittest.main()
