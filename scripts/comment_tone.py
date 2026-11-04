#!/usr/bin/env python3
"""ほかの人の投稿へのコメントの言い方の点検（2026-11-05 オーナー決定・台帳 O14）。

大きなアカウントの投稿にすばやく反応するときも、偉そうに絡まない（上から目線・知ったかぶり・訂正口調・説教をしない）。
コメントには具体的で考えた一言を必ず入れる（公式の発表にある事実・役に立つ見方・本当に知りたい問い）。ていねいで謙虚に。
投稿するのは今までどおり、オーナーが1件ずつ OK してから（O3）。

  python3 scripts/comment_tone.py "コメントの下書き"      # 問題が無ければ ok（終了コード 0）、あれば一覧（終了コード 1）
  python3 scripts/comment_tone.py --file drafts.json     # [{"text": ...}, ...] をまとめて点検

朝・昼・夕のコメントの下書き（対話の回）は、オーナーに見せる前にこれを通す。毎日の見張りの手元の点検
（scripts/owner_rules_audit.py --comment-log）も、履歴に本文（text）があれば同じ基準で見る。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 上から目線・知ったかぶり・訂正口調・説教（ほかの人の投稿へのコメントでは使わない）
CONDESCENDING = [
    r"知らない(?:ん|の)ですか", r"ご存じない", r"ご存知ない", r"勉強不足", r"常識(?:です|だ|ですよ|でしょう)", r"当然(?:です|でしょう|だ)",
    r"当たり前(?:です|でしょう|だ)", r"誤り(?:です|だ)", r"間違い(?:です|だ)(?!った)", r"正しくは", r"それは違(?:います|う)",
    r"分かってない", r"わかってない", r"浅い(?:です|ね|な)", r"甘い(?:です|ね|な)", r"素人", r"初歩的", r"釈迦に説法",
    r"(?:もう少し|ちゃんと)調べ", r"(?:よく|ちゃんと)読んで", r"教えてあげ", r"念のため言っておく", r"言っておきますが",
    r"(?:です|ます)けどね", r"まあ(?:、)?(?:普通|ふつう)は", r"今更", r"今さら", r"周回遅れ", r"もう古い", r"でしかない",
    r"に過ぎません", r"にすぎません", r"笑$", r"（笑）", r"w{2,}$",
]
CONDESCENDING_RE = re.compile("|".join(CONDESCENDING))

# 中身の無い反応だけのコメント（具体的な一言が無い）
EMPTY_ONLY = re.compile(r"^(?:すごい|すごいです|素晴らしい|素晴らしいです|勉強になります|参考になります|ありがとうございます|なるほど|いいですね|わかります|同感です)[!！。、…\s]*$")

# 具体的な一言のしるし: 数字・固有名詞（英字）・「」の引用・問い・公式の出どころ・自分の経験や見方の言い方
SUBSTANCE_RE = re.compile(r"[0-9０-９]|[A-Za-z]{2,}|「[^」]{2,}」|[?？]|公式|発表|によると|では|私も|自分も|個人的に|気になる|気になりました|知りたい|伺いたい|試し|使って")

POLITE_RE = re.compile(r"(?:です|ます|でした|ました|ません|でしょうか|ですね|ますね|ですか|ください)")


def problems(text: str) -> list[str]:
    """コメント1件の問題（空なら OK）"""
    text = str(text or "").strip()
    out = []
    if not text:
        return ["[O14] コメントが空"]
    m = CONDESCENDING_RE.search(text)
    if m:
        out.append(f"[O14] 偉そうに聞こえる言い方「{m.group(0)}」（訂正・説教・知ったかぶりをしない。ていねいで謙虚に）")
    if EMPTY_ONLY.match(text) or not SUBSTANCE_RE.search(text):
        out.append("[O14] 具体的な一言が無い（公式の発表にある事実・役に立つ見方・本当に知りたい問いのどれかを入れる）")
    if not POLITE_RE.search(text):
        out.append("[O14] ていねいな言い方（です・ます）になっていない")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text", nargs="?", default="")
    ap.add_argument("--file", default="")
    args = ap.parse_args()
    texts = [args.text] if args.text else []
    if args.file:
        data = json.loads(Path(args.file).expanduser().read_text("utf-8"))
        texts += [str((d or {}).get("text") or (d or {}).get("comment") or "") if isinstance(d, dict) else str(d) for d in data]
    bad = 0
    for t in texts:
        found = problems(t)
        if found:
            bad += 1
            print(f"NG: {t[:60]}\n  " + "\n  ".join(found))
        else:
            print(f"ok: {t[:60]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
