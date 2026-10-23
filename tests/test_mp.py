import unittest
from cnflu import mp

HTML = """<html><body><h1>全国急性呼吸道传染病哨点监测情况（2026年第42周）</h1>
<p>2026年第42周（2026年10月12日-2026年10月18日）</p>
<table><tr><td>病原体</td><td>门急诊</td><td>较上周</td><td>住院</td><td>较上周</td></tr>
<tr><td>流感病毒</td><td>15.4</td><td>+1.9</td><td>4.8</td><td>+0.5</td></tr>
<tr><td>新型冠状病毒</td><td>2.9</td><td>-0.5</td><td>1.2</td><td>-0.1</td></tr>
</table></body></html>"""

class TestMP(unittest.TestCase):
    def test_parse_page(self):
        r = mp.parse_page(HTML)
        self.assertEqual((r["year"], r["week"], r["week_end"]), (2026, 42, "2026-10-18"))
        self.assertEqual(r["p"]["流感病毒"], {"ili": 15.4, "ili_d": 1.9, "sari": 4.8, "sari_d": 0.5})
        self.assertEqual(r["p"]["新型冠状病毒"]["ili_d"], -0.5)
    def test_parse_page_empty(self):
        self.assertIsNone(mp.parse_page("<p>无关页面</p>"))

if __name__ == "__main__": unittest.main()
