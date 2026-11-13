"""2026-11-10（台帳 A71）: 読者がやることのガイドは、同じ発表のニュースの重複にしない（scripts/story.py）。

ドコモの流出の「今日やるのは明細とdアカウントの確認」（前日いちばん読まれた記事）が、同じ出典URLのニュースの
duplicateOf にされ、canonical が代表へ向いて検索から外れていた。本当の重複（同じ発表・同じ疑問）は今までどおり見分ける。
ネットワークは使わない。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import indexnow  # noqa: E402
import story  # noqa: E402

URL = "https://www.docomo.ne.jp/info/notice/page/261106_00_m.html"
NEWS_BODY = "\n\n".join(["## 最大約30万件の対象情報と問い合わせ先", "## 不審なメール・SMS・電話への対応", "## 復旧見込みは未定、侵入経路などを調査中"]) + "\n" + "本文" * 900
FAMILY_BODY = "\n\n".join([
    "## 流れた情報には、法定代理人と子育て応援の情報も入っていた",
    "## 家族の確認で、読者から出そうな疑問に答える",
    "### 家族の分も、まとめて確認できますか",
    "### 子どもの回線は対象になりますか",
    "### 親名義の回線を使っている場合、誰が確認するのですか",
    "## 状況別に、いま取る行動",
]) + "\n" + "本文" * 900


def art(slug, title, hours=0, body=NEWS_BODY, url=URL, **kw):
    at = f"2026-11-0{7 + hours // 24}T{hours % 24:02d}:00:00+00:00"
    base = {"slug": slug, "title": title, "sourceUrl": url, "generatedAt": at, "publishedAt": at, "genreSlug": "business",
            "keywords": ["ドコモ", "情報流出"], "body": body, "channelSlug": "docomo-ne-jp"}
    base.update(kw)
    return base


def plan_of(*items):
    stories = [story.Story(x) for x in items]
    return story.plan(stories, story.doc_freq(stories))


class GuideRoleTest(unittest.TestCase):
    def test_title_roles(self):
        self.assertEqual("action", story.page_role("ドコモ情報流出、最大30万件　今日やるのは明細とdアカウントの確認"))
        self.assertEqual("eligibility", story.page_role("ニトリ会員情報、最大3,762万件流出の恐れ　対象の確かめ方と今やること"))
        self.assertEqual("eligibility", story.page_role("年金生活者支援給付金、自分は対象？　生年月日と前年の年金収入で確かめる"))
        self.assertEqual("family", story.page_role("ドコモ流出は最大30万件　一部は法定代理人の情報も含む"))
        self.assertEqual("recap", story.page_role("Google、10月のAI発表をまとめ公開　「Gemini 4 Argon」提供済み、詐欺対策も"))
        # ニュースの題名はニュースのまま（発表・確認された などでガイドにしない）
        for title in ("ドコモの顧客情報最大約30万件流出　My docomoは緊急メンテナンス中",
                      "ドコモ、不正アクセスを確認　オンラインショップを停止",
                      "OpenAI、新AIモデル「GPT-6.1 Terra」を発表　API料金は半分、速度は3倍以上に",
                      "丸隆の電気ストーブ、端子の発火のおそれで点検交換　品番DMS-091-WHが対象"):
            self.assertEqual("news", story.page_role(title), title)

    def test_body_headings_decide_role_of_news_shaped_title(self):
        self.assertEqual("family", story.article_role({"title": "ドコモ流出は最大30万件", "body": FAMILY_BODY}))
        self.assertEqual("news", story.article_role({"title": "ドコモの顧客情報最大約30万件流出", "body": NEWS_BODY}))
        # 「今やること」の章が1つあるだけのニュースはニュース
        one = "## 何が起きたか\n\n## 今やること\n\n## まだ分からないこと\n" + "本文" * 900
        self.assertEqual("news", story.article_role({"title": "ドコモの顧客情報最大約30万件流出", "body": one}))


class GuideIsNotDuplicateTest(unittest.TestCase):
    def test_guides_are_not_duplicates_of_the_news(self):
        news = art("news", "ドコモの顧客情報最大約30万件流出　My docomoは緊急メンテナンス中", body=NEWS_BODY + "本文" * 50)
        todo = art("todo", "ドコモ情報流出、最大30万件　今日やるのは明細とdアカウントの確認", hours=26)
        family = art("family", "ドコモ流出は最大30万件　一部は法定代理人の情報も含む", hours=42, body=FAMILY_BODY)
        again = art("again", "ドコモの顧客情報が最大約30万件流出　緊急メンテナンス続く", hours=30)
        result = plan_of(news, todo, family, again)
        self.assertNotIn("todo", result)
        self.assertNotIn("family", result)
        self.assertEqual(("news", "同じ出典URL"), result["again"])  # 同じ疑問（ニュース）どうしは今までどおり重複

    def test_same_guide_twice_is_still_a_duplicate(self):
        a = art("a", "ドコモ情報流出　今日やるのは明細とdアカウントの確認", hours=1, body=NEWS_BODY + "本文" * 50)
        b = art("b", "ドコモ流出、今やることは明細の確認とパスワード変更", hours=3)
        self.assertEqual({"b": ("a", "同じ出典URL")}, plan_of(a, b))

    def test_recap_is_not_a_duplicate_of_one_product(self):
        demo = art("demo", "Googleが「Gemini 4 Argon」でスマート時計を自作するデモを公開", url="", genreSlug="ai", channelSlug="google-developers",
                   keywords=["Gemini 4 Argon", "Google"])
        recap = art("recap", "Google、10月のAI発表をまとめ公開　「Gemini 4 Argon」提供済み、詐欺対策も", hours=100, genreSlug="ai",
                    url="https://blog.google/technology/ai/google-ai-updates-october-2026/", channelSlug="google-blog-all",
                    keywords=["Gemini 4 Argon", "Google"])
        self.assertNotIn("recap", plan_of(demo, recap))

    def test_deep_dive_articles_are_never_grouped(self):
        news = art("news", "ドコモの顧客情報最大約30万件流出")
        deep = art("deep", "ドコモの顧客情報最大約30万件流出、その後", hours=5, angleOf="other-base", deepDive="qa")
        self.assertNotIn("deep", plan_of(news, deep))

    def test_mark_links_guides_with_angle_of(self):
        """mark は役割の違う同じ出典の記事に angleOf を付ける（サイトと IndexNow の予備の判定「同じ出典URLは1本」から外す）"""
        news = art("news", "ドコモの顧客情報最大約30万件流出　My docomoは緊急メンテナンス中")
        todo = art("todo", "ドコモ情報流出、最大30万件　今日やるのは明細とdアカウントの確認", hours=26, body=NEWS_BODY + "本文" * 300)
        with tempfile.TemporaryDirectory() as tmp:
            by_slug = {}
            for d in (news, todo):
                p = Path(tmp) / f"{d['slug']}.json"
                p.write_text(json.dumps(d, ensure_ascii=False), "utf-8")
                by_slug[d["slug"]] = (p, d)
            stories = [story.Story(news), story.Story(todo)]
            story.link_siblings(stories, story.doc_freq(stories), None, False, by_slug, {})
            saved = json.loads((Path(tmp) / "todo.json").read_text("utf-8"))
        self.assertEqual("news", saved["angleOf"])
        self.assertIn("news", saved["relatedSlugs"])
        # 本文の長いガイドが予備の判定でニュースを重複にしない（angleOf のある記事は予備の判定に入れない）
        self.assertEqual(set(), indexnow.duplicate_slugs([news, saved]))


class RealDataTest(unittest.TestCase):
    """本番の記事（content/articles）で、外した印が戻っていない・検索に出る"""

    UNMARKED = ("docomo-data-leak-what-to-do", "docomo-data-leak-family-lines", "google-ai-news-october-2026",
                "microsoft-foundry-agent-framework-customization")

    def test_unmarked_articles_are_indexable_with_self_canonical(self):
        rows = [d for _, d in story.load_all()]
        dups = indexnow.duplicate_slugs(rows)
        by = {d["slug"]: d for d in rows}
        for slug in self.UNMARKED:
            if slug not in by:
                continue  # 取り下げた記事は見ない
            self.assertFalse(by[slug].get("duplicateOf"), slug)
            self.assertNotIn(slug, dups, slug)
            self.assertIsNone(indexnow.noindex_reason(by[slug], dups), slug)

    def test_plan_does_not_mark_them_again(self):
        rows = [d for _, d in story.load_all() if story.eligible(d)]
        stories = sorted((story.Story(d) for d in rows), key=lambda s: (s.gen.isoformat() if s.gen else "9", s.slug))
        result = story.plan(stories, story.doc_freq(stories))
        for slug in self.UNMARKED:
            self.assertNotIn(slug, result, slug)


if __name__ == "__main__":
    unittest.main()
