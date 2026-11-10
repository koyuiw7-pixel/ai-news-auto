"""取り下げた記事（content/retired.json。410 を返す）へのリンクが、載っている記事・データに残っていないか（台帳 A9）。

2026-11-08 に132本を戻したとき、戻した記事の中に取り下げ済みのまとめ記事への roundupSlug や本文のリンクが残った
（scripts/retire_articles.py の参照の付け替えを回していなかった）。記事を戻したら `python3 scripts/retire_articles.py --resweep --apply` を回す。
画面の側でも、取り下げた・無い記事へのリンクは出さない（lib/live-links.ts）。
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import retire_articles  # noqa: E402

SLUG_KEYS = ("slug", "verdictSource", "duplicateOf", "angleOf", "roundupSlug", "mainSlug")
# サイト内の記事へのリンク（相対のリンク・自分のドメインの絶対URL）。他のサイトの /articles/... は数えない
LINK = re.compile(r"(?:https://ai-tech-express\.jp|(?<![\w.\-/:]))/articles/([A-Za-z0-9_-]+)")


def references(value, key: str = ""):
    """(場所, slug) を並べる。slug の欄・relatedSlugs・文字の中のサイト内リンク"""
    if isinstance(value, dict):
        for k, v in value.items():
            if k in SLUG_KEYS and isinstance(v, str) and v:
                yield k, v
            elif k == "relatedSlugs" and isinstance(v, list):
                for s in v:
                    if isinstance(s, str):
                        yield k, s
            else:
                yield from references(v, k)
    elif isinstance(value, list):
        for v in value:
            yield from references(v, key)
    elif isinstance(value, str) and "/articles/" in value:
        for m in LINK.finditer(value):
            yield f"{key}(link)", m.group(1)


def content_files() -> list[Path]:
    files = sorted(retire_articles.ARTICLES.glob("*.json"))
    files += [ROOT / f for f in retire_articles.DATA_FILES]
    files += [p for d in retire_articles.DATA_DIRS for p in sorted((ROOT / d).glob("*.json"))]
    return [p for p in files if p.exists()]


class RetiredLinksTest(unittest.TestCase):
    def test_no_live_reference_to_retired_articles(self):
        retired = set(json.loads(retire_articles.RETIRED.read_text(encoding="utf-8")).get("articles") or {})
        bad = []
        for path in content_files():
            data = json.loads(path.read_text(encoding="utf-8"))
            own = data.get("slug") if path.parent == retire_articles.ARTICLES else None
            for where, slug in references(data):
                if slug in retired and not (where == "slug" and slug == own):
                    bad.append(f"{path.relative_to(ROOT)} {where} → {slug}")
        self.assertEqual(bad, [], "取り下げた記事へのリンクが残っています。python3 scripts/retire_articles.py --resweep --apply で直す:\n" + "\n".join(bad[:30]))

    def test_reference_scanner_finds_each_field(self):
        sample = {
            "roundupSlug": "gone-a",
            "relatedSlugs": ["gone-b", "live"],
            "duplicateOf": "gone-c",
            "body": "詳しくは[まとめ](/articles/gone-d)へ。外のサイト https://example.com/articles/gone-e は数えない。https://ai-tech-express.jp/articles/gone-f",
            "sources": [{"slug": "gone-g", "title": "元記事"}],
        }
        found = {slug for _, slug in references(sample)}
        self.assertEqual(found, {"gone-a", "gone-b", "live", "gone-c", "gone-d", "gone-f", "gone-g"})

    def test_rewriter_drops_roundup_and_slug_text(self):
        rw = retire_articles.Rewriter({"gone": {"title": "x"}})
        out = rw.walk({
            "slug": "keep",
            "roundupSlug": "gone",
            "roundupTitle": "取り下げたまとめ",
            "relatedSlugs": ["gone", "other"],
            "body": "前の記事（[gone](/articles/gone)）と[まとめ](/articles/gone)。",
        })
        self.assertNotIn("roundupSlug", out)
        self.assertNotIn("roundupTitle", out)
        self.assertEqual(out["relatedSlugs"], ["other"])
        self.assertEqual(out["body"], "前の記事とまとめ。")

    def test_resweep_dry_run_writes_nothing(self):
        before = {p: p.read_bytes() for p in content_files()}
        before[retire_articles.RETIRED] = retire_articles.RETIRED.read_bytes()
        from datetime import datetime, timezone
        stats = retire_articles.apply({}, datetime.now(timezone.utc), dry_run=True)
        self.assertIn("files", stats)
        for p, raw in before.items():
            self.assertEqual(p.read_bytes(), raw, f"確認だけのはずが書き換えた: {p}")


if __name__ == "__main__":
    unittest.main()
