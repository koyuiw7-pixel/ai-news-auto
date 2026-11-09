"""X（@saisoku_ai）だけの投稿（Buffer 経由）。2026-11-06 オーナー承認・台帳 S42。2026-11-07（sns_plan.json の x.start）から

X は Threads の写しをやめ、X だけの上限・枠・話題・文面で出す。Threads の予定・速報・朝のまとめからは X に出さない
（threads_post.publish_extra_channels・sns_video_followup.publish_queued・morning_digest が x.start の日から X を外す）。

  枠: 日本時間 7:30・12:30・21:00 に1本ずつ・1日3本まで（sns_plan.json の x.daily_cap）。枠に遅れたら次の枠の前（最後は23時）まで出してよい。
      7時より前・23時より後は出さない。Threads の本数とは別に数え、お互いの本数に数えない。
  速報・ミサイル・災害の知らせ: 枠の外ですぐ出し、本数に数えない（台帳 S41）。速報のワークフローから --breaking-only で呼ぶ。
      ふつうの回でも、出てから30分たっても X に出ていない速報は拾う（深夜1〜5時は災害の知らせだけ）。
  話題（通常の枠）: 公式の地震・気象の知らせ → 通信・サービスの障害 → 製品・セール・値段 → 有名ブランド（sns_plan.x_topic）。
      決算の数字だけの記事は出さない（速報も）。製品の文（Switch 2 の販売台数など）があれば、その製品を1行目にして出す。
      海外の企業向け・開発者向け（S28）は今までどおり出さない。
  文面: 1行目は検索される言葉（地震・製品の名前・ブランドの名前）から始めて事実を言う。そのあと記事の事実の文を1〜2つ。
      問いかけは付けない。ハッシュタグは災害・大きな行事だけ1つまで。全角140字まで（X の数え方で280）。
      画像は記事のカード（今までどおり）。記事のリンクは返信に置く（utm_campaign=xpost・utm_content=card_reply）。
  2026-11-09 オーナー承認（台帳 S50）: X の投稿は全部、①画像を必ず付ける（Muse の説明の図 public/fig/<slug>-fig*.png・記事の figures が
      あればそれ、無ければ記事の本物の画像が載るカード。文字だけのカード・ロゴ・ほかの記事の画像は使わない＝ルール24）。画像の無い記事は
      飛ばして次の記事を選び、出せる記事が無ければその枠は出さない。②本文にリンクを置かず、すぐ後の自分への返信に「続き（◯◯）→ URL」
      （utm_source=x）。③ハッシュタグは、いまのトレンドの言葉（state/trend_signals.json）に当たる記事だけ1つ（sns_plan.x_trend_tag）。
      1日15本の枠はそのまま（1週間後に1本あたりの表示で見直す）。
  記録: state/x_posted.json（{slug: {id, at, kind=slot|breaking|alert, slot, title}}）。

  python3 scripts/x_post.py --dry-run [--breaking-only] [--slug SLUG]  # 文面を表示（Buffer を呼ばない）
  python3 scripts/x_post.py [--breaking-only]                          # THREADS_MODE=live のときだけ投稿（BUFFER_API_KEY）
  python3 scripts/x_post.py --merge FILE                               # 手元の記録を最新の state に足す
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bluesky_post as bp  # noqa: E402  記事の読み込み・同じ話題の判定・検索に出す記事の基準を同じものにする
import sns_plan  # noqa: E402
import sns_reader  # noqa: E402  2026-11-08 夜: Threads と同じ読者向けの書き方（ルール23）
import sns_rules  # noqa: E402
import threads_post as tp  # noqa: E402

STATE_PATH = tp.ROOT / "state" / "x_posted.json"
CAMPAIGN = sns_rules.X_CAMPAIGN
MORNING_HOURS = 12  # 朝の枠で使う記事の新しさ（生成から）
FILL_MIN_AGE_MIN = 15  # 生成直後はまだ公開前のことがある
CATCHUP_MIN_AGE_MIN = 30  # ふつうの回で拾う速報は、速報のワークフローが出し終えるのを待つ（同じ記事を同時に出さない）
SIMILAR_HOURS = 24  # この時間内に X に出した投稿と同じ話題の記事は使わない
MAX_BREAKING_PER_RUN = 2
FACT_LINES = 2  # 1行目のあとに置く事実の文の数（入る分だけ）
FIG_DIR = tp.ROOT / "public" / "fig"
FIG_NAME_RE = re.compile(r"-fig\d{1,2}\.(?:png|jpe?g|webp)$")
CARD_SIZE = (1600, 900)  # 門番に渡すカードの縦横（今までどおり）


def log(message: str) -> None:
    print(message, flush=True)


# ---- 記録 ----

def load(path: Path | None = None) -> dict:
    path = path or STATE_PATH
    try:
        data = json.loads(path.read_text("utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data: dict, path: Path | None = None) -> None:
    path = path or STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse(raw) -> datetime | None:
    try:
        when = datetime.fromisoformat(str(raw).replace("Z", "+00:00")) if raw else None
    except ValueError:
        return None
    return when if when is None or when.tzinfo else when.replace(tzinfo=timezone.utc)


def on_x(slug: str, xs: dict, posted: dict) -> bool:
    """この記事を X にもう出したか・前に失敗・見送りにしたか（x_posted と、2026-11-06 までの Threads の記録の channels.twitter）"""
    if slug in xs:
        return True
    entry = (posted or {}).get(slug) or {}
    return bool((entry.get("channels") or {}).get("twitter")) or bool(entry.get("ownerHold"))


def counted(xs: dict, start: datetime, end: datetime) -> int:
    """start〜end に出した X の通常の枠の投稿の数（速報・災害の知らせは数えない）"""
    return sum(1 for rec in xs.values() if isinstance(rec, dict) and rec.get("kind") == "slot" and rec.get("id")
               and (when := _parse(rec.get("at"))) and start <= when < end)


def _day_start(now: datetime) -> datetime:
    return now.astimezone(tp.JST).replace(hour=0, minute=0, second=0, microsecond=0)


def posted_today(xs: dict, now: datetime) -> int:
    """今日（日本時間）の上限に数える X の投稿の数（Threads の本数とは別。台帳 S42）"""
    start = _day_start(now)
    return counted(xs, start, start + timedelta(days=1))


def breaking_today(xs: dict, now: datetime) -> int:
    start = _day_start(now)
    return sum(1 for rec in xs.values() if isinstance(rec, dict) and rec.get("kind") in ("breaking", "alert") and rec.get("id")
               and (when := _parse(rec.get("at"))) and start <= when < start + timedelta(days=1))


# ---- 文面（sns_rules ルール20） ----

def alert(article: dict) -> bool:
    """急ぎの安全の知らせ（地震・津波・警報・ミサイル）。速報の深夜の止めも当てない"""
    return sns_rules.is_urgent(article) or sns_plan.cap_exempt(article)


def first_line(article: dict) -> str:
    """1行目: 検索される言葉から始まる事実（題名）。決算の記事は製品の文から"""
    kw = sns_plan.x_keyword(article)
    title = re.sub(r"^【速報】\s*", "", str(article.get("title") or article.get("seoTitle") or "").strip())
    if not kw or not title:
        return ""
    if sns_plan.finance_topic(article) and not article.get("disaster"):
        return sns_plan.product_sentence(article)
    if title.startswith(kw) or title.startswith(f"【{kw}"):
        return title
    if f"「{kw}」" in title:
        title = re.sub(r"[ 　、]{2,}", "　", title.replace(f"「{kw}」", "", 1)).strip(" 　、")
    return f"【{kw}】{title}"


def fact_candidates(article: dict) -> list[str]:
    if article.get("disaster"):
        # 地震・津波は気象庁のデータから作った決まった文面の2行目から（AI に書かせない）
        return [x.strip() for x in str(article.get("threadsPost") or "").splitlines()[1:] if x.strip()]
    found = sns_plan.article_sentences(article)
    if sns_plan.finance_topic(article):
        # 製品から始まる1行目のあとは、製品の話の文か題名（何の発表か）だけ（決算の数字だけの文を並べない）
        kw = sns_plan.x_keyword(article)
        found = [x for x in found if kw and kw in x] + [str(article.get("title") or "").strip()]
    return found


def _bigrams(text: str) -> set[str]:
    t = re.sub(r"[\s、。，．,.「」『』（）()・：:]", "", text)
    return {t[i:i + 2] for i in range(len(t) - 1)}


def adds_news(fact: str, lines: list[str], article: dict | None = None) -> bool:
    """前の行に無い中身が半分以上ある文か（同じ数字・同じ言葉のくり返しを並べない）"""
    mine = _bigrams(fact)
    seen = set().union(*(_bigrams(x) for x in lines)) if lines else set()
    if not mine or len(mine - seen) / len(mine) < 0.5:
        return False
    # 同じ大きな数字（7,029本など）と同じ主語をもう一度言う文は、言い直し
    big = {n for x in lines for n in re.findall(r"\d[\d,]{2,}", x)}
    subject = sns_plan.x_keyword(article) if article else ""
    return not (big & set(re.findall(r"\d[\d,]{2,}", fact)) and subject and subject in fact)


def usable_fact(line: str) -> bool:
    if len(line) < 10 or "？" in line or "?" in line:
        return False
    if sns_rules.HARD_WORDS.search(line) or sns_rules.SUMMARY_LEAD_RE.match(line) or sns_rules.LEAD_WORD_RE.match(line):
        return False
    return not sns_rules.EMOJI_RE.search(line)


def x_text(article: dict) -> str:
    """X だけの文面（リンクは返信なので入れない）。作れなければ \"\""""
    first = first_line(article)
    if not first or sns_rules.x_weight(first) > sns_rules.X_LIMIT - 20:
        return ""
    tag = sns_plan.x_hashtag(article)
    lines = [first]
    for fact in fact_candidates(article):
        if len(lines) > FACT_LINES:
            break
        if not usable_fact(fact) or not adds_news(fact, lines, article) or any(sns_rules.near_duplicate(fact, x) or tp.overlap(fact, x) >= 14 for x in lines):
            continue
        if not article.get("disaster") and fact != str(article.get("title") or "").strip() and not re.search(r"[。！!）)」]$", fact):
            fact += "。"  # 要点（文末の無い形）も文にそろえる
        if sns_rules.x_weight("\n".join([*lines, fact, tag]).strip()) <= sns_rules.X_LIMIT:
            lines.append(fact)
    if len(lines) < 2 and not article.get("disaster"):
        return ""  # 1行目だけでは事実が足りない
    return "\n".join([*lines, tag] if tag else lines)


def reply_link(article: dict) -> str:
    """返信の文（2026-11-09 台帳 S50: URL だけにせず「続き → URL」）"""
    url = tp.utm_link(f"{tp.site_url()}/articles/{article['slug']}", "x", CAMPAIGN, ptype="card", pos="reply")
    return f"続き → {url}"


# ---- 画像（2026-11-09 オーナー承認・台帳 S50。ルール24） ----

def _local_size(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image  # noqa: PLC0415

        with Image.open(path) as im:
            return im.size
    except Exception:  # noqa: BLE001
        return None


def figure_image(article: dict) -> tuple[str, tuple[int, int]] | None:
    """Muse の説明の図（記事の figures・public/fig/<slug>-fig*.png）のうち、この記事の名前で 16:9 のもの。(URL, 縦横) か None"""
    slug = str(article.get("slug") or "")
    if not slug:
        return None
    srcs = [str((f or {}).get("src") or "") for f in article.get("figures") or [] if isinstance(f, dict)]
    if FIG_DIR.is_dir():
        srcs += sorted(f"/fig/{p.name}" for p in FIG_DIR.glob(f"{slug}-fig*"))
    for src in dict.fromkeys(srcs):
        name = src.rsplit("/", 1)[-1]
        if not src.startswith("/fig/") or not name.startswith(f"{slug}-fig") or not FIG_NAME_RE.search(name):
            continue  # ほかの記事の図は使わない
        size = _local_size(FIG_DIR / name)
        if size and abs(size[0] / max(size[1], 1) - sns_rules.ASPECT) / sns_rules.ASPECT <= sns_rules.ASPECT_TOL:
            return f"{tp.site_url()}{src}", size
    return None


def x_image(article: dict) -> dict | None:
    """X の投稿に付ける画像 {"url", "width", "height", "note"}。Muse の図 → 記事の本物の画像が載るカード。どちらも無ければ None"""
    if fig := figure_image(article):
        return {"url": fig[0], "width": fig[1][0], "height": fig[1][1], "note": "Muse の説明の図", "from": "figure"}
    if sns_rules.photo_problem(article):
        return None  # 文字だけのカード・ロゴ・ほかの記事の画像しか無い（ルール24）
    return {"url": tp.card_url(article), "width": CARD_SIZE[0], "height": CARD_SIZE[1], "note": tp.card_photo_note(article), "from": "card"}


def gate_kind(article: dict) -> str:
    return "disaster" if article.get("disaster") else "xpost"


def compose_post(article: dict) -> dict:
    """X に出す文面 {"text", "reply", "kind", "style"}。2026-11-08 夜（ルール23）から、Threads の読者向けの文面（誰の話か・数字1つ・
    決め手は記事に）があればそれを X の長さに合わせて使い、返信は「続き（◯◯）→ URL」。無ければ今までの X の書き方（ルール20）。
    地震・津波の型は今までどおり"""
    if not article.get("disaster") and not alert(article):
        if got := sns_reader.x_post(article):
            return {"text": got["text"], "reply": got["reply"], "kind": "reader", "style": "reader"}
    return {"text": x_text(article), "reply": reply_link(article), "kind": gate_kind(article), "style": "classic"}


def build_input(article: dict, channel_id: str, text: str | None = None, post: dict | None = None) -> dict:
    """Buffer の createPost の入力（本文＋記事のカード、返信に記事のリンク）。いますぐ出す"""
    post = post or ({"text": text, "reply": reply_link(article)} if text is not None else compose_post(article))
    image = x_image(article) or {"url": tp.card_url(article)}  # 画像の無い記事は ok_for_x で外す（門番のルール24も止める）
    thread = [{"text": post["text"], "assets": [{"image": {"url": image["url"]}}]}, {"text": post["reply"], "assets": []}]
    return {"channelId": channel_id, "schedulingType": "automatic", "text": post["text"], "assets": [],
            "metadata": {"twitter": {"thread": thread}}, "mode": "shareNow"}


def problems(article: dict, text: str, post: dict | None = None) -> list[str]:
    """送る前の門番と同じ見方（Buffer・画像の大きさは見ない）"""
    post = post or {"text": text, "reply": reply_link(article), "kind": gate_kind(article)}
    image = x_image(article)
    if not image:
        return ["[ルール24] X に付ける記事に合う本物の画像が無い（Muse の図も、写真の載るカードも無い。台帳 S50）"]
    out = sns_rules.check_post("x", post["text"], [{"type": "image", "url": image["url"], "width": image["width"], "height": image["height"]}],
                               article, kind=post["kind"], reply_text=post["reply"])
    if sns_rules.links_in(post["text"]):
        out.append("[ルール1] X は本文にリンクを置かない（返信だけ。台帳 S50）")
    return out


# ---- 選び方 ----

def _recent_titles(xs: dict, now: datetime, by_slug: dict) -> list[str]:
    out = []
    for slug, rec in xs.items():
        when = _parse((rec or {}).get("at"))
        if when and now - when <= timedelta(hours=SIMILAR_HOURS):
            out.append((rec or {}).get("title") or (by_slug.get(slug) or {}).get("title") or "")
    return [t for t in out if t]


def breaking_fresh(article: dict, now: datetime) -> bool:
    """速報として出す時間の中か（出てから90分以内、深夜に作った速報は朝の分）"""
    made = _parse(article.get("generatedAt"))
    if not made or not (article.get("breaking") or alert(article)):
        return False
    return now - made <= timedelta(minutes=tp.BREAKING_MAX_AGE_MIN) or bool(article.get("breaking") and tp.queued_for_morning(article, now))


def ok_for_x(article: dict, xs: dict, posted: dict, recent: list[str]) -> bool:
    slug = article.get("slug") or ""
    if not slug or on_x(slug, xs, posted):
        return False
    if sns_plan.excluded(article) or sns_plan.x_earnings_only(article):
        return False  # 海外の企業向け・開発者向け（S28）・決算の数字だけ（S42）
    if not x_image(article):
        return False  # 画像の無い記事は飛ばして次の記事（台帳 S50。枠に出せる記事が無ければその枠は出さない）
    if any(bp.similar(article.get("title", ""), t) for t in recent):
        return False
    post = compose_post(article)
    return bool(post["text"]) and not problems(article, post["text"], post)


def breaking_targets(xs: dict, posted: dict, now: datetime, articles: list[dict], min_age_min: int = 0) -> list[dict]:
    """枠の外ですぐ出す速報・災害の知らせ（新しい順）。深夜1〜5時は災害の知らせだけ（速報は朝の分に回る）"""
    if breaking_today(xs, now) >= tp.BREAKING_PER_DAY:
        return []
    quiet = now.astimezone(tp.JST).hour in tp.BREAKING_QUIET_HOURS_JST
    by_slug = {a["slug"]: a for a in articles if a.get("slug")}
    recent = _recent_titles(xs, now, by_slug)
    out = []
    for article in articles:
        if not breaking_fresh(article, now) or (quiet and not alert(article)):
            continue
        made = _parse(article.get("generatedAt"))
        if now - made < timedelta(minutes=min_age_min):
            continue
        if ok_for_x(article, xs, posted, recent):
            out.append(article)
    out.sort(key=lambda a: a.get("generatedAt") or "", reverse=True)
    return out[:MAX_BREAKING_PER_RUN]


def candidates(xs: dict, posted: dict, now: datetime, since: datetime, articles: list[dict]) -> list[dict]:
    """通常の枠に出せる記事（いい順）: since 以降に作った検索に出す記事で、まだ X に出しておらず、X の話題の点数の高い順 → 新しい順。
    速報の時間の中の記事は速報として出すので入れない"""
    is_indexable, duplicate_slugs = bp._indexable_rule()
    dups = duplicate_slugs(articles)
    by_slug = {a["slug"]: a for a in articles if a.get("slug")}
    recent = _recent_titles(xs, now, by_slug)
    out = []
    for article in articles:
        made = _parse(article.get("generatedAt"))
        if not made or not since <= made <= now - timedelta(minutes=FILL_MIN_AGE_MIN) or breaking_fresh(article, now):
            continue
        if not is_indexable(article, dups) and not alert(article):
            continue
        if sns_plan.x_score(article) < 0 or not ok_for_x(article, xs, posted, recent):
            continue
        # 2026-11-08 夜 オーナー: 軸は暮らしの安全・お金・手続き（レーン＋手続きの言葉）。読者向けの文面がある記事を先に。同じなら X の話題の点数
        out.append(((sns_reader.rank_key(article, "x", made)[0], sns_plan.x_score(article), made), article))
    out.sort(key=lambda x: x[0], reverse=True)
    return [a for _, a in out]


def slot_pick(slot: tuple[int, datetime, datetime], xs: dict, posted: dict, now: datetime, articles: list[dict]) -> dict | None:
    """この枠に出す1本。朝の枠は夜のあいだの記事、昼の枠はその日の記事、夜の枠は昼の枠からの記事（無ければその日の記事）"""
    index, start, _ = slot
    if index == 0:
        ranges = [now - timedelta(hours=MORNING_HOURS)]
    elif index == 1:
        ranges = [_day_start(now), now - timedelta(hours=MORNING_HOURS)]
    else:
        previous = sns_plan.x_slot_window(start - timedelta(minutes=1))
        ranges = [previous[1] if previous else start, _day_start(now)]
    for since in ranges:
        if found := candidates(xs, posted, now, since, articles):
            return found[0]
    return None


def choose(xs: dict, posted: dict, now: datetime, articles: list[dict] | None = None, breaking_only: bool = False) -> list[tuple[dict, str]]:
    """この実行で出すもの [(記事, 種類)]。種類は breaking・alert（枠の外・本数に数えない）か slot（X の枠に1本・1日 x.daily_cap 本まで）"""
    articles = bp.load_articles() if articles is None else articles
    out = [(a, "alert" if alert(a) else "breaking")
           for a in breaking_targets(xs, posted, now, articles, 0 if breaking_only else CATCHUP_MIN_AGE_MIN)]
    if breaking_only:
        return out
    slot = sns_plan.x_slot_window(now)
    if not slot or posted_today(xs, now) >= sns_plan.x_daily_cap() or counted(xs, slot[1], slot[2]):
        return out
    taken = {a["slug"] for a, _ in out}
    pick = slot_pick(slot, xs, posted, now, [a for a in articles if a.get("slug") not in taken])
    return out + [(pick, "slot")] if pick else out


# ---- 投稿 ----

def page_live(article: dict) -> bool:
    import breaking_post  # noqa: PLC0415

    return breaking_post.is_ok(f"{tp.site_url()}/articles/{article['slug']}", image=False) and breaking_post.is_ok(tp.card_url(article), image=True)


def send(api_key: str, channel_id: str, article: dict, slot_at: datetime | None, breaking: bool, post: dict | None = None) -> str:
    """Buffer に1件作る（tp.create_post が門番・同じ記事の確かめを通す）。いますぐが通らなければ1分後の予約"""
    import buffer_budget  # noqa: PLC0415

    post = post or compose_post(article)
    post_input = build_input(article, channel_id, post=post)
    with buffer_budget.priority(sns_plan.slot_priority(slot_at, article, breaking=breaking)):
        try:
            return tp.create_post(api_key, dict(post_input), service="twitter", article=article, source="x_post", kind=post["kind"])
        except sns_rules.SnsRuleViolation:
            raise
        except RuntimeError as error:
            if tp.is_buffer_unavailable(error):
                raise
            log(f"  [x] いますぐの投稿が通らないため、1分後の予約にします: {error}")
            post_input.update({"mode": "customScheduled", "dueAt": tp.utc_z(datetime.now(timezone.utc) + timedelta(minutes=1))})
            return tp.create_post(api_key, post_input, service="twitter", article=article, source="x_post", kind=post["kind"])


def merge(mine_path: str) -> int:
    """手元の記録を最新の state/x_posted.json に足す（和集合。既にあるものは変えない）"""
    mine = load(Path(mine_path))
    data = load()
    added = 0
    for slug, rec in mine.items():
        if slug not in data:
            data[slug] = rec
            added += 1
    if added or not STATE_PATH.exists():
        save(data)
    log(f"[x] 記録に {added} 件を足しました")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--breaking-only", action="store_true", help="速報・災害の知らせだけ（速報のワークフローから）")
    parser.add_argument("--slug", default="", help="確認用: この記事の X の文面を表示（--dry-run と一緒に）")
    parser.add_argument("--merge", default="")
    args = parser.parse_args()
    if args.merge:
        return merge(args.merge)
    now = datetime.now(timezone.utc)
    live = os.environ.get("THREADS_MODE") == "live" and not args.dry_run and not args.slug
    if live and not sns_plan.x_on(now):
        log(f"[x] X だけの枠は {sns_plan.x_plan().get('start')} から（それまでは今までどおり Threads の予定から出る）")
        return 0
    sns_plan.use_x_trends()  # トレンドの言葉に当たる記事だけタグを1つ（台帳 S50）
    xs = load()
    posted = tp.load_state()
    flat = dict(posted.get("posted") or {})
    articles = bp.load_articles()
    if args.slug:
        todo = [(next(a for a in articles if a.get("slug") == args.slug), "sample")]
    else:
        todo = choose(xs, flat, now, articles, breaking_only=args.breaking_only)
        log(f"[x] 今日 {posted_today(xs, now)}/{sns_plan.x_daily_cap()} 本（速報 {breaking_today(xs, now)} 本は数えない）")
        if not todo and not live and not args.breaking_only:
            todo = [(a, "sample") for a in candidates(xs, flat, now, now - timedelta(hours=24), articles)[:1]]
    if not todo:
        log("[x] 出すものはありません（上限・枠・対象なし）")
        return 0
    key = os.environ.get("BUFFER_API_KEY", "").strip()
    channel_id = ""
    if live:
        if not key:
            log("[x] BUFFER_API_KEY が無いため投稿できません")
            return 0
        channel = tp.buffer_channels(key).get("twitter")
        if not channel:
            log("[x] Buffer に X のチャンネルが見つかりません")
            return 0
        channel_id = channel["id"]
    summary = [f"### X の投稿 {'（投稿）' if live else '（下書き・未投稿）'}", ""]
    for article, kind in todo:
        slug = article["slug"]
        post = compose_post(article)
        text = post["text"]
        slot = sns_plan.x_slot_window(now) if kind == "slot" else None
        image = x_image(article) or {"url": "（無し）", "note": "画像が無いので出さない"}
        log(f"--- {slug} ({kind}・{post['style']}・話題 {sns_plan.x_topic(article)[0] or '-'}・{sns_rules.x_weight(text)}/{sns_rules.X_LIMIT})\n{text}\n[返信] {post['reply']}\n[画像] {image['url']}（{image['note']}）")
        summary += [f"**{slug}** ({kind}・{post['style']})", "", "```", text, "---", post["reply"], "```", f"画像: {image['url']}", ""]
        if not live:
            for problem in problems(article, text, post):
                log(f"  [check] {problem}")
            continue
        if kind in ("breaking", "alert") and not page_live(article):
            log(f"  [x] {slug}: 記事かカードがまだ開けません。次の回にもう一度")
            continue
        try:
            post_id = send(key, channel_id, article, slot[1] if slot else None, breaking=kind != "slot", post=post)
        except sns_rules.SnsRuleViolation as error:
            xs[slug] = {"failed": "rule", "violations": list(error.violations)[:5], "title": article.get("title", ""), "kind": kind}
            continue
        except Exception as error:  # noqa: BLE001
            if tp.is_buffer_unavailable(error):
                log(f"  [x] Buffer の上限のため次の回に: {str(error)[:160]}")
                break
            log(f"  [x] {slug} 失敗: {error}")
            xs[slug] = {"failed": str(error)[:200], "title": article.get("title", ""), "kind": kind}
            continue
        xs[slug] = {"id": post_id, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "kind": kind,
                    "slot": slot[1].strftime("%H:%M") if slot else "", "title": article.get("title", ""),
                    "topic": sns_plan.x_topic(article)[0], "style": post["style"]}
        log(f"  [x] {slug} ({kind}): {post_id}")
    tp.write_summary(summary)
    if live:
        save(xs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
