"""
過去の記事の見出し（title）を、その分野に詳しくない人にも届く書き方に書き直す。
検索用タイトル（seoTitle）は名前で検索する人向けなので変えない。

- 「正体（何の会社・何のサービスか）」「種類（新AIモデル・新機能・値下げ…）」「何が変わるか」を入れる
- 見出しに無かった数字・事実は足さない（記事の説明・要点にあるものだけ使う）
- 1回の呼び出しで複数本まとめて直して、無料枠を節約する

使い方: .venv/bin/python scripts/rewrite_titles.py [--limit N] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import llm  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
DONE_KEY = "titleRewritten"
BATCH = 15

RULES = """あなたはニュースサイトの見出し担当の編集者です。次の記事見出しを、その分野に詳しくない一般の人にも届く見出しに書き直してください。
ルール:
- 固有名詞だけで終わらせず「何の・どんな種類のものか」と「何が新しい／何が変わるか」を入れる。
  会社・製品には一言で正体を添える（例:「ChatGPTのOpenAIが」「Googleの生成AI『Gemini』に」「AI半導体のNVIDIAが」）。
  種類を言う（新AIモデル／新機能／新サービス／新登場／値下げ／日本でも提供開始 など）。変化を言う（料金は半分に／〇〇もAIにお任せ など）。
- 専門用語（API・トークン・ベンチマーク・推論・エージェント等）は見出しに使わないか、使うなら日常語を添える。
- 事実は「元の見出し」「説明」「要点」に書かれていることだけ。新しい数字・日付・機能を足さない。誇張・煽り語（衝撃／ついに／ヤバい／必見）と感嘆符は使わない。
- 全角28〜48字。製品名・モデル名などの固有名詞は元の表記のまま残す。
- AI以外のジャンル（暮らし・スポーツ等）の記事も同じ考え方で、誰の何が変わるのかが伝わる見出しにする。
- すでに十分に分かりやすい見出しは、ほぼそのままでよい。
出力は JSON: {"items":[{"slug":"...","title":"..."}]} のみ。"""

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {"slug": {"type": "STRING"}, "title": {"type": "STRING"}},
                "required": ["slug", "title"],
            },
        }
    },
    "required": ["items"],
}


def numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:\.\d+)?", text))


BANNED = ("取材", "検証", "実測", "試してみた", "使ってみた", "衝撃", "ついに", "必見", "ヤバ")


def proper_nouns(title: str) -> set[str]:
    """元の見出しの固有名詞（英数字の名前と「」『』の中身）。書き直しても必ず残す"""
    names = {w for w in re.findall(r"[A-Za-z][A-Za-z0-9.+\-]*(?:\s[A-Z0-9][A-Za-z0-9.+\-]*)*", title) if len(w) >= 2}
    names |= set(re.findall(r"[「『]([^」』]{1,30})[」』]", title))
    return names


def valid(old: dict, new_title: str) -> bool:
    if not 20 <= len(new_title) <= 50 or "！" in new_title or "!" in new_title:
        return False
    if any(word in new_title for word in BANNED):
        return False
    if any(name not in new_title for name in proper_nouns(old["title"])):
        return False
    source = " ".join([old["title"], old.get("description", ""), " ".join(old.get("highlights", []))])
    # 元に無い数字を足していないか
    return numbers(new_title) <= numbers(source)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    llm._load_env_local()  # noqa: SLF001

    rows = []
    for path in sorted(ARTICLES.glob("*.json")):
        a = json.loads(path.read_text("utf-8"))
        if a.get(DONE_KEY):
            continue
        rows.append((path, a))
    if args.limit:
        rows = rows[: args.limit]
    print(f"[titles] 対象 {len(rows)} 本")

    changed = 0
    for i in range(0, len(rows), BATCH):
        chunk = rows[i : i + BATCH]
        payload = [
            {"slug": a["slug"], "genre": a.get("genre", ""), "title": a["title"],
             "description": a.get("description", "")[:160], "highlights": a.get("highlights", [])[:3]}
            for _, a in chunk
        ]
        try:
            data, model = llm.generate_json(RULES, json.dumps(payload, ensure_ascii=False), SCHEMA, temperature=0.4, max_output_tokens=8192, tier="bulk")
        except Exception as error:  # noqa: BLE001
            print(f"[titles] 失敗（{i}〜）: {str(error)[:120]}")
            break
        by_slug = {str(x.get("slug")): str(x.get("title", "")).strip() for x in data.get("items", [])}
        for path, a in chunk:
            new = by_slug.get(a["slug"], "")
            ok = bool(new) and valid(a, new)
            if ok and new != a["title"]:
                print(f"  {a['title']}\n→ {new}")
                if not args.dry_run:
                    a.setdefault("originalTitle", a["title"])
                    a["title"] = new
                changed += 1
            elif new and not ok:
                print(f"  [保留] {a['title']}  ×  {new}")
            # 基準を満たさなかった記事は印を付けず、次回（上位のAIが使えるとき）にやり直す
            if not args.dry_run and ok:
                a[DONE_KEY] = True
                path.write_text(json.dumps(a, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[titles] {min(i + BATCH, len(rows))}/{len(rows)}（{model}）")
    print(f"[titles] 書き直し {changed} 本")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
