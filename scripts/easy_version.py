#!/usr/bin/env python3
"""「かんたんに読む」版（記事 JSON の easy）を、記事の本文だけを材料に作り直す（2026-11-10 オーナー指摘）。

困っていたこと: Muse の記事（museFile のある記事）の easy は「## ひとことで言うと」の要約だけのことが多い。
記事ページは「この記事のポイント」がある記事では、その要約の章を出さない（台帳 A28。lib/article-sections.ts の
dropSummarySections）。すると easy が空になり、「かんたんに読む」の切り替え（components/ReadingMode.tsx）が出なかった。
いちばん読まれている暮らしとお金の記事（電気代・児童手当・年金の給付金など）で起きていた。

この段がすること（1記事に LLM を最大2回＋事実確認）:
  1. thin(record): 表示の段と同じ規則（scripts/section_gate.py で中身なしの章・つなぎの文を除き、要点がある記事では
     要約の章を除く）で、残る中身が EASY_MIN_CHARS 字に満たないか
  2. 本文（body）だけを材料に、短く・専門用語なしで、本文と同じ事実のかんたん版を書かせる
     （「## ひとことで言うと」＋ 何が変わる／自分は対象か／いつ・いくら／やること の役目の章。見出しは中身の言葉）
  3. 確かめる（1つでも合わなければ使わない。記事はそのまま）:
     - 数字（金額・日付・電話番号の数を含む）がすべて本文にある（scripts/calc_facts.py。計算した数字も認めない）
     - 本文を元記事とみなした事実確認（scripts/quality.py の fact_check。創作・矛盾が無く、点数が EASY_MIN_SCORE 以上）
     - 表示したときに要約以外の章が2つ以上残る・本文より短い・「｜」を使わない・幼い言い方などの文体の門（section_gate.style_problems）
     - すべての段で同じ合格の基準（quality.added_problems。書き換えで新しく増える不合格が無い）
  失敗しても記事の公開・ほかの処理は止めない（呼び出し側は例外を握りつぶしてよい。ensure は例外を出さない）。

  python3 scripts/easy_version.py --slug electricity-bill-nov-2026-subsidy-ends          # 試し（前と後を表示。書き込まない）
  python3 scripts/easy_version.py --slug electricity-bill-nov-2026-subsidy-ends --apply  # 書き込む
  python3 scripts/easy_version.py --muse --apply --max 30 --purpose helper               # Muse の記事で空になるものを新しい順に
  python3 scripts/easy_version.py --list                                                 # 空になる記事の一覧（LLM なし）
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import section_gate as gate  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "content" / "articles"

# 表示で残る中身（要約の章を除く）がこれより短ければ作り直す
EASY_MIN_CHARS = 120
EASY_MIN_SCORE = 85
MAX_ATTEMPTS = 2
BODY_CAP = 9000
# lib/article-sections.ts の SUMMARY_HEADING_RE と同じ
SUMMARY_HEADING_RE = re.compile(r"^(?:ひとことで言うと|ひとすることで言うと|要点|この記事のポイント|ポイント|要約)[？?]?$")
SUMMARY_OPENER_RE = re.compile(r"^要約すると\s*[、,:：]?\s*")
QUESTION_HEADING_RE = re.compile(r"(?m)^## .*[？?]\s*$")

SCHEMA = {
    "type": "OBJECT",
    "properties": {"easy_markdown": {"type": "STRING"}},
    "required": ["easy_markdown"],
}

SYSTEM = """あなたはニュースサイトの編集者です。記事の本文だけを材料に、専門用語を使わない「かんたんに読む」版を書きます。
事実は本文に書いてあることだけ。出力は指定の JSON だけ。"""

PROMPT = """# 記事の題名
{title}

# 記事の本文（これだけを材料にする）
<<<
{body}
>>>

# 書くもの: easy_markdown（記事ページの「かんたんに読む」版。忙しい社会人が1分で読む）
- 最初は「## ひとことで言うと」と、その下に1〜2文の要約。
- そのあとに章を2〜4個。章の役目は次の順（本文にその役目の事実が無い章は作らない。埋めない）:
  1. 何が変わるのか
  2. 自分は対象か（誰が当てはまるか・当てはまらないか）
  3. いつ・いくら（日付・金額・期限）
  4. やること（手続き・窓口・確かめ方。本文にあるものだけ）
- 読者がいちばん知りたい数字（本文の中心の金額・日付・期限を2〜4個）は、必ずどこかの章に入れる。数字の羅列にはしない。
- 見出しは役目の名前ではなく、その章の中身を短く言う言葉にする（例:「11月分の請求から値引きがなくなる」「低圧で契約している家庭が対象」）。
  「自分に関係ある？」のような決まった質問の見出し・「？」で終わる見出しは使わない。「｜」は使わない。
- 各章は2〜4文か、短い箇条書き（3〜5項目）。1文は40字くらいまで。表は使わない。
- 専門用語は使わない。どうしても要る言葉は、初めて出たところで（ ）で短く言い換える。
- 大人の読者向けの落ち着いたです・ます調。幼い言い方（「すごい」「〜しちゃう」「〜なんです」）・子ども向けの例え・「〜しましょう」の呼びかけは使わない。
- 事実・数字・日付・金額・電話番号・窓口や制度の名前は、上の本文に書いてあるものだけを、本文の表記どおりに使う。
  本文に無いことは書かない。自分で計算した数字（合計・差・年額など）も書かない。推測・一般論・つなぎの文で埋めない。
- 本文の文をそのまま写さず、短くやさしく言い直す。全体で本文より短く（目安 300〜700字）。リンクは使わない。{feedback}"""

FEEDBACK = """

# 前の案の問題（必ず直す）
{items}"""


def _strip_marks(text: str) -> str:
    return re.sub(r"[*_`]", "", text or "").strip()


def visible_easy(record: dict) -> str:
    """記事ページに出るかんたん版の中身（app/articles/[slug]/page.tsx と同じ順: 要約の書き出しを外す → 中身なしの章を除く →
    要点がある記事では要約の章を除く）"""
    easy = (record.get("easy") or "").strip()
    if not easy:
        return ""
    lines = easy.split("\n")
    i = next((k for k, l in enumerate(lines) if l.strip() and not l.strip().startswith("#")), -1)
    if i >= 0 and SUMMARY_OPENER_RE.match(lines[i].strip()):
        lines[i] = SUMMARY_OPENER_RE.sub("", lines[i].strip())
    titles = (record.get("sectionTitles") or {}).get("easy") if isinstance(record.get("sectionTitles"), dict) else None
    cleaned, _ = gate.clean_markdown("\n".join(lines), titles=titles if isinstance(titles, dict) else None)
    if not record.get("highlights"):
        return cleaned.strip()
    keep = []
    for head, content in gate.split_sections(cleaned):
        if head is not None and SUMMARY_HEADING_RE.match(_strip_marks(head)):
            continue
        keep.append(content.strip() if head is None else f"## {head}\n{content}".strip())
    return "\n\n".join(x for x in keep if x).strip()


def _plain(text: str) -> str:
    return re.sub(r"(?m)^#+ .*$|\s", "", text or "")


def thin(record: dict) -> bool:
    """「かんたんに読む」の切り替えが出ない・ほとんど中身が無い記事か（本文がある記事だけ）"""
    if len(_plain(record.get("body") or "")) < 300:
        return False
    return len(_plain(visible_easy(record))) < EASY_MIN_CHARS


def number_problems(easy: str, body: str) -> list[str]:
    """かんたん版の数字（日付・電話番号の数も）が、すべて本文にあるか（計算した数字も認めない）"""
    import calc_facts  # noqa: PLC0415

    allowed = calc_facts.values(body)
    missing = []
    for q in calc_facts.extract(easy):
        if not any(abs(q.value - v) <= 1e-9 * max(1.0, abs(v)) for v in allowed) and q.text not in missing:
            missing.append(q.text)
    if missing:
        return [f"本文に無い数字がある（{'、'.join('「' + m + '」' for m in missing[:6])}）。本文の数字だけを本文の表記で使い、計算しない"]
    return []


def shape_problems(easy: str, record: dict) -> list[str]:
    problems = []
    if not easy.startswith("## ひとことで言うと"):
        problems.append("最初を「## ひとことで言うと」にする")
    if "｜" in easy:
        problems.append("「｜」を使わない")
    if QUESTION_HEADING_RE.search(easy):
        problems.append("「？」で終わる見出しを使わない。章の中身を言う見出しにする")
    if "](" in easy or "|" in easy:
        problems.append("リンクと表は使わない")
    after = {**record, "easy": easy}
    shown = visible_easy(after)
    sections = [h for h, _ in gate.split_sections(shown) if h]
    if len(sections) < 2 or len(_plain(shown)) < EASY_MIN_CHARS:
        problems.append("要約のあとに、中身のある章を2つ以上書く（何が変わる／自分は対象か／いつ・いくら／やること）")
    if len(_plain(easy)) >= len(_plain(record.get("body") or "")):
        problems.append("本文より短く書く")
    problems += gate.style_problems({"body": "", "easy": easy})
    return problems


def check(record: dict, easy: str, *, facts: bool = True) -> tuple[list[str], dict]:
    """(問題のリスト, 事実確認の結果)。空なら使ってよい"""
    import quality  # noqa: PLC0415

    body = record.get("body") or ""
    problems = shape_problems(easy, record) + number_problems(easy, body)
    after = {**record, "easy": easy}
    problems += quality.added_problems(record, after)
    if problems or not facts:
        return problems, {}
    # 本文を元記事とみなし、かんたん版だけを確かめる（題名・リード・要点は入れない。本文に無い事実が無いかだけを見る）
    verdict = quality.fact_check({"title": "", "lede": "", "highlights": [], "body": "", "easy": easy}, body[:BODY_CAP])
    if not verdict.get("grounded") or verdict.get("fatal") or verdict.get("score", 0) < EASY_MIN_SCORE:
        problems.append(f"本文との事実確認で不合格（{verdict.get('score')}点）: " + " / ".join(verdict.get("problems") or [])[:400])
    return problems, verdict


def generate(record: dict, *, purpose: str | None = "helper", log=print) -> tuple[str | None, dict]:
    """(新しいかんたん版 or None, 報告)。例外は出さない"""
    import article_style  # noqa: PLC0415
    import llm  # noqa: PLC0415

    body = (record.get("body") or "").strip()
    report: dict = {"attempts": 0, "problems": [], "model": ""}
    problems: list[str] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        report["attempts"] = attempt
        feedback = FEEDBACK.format(items="\n".join(f"- {p}" for p in problems)) if problems else ""
        prompt = PROMPT.format(title=record.get("title") or "", body=body[:BODY_CAP], feedback=feedback)
        try:
            data, model = llm.generate_json(SYSTEM, prompt, SCHEMA, temperature=0.3, max_output_tokens=4096, tier="bulk", purpose=purpose)
        except Exception as error:  # noqa: BLE001 - LLM が使えなければ、記事はそのまま
            report["problems"] = [f"LLM が使えませんでした（{str(error)[:120]}）"]
            return None, report
        report["model"] = model
        easy = str(data.get("easy_markdown") or "").strip()
        easy = re.sub(r"\n{3,}", "\n\n", easy.replace("\r", ""))
        # 決まった言い回しの自動の手直し（ほかの段と同じ。scripts/article_style.py）
        try:
            fixed = {"easy": easy, "sourceName": record.get("sourceName") or ""}
            article_style.autofix(fixed)
            easy = (fixed.get("easy") or easy).strip()
        except Exception:  # noqa: BLE001 - 手直しが使えなくても、下の確かめは通す
            pass
        try:
            problems, verdict = check(record, easy)
        except Exception as error:  # noqa: BLE001 - 事実確認ができなければ使わない（緩める方向に倒さない）
            report["problems"] = [f"事実確認ができませんでした（{str(error)[:120]}）"]
            return None, report
        report["problems"] = problems
        if not problems:
            report["score"] = verdict.get("score")
            return easy + "\n", report
        log(f"   [easy] 試行{attempt}: {problems[0][:160]}")
    return None, report


def ensure(record: dict, *, purpose: str | None = "helper", log=print) -> str:
    """かんたん版が空になる記事なら作り直して record["easy"] に入れる。"skip" / "ok" / "fail: 理由"。例外は出さない"""
    try:
        if not thin(record):
            return "skip"
        easy, report = generate(record, purpose=purpose, log=log)
    except Exception as error:  # noqa: BLE001 - 公開を止めない
        return f"fail: {str(error)[:160]}"
    if easy is None:
        return "fail: " + " / ".join(report.get("problems") or [])[:300]
    record["easy"] = easy
    return f"ok（{report.get('model')}・{report.get('score')}点）"


def targets(args) -> list[Path]:
    if args.slug:
        return [ARTICLES_DIR / f"{s.strip()}.json" for s in args.slug.split(",") if s.strip()]
    paths = []
    for path in ARTICLES_DIR.glob("*.json"):
        try:
            record = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if args.muse and not record.get("museFile"):
            continue
        if thin(record):
            paths.append((str(record.get("publishedAt") or ""), path))
    return [p for _, p in sorted(paths, reverse=True)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", help="この記事だけ（カンマ区切り）")
    ap.add_argument("--muse", action="store_true", help="Muse の記事（museFile のある記事）だけ")
    ap.add_argument("--all", action="store_true", help="すべての記事")
    ap.add_argument("--list", action="store_true", help="空になる記事の一覧だけ（LLM なし）")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--purpose", default="helper", help="Claude API の段（helper = Haiku）。none で無料モデルだけ")
    args = ap.parse_args(argv)
    if not (args.slug or args.muse or args.all):
        ap.print_help()
        return 1
    paths = targets(args)
    if args.list:
        for p in paths:
            print(p.stem)
        print(f"{len(paths)}本", file=sys.stderr)
        return 0
    import llm  # noqa: PLC0415

    llm._load_env_local()  # noqa: SLF001 - 手元の実行用（CI は環境変数）
    purpose = None if args.purpose == "none" else args.purpose
    done = failed = 0
    for path in paths:
        record = json.loads(path.read_text("utf-8"))
        if not thin(record):
            print(f"[skip] {path.stem}: かんたん版に中身がある", flush=True)
            continue
        easy, report = generate(record, purpose=purpose)
        if easy is None:
            failed += 1
            print(f"[NG] {path.stem}: {' / '.join(report.get('problems') or [])[:240]}（記事はそのまま）", flush=True)
            time.sleep(2)
            continue
        print(f"[ok] {path.stem}: {len(_plain(easy))}字・{report.get('score')}点（{report.get('model')}）", flush=True)
        if not args.apply:
            print(easy)
            continue
        # 書き込む直前に読み直す（ほかの処理が同じ記事を直していたら見送る）
        latest = json.loads(path.read_text("utf-8"))
        if latest.get("body") != record.get("body") or latest.get("easy") != record.get("easy"):
            print(f"     {path.stem}: 処理中に本文が変わったので見送り", flush=True)
            continue
        latest["easy"] = easy
        path.write_text(json.dumps(latest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        done += 1
        if args.max and done >= args.max:
            break
    print(f"かんたん版: 作り直し {done}本 / 見送り {failed}本", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
