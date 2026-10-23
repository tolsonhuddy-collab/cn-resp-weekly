import unittest
from cnflu import notif, temp

PAGE = ('<p>乙类</p><table><tr><td>百日咳</td><td>453</td><td>0</td></tr><tr><td>猩红热</td><td>1,032</td><td>0</td></tr>'
        '<tr><td>肺结核<strong><sup>9</sup></strong></td><td>55082</td><td>182</td></tr>'
        '<tr><td>人感染新亚型流感<sup>5</sup></td><td>4</td><td>0</td></tr>'
        '<tr><td>流行性腮腺炎</td><td>5362</td><td>0</td></tr><tr><td>流行性感冒</td><td>827013</td><td>2</td></tr>'
        '<tr><td>手足口病</td><td>85884</td><td>0</td></tr></table>')
LIST = '<li><a href="./202609/t20260918_1840340.html" title="x">2026年8月全国传染病疫情概况</a></li>'

class T(unittest.TestCase):
    def test_page(self):
        d = notif.parse_page(PAGE)
        self.assertEqual(d["百日咳"], [453, 0]); self.assertEqual(d["猩红热"], [1032, 0])
        self.assertEqual(d["流行性腮腺炎"], [5362, 0]); self.assertEqual(d["流行性感冒"], [827013, 2])
        self.assertEqual(d["肺结核"], [55082, 182]); self.assertEqual(d["人感染新亚型流感"], [4, 0])
        self.assertEqual(d["手足口病"], [85884, 0])
    def test_list(self):
        self.assertEqual(notif.parse_list(LIST), [(2026, 8, notif.BASE + "202609/t20260918_1840340.html", "2026-09-18")])
    def test_drops(self):
        self.assertEqual(temp.drops([10, 2, 3, -5.0, -6]), [1, 3])   # 10→2 降8；3→-5 降8
        self.assertEqual(temp.drops([10, 2.1, None, 0]), [])
if __name__ == "__main__": unittest.main()
