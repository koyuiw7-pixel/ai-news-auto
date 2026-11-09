#!/usr/bin/env python3
"""X・Bluesky・Facebook の読者向けの書き方（2026-11-08 夜 オーナー承認・sns_rules ルール23）。

Threads の新しい書き方（scripts/threads_reader.py・ルール22）は 11/8 に8本で90人をサイトに連れてきた（X・Facebook・Bluesky は0人）。
そこで3つの SNS も同じ文面（state/threads_reader.json に残した Threads の文面＝オーナーが見た下書きと同じ）を使い回し、
SNS ごとの長さ・リンクの置き場所だけ合わせる。

  X:        本文（全角140字まで・リンク無し）＋記事のカード。返信に「続き（◯◯）→ URL」（今までどおり返信。utm_source=x・reader_reply）
            入らなければ「誰の話か＋数字の入った事実1文＋記事にしかないもの」に縮める。タグは災害・大きな行事だけ1つまで
  Bluesky:  本文＋「続き（◯◯）→ URL」の行（リンクカードつき・300字まで・utm_source=bluesky・reader_body）。タグは1つまで（災害・安全は無し）
  Facebook: Threads の本文そのまま＋「続き（◯◯）→ URL」の行（リンクカードか動画・utm_source=facebook・reader_body）。タグは付けない

各 SNS の投稿の処理（x_post・bluesky_post・facebook_post）は LLM を使わない。文面はここで state から読むだけ。
文面がまだ無い記事は、記事の自動処理（auto_run.yml の Post to Threads。LLM の鍵がある回）が `--prepare` で先に作っておく
（threads_reader.compose で作り、同じ state/threads_reader.json に下書きとして残す＝あとで Threads に出すときも同じ文面）。
文面が無い・SNS の決まりに合わない記事は、今までの SNS ごとの書き方で出す（投稿の本数は落とさない）。

選ぶ順番（3つの SNS とも）: 暮らしの安全・お金・手続き（sns_plan のレーン safety・money ＋手続きの言葉）→ 読者向けの文面がある → 新しさ。

  python3 scripts/sns_reader.py --show <slug>     # 3つの SNS の文面を表示（投稿しない）
  python3 scripts/sns_reader.py --prepare [--max 3]  # これから出す記事の文面を作っておく（LLM。記事の自動処理の回から）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sns_plan  # noqa: E402
import sns_rules  # noqa: E402
import threads_reader  # noqa: E402

SITE = threads_reader.SITE
PLATFORMS = ("x", "bluesky", "facebook")
UTM_CONTENT = {"x": sns_rules.READER_UTM_CONTENT, "bluesky": sns_rules.READER_BODY_UTM_CONTENT, "facebook": sns_rules.READER_BODY_UTM_CONTENT}
# 手続き・お金・暮らしの安全の言葉（レーンの点数に足す。2026-11-08 夜 オーナー「軸は暮らしの安全・お金・手続き」）
PROCEDURE_RE = re.compile(r"手続き|申請|届け出|届出|期限|締め切り|対象|確認方法|切り替え|更新|給付|控除|還付|納付|保険料|年金|支給|値上げ|料金|流出|不正|詐欺|注意")
PROCEDURE_BONUS = 1.5
READY_BONUS = 1.0  # 読者向けの文面がもうある記事を、同じくらいの点数なら先に
PREPARE_HOURS = 24
PREPARE_MAX = 3
PREPARE_RETRY_HOURS = 6
FAILED_KEY = "snsPrepareFailed"


def log(message: str) -> None:
    print(message, flush=True)


# ---- 文面 ----

def pair(article: dict, state: dict | None = None) -> dict | None:
    """state/threads_reader.json に残した、この記事の読者向けの文面（無ければ None。LLM は使わない）"""
    state = state if state is not None else threads_reader.load_state()
    rec = (state.get("posts") or {}).get(str(article.get("slug") or ""))
    if rec and rec.get("main") and rec.get("label") and rec.get("version") == threads_reader.VERSION \
            and not sns_rules.reader_field_leak(rec["main"]):
        return rec  # 部品の名前（closing など）が混ざった下書きは使わない（11/9）
    return None


def link(slug: str, platform: str) -> str:
    q = urllib.parse.urlencode({"utm_source": platform, "utm_medium": "social", "utm_campaign": slug, "utm_content": UTM_CONTENT[platform]})
    return f"{SITE}/articles/{slug}?{q}"


def label_of(rec: dict) -> str:
    return re.sub(r"[（）()\s]", "", str(rec.get("label") or "")).strip("。、")


def link_line(rec: dict, url: str) -> str:
    return f"続き（{label_of(rec)}）→ {url}"


def blocks(main: str) -> tuple[str, list[str], str]:
    """(1行目＝誰の話か, 事実の文, 最後の文＝記事にしかないもの)"""
    lines = [x.strip() for x in str(main or "").splitlines() if x.strip()]
    if len(lines) < 3:
        return (lines[0] if lines else ""), lines[1:], ""
    return lines[0], lines[1:-1], lines[-1]


def short_main(main: str) -> str:
    """誰の話か＋数字の入った事実1文＋記事にしかないもの（X・Bluesky の字数に入らないとき）"""
    who, facts, closing = blocks(main)
    with_number = [f for f in facts if sns_rules.reader_numbers(f)]
    if not who or not closing or not with_number:
        return ""
    return f"{who}\n\n{with_number[0]}\n\n{closing}"


def variants(main: str) -> list[str]:
    out = [str(main or "").strip()]
    if (s := short_main(main)) and s not in out:
        out.append(s)
    return [v for v in out if v]


def x_post(article: dict, state: dict | None = None) -> dict | None:
    """X の文面 {"text", "reply", "label"}（本文にリンク無し・返信に「続き（◯◯）→ URL」）。使えなければ None"""
    rec = pair(article, state)
    if not rec:
        return None
    reply = link_line(rec, link(article["slug"], "x"))
    tag = sns_plan.x_hashtag(article)
    for main in variants(rec["main"]):
        for text in ([f"{main}\n{tag}", main] if tag else [main]):
            if sns_rules.x_weight(text) > sns_rules.X_LIMIT:
                continue
            if not sns_rules.check_reader_post("x", text, reply, article):
                return {"text": text, "reply": reply, "label": label_of(rec)}
    return None


def bluesky_tag(article: dict) -> str:
    try:
        import bluesky_post as bp  # noqa: PLC0415

        return bp.brief_hashtag(article)
    except Exception:  # noqa: BLE001
        return ""


def bluesky_post(article: dict, state: dict | None = None) -> dict | None:
    """Bluesky の文面 {"main", "lead", "tag", "link", "text"}。text は投稿の本文そのもの（リンクの表示は短い形）。使えなければ None"""
    rec = pair(article, state)
    if not rec:
        return None
    url = link(article["slug"], "bluesky")
    shown = re.sub(r"^https?://|\?.*$", "", url)
    lead = f"続き（{label_of(rec)}）→"
    tag = bluesky_tag(article)
    for main in variants(rec["main"]):
        for t in ([tag, ""] if tag else [""]):
            text = f"{main}\n\n{lead} {shown}" + (f"\n{t}" if t else "")
            if len(text) > sns_rules.LIMITS["bluesky"]:
                continue
            if not sns_rules.check_reader_post("bluesky", text, "", article, links=[url]):
                return {"main": main, "lead": lead, "tag": t, "link": url, "shown": shown, "text": text, "label": label_of(rec)}
    return None


def facebook_post(article: dict, state: dict | None = None) -> dict | None:
    """Facebook の文面 {"text", "link"}（Threads の本文そのもの＋最後の行に「続き（◯◯）→ URL」）。使えなければ None"""
    rec = pair(article, state)
    if not rec:
        return None
    url = link(article["slug"], "facebook")
    text = f"{str(rec['main']).strip()}\n\n{link_line(rec, url)}"
    if len(text) > sns_rules.LIMITS["facebook"] or sns_rules.check_reader_post("facebook", text, "", article):
        return None
    return {"text": text, "link": url, "label": label_of(rec)}


COMPOSERS = {"x": x_post, "bluesky": bluesky_post, "facebook": facebook_post}


def ready(article: dict, platform: str, state: dict | None = None) -> bool:
    try:
        return COMPOSERS[platform](article, state) is not None
    except Exception:  # noqa: BLE001
        return False


# ---- 選ぶ順番 ----

def daily_score(article: dict) -> float:
    """暮らしの安全・お金・手続き（レーンの点数＋手続きの言葉）。SNS に出さない記事は -100"""
    score = sns_plan.sns_score(article)
    if score < 0:
        return score
    text = f"{article.get('title') or ''} {article.get('description') or ''}"
    if sns_plan.has_lane(article) and PROCEDURE_RE.search(text):
        score += PROCEDURE_BONUS
    return score


def rank_key(article: dict, platform: str, made, state: dict | None = None) -> tuple:
    return (daily_score(article) + (READY_BONUS if ready(article, platform, state) else 0.0), made)


# ---- 下書きを先に作る（記事の自動処理の回・LLM） ----

def _parse(raw) -> datetime | None:
    try:
        when = datetime.fromisoformat(str(raw).replace("Z", "+00:00")) if raw else None
    except ValueError:
        return None
    return when if when is None or when.tzinfo else when.replace(tzinfo=timezone.utc)


def _posted_everywhere(slug: str) -> bool:
    import x_post as xp  # noqa: PLC0415
    import facebook_post as fp  # noqa: PLC0415
    import bluesky_post as bp  # noqa: PLC0415

    return slug in xp.load() and slug in fp.load() and slug in bp.load_extra()


def prepare_targets(now: datetime, articles: list[dict], state: dict, hours: int = PREPARE_HOURS) -> list[dict]:
    """これから X・Bluesky・Facebook に出しそうな記事で、読者向けの文面がまだ無いもの（点数の高い順）"""
    import bluesky_post as bp  # noqa: PLC0415

    is_indexable, duplicate_slugs = bp._indexable_rule()
    dups = duplicate_slugs(articles)
    failed = state.get(FAILED_KEY) or {}
    out = []
    for article in articles:
        made = _parse(article.get("generatedAt"))
        slug = article.get("slug") or ""
        if not slug or not made or now - made > timedelta(hours=hours) or article.get("disaster") or sns_rules.is_urgent(article):
            continue
        if pair(article, state) or not is_indexable(article, dups) or daily_score(article) <= 0:
            continue
        if (when := _parse(failed.get(slug))) and now - when < timedelta(hours=PREPARE_RETRY_HOURS):
            continue
        if _posted_everywhere(slug):
            continue
        out.append(((daily_score(article), made), article))
    out.sort(key=lambda x: x[0], reverse=True)
    return [a for _, a in out]


def prepare(max_new: int = PREPARE_MAX, now: datetime | None = None, articles: list[dict] | None = None, generate=None) -> int:
    """読者向けの文面を max_new 本まで作って state/threads_reader.json に下書きとして残す（Threads に出すときも同じ文面）"""
    import bluesky_post as bp  # noqa: PLC0415

    now = now or datetime.now(timezone.utc)
    articles = bp.load_articles() if articles is None else articles
    state = threads_reader.load_state()
    made = 0
    for article in prepare_targets(now, articles, state)[: max(0, max_new) * 2]:
        if made >= max_new:
            break
        try:
            rec = threads_reader.compose(article, state=state, generate=generate)
        except threads_reader.ReaderNotReady as error:
            log(f"[sns-reader] {article['slug']}: 文面を作れませんでした（{str(error)[:120]}）。今までの書き方で出します")
            state.setdefault(FAILED_KEY, {})[article["slug"]] = now.isoformat(timespec="seconds")
            threads_reader.save_state(state)
            continue
        threads_reader.remember(article, rec, state=state)
        made += 1
        log(f"[sns-reader] {article['slug']}: 文面を作りました\n{rec['main']}\n--- {rec['reply']}")
    log(f"[sns-reader] 新しく作った文面 {made} 本")
    return made


def show(slug: str) -> None:
    article = json.loads((threads_reader.ARTICLES_DIR / f"{slug}.json").read_text("utf-8"))
    for platform in PLATFORMS:
        got = COMPOSERS[platform](article)
        print(f"=== {platform}")
        if not got:
            print("（読者向けの文面なし・決まりに合わない → 今までの書き方）")
        elif platform == "x":
            print(f"{got['text']}\n--- 返信\n{got['reply']}\n（{sns_rules.x_weight(got['text'])}/{sns_rules.X_LIMIT}）")
        elif platform == "bluesky":
            print(f"{got['text']}\n（{len(got['text'])}/300・リンク先 {got['link']}）")
        else:
            print(got["text"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--show", nargs="+", metavar="SLUG")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--max", type=int, default=PREPARE_MAX)
    args = parser.parse_args()
    if args.show:
        for slug in args.show:
            show(slug)
        return 0
    if args.prepare:
        prepare(args.max)
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
