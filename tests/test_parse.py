import unittest, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from cnflu import parse, build

FX = pathlib.Path(__file__).parent / "fixtures"

class TestWeek42(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = parse.parse_text((FX / "2026-W42.txt").read_text())
    def test_dates(self):
        self.assertEqual((self.r["week_start"], self.r["week_end"], self.r["week"]), ("2026-10-12", "2026-10-18", 42))
    def test_ili(self):
        self.assertEqual((self.r["ili_south"], self.r["ili_north"]), (4.5, 2.8))
        self.assertEqual((self.r["ili_south_prev"], self.r["ili_north_prev"]), (4.6, 3.0))
        self.assertEqual(self.r["same_period_south"], {2023: 5.3, 2024: 3.3, 2025: 3.8})
        self.assertEqual(self.r["same_period_north"], {2023: 3.6, 2024: 3.4, 2025: 2.8})
    def test_positivity(self):
        self.assertEqual((self.r["pos_south"], self.r["pos_north"], self.r["pos_total"]), (19.5, 3.8, 12.1))
    def test_subtypes(self):
        self.assertEqual(self.r["h3n2_total"], 80.6); self.assertEqual(self.r["h1n1_total"], 19.4)
        self.assertEqual((self.r["a_total"], self.r["b_total"], self.r["vic_total"]), (66.1, 33.9, 100.0))
    def test_outbreaks_match(self):
        self.assertEqual(self.r["outbreaks"], 28)
        self.assertEqual(self.r["match_h3n2_pct"], 90.0)

class TestSmall(unittest.TestCase):
    def test_dates_variants(self):
        self.assertEqual(parse.parse_dates("July 20 to 26, 2026 (Week 30)")[:2], ("2026-07-20", "2026-07-26"))
        self.assertEqual(parse.parse_dates("December 29, 2025 to January 4, 2026 (Week 1)")[0], "2025-12-29")
    def test_zero_cell_and_fullwidth(self):
        txt = "No. of positive specimens (%) 282(2.8%) 4(0.1%) 286(2.2%) Influenza A 240(85.1%） 3(75.0%) 243(85.0%) A(H1N1)pdm09 31(12.9%) 0 31(12.8%)"
        r = parse.parse_table(parse._norm(txt))
        self.assertEqual((r["a_south"], r["h1n1_north"], r["h1n1_total"]), (85.1, 0.0, 12.8))
    def test_no_outbreaks(self):
        self.assertEqual(parse.parse_outbreaks("There were no ILI outbreaks reported"), 0)
        self.assertEqual(parse.parse_outbreaks("There was 1 ILI outbreak reported"), 1)
    def test_season(self):
        self.assertEqual(build.season_of("2026-10-18")[0], "2026-27")
        self.assertEqual(build.season_of("2026-01-04")[0], "2025-26")

if __name__ == "__main__":
    unittest.main()
