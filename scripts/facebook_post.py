"""Facebook ページ「サイソクニュース」だけの投稿（Buffer 経由）。2026-11-06 オーナー承認・台帳 S43。2026-11-07（sns_plan.json の facebook.start）から

Facebook は Threads の写しをやめ、Facebook だけの上限・枠・文面で出す。Threads の予定・速報からは Facebook に出さない
（threads_post.publish_extra_channels・sns_video_followup.publish_queued が facebook.start の日から Facebook を外す）。

  枠: 日本時間 7:30（朝の要の1本）・12:30（暮らしの話題＝家計・値上げ・暮らし・制度）・20:00（その日いちばん強い記事）に1本ずつ・
      1日3本まで（sns_plan.json の facebook.daily_cap）。枠に遅れたら次の枠の前（最後は23時）まで出してよい。7時より前・23時より後は出さない。
      Threads・X の本数とは別に数え、お互いの本数に数えない。
  速報・ミサイル・災害の知らせ: 枠の外ですぐ出し、本数に数えない（台帳 S41）。速報のワークフローから --breaking-only で呼ぶ。
  話題: SNS のレーン（sns_plan.sns_score）。海外の企業向け・開発者向け（S28）は出さない。決算・株の話題は1日 finance.cap 本まで（S39）。
  文面: 1行目＝数字の入った事実、2行目＝家計や暮らしにどう響くか（どちらも記事の文そのもの＝lede・やさしい版・要点／workMoney・verdict.take）。
      入れば3行目にもう1つの事実。問いかけは付けない（門番は暮らしの話題だけ許す。災害・安全には付けない＝S35）。
      記事のリンクは本文の最後（utm_campaign=fbpost）。写真のときはリンクカード（記事のカード）、承認された SNS 動画（qa_ok）があれば動画を
      直接（Buffer の assets の video。リンクカードと動画は同時に付けられないので、リンクは本文だけ）。
  記録: state/facebook_posted.json（{slug: {id, at, kind=slot|breaking|alert, slot, title, media}}）。
  計測: Facebook からの訪問は日本からの訪問と UTM だけで数える（米国・スウェーデン・アイルランドの facebook の参照は Meta のリンクの読み取り）。

  python3 scripts/facebook_post.py --dry-run [--breaking-only] [--slug SLUG]  # 文面を表示（Buffer を呼ばない）
  python3 scripts/facebook_post.py [--breaking-only]                          # THREADS_MODE=live のときだけ投稿（BUFFER_API_KEY）
  python3 scripts/facebook_post.py --merge FILE                               # 手元の記録を最新の state に足す
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bluesky_post as bp  # noqa: E402
import sns_plan  # noqa: E402
import sns_rules  # noqa: E402
import threads_post as tp  # noqa: E402
import x_post as xp  # noqa: E402  記録の数え方・速報の判定は X と同じもの

STATE_PATH = tp.ROOT / "state" / "facebook_posted.json"
CAMPAIGN = sns_rules.FB_CAMPAIGN
MORNING_HOURS = 12
FILL_MIN_AGE_MIN = 15
CATCHUP_MIN_AGE_MIN = 30
SIMILAR_HOURS = 24
MAX_BREAKING_PER_RUN = 2
LIFESTYLE_BONUS = 10.0  # 12:30 の枠で暮らしの話題を先に
# 2行目に向く文（読者の家計・暮らし・手続きの話）
LIFE_HINT = re.compile(r"家計|暮らし|生活|毎月|料金|支払|負担|節約|受け取|もらえ|使え|できます|確認|申請|手続き|人は|方は|世帯|家庭|対象|選択肢|比べ")
LOW_IMPACT_RE = re.compile(r"影響は(?:小さ|限定|あまりな|ほぼな)")


def log(message: str) -> None:
    print(message, flush=True)


def load(path: Path | None = None) -> dict:
    return xp.load(path or STATE_PATH)


def save(data: dict, path: Path | None = None) -> None:
    xp.save(data, path or STATE_PATH)


def on_fb(slug: str, fs: dict, posted: dict) -> bool:
    """この記事を Facebook にもう出したか・前に失敗・見送りにしたか（facebook_posted と、2026-11-06 までの Threads の記録の channels.facebook）"""
    if slug in fs:
        return True
    entry = (posted or {}).get(slug) or {}
    return bool((entry.get("channels") or {}).get("facebook")) or bool(entry.get("ownerHold"))


def posted_today(fs: dict, now: datetime) -> int:
    """今日（日本時間）の上限に数える Facebook の投稿の数（Threads・X の本数とは別。台帳 S43）"""
    return xp.posted_today(fs, now)


def finance_today(fs: dict, now: datetime, by_slug: dict) -> int:
    start = xp._day_start(now)
    return sum(1 for slug, rec in fs.items() if isinstance(rec, dict) and rec.get("id") and (when := xp._parse(rec.get("at")))
               and start <= when < start + timedelta(days=1) and sns_plan.finance_topic(by_slug.get(slug) or {"title": rec.get("title", "")}))


# ---- 文面（sns_rules ルール21） ----

def _ok_line(line: str) -> bool:
    return not sns_rules.brief_line_problems(line)  # やさしい です・ます・問いかけなし・110字まで・硬い言葉なし


def fb_lines(article: dict) -> list[str]:
    """(1行目＝数字の入った事実, 2行目＝暮らしにどう響くか, [3行目＝もう1つの事実])。どれも記事の文そのもの。作れなければ []"""
    if article.get("disaster"):
        # 地震・津波は気象庁のデータから作った決まった文面（AI に書かせない）
        return [x.strip() for x in str(article.get("threadsPost") or "").splitlines() if x.strip()]
    sentences = sns_plan.article_sentences(article)
    facts = [x for x in sentences if re.search(r"[0-9０-９]", x) and len(x) >= 15 and _ok_line(x)]
    impacts, weak = [], []
    sources = [*((article.get("workMoney") or {}).get("points") or []), (article.get("verdict") or {}).get("take"), *sentences]
    for src in sources:
        for x in sns_plan._sentences(src):
            if len(x) < 12 or not _ok_line(x) or x in impacts or x in weak:
                continue
            (impacts if LIFE_HINT.search(x) and not LOW_IMPACT_RE.search(x) else weak).append(x)
    for fact in facts:
        for impact in impacts:
            if sns_rules.near_duplicate(fact, impact) or not xp.adds_news(impact, [fact], article):
                continue
            lines = [fact, impact]
            extra = next((x for x in facts if x not in lines and not any(sns_rules.near_duplicate(x, y) for y in lines)
                          and xp.adds_news(x, lines, article)), "")
            return lines + ([extra] if extra else [])
    return []


def fb_text(article: dict) -> str:
    return "\n".join(fb_lines(article))


def article_link(article: dict, video: bool) -> str:
    return tp.utm_link(f"{tp.site_url()}/articles/{article['slug']}", "facebook", CAMPAIGN, ptype="video" if video else "card", pos="body")


def video_for(article: dict) -> dict:
    """承認された SNS 動画（sns_video_followup.qa_ok に通った版）。無ければ {}。急ぎの安全の知らせは動画を待たない・付けない"""
    if sns_rules.is_urgent(article):
        return {}
    try:
        return bp.video_of(article["slug"])
    except Exception:  # noqa: BLE001 - 動画の記録が読めなければ写真のカードで出す
        return {}


def gate_kind(article: dict) -> str:
    return "disaster" if article.get("disaster") else "fbpost"


def build_input(article: dict, channel_id: str, video: dict | None = None) -> dict:
    """Buffer の createPost の入力。本文の最後に記事のリンク。動画があれば動画を直接（assets）、無ければリンクカード（記事のカード）"""
    video = video or {}
    link = article_link(article, bool(video))
    text = f"{fb_text(article)}\n\n{link}"
    meta: dict = {"facebook": {"type": "post"}}
    assets: list[dict] = []
    if video.get("url"):
        assets = [{"video": {"url": video["url"]}}]  # 動画を直接（リンクカードとは同時に付けられない。リンクは本文）
    else:
        meta["facebook"]["linkAttachment"] = {"url": link, "title": article.get("seoTitle") or article["title"],
                                              "description": str(article.get("description") or "")[:120],
                                              "thumbnail": {"url": tp.card_url(article)}}
    return {"channelId": channel_id, "schedulingType": "automatic", "text": text, "assets": assets, "metadata": meta, "mode": "shareNow"}


def problems(article: dict, video: dict | None = None) -> list[str]:
    """送る前の門番と同じ見方（Buffer・画像の大きさは見ない）"""
    inp = build_input(article, "check", video)
    text, _reply, media, links = sns_rules.buffer_parts("facebook", inp)
    media = [{**m, "width": 1920, "height": 1080} for m in media] or [{"type": "video", "url": (video or {}).get("url", ""), "width": 1920, "height": 1080}]
    return sns_rules.check_post("facebook", text, media, article, kind=gate_kind(article), links=links)


# ---- 選び方 ----

def _recent_titles(fs: dict, now: datetime, by_slug: dict) -> list[str]:
    out = []
    for slug, rec in fs.items():
        when = xp._parse((rec or {}).get("at"))
        if when and now - when <= timedelta(hours=SIMILAR_HOURS):
            out.append((rec or {}).get("title") or (by_slug.get(slug) or {}).get("title") or "")
    return [t for t in out if t]


def ok_for_fb(article: dict, fs: dict, posted: dict, recent: list[str]) -> bool:
    slug = article.get("slug") or ""
    if not slug or on_fb(slug, fs, posted) or sns_plan.excluded(article):
        return False
    if any(bp.similar(article.get("title", ""), t) for t in recent):
        return False
    return bool(fb_lines(article)) and not problems(article)


def breaking_targets(fs: dict, posted: dict, now: datetime, articles: list[dict], min_age_min: int = 0) -> list[dict]:
    """枠の外ですぐ出す速報・災害の知らせ（新しい順）。深夜1〜5時は災害の知らせだけ。決算・株の話題は1日 finance.cap 本まで（S39）"""
    if xp.breaking_today(fs, now) >= tp.BREAKING_PER_DAY:
        return []
    quiet = now.astimezone(tp.JST).hour in tp.BREAKING_QUIET_HOURS_JST
    by_slug = {a["slug"]: a for a in articles if a.get("slug")}
    recent = _recent_titles(fs, now, by_slug)
    fin = finance_today(fs, now, by_slug)
    out = []
    for article in sorted(articles, key=lambda a: a.get("generatedAt") or "", reverse=True):
        if not xp.breaking_fresh(article, now) or (quiet and not xp.alert(article)):
            continue
        if now - xp._parse(article.get("generatedAt")) < timedelta(minutes=min_age_min):
            continue
        if sns_plan.finance_topic(article):
            if fin >= sns_plan.finance_cap():
                continue
        if ok_for_fb(article, fs, posted, recent):
            out.append(article)
            fin += sns_plan.finance_topic(article)
    return out[:MAX_BREAKING_PER_RUN]


def candidates(fs: dict, posted: dict, now: datetime, since: datetime, articles: list[dict], lifestyle: bool = False) -> list[dict]:
    """通常の枠に出せる記事（いい順）: since 以降に作った検索に出す記事で、まだ Facebook に出しておらず、SNS の点数の高い順 → 新しい順。
    lifestyle（12:30 の枠）なら暮らしの話題を先に。速報の時間の中の記事は速報として出すので入れない"""
    is_indexable, duplicate_slugs = bp._indexable_rule()
    dups = duplicate_slugs(articles)
    by_slug = {a["slug"]: a for a in articles if a.get("slug")}
    recent = _recent_titles(fs, now, by_slug)
    finance_full = finance_today(fs, now, by_slug) >= sns_plan.finance_cap()
    out = []
    for article in articles:
        made = xp._parse(article.get("generatedAt"))
        if not made or not since <= made <= now - timedelta(minutes=FILL_MIN_AGE_MIN) or xp.breaking_fresh(article, now):
            continue
        if not is_indexable(article, dups) and not xp.alert(article):
            continue
        if (finance_full and sns_plan.finance_topic(article)) or not ok_for_fb(article, fs, posted, recent):
            continue
        score = sns_plan.sns_score(article) + (LIFESTYLE_BONUS if lifestyle and sns_plan.fb_lifestyle(article) else 0.0)
        out.append(((score, made), article))
    out.sort(key=lambda x: x[0], reverse=True)
    return [a for _, a in out]


def slot_pick(slot: tuple[int, datetime, datetime], fs: dict, posted: dict, now: datetime, articles: list[dict]) -> dict | None:
    """この枠に出す1本。7:30＝夜のあいだのいちばん、12:30＝その日の暮らしの話題（無ければその日のいちばん）、20:00＝その日いちばん強い記事"""
    index, _start, _ = slot
    lifestyle = index == int(sns_plan.fb_plan().get("lifestyle_slot", 1))
    if index == 0:
        ranges = [now - timedelta(hours=MORNING_HOURS)]
    else:
        ranges = [xp._day_start(now), now - timedelta(hours=MORNING_HOURS)]
    for since in ranges:
        if found := candidates(fs, posted, now, since, articles, lifestyle=lifestyle):
            return found[0]
    return None


def choose(fs: dict, posted: dict, now: datetime, articles: list[dict] | None = None, breaking_only: bool = False) -> list[tuple[dict, str]]:
    """この実行で出すもの [(記事, 種類)]。種類は breaking・alert（枠の外・本数に数えない）か slot（Facebook の枠に1本・1日 facebook.daily_cap 本まで）"""
    articles = bp.load_articles() if articles is None else articles
    out = [(a, "alert" if xp.alert(a) else "breaking")
           for a in breaking_targets(fs, posted, now, articles, 0 if breaking_only else CATCHUP_MIN_AGE_MIN)]
    if breaking_only:
        return out
    slot = sns_plan.fb_slot_window(now)
    if not slot or posted_today(fs, now) >= sns_plan.fb_daily_cap() or xp.counted(fs, slot[1], slot[2]):
        return out
    taken = {a["slug"] for a, _ in out}
    pick = slot_pick(slot, fs, posted, now, [a for a in articles if a.get("slug") not in taken])
    return out + [(pick, "slot")] if pick else out


# ---- 投稿 ----

def send(api_key: str, channel_id: str, article: dict, video: dict, slot_at: datetime | None, breaking: bool) -> str:
    """Buffer に1件作る（tp.create_post が門番・同じ記事の確かめを通す）。いますぐが通らなければ1分後の予約"""
    import buffer_budget  # noqa: PLC0415

    post_input = build_input(article, channel_id, video)
    with buffer_budget.priority(sns_plan.slot_priority(slot_at, article, breaking=breaking)):
        try:
            return tp.create_post(api_key, dict(post_input), service="facebook", article=article, source="facebook_post", kind=gate_kind(article))
        except sns_rules.SnsRuleViolation:
            raise
        except RuntimeError as error:
            if tp.is_buffer_unavailable(error):
                raise
            log(f"  [facebook] いますぐの投稿が通らないため、1分後の予約にします: {error}")
            post_input.update({"mode": "customScheduled", "dueAt": tp.utc_z(datetime.now(timezone.utc) + timedelta(minutes=1))})
            return tp.create_post(api_key, post_input, service="facebook", article=article, source="facebook_post", kind=gate_kind(article))


def merge(mine_path: str) -> int:
    """手元の記録を最新の state/facebook_posted.json に足す（和集合。既にあるものは変えない）"""
    mine = load(Path(mine_path))
    data = load()
    added = 0
    for slug, rec in mine.items():
        if slug not in data:
            data[slug] = rec
            added += 1
    if added or not STATE_PATH.exists():
        save(data)
    log(f"[facebook] 記録に {added} 件を足しました")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--breaking-only", action="store_true", help="速報・災害の知らせだけ（速報のワークフローから）")
    parser.add_argument("--slug", default="", help="確認用: この記事の Facebook の文面を表示（--dry-run と一緒に）")
    parser.add_argument("--merge", default="")
    args = parser.parse_args()
    if args.merge:
        return merge(args.merge)
    now = datetime.now(timezone.utc)
    live = os.environ.get("THREADS_MODE") == "live" and not args.dry_run and not args.slug
    if live and not sns_plan.fb_on(now):
        log(f"[facebook] Facebook だけの枠は {sns_plan.fb_plan().get('start')} から（それまでは今までどおり Threads の予定から出る）")
        return 0
    fs = load()
    posted = dict(tp.load_state().get("posted") or {})
    articles = bp.load_articles()
    if args.slug:
        todo = [(next(a for a in articles if a.get("slug") == args.slug), "sample")]
    else:
        todo = choose(fs, posted, now, articles, breaking_only=args.breaking_only)
        log(f"[facebook] 今日 {posted_today(fs, now)}/{sns_plan.fb_daily_cap()} 本（速報 {xp.breaking_today(fs, now)} 本は数えない）")
        if not todo and not live and not args.breaking_only:
            todo = [(a, "sample") for a in candidates(fs, posted, now, now - timedelta(hours=24), articles)[:1]]
    if not todo:
        log("[facebook] 出すものはありません（上限・枠・対象なし）")
        return 0
    key = os.environ.get("BUFFER_API_KEY", "").strip()
    channel_id = ""
    if live:
        if not key:
            log("[facebook] BUFFER_API_KEY が無いため投稿できません")
            return 0
        channel = tp.buffer_channels(key).get("facebook")
        if not channel:
            log("[facebook] Buffer に Facebook のチャンネルが見つかりません")
            return 0
        channel_id = channel["id"]
    summary = [f"### Facebook の投稿 {'（投稿）' if live else '（下書き・未投稿）'}", ""]
    for article, kind in todo:
        slug = article["slug"]
        video = video_for(article)
        inp = build_input(article, channel_id or "check", video)
        media = f"動画（{video.get('variant')}）" if video else "リンクカード"
        log(f"--- {slug} ({kind}・{media}・{len(inp['text'])}字)\n{inp['text']}")
        summary += [f"**{slug}** ({kind}・{media})", "", "```", inp["text"], "```", ""]
        if not live:
            for problem in problems(article, video):
                log(f"  [check] {problem}")
            continue
        if kind in ("breaking", "alert") and not xp.page_live(article):
            log(f"  [facebook] {slug}: 記事かカードがまだ開けません。次の回にもう一度")
            continue
        slot = sns_plan.fb_slot_window(now) if kind == "slot" else None
        try:
            post_id = send(key, channel_id, article, video, slot[1] if slot else None, breaking=kind != "slot")
        except sns_rules.SnsRuleViolation as error:
            fs[slug] = {"failed": "rule", "violations": list(error.violations)[:5], "title": article.get("title", ""), "kind": kind}
            continue
        except Exception as error:  # noqa: BLE001
            if tp.is_buffer_unavailable(error):
                log(f"  [facebook] Buffer の上限のため次の回に: {str(error)[:160]}")
                break
            log(f"  [facebook] {slug} 失敗: {error}")
            fs[slug] = {"failed": str(error)[:200], "title": article.get("title", ""), "kind": kind}
            continue
        fs[slug] = {"id": post_id, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "kind": kind,
                    "slot": slot[1].strftime("%H:%M") if slot else "", "title": article.get("title", ""),
                    "media": "video" if video else "card", **({"variant": video.get("variant")} if video else {})}
        log(f"  [facebook] {slug} ({kind}): {post_id}")
    tp.write_summary(summary)
    if live:
        save(fs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
