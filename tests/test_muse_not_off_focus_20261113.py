"""依頼した記事（Muse）は題名の語で「主題外」として止めない（2026-11-13 ブックオフのフェアが止まった）"""
import sys, pathlib, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import indexnow


class MuseNotOffFocus(unittest.TestCase):
    def art(self, **kw):
        base = {"title": "ブックオフのオータムフェア2026、11月14・15日は買上額のほぼ20%分クーポン", "body": "あ" * 2000, "sourceType": "web"}
        base.update(kw)
        return base

    def test_muse_article_is_not_blocked_as_off_focus(self):
        self.assertNotEqual(indexnow.publish_block_reason(self.art(writer="muse")), "off-focus")

    def test_other_blocks_still_apply_to_muse(self):
        a = self.art(writer="muse")
        if indexnow.focus_reason(a) in ("wire", "creator-video"):
            self.assertIsNotNone(indexnow.publish_block_reason(a))


if __name__ == "__main__":
    unittest.main()
