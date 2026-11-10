"""オーナーの決まり（縦棒「｜」と「ざっくり」を使わない）が、記事と画面のタイトルに守られているかを見る。

2026-11-10 SEO 作業の束 A3。記事の title / seoTitle / description / 本文、
products・choose のページ題、掲載終了ページの題、まとめ投稿の題に縦棒が無いこと。
"""
import glob
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from article_style import ZAKKURI_RE  # noqa: E402

BAR = "｜"
TEXT_FIELDS = ("title", "seoTitle", "description", "lede", "body", "easy")


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


class ArticleCorpusTest(unittest.TestCase):
    def setUp(self):
        self.files = sorted(glob.glob(os.path.join(ROOT, "content", "articles", "*.json")))
        self.assertGreater(len(self.files), 100)

    def test_no_bar_or_zakkuri_in_article_text(self):
        bad = []
        for path in self.files:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for key in TEXT_FIELDS:
                value = data.get(key)
                if not isinstance(value, str):
                    continue
                if BAR in value:
                    bad.append(f"{os.path.basename(path)} {key}: 縦棒")
                if ZAKKURI_RE.search(value):
                    bad.append(f"{os.path.basename(path)} {key}: ざっくり")
        self.assertEqual(bad, [])


class SourceTitleTest(unittest.TestCase):
    def test_product_and_choose_titles(self):
        for rel in ("lib/products.ts", "lib/choose-data.ts"):
            for line in _read(rel).splitlines():
                if re.search(r"\btitle\b|とは", line) and not line.strip().startswith(("//", "*", "/*")):
                    self.assertNotIn(BAR, line, f"{rel}: {line.strip()}")

    def test_gone_page_titles(self):
        src = _read("cloudflare/worker.ts")
        for m in re.finditer(r"<title>[^<]*</title>", src):
            self.assertNotIn(BAR, m.group(0))

    def test_digest_title_builders(self):
        for rel in ("scripts/morning_digest.py", "scripts/bluesky_post.py"):
            self.assertNotIn(f"{BAR}サイソクニュース", _read(rel), rel)

    def test_prompts_do_not_invite_bar(self):
        for rel in ("scripts/main.py", "scripts/web_articles.py", "scripts/rewrite_titles.py", "scripts/roundup.py"):
            src = _read(rel)
            self.assertNotIn(f"「{BAR}」「：」", src, rel)
            for m in re.finditer(r"良い例:.*|「〇〇の使い方と料金.」", src):
                self.assertNotIn(BAR, m.group(0), rel)

    def test_faq_name_splits_on_fullwidth_space(self):
        src = _read("app/articles/[slug]/page.tsx")
        m = re.search(r"seoTitle\?\.split\(/\[([^\]]*)\]", src)
        self.assertIsNotNone(m)
        self.assertIn("　", m.group(1))
        self.assertIn(BAR, m.group(1))  # 古い題の区切りも残す


if __name__ == "__main__":
    unittest.main()
