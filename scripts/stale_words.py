#!/usr/bin/env python3
"""古くなる「今日・明日・今週」と、過ぎた予定の見出し（SEO A19・2026-11-10）。

1. 相対の言葉に日付を添える（absolutize）
   「本日より」→「11月2日より」（日の言葉は置きかえ）、「来週」→「来週（11月9日の週）」、「今年度」→「今年度（2026年度）」（かっこで添える）。
   基準は出典の発表日（sourcePublishedAt。日本時間）。無い記事は書きかえず、一覧に出すだけ。
   日の言葉は同じ日の日付に置きかえ、週・月・年はかっこで日付を足すだけなので、文の意味は変わらない（うそにならない）。
   書きかえないもの: 「」『』の中（引用・例の文）、見出し・表の行、「前年度比」のような比べる言葉、
   「今日から使える」のような決まった言い回し（あいまいなので一覧に出す）。
   生成のとき（scripts/article_style.py の autofix）と、7日以上前の記事の掃除（--sweep）で同じ関数を使う。
   言い回しの直しなので、更新日時は動かさない（scripts/updated_at.py の kind="style"）。

2. 過ぎた予定の見出し（--passed）
   「11月6日施行へ」「11月3日発売」のように、題名の日付が公開より後で、今日より前の記事。
   公式のページを読み直し、その日付が今も書かれていて「延期・中止」などの案内が無いときだけ、
   「予定の11月6日を過ぎました。11月10日時点の公式ページでは、日付の変更や延期の案内はありません」の更新履歴を足す
   （確かめた日の事実。updated_at.touch_updated の kind="followup"）。読めない・日付が無い・延期の言葉があるページは一覧に出すだけ。

  python3 scripts/stale_words.py --sweep            # 7日以上前の記事で直せるところと、あいまいな文の一覧（下見）
  python3 scripts/stale_words.py --sweep --apply
  python3 scripts/stale_words.py --passed           # 過ぎた予定の見出しの一覧（下見。公式ページは読まない）
  python3 scripts/stale_words.py --passed --apply   # 公式ページを確かめて更新履歴を足す
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import updated_at  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "content" / "articles"
JST = timezone(timedelta(hours=9))
SWEEP_AGE_DAYS = 7

FIELDS = ("body", "easy", "lede", "description")
LIST_FIELDS = ("highlights",)

# 日付を添える言葉。（前に「前」「昨」が付く比べる言葉は別。「前年度比」などは対象外）
WORD_RE = re.compile(r"(?<![前翌同毎])(本日|今日|明日|昨日|今週|来週|先週|今月|来月|先月|今年度|来年度|昨年度|今年|来年|昨年)(?!度)")
# 「今日」「明日」「昨日」は言い回しが多いので、時刻・起点の言葉が続くときだけ
DAY_WORDS = {"今日", "明日", "昨日"}
# 決まった言い回し（日付を足すとおかしい・読者の「今日」の意味）。書きかえず一覧に出す
IDIOM_TAIL = re.compile(r"^(?:から|より)?(?:すぐ)?(?:使え|試せ|試す|試し|でき|始め|実践|役立|私たち|には|やる|の最先端)")
# 「今日から直接試すことはできません」のような、読者の「今日」の意味になりやすい言い回し（あいまい）
GENERIC_NEAR = re.compile(r"試|使え|使う|でき|始め|実践|役立|活用|活か|取り入れ|備え|見直|やる|すぐ|作業|手順")
DAY_STRICT = re.compile(r"^(?:付|時点|現在|正午|午前|午後|をもって)")
RELEASE_NEAR = re.compile(r"提供|開始|配信|発売|販売|受付|公開|施行|適用|利用可能|ダウンロード|順次|始ま|スタート")
YEAR_WORDS = {"今年", "来年", "昨年"}
QUOTE_PAIRS = {"「": "」", "『": "』", "“": "”", "`": "`"}


def base_date(record: dict) -> date | None:
    """相対の言葉の基準日（出典の発表日。日本時間）。無ければ None（書きかえない）"""
    raw = str(record.get("sourcePublishedAt") or "").strip()
    if not raw:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return date.fromisoformat(raw)
    try:
        when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (when if when.tzinfo else when.replace(tzinfo=JST)).astimezone(JST).date()


def _md(d: date) -> str:
    return f"{d.month}月{d.day}日"


def _month(d: date, delta: int) -> str:
    y, m = divmod(d.year * 12 + d.month - 1 + delta, 12)
    return f"{m + 1}月" if y == d.year else f"{y}年{m + 1}月"


def _fy(d: date) -> int:
    return d.year if d.month >= 4 else d.year - 1


def label_for(word: str, d: date) -> str:
    """言葉に添える日付（かっこの中）"""
    monday = d - timedelta(days=d.weekday())
    return {
        "本日": _md(d), "今日": _md(d), "明日": _md(d + timedelta(days=1)), "昨日": _md(d - timedelta(days=1)),
        "今週": f"{_md(monday)}の週", "来週": f"{_md(monday + timedelta(days=7))}の週", "先週": f"{_md(monday - timedelta(days=7))}の週",
        "今月": _month(d, 0), "来月": _month(d, 1), "先月": _month(d, -1),
        "今年": f"{d.year}年", "来年": f"{d.year + 1}年", "昨年": f"{d.year - 1}年",
        "今年度": f"{_fy(d)}年度", "来年度": f"{_fy(d) + 1}年度", "昨年度": f"{_fy(d) - 1}年度",
    }[word]


def _quoted_spans(line: str) -> list[tuple[int, int]]:
    spans, stack = [], []
    for i, ch in enumerate(line):
        if stack and ch == QUOTE_PAIRS[line[stack[-1]]]:
            start = stack.pop()
            if not stack:
                spans.append((start, i))
        elif ch in QUOTE_PAIRS and ch != "`" or (ch == "`" and not stack):
            stack.append(i)
    if stack:  # 閉じていないかっこは行末まで
        spans.append((stack[0], len(line)))
    return spans


def _fix_line(line: str, d: date, ambiguous: list[str]) -> str:
    stripped = line.lstrip()
    if stripped.startswith(("#", "|")):
        return line
    quoted = _quoted_spans(line)
    out, last = [], 0
    for m in WORD_RE.finditer(line):
        word, start, end = m.group(1), m.start(), m.end()
        if any(a <= start <= b for a, b in quoted):
            continue
        tail = line[end:end + 12]
        if tail.startswith(("（", "(")):  # すでに日付などが添えてある
            continue
        if word not in YEAR_WORDS and re.match(r"\d{1,4}[年月/]", tail):  # 「本日10月29日から」のように日付が続くときはそのまま
            continue
        near = line[end:end + 16]
        # 「今日」「明日」「昨日」は、時刻の言葉が続くか、「から・より」の後に提供・開始などの言葉があるときだけ（ほかは読者の「今日」の言い回し）
        day_ok = bool(DAY_STRICT.match(tail)) or (bool(re.match(r"^(?:から|より)", tail)) and bool(RELEASE_NEAR.search(near)) and not GENERIC_NEAR.search(near))
        if IDIOM_TAIL.match(tail) or (word in DAY_WORDS and not day_ok):
            ambiguous.append(line[max(0, start - 20):end + 20].strip())
            continue
        if word in YEAR_WORDS and re.match(r"\d{1,2}月", tail):
            # 「今年11月」→「2026年11月」
            out.append(line[last:start] + label_for(word, d))
        elif word in DAY_WORDS or word == "本日":
            # 日の言葉は日付に置きかえる（「本日から」→「11月2日から」）。ほかはかっこで添える（「来週（11月9日の週）」）
            out.append(line[last:start] + label_for(word, d))
        else:
            out.append(line[last:end] + f"（{label_for(word, d)}）")
        last = end
    out.append(line[last:])
    return "".join(out)


def absolutize_text(text: str, d: date, ambiguous: list[str] | None = None) -> str:
    sink = ambiguous if ambiguous is not None else []
    return "\n".join(_fix_line(line, d, sink) for line in text.split("\n"))


def absolutize(record: dict) -> tuple[list[str], list[str]]:
    """記事の相対の言葉に日付を添える。(直した欄, あいまいで残した文)。基準日が無い記事は何もしない"""
    d = base_date(record)
    changed: list[str] = []
    ambiguous: list[str] = []
    if d is None:
        return changed, ambiguous
    for key in FIELDS:
        text = record.get(key)
        if isinstance(text, str) and WORD_RE.search(text):
            new = absolutize_text(text, d, ambiguous)
            if new != text:
                record[key] = new
                changed.append(key)
    for key in LIST_FIELDS:
        vals = record.get(key)
        if isinstance(vals, list) and any(isinstance(v, str) and WORD_RE.search(v) for v in vals):
            new_vals = [absolutize_text(v, d, ambiguous) if isinstance(v, str) else v for v in vals]
            if new_vals != vals:
                record[key] = new_vals
                changed.append(key)
    faq = record.get("faq")
    if isinstance(faq, list):
        for row in faq:
            if isinstance(row, dict) and isinstance(row.get("a"), str) and WORD_RE.search(row["a"]):
                new = absolutize_text(row["a"], d, ambiguous)
                if new != row["a"]:
                    row["a"] = new
                    if "faq" not in changed:
                        changed.append("faq")
    if WORD_RE.search(str(record.get("title") or "")):
        ambiguous.append(f"題名: {record.get('title')}")
    return changed, ambiguous


# --------------------------------------------------------------------------- #
# 過ぎた予定の見出し
# --------------------------------------------------------------------------- #

PLAN_RE = re.compile(r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日(?:[^。、]{0,14}?)(へ|予定|開始|施行|始まる|から|スタート|締め切|期限|まで|実施|発売|提供|開催)")
POSTPONED_RE = re.compile(r"延期|中止|取りやめ|見送り|延長|変更になりました|日程を変更")


def _created(record: dict) -> date | None:
    raw = str(record.get("generatedAt") or record.get("publishedAt") or "")
    try:
        when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (when if when.tzinfo else when.replace(tzinfo=timezone.utc)).astimezone(JST).date()


def planned_date(record: dict) -> tuple[date, str] | None:
    """題名の予定の日付（公開より後）。(日付, 題名の中の言葉)"""
    m = PLAN_RE.search(str(record.get("title") or ""))
    created = _created(record)
    if not m or not created:
        return None
    year = int(m.group(1)) if m.group(1) else created.year
    try:
        when = date(year, int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    if not m.group(1) and when < created - timedelta(days=180):
        when = date(year + 1, when.month, when.day)
    return (when, m.group(0)) if when > created else None


def passed_note_exists(record: dict, when: date) -> bool:
    return any(u.get("kind") == "followup" and f"予定の{_md(when)}を過ぎました" in str(u.get("title") or "")
               for u in record.get("updates") or [])


def passed_candidates(today: date, records: list[dict]) -> list[tuple[dict, date, str]]:
    out = []
    for record in records:
        found = planned_date(record)
        if found and found[0] < today and not passed_note_exists(record, found[0]):
            out.append((record, found[0], found[1]))
    return out


def _date_forms(when: date) -> list[str]:
    reiwa = when.year - 2018
    return [f"{when.month}月{when.day}日", f"{when.year}/{when.month}/{when.day}", f"{when.year}-{when.month:02d}-{when.day:02d}",
            f"{when.month}/{when.day}", f"令和{reiwa}年{when.month}月{when.day}日", f"{when.month:02d}月{when.day:02d}日"]


def judge_page(text: str, when: date) -> tuple[bool, str]:
    """公式ページの文に予定の日付があり、延期・中止の言葉が無いか。(書いてよいか, 理由)"""
    norm = re.sub(r"\s+", "", text or "").translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    if not norm:
        return False, "公式ページを読めない"
    if not any(form in norm for form in _date_forms(when)):
        return False, "公式ページに予定の日付が見つからない"
    if m := POSTPONED_RE.search(norm):
        return False, f"公式ページに「{m.group(0)}」がある（人が確かめる）"
    return True, ""


def passed_note(when: date, checked: date) -> str:
    return f"予定の{_md(when)}を過ぎました。{_md(checked)}時点の公式ページでは、日付の変更や延期の案内はありません"


def apply_passed(record: dict, when: date, page_text: str, checked: datetime) -> tuple[bool, str]:
    ok, why = judge_page(page_text, when)
    if not ok:
        return False, why
    updated_at.touch_updated(record, "followup", at=checked.astimezone(timezone.utc), title=passed_note(when, checked.astimezone(JST).date()),
                             source_url=str(record.get("sourceUrl") or ""), source_name=str(record.get("sourceName") or ""))
    return True, ""


# --------------------------------------------------------------------------- #


def load_all() -> list[tuple[Path, dict]]:
    out = []
    for path in sorted(ARTICLES_DIR.glob("*.json")):
        try:
            out.append((path, json.loads(path.read_text("utf-8"))))
        except (OSError, json.JSONDecodeError):
            continue
    return out


def save(path: Path, record: dict) -> None:
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--passed", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    now = datetime.now(timezone.utc)
    today = now.astimezone(JST).date()
    items = load_all()
    if args.sweep:
        fixed, listed = 0, 0
        for path, record in items:
            created = _created(record)
            if not created or (today - created).days < SWEEP_AGE_DAYS or record.get("type") == "roundup":
                continue
            changed, ambiguous = absolutize(record)
            if changed:
                fixed += 1
                print(f"[fix] {record['slug']}: {', '.join(changed)}")
                if args.apply:
                    save(path, record)
            for line in ambiguous[:4]:
                listed += 1
                print(f"   [そのまま] {record['slug']}: {line}")
        print(f"[stale-words] 日付を添えた記事 {fixed} 本・あいまいで残した文 {listed} 件{'（書き込み済み）' if args.apply else '（下見）'}")
    if args.passed:
        found = passed_candidates(today, [r for _, r in items])
        paths = {r["slug"]: p for p, r in items}
        print(f"[stale-words] 過ぎた予定の見出し: {len(found)} 本")
        for record, when, phrase in found:
            print(f"  {record['slug']}: 「{phrase}」（{when.isoformat()}）")
            if not args.apply:
                continue
            import feeds  # noqa: PLC0415 - 公式ページを読むときだけ

            try:
                text = feeds.fetch_article_text(str(record.get("sourceUrl") or "")).get("text", "")
            except Exception as error:  # noqa: BLE001
                text = ""
                print(f"     読めない: {str(error)[:100]}")
            ok, why = apply_passed(record, when, text, now)
            print(f"     {'更新履歴を足した' if ok else 'そのまま（' + why + '）'}")
            if ok:
                save(paths[record["slug"]], record)
    if not (args.sweep or args.passed):
        ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
