#!/usr/bin/env python3
"""Threads の自動投稿の新しい書き方（2026-11-07 夜 オーナー承認・台帳 S46）。

11/7 に手で出した新しい書き方は表示 20 / 36 / 129（従来の自動の書き方は多くて 18）。ただし投稿で全部を言い切ったので、
サイトへのクリックは3回ほどだった。そこで「誰の話か・数字1つ」で読ませ、決め手は記事に残す。

本文（1件目・リンク無し）
  1. 1行目で誰の話かを言う（「〜な人へ。」「〜している人、」など。言い方は回す＝前の投稿と同じ形を続けない。FORMS）
  2. 大事な数字はちょうど1つ（日付・時刻は数えない）
  3. 対象の判定のすべて・手順・細かい期限は書かない。最後の文で「記事にしかないもの」を自然に言う
     （「対象かどうかの判定表は記事に置きました」など。直近と同じ言い回しは使わない）
返信（2件目）
  4. 「続き（対象の早見表）→ URL」の形の文。URL だけにしない。リンクは返信だけ（11/3 に本文のリンクで表示が落ちた）
  5. URL には utm_source=threads&utm_medium=social&utm_campaign=<記事の slug>&utm_content=reader_reply（投稿ごとのクリックを数える）
  6. 「｜」を使わない。決まり文句の使い回し・子どもっぽい言い方・煽りはしない

文面は LLM（llm.generate_json）で作り、sns_rules.check_threads_reader で確かめる。通らなければ出さない（次の回にもう一度）。
作った文面は state/threads_reader.json に残す（オーナーが見た下書きと、実際に出る文面を同じにするため）。

止め: state/threads_hold.json の held が true の間は、Threads の自動投稿を出さない（threads_gate.style_hold）。
  オーナーが最初の3本を承認したら held を false にする（それだけで再開する）。

  python scripts/threads_reader.py --draft <slug> [<slug> ...]   # 投稿せずに文面を作って表示する（state に残す）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "state" / "threads_reader.json"
ARTICLES_DIR = ROOT / "content" / "articles"
SITE = "https://ai-tech-express.jp"
UTM_CONTENT = "reader_reply"
VERSION = 1

# 1行目の「誰の話か」の言い方（前の投稿と同じ形を続けない）
FORMS = {
    "he": "「〜な人へ。」「〜の方へ。」のように、名指しして「へ。」で1行目を終える",
    "ten": "「〜している人、」のように名指しして読点で受け、同じ1行の中で短く用件を続ける",
    "wa": "「〜を使っている人は、」のように「は、」で受け、同じ1行の中で何が起きたかを短く続ける",
    "ni": "「〜な人に関わる話です。」「〜の人に向けた知らせです。」のように、誰に関わる話かを1文で言う",
}
FORM_ORDER = ["he", "ten", "wa", "ni"]


from threads_gate import ThreadsHeld  # noqa: E402


class ReaderNotReady(ThreadsHeld):
    """新しい書き方の文面を作れなかった（LLM が使えない・チェックを通らない）。投稿は落とさず次の回にもう一度"""


def log(message: str) -> None:
    print(message, flush=True)


def load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text("utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def save_state(data: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")


def article_url(slug: str) -> str:
    q = urllib.parse.urlencode({"utm_source": "threads", "utm_medium": "social", "utm_campaign": slug, "utm_content": UTM_CONTENT})
    return f"{SITE}/articles/{slug}?{q}"


def reply_text(slug: str, label: str) -> str:
    label = re.sub(r"[（）()\s]", "", str(label or "")).strip("。、")
    return f"続き（{label}）→ {article_url(slug)}"


def form_of(first_line: str) -> str:
    """1行目の言い方（FORMS のどれか。分からなければ ""）"""
    line = str(first_line or "").strip()
    who = r"(?:人|方|皆さん|担当者|利用者|契約者|会員|事業主|ユーザー|家庭|世帯|オーナー)"
    if re.search(who + r"へ。?$", line):
        return "he"
    if re.search(who + r"は、", line):
        return "wa"
    if re.search(who + r"(?:に|へ)(?:関わる|向けた|関係する)", line):
        return "ni"
    if re.search(who + r"、", line):
        return "ten"
    return ""


def recent(field: str, n: int = 6, state: dict | None = None) -> list[str]:
    """直近の文面の form / ending（新しい順）"""
    rows = sorted((state if state is not None else load_state()).get("posts", {}).values(), key=lambda r: r.get("at", ""), reverse=True)
    return [str(r.get(field) or "") for r in rows[:n] if r.get(field)]


def next_form(state: dict | None = None) -> str:
    """前の投稿の次の言い方（同じ形を続けない）"""
    last = recent("form", 1, state)
    if not last or last[0] not in FORM_ORDER:
        return FORM_ORDER[0]
    return FORM_ORDER[(FORM_ORDER.index(last[0]) + 1) % len(FORM_ORDER)]


def ending_of(main: str) -> str:
    lines = [x.strip() for x in str(main or "").splitlines() if x.strip()]
    return lines[-1] if lines else ""


def source_text(article: dict) -> str:
    parts = [article.get("title"), article.get("seoTitle"), article.get("description"), article.get("lede"), article.get("summaryLine"),
             " ".join(str(h) for h in article.get("highlights") or []), " ".join(str(h) for h in article.get("todayActions") or []),
             " ".join(str((p or {}).get("q", "")) + str((p or {}).get("a", "")) for p in article.get("faq") or []),
             " ".join(str(x) for x in ((article.get("workMoney") or {}).get("points") or [])), article.get("body"), article.get("easy")]
    return "\n".join(str(p or "") for p in parts)


def prompt_for(article: dict, form: str, avoid_endings: list[str], avoid_first: list[str]) -> str:
    body = str(article.get("body") or "")[:2000]
    return (
        "次の記事を Threads で紹介する投稿を、部品ごとに書く（11/7 に表示が多かった書き方）。\n"
        f"- who_line: 1行目。この記事が誰に関わる話かを、記事に出てくる立場・状況で具体的に言う。言い方は次の形: {FORMS[form]}。"
        "全角40字以内。ジャンルから作った決まった呼びかけ（「〜好きの皆さん」など）は使わない。数字は入れない。\n"
        "- key_number: 読者にとっていちばん大事な数字を1つ（件数・金額・割合など。記事にある書き方のまま。例「約30万件」「最大104万円」）。\n"
        "- facts: 何が起きたか・何が変わるかを2文（です・ます）。key_number はこの2文のどちらかに1回だけ入れる。"
        "who_line で言ったことは繰り返さない。ほかの数字（件数・金額・割合）は書かない（日付は書いてよいが、期限の日付は書かない）。\n"
        "  対象かどうかの判定のすべて、申請や対処の手順は書かない（記事で読んでもらう）。\n"
        "- closing: 最後の1文。記事にしかないもの（判定表・手順・問い合わせ先・対象の一覧など、この記事に実際にあるもの）を"
        "記事に置いたと自然に言う。全角35字以内。言い回しは記事に合わせて毎回変える。\n"
        "- label: 返信「続き（ここ）→ URL」の「ここ」に入る、closing で言ったものの短い名前（全角4〜12字。例: 対象の早見表、補償の流れ）。\n"
        "落ち着いた大人の自然な日本語。煽り（衝撃・必見・知らないと損・！）・絵文字・ハッシュタグ・URL・「｜」・「〜しましょう」は使わない。"
        "子どもっぽい言い方もしない。記事に無い事実・数字は書かない。見出しをそのまま繰り返さない。同じ言葉を何度も繰り返さない。\n"
        f"直近の投稿と同じ1行目・最後の文にしない。直近の1行目: {' / '.join(avoid_first) or 'なし'}。直近の最後の文: {' / '.join(avoid_endings) or 'なし'}\n\n"
        f"見出し: {article.get('title', '')}\n要約: {article.get('description', '')}\n冒頭: {article.get('lede', '')}\n"
        f"要点: {' / '.join(str(h) for h in article.get('highlights') or [])}\n"
        f"今日やること（記事にある）: {' / '.join(str(h) for h in article.get('todayActions') or [])}\n"
        f"よくある質問（記事にある）: {' / '.join(str((p or {}).get('q', '')) for p in article.get('faq') or [])}\n本文: {body}"
    )


def assemble(data: dict) -> str:
    facts = data.get("facts") or []
    if isinstance(facts, str):
        facts = [facts]
    parts = [str(data.get("who_line") or "").strip(), "\n".join(str(f).strip() for f in facts if str(f).strip()), str(data.get("closing") or "").strip()]
    return "\n\n".join(p for p in parts if p)


def compose(article: dict, *, state: dict | None = None, form: str = "", generate=None, tries: int = 3) -> dict:
    """新しい書き方の文面 {"main", "reply", "label", "form", "ending"}。作れなければ ReaderNotReady"""
    import sns_rules

    state = state if state is not None else load_state()
    form = form or next_form(state)
    avoid_end = recent("ending", 6, state)
    avoid_first = [str(r.get("main") or "").splitlines()[0] for r in state.get("posts", {}).values() if r.get("main")][-6:]
    schema = {"type": "OBJECT", "properties": {
        "who_line": {"type": "STRING"}, "key_number": {"type": "STRING"}, "facts": {"type": "ARRAY", "items": {"type": "STRING"}},
        "closing": {"type": "STRING"}, "label": {"type": "STRING"}}, "required": ["who_line", "facts", "closing", "label"]}
    if generate is None:
        import llm  # noqa: PLC0415

        def generate(prompt: str) -> dict:
            data, _ = llm.generate_json("あなたはニュースサイトの SNS 担当の編集者です。自然で正しい日本語だけを書きます。", prompt, schema,
                                        tier="quality", max_output_tokens=2048, purpose="sns")
            return data
    problems: list[str] = []
    for _ in range(max(1, tries)):
        try:
            data = generate(prompt_for(article, form, avoid_end, avoid_first) + (f"\n\n前の案の直すところ: {' / '.join(problems)}" if problems else ""))
        except Exception as error:  # noqa: BLE001
            raise ReaderNotReady(f"新しい書き方の文面を作れませんでした（{str(error)[:120]}）") from error
        main = re.sub(r"\n{3,}", "\n\n", assemble(data).replace("\r", "")).strip()
        reply = reply_text(article["slug"], str(data.get("label") or ""))
        problems = sns_rules.check_threads_reader("threads", main, reply, article, recent_endings=avoid_end, recent_forms=recent("form", 1, state))
        if problems:
            log(f"  [threads-reader] {article['slug']}: 直して書き直します（{' / '.join(problems[:3])}）: {main[:60]}")
        else:
            return {"main": main, "reply": reply, "label": str(data.get("label") or ""), "form": form_of(main.splitlines()[0]), "ending": ending_of(main)}
    raise ReaderNotReady("新しい書き方の文面がチェックを通りません: " + " / ".join(problems[:4]))


def remember(article: dict, pair: dict, *, status: str = "draft", state: dict | None = None) -> dict:
    state = state if state is not None else load_state()
    rec = state.setdefault("posts", {}).setdefault(article["slug"], {})
    rec.update({k: pair[k] for k in ("main", "reply", "label", "form", "ending")})
    rec.setdefault("at", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    rec["status"] = status
    rec["version"] = VERSION
    save_state(state)
    return state


def pair_for(article: dict, *, generate=None) -> dict:
    """この記事の文面（作ってあればそれを使う＝オーナーが見た下書きと同じ。無ければ作って残す）"""
    state = load_state()
    rec = (state.get("posts") or {}).get(article["slug"])
    if rec and rec.get("main") and rec.get("reply") and rec.get("version") == VERSION:
        return rec
    pair = compose(article, state=state, generate=generate)
    remember(article, pair, state=state)
    return pair


def is_reader_input(post_input: dict) -> bool:
    thread = (((post_input.get("metadata") or {}).get("threads") or {}).get("thread")) or []
    return len(thread) >= 2 and f"utm_content={UTM_CONTENT}" in str(thread[1].get("text") or "")


def apply_input(post_input: dict, article: dict, *, generate=None) -> dict:
    """Buffer の Threads の入力を、新しい書き方（本文＋返信のリンク）にする（その場で。画像・トピックはそのまま）"""
    pair = pair_for(article, generate=generate)
    meta = post_input.setdefault("metadata", {}).setdefault("threads", {})
    thread = meta.get("thread") or [{"text": post_input.get("text") or "", "assets": []}]
    first = dict(thread[0])
    first["text"] = pair["main"]
    meta["thread"] = [first, {"text": pair["reply"], "assets": []}]
    post_input["text"] = pair["main"]
    return pair


def mark_posted(slug: str) -> None:
    state = load_state()
    rec = (state.get("posts") or {}).get(slug)
    if rec:
        rec["status"] = "posted"
        rec["at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        save_state(state)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--draft", nargs="+", metavar="SLUG", help="投稿せずに文面を作って表示する")
    args = parser.parse_args()
    if not args.draft:
        parser.print_help()
        return 0
    for slug in args.draft:
        article = json.loads((ARTICLES_DIR / f"{slug}.json").read_text("utf-8"))
        state = load_state()
        state.get("posts", {}).pop(slug, None)
        pair = compose(article, state=state)
        remember(article, pair, state=state)
        print(f"=== {slug}（{pair['form']}）\n{pair['main']}\n--- 返信\n{pair['reply']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
