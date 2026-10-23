import unittest
from cnflu import metrics as M
from cnflu.parse import parse_dates, _norm

class T(unittest.TestCase):
    def test_onset_summer_tail(self):
        # 2026-27 情形：季初承接夏季 H3N2 尾部(19.0)，低谷后再起
        d = {0: 19.0, 1: 15, 2: 11, 3: 8, 4: 6, 5: 7, 6: 9, 7: 12.1, 8: 15}
        self.assertEqual(M.onset_peak(d), (7, 8, 15))
    def test_onset_continue(self):
        self.assertEqual(M.onset_peak({0: 20, 1: 25, 2: 30, 3: 22})[0], "延续")
    def test_onset_none(self):
        self.assertEqual(M.onset_peak({0: 2, 1: 3, 2: 4}), (None, 2, 4))
    def test_pctl_bands(self):
        arr = [1, 2, 3, 4]
        self.assertEqual(M.pctl(0.5, arr), 0); self.assertEqual(M.pctl(5, arr), 100); self.assertEqual(M.pctl(3, arr), 50)
        self.assertIsNone(M.pctl(None, arr))
        self.assertEqual(M.level(24), "低于往年"); self.assertEqual(M.level(25), "往年常见")
        self.assertEqual(M.level(75), "往年常见"); self.assertEqual(M.level(76), "高于往年"); self.assertEqual(M.level(None), "—")
    def test_focus_hot(self):
        c = [("流感", 15, 1.9, 100), ("新冠", 3, 2.5, 50), ("RSV", 1, -0.2, 90)]
        self.assertEqual(M.focus(c), "流感")
    def test_focus_fallback(self):
        c = [("流感", 15, -1, 100), ("新冠", 3, 0.4, 50), ("RSV", 1, 0.1, 10)]
        self.assertEqual(M.focus(c), "新冠")
        self.assertIsNone(M.focus([("x", 1, None, 99)]))
    def test_old_dates(self):
        self.assertEqual(parse_dates(_norm("During week 20 (May 17th–May 23th 2021)")), ("2021-05-17", "2021-05-23", 20))
        self.assertEqual(parse_dates(_norm("During week 52 (Dec 27th 2021–Jan 2nd 2022)")), ("2021-12-27", "2022-01-02", 52))
        self.assertEqual(parse_dates(_norm("During week 30 (Jul 26th–Oct 1st2021) x During week 30(July 26th – Aug 1st 2021)")), ("2021-07-26", "2021-08-01", 30))
        self.assertEqual(parse_dates(_norm("Report June15 to 22, 2025 (Week 25)"))[1:], ("2025-06-22", 25))

if __name__ == "__main__": unittest.main()
