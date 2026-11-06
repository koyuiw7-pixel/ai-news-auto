import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import calc_facts  # noqa: E402


class OkuTableTest(unittest.TestCase):
    """「（億円）」単位の決算の表の数字を、記事の「2兆9,160億円」と同じ値として認める（2026-11-06 KDDI）"""

    def test_oku_table_values_are_allowed(self):
        allowed = calc_facts.values("＜連結業績＞ （億円） 売上高 29,160 30,528 +4.7％")
        q = calc_facts.extract("売上高は2兆9,160億円")[0]
        self.assertTrue(calc_facts.supported(q, allowed))

    def test_without_unit_header_not_scaled(self):
        allowed = calc_facts.values("売上高 29,160 30,528")
        q = calc_facts.extract("売上高は2兆9,160億円")[0]
        self.assertFalse(calc_facts.supported(q, allowed))


if __name__ == "__main__":
    unittest.main()
