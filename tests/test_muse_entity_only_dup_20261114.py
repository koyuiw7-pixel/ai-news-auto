"""固有名詞が同じだけでは重複にしない（2026-11-14 無印のカード番号流出が MUJI Card のポイントの記事と重複扱いで止まった）"""
import sys, pathlib, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import dedupe
import muse_articles


class EntityOnlyDup(unittest.TestCase):
    A = "無印良品 MUJI Card カード番号流出、対象は2021年7月までの入会者　確認方法と再発行"
    B = "MUJI Cardのマイル廃止、買い物100円で1ポイントに　期限は5ヵ月後の月末まで"

    def test_similarity_is_below_the_floor(self):
        sim = dedupe.jaccard(dedupe.bigrams(self.A), dedupe.bigrams(self.B))
        self.assertLess(sim, muse_articles.ENTITY_ONLY_MIN_SIMILARITY)

    def test_shared_entities_alone_still_hit_in_the_shared_index(self):
        idx = dedupe.Index(); idx.add(self.B, label=self.B)
        hit = idx.match(self.A, "")
        self.assertTrue(hit and hit[0].startswith("固有名詞が一致"))

    def test_similar_titles_with_shared_entities_stay_duplicates(self):
        idx = dedupe.Index(); idx.add(self.B, label=self.B)
        c = "MUJI Cardのマイル廃止、100円で1ポイントに変更　期限は5ヵ月後の月末"
        hit = idx.match(c, "")
        self.assertTrue(hit)
        self.assertFalse(hit[0].startswith("固有名詞が一致") and dedupe.jaccard(dedupe.bigrams(c), dedupe.bigrams(self.B)) < muse_articles.ENTITY_ONLY_MIN_SIMILARITY)


if __name__ == "__main__":
    unittest.main()
