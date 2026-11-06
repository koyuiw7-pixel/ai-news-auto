#!/usr/bin/env python3
"""SNS の伸ばし方の計画を1か所で持つ（2026-11-05 とろいも案 v1。台帳 S27〜S31）。設定は scripts/sns_plan.json。

すべての投稿の経路（threads_post・breaking_post・bluesky_post・morning_digest・sns_video_followup・門番 sns_rules）が
ここを読む。経路ごとに別の決まりを書かない（O13）。

  lane_of(article)        → (レーン名, 点数)。safety（障害・流出・安全）> money（お金・制度・政府）> brand（有名ブランド）> consumer_ai
  excluded(article)       → SNS に出さない理由（海外の企業向け・開発者向け。サイトには載せる）。出してよければ ""
  sns_score(article)      → 並べ順の点数（レーン＋ Muse の動画待ち）
  slots_jst()             → 通常の投稿の時刻 [(時, 分), ...]
  daily_cap() / cap_exempt(article_or_entry)  → 1日の上限と、上限に数えない種類（ミサイル・災害）
  bluesky_daily_cap() / bluesky_slot_window(now) → Bluesky だけの1日3本と枠 7:30・13:00・21:00（Threads と別に数える。S40）
  x_on() / x_daily_cap() / x_slot_window(now) / x_topic / x_earnings_only / x_keyword / x_hashtag → X だけの1日3本と枠 7:30・12:30・21:00・話題・文面（S42）
  fb_on() / fb_daily_cap() / fb_slot_window(now) / fb_lifestyle → Facebook だけの1日3本と枠 7:30・12:30・20:00・暮らしの話題（S43）
  count_today(posted, day, extra) → その日（日本時間）に出した（予約した）自分の投稿の数
  utm_content(ptype, pos) → "video_body" など
  hook_format_on()  → 2026-11-05 オーナー承認でワークフローの既定は on（変数で 0 にすれば止まる）
  link_ab_on()      → 2026-11-05 夕方に終了（常に False。交互の比べはしない。S31）
  threads_link_position() → 変数 THREADS_LINK_POS（reply / body。空なら body）。2026-11-06 テストの日から（S39）
  finance_topic(article)  → 決算・株・業績・配当・自社株買い・TOB の話題か（Threads は1日 finance_cap 本まで。S39）
  slot_priority(slot, article)  → Buffer の30日の上限が近いときにまだ作る投稿か
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN_PATH = Path(__file__).resolve().parent / "sns_plan.json"
MUSE_QUEUE = ROOT / "state" / "muse_queue.json"
JST = timezone(timedelta(hours=9))


@lru_cache(maxsize=1)
def plan() -> dict:
    return json.loads(PLAN_PATH.read_text("utf-8"))


@lru_cache(maxsize=None)
def _re(pattern: str) -> re.Pattern:
    return re.compile(pattern)


def _text(article: dict) -> str:
    tags = " ".join(str(t) for t in (article.get("tags") or []) if t)
    return f"{article.get('title', '')} {article.get('seoTitle', '')} {tags}"


def _host(article: dict) -> str:
    url = str(article.get("sourceUrl") or "")
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return ""
    return parts.netloc.lower().split(":")[0]


def japanese_source(article: dict) -> bool:
    """出どころが日本の会社・官公庁のサイト（ドメインが .jp）。海外の会社の日本語のページ（/jp/）は海外として扱う"""
    host = _host(article)
    if not host:
        return False
    if _re(plan()["exclude"]["japan_host_re"]).search(host):
        return True
    return any(host == h or host.endswith("." + h) for h in plan()["exclude"].get("japan_hosts") or [])


def lanes(article: dict) -> list[tuple[str, int]]:
    """当たるレーン（点数の高い順）"""
    text = _text(article)
    out = []
    for name, lane in plan()["lanes"].items():
        if not _re(lane["re"]).search(text):
            continue
        if lane.get("needs_re") and not _re(lane["needs_re"]).search(f"{text} {article.get('lede', '')}"):
            continue
        out.append((name, int(lane["score"])))
    return sorted(out, key=lambda x: -x[1])


def lane_of(article: dict) -> tuple[str, int]:
    found = lanes(article)
    return found[0] if found else ("", 0)


def excluded(article: dict | None) -> str:
    """SNS に出さない理由（海外の企業向け・開発者向けの話題）。出してよければ ""。
    災害・ミサイル・急ぎの安全の知らせ（disaster / urgent / safetyAlert）は外さない。
    掃除で取り下げたあと書き直して同じ URL に戻した記事（restoredAt。2026-11-06 台帳 A46）は新着ではないので出さない"""
    if article and article.get("restoredAt"):
        return "取り下げたあと書き直して戻した記事（新着ではない。台帳 A46）は SNS に出さない（サイトだけ）"
    if not article or article.get("disaster") or article.get("urgent") or article.get("safetyAlert"):
        return ""
    if article.get("kind") == "digest" or article.get("items"):
        return ""
    ex = plan()["exclude"]
    text = _text(article)
    audience = str((article.get("verdict") or {}).get("audience") or "")
    hit = _re(ex["text_re"]).search(text)
    aud = _re(ex["audience_re"]).search(audience) if audience else None
    if not (hit or aud):
        return ""
    if not aud and japanese_source(article):
        return ""  # 日本の会社・官公庁の発表は外さない（日本の読者に関係する）。読者が開発者・IT 担当の記事は日本の発表でも外す
    if not aud and lane_of(article)[0] == "safety":
        return ""  # 一般の人が使うサービスの障害・流出は外さない
    why = f"「{hit.group(0)}」" if hit else f"読者が「{audience}」"
    return f"海外の企業向け・開発者向けの話題（{why}）は SNS に出さない（サイトだけ）"


def muse_slugs(now: datetime | None = None) -> set[str]:
    """Muse に頼んで、まだ待っている記事と、Muse の動画が届いた記事（state/muse_queue.json）。
    2026-11-05 オーナー判断「動画は全投稿を Muse に任せる」: 届いた動画がある記事を先に出す（queued だけだと、届いた途端に順位が下がっていた）"""
    data = load_muse_queue()
    return {i["slug"] for i in data.get("items", []) if i.get("status") in ("queued", "delivered")}


def sns_score(article: dict) -> float:
    """SNS に出す順番の点数。レーン → Muse に頼んだ記事 → 新しさは呼ぶ側で"""
    if excluded(article):
        return -100.0
    score = float(lane_of(article)[1])
    if article.get("slug") in muse_slugs():
        score += 2.0
    if japanese_source(article):
        score += 0.5  # 同じレーンなら日本の会社・官公庁の発表を先に（2026-11-06。海外の企業向けの料金の話が18:45の1番手になっていた）
    return score


def has_lane(article: dict) -> bool:
    return bool(lane_of(article)[0])


# ---- 枠と1日の上限 ----

def _hm(value: str) -> tuple[int, int]:
    h, m = value.split(":")
    return int(h), int(m)


def slots_jst() -> list[tuple[int, int]]:
    return sorted(_hm(s) for s in plan()["slots_jst"])


def digest_slot_jst() -> tuple[int, int]:
    return _hm(plan().get("digest_slot_jst") or plan()["slots_jst"][0])


def daily_cap() -> int:
    raw = os.environ.get("SNS_DAILY_CAP", "").strip()
    cap = int(raw) if raw.isdigit() else int(plan()["daily_cap"])
    return max(0, min(cap, int(plan()["daily_cap"])))  # 変数で減らすことはできるが、計画より増やさない


# ---- Bluesky だけの枠と上限（2026-11-06 オーナー承認・台帳 S40。Threads の daily_cap・slots_jst とは別に数える） ----

def bluesky_plan() -> dict:
    return plan().get("bluesky") or {}


def bluesky_slots_jst() -> list[tuple[int, int]]:
    return sorted(_hm(s) for s in bluesky_plan().get("slots_jst") or [])


def bluesky_daily_cap() -> int:
    """Bluesky の1日（日本時間）の上限。変数 BLUESKY_PER_DAY で減らすことはできるが、計画より増やさない"""
    cap = int(bluesky_plan().get("daily_cap") or 0)
    raw = os.environ.get("BLUESKY_PER_DAY", "").strip()
    return max(0, min(int(raw), cap)) if raw.isdigit() else cap


def bluesky_slot_window(now: datetime) -> tuple[int, datetime, datetime] | None:
    """今の時刻が入る Bluesky の枠（番号, 始まり, 終わり）。枠は次の枠の前まで、最後の枠は window_end まで。
    朝の最初の枠の前・window_start より前・window_end より後は None（出さない）"""
    return _slot_window(bluesky_plan(), now)


def _slot_window(block: dict, now: datetime) -> tuple[int, datetime, datetime] | None:
    """SNS ごとの枠（block の slots_jst・window_start・window_end）で、今の時刻が入る枠（番号, 始まり, 終わり）。外なら None"""
    local = now.astimezone(JST)
    day = local.replace(hour=0, minute=0, second=0, microsecond=0)
    at = lambda hm: day + timedelta(hours=hm[0], minutes=hm[1])  # noqa: E731
    first = at(_hm(block.get("window_start") or "07:00"))
    last = at(_hm(block.get("window_end") or "23:00"))
    starts = [max(first, at(hm)) for hm in sorted(_hm(x) for x in block.get("slots_jst") or [])]
    for i, start in enumerate(starts):
        end = min(starts[i + 1] if i + 1 < len(starts) else last, last)
        if start <= local < end:
            return i, start, end
    return None


# ---- X だけの枠・上限・話題（2026-11-06 オーナー承認・台帳 S42。2026-11-07 から。Threads の daily_cap・slots_jst とは別に数える） ----

def x_plan() -> dict:
    return plan().get("x") or {}


def _started(block: dict, when: datetime | None) -> bool:
    start = str(block.get("start") or "")
    if not start:
        return False
    when = when or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(JST).date() >= date.fromisoformat(start)


def x_on(when: datetime | None = None) -> bool:
    """X だけの枠で出す日か（sns_plan.json の x.start の日から）。この日からは X の投稿は scripts/x_post.py だけが出す
    （Threads の予定・速報・朝のまとめからは X に出さない）"""
    return _started(x_plan(), when)


def x_slots_jst() -> list[tuple[int, int]]:
    return sorted(_hm(s) for s in x_plan().get("slots_jst") or [])


def x_daily_cap() -> int:
    """X の1日（日本時間）の通常の投稿の上限。変数 X_PER_DAY で減らすことはできるが、計画より増やさない"""
    cap = int(x_plan().get("daily_cap") or 0)
    raw = os.environ.get("X_PER_DAY", "").strip()
    return max(0, min(int(raw), cap)) if raw.isdigit() else cap


def x_slot_window(now: datetime) -> tuple[int, datetime, datetime] | None:
    """今の時刻が入る X の枠（番号, 始まり, 終わり）。7:30・12:30・21:00。7時より前・23時より後・最初の枠の前は None"""
    return _slot_window(x_plan(), now)


def _alert(article: dict) -> bool:
    return bool(article.get("disaster") or article.get("urgent") or article.get("safetyAlert") or cap_exempt(article))


def x_topic(article: dict) -> tuple[str, int]:
    """X の通常の枠での話題（名前, 点数）。公式の地震・気象の知らせ > 障害 > 製品・セール・値段 > 有名ブランド。当たらなければ ("", 0)"""
    text = _text(article)
    found = {name for name, _ in lanes(article)}
    for topic in x_plan().get("topics") or []:
        if topic.get("flags") and _alert(article):
            return topic["name"], int(topic["score"])
        if topic.get("re") and _re(topic["re"]).search(text):
            return topic["name"], int(topic["score"])
        if topic.get("lanes") and found & set(topic["lanes"]):
            return topic["name"], int(topic["score"])
    return "", 0


def x_score(article: dict) -> float:
    """X の枠で選ぶ順の点数（話題＋レーン）。SNS に出さない話題・決算の数字だけの記事は -100"""
    if excluded(article) or x_earnings_only(article):
        return -100.0
    return float(x_topic(article)[1] + lane_of(article)[1])


_SENTENCE = re.compile(r"[^。！!]+[。！!]?")


def _sentences(text) -> list[str]:
    return [m.group(0).strip() for m in _SENTENCE.finditer(str(text or "").replace("\n", "")) if m.group(0).strip()]


def article_sentences(article: dict) -> list[str]:
    """記事の事実の文（lede → やさしい版の書き出し → 要点 → 説明の順）。X・Facebook の文面はここからそのまま選ぶ"""
    easy = re.search(r"##\s*ひとことで言うと\s*\n+([^\n#]+)", str(article.get("easy") or ""))
    srcs = [article.get("lede"), easy.group(1) if easy else "", *(article.get("highlights") or []), article.get("description")]
    out: list[str] = []
    for src in srcs:
        for x in _sentences(src):
            if x not in out:
                out.append(x)
    return out


def product_sentence(article: dict) -> str:
    """製品の名前（x.product_re）から始まる記事の文（Switch 2 の販売台数など）。無ければ """""
    pat = x_plan().get("product_re")
    if not pat:
        return ""
    return next((x for x in article_sentences(article) if _re(f"^(?:{pat})").match(x)), "")


def x_earnings_only(article: dict | None) -> bool:
    """決算の数字だけの記事か（X には出さない。2026-11-06 オーナー承認・台帳 S42）。決算・株の話題（finance.re）で、
    有名な製品から始まる文（Switch 2 の販売台数など）が無いもの。製品の文があれば、その製品を1行目にして出してよい"""
    article = article or {}
    return finance_topic(article) and not product_sentence(article)


_LEAD = re.compile(r"^(?:【[^】]{1,12}】)?\s*")


def x_keyword(article: dict) -> str:
    """X の1行目の頭に置く、検索される言葉（地震・震度・製品の名前・ブランドの名前）"""
    title = str(article.get("title") or article.get("seoTitle") or "").strip()
    if _alert(article):
        m = re.match(r"【([^】]{1,12})】", title)
        if m and m.group(1) != "速報":
            return m.group(1)
        for pattern, _tag in x_plan().get("alert_tags") or []:
            if m := _re(pattern).search(title):
                return m.group(0)
    if finance_topic(article) and (sent := product_sentence(article)):
        return _re(f"^(?:{x_plan()['product_re']})").match(sent).group(0).strip()
    body = _LEAD.sub("", title)
    pats = [x_plan().get("product_re") or "", plan()["lanes"]["brand"]["re"], plan()["lanes"]["money"]["re"]]
    # 「」の中の製品名（「Galaxy Buds On」など）を先に
    for name in re.findall(r"「([^」]{2,30})」", body):
        if any(p and _re(p).search(name) for p in pats):
            return name.strip()
    best = None
    for p in pats:
        for m in _re(p).finditer(body) if p else []:
            key = (m.start(), -len(m.group(0)))
            if best is None or key < best[0]:
                best = (key, m.group(0))
            break
    if best:
        return best[1].strip()
    # 当たらなければ題名の頭の主語（「横浜ゴムの…」の横浜ゴム）
    m = re.match(r"^([^、　：:「（(｜|\s]{2,12}?)(?:の|が|は|に|と|で|、|　|：|:)", body)
    return m.group(1) if m else ""


def x_starts_with_keyword(first: str, article: dict) -> bool:
    """X の1行目が検索される言葉から始まっているか（【】で囲んだ形も可）"""
    head = re.sub(r"^【([^】]{1,30})】", r"\1", str(first or "").strip())
    keys = [x_keyword(article), *[str(t) for t in article.get("tags") or [] if len(str(t)) >= 2]]
    if any(k and head.startswith(k) for k in keys):
        return True
    pats = [x_plan().get("product_re") or "", plan()["lanes"]["brand"]["re"], plan()["lanes"]["money"]["re"]]
    return any(p and _re(f"^(?:{p})").match(head) for p in pats)


def x_hashtag(article: dict | None) -> str:
    """X のハッシュタグ（1つまで）。災害の知らせ（#地震 など）と大きな行事（WBC など）だけ。ほかは付けない"""
    article = article or {}
    text = _text(article)
    if _alert(article):
        for pattern, tag in x_plan().get("alert_tags") or []:
            if _re(pattern).search(text):
                return tag
        return ""
    ev = x_plan().get("event_re")
    if ev and (m := _re(ev).search(str(article.get("title") or ""))):
        return "#" + m.group(0)
    return ""


# ---- Facebook だけの枠・上限・文面（2026-11-06 オーナー承認・台帳 S43。2026-11-07 から。Threads・X とは別に数える） ----

def fb_plan() -> dict:
    return plan().get("facebook") or {}


def fb_on(when: datetime | None = None) -> bool:
    """Facebook だけの枠で出す日か（sns_plan.json の facebook.start の日から）。この日からは Facebook の投稿は
    scripts/facebook_post.py だけが出す（Threads の予定・速報からは Facebook に出さない）"""
    return _started(fb_plan(), when)


def fb_slots_jst() -> list[tuple[int, int]]:
    return sorted(_hm(s) for s in fb_plan().get("slots_jst") or [])


def fb_daily_cap() -> int:
    """Facebook の1日（日本時間）の通常の投稿の上限。変数 FACEBOOK_PER_DAY で減らすことはできるが、計画より増やさない"""
    cap = int(fb_plan().get("daily_cap") or 0)
    raw = os.environ.get("FACEBOOK_PER_DAY", "").strip()
    return max(0, min(int(raw), cap)) if raw.isdigit() else cap


def fb_slot_window(now: datetime) -> tuple[int, datetime, datetime] | None:
    """今の時刻が入る Facebook の枠（番号, 始まり, 終わり）。7:30・12:30・20:00。7時より前・23時より後・最初の枠の前は None"""
    return _slot_window(fb_plan(), now)


def fb_lifestyle(article: dict | None) -> bool:
    """暮らしの話題か（家計・値上げ・暮らし・制度。12:30 の枠で先に選ぶ・問いかけを付けてよい）。災害・ミサイルの知らせは当たらない"""
    article = article or {}
    if _alert(article) or article.get("items"):
        return False
    pat = fb_plan().get("lifestyle_re")
    return bool(pat) and bool(_re(pat).search(f"{_text(article)} {article.get('lede', '')}"))


def min_gap() -> timedelta:
    return timedelta(minutes=int(plan()["min_gap_min"]))


def cap_exempt(record: dict | None) -> bool:
    """1日の上限に数えない（ミサイル・災害の知らせ）。記事でも投稿の記録でもよい"""
    record = record or {}
    if record.get("disaster") or record.get("missile") or record.get("hook") == "disaster":
        return True
    kind = str(record.get("publicInterest") or record.get("publicInterestKind") or "")
    if not kind and record.get("title"):
        import public_interest  # noqa: PLC0415 - 記事の題名からミサイル・災害かを見る（同じ判定を1か所で）

        kind = public_interest.category(str(record.get("title") or "")) or ""
    return kind in plan()["cap_exempt"]


def breaking_exempt(record: dict | None) -> bool:
    """速報は1日の上限に数えない（2026-11-06 12:4x オーナー決定「速報は本数に関係なく出す」・台帳 S41）。
    速報かどうかの判定（公式の発表・出てから90分以内など）と、同じ話題を2回出さない・決算の上限（S39）はそのまま"""
    return bool((record or {}).get("breaking"))


def _when(rec: dict) -> datetime | None:
    for key in ("dueAt", "postedAt", "sentAt"):
        raw = rec.get(key)
        if not raw:
            continue
        try:
            when = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            continue
        return when if when.tzinfo else when.replace(tzinfo=timezone.utc)
    pending = (rec.get("pending") or {}).get("slot")
    if pending:
        try:
            return datetime.fromisoformat(pending)
        except ValueError:
            return None
    return None


def count_today(posted: dict, day: date, skipped: set[str] | None = None) -> int:
    """その日（日本時間）に出した・予約した自分の投稿の数（Threads の記録。X・Facebook は 2026-11-07 から別に数える＝S42・S43）。
    動画が作れず出さなかったもの（skipped）とミサイル・災害・速報は数えない"""
    skipped = skipped or set()
    n = 0
    for slug, rec in (posted or {}).items():
        if slug in skipped or cap_exempt(rec) or breaking_exempt(rec):
            continue
        if not (rec.get("id") or rec.get("status") == "awaiting_video" or rec.get("style") == "digest"):
            continue
        when = _when(rec)
        if when and when.astimezone(JST).date() == day:
            n += 1
    return n


def video_skipped(path: Path | None = None) -> set[str]:
    """動画が作れず出さなかった記事（state/sns_video.json の queued が skipped）。1日の上限に数えない"""
    path = path or ROOT / "state" / "sns_video.json"
    try:
        data = json.loads(path.read_text("utf-8"))
    except (FileNotFoundError, ValueError):
        return set()
    return {k for k, v in (data.get("queued") or {}).items() if (v or {}).get("status") == "skipped"}


def cap_left(posted: dict, day: date, skipped: set[str] | None = None) -> int:
    return max(0, daily_cap() - count_today(posted, day, skipped))


def slot_priority(slot: datetime | None, article: dict | None = None, breaking: bool = False) -> str:
    """Buffer の30日の上限が近いときにまだ作る投稿か（"high"）。速報・safety/money の記事・優先の枠（plan の priority）"""
    pr = plan().get("priority") or {}
    if breaking or (article or {}).get("breaking"):
        return "high"
    if article and lane_of(article)[0] in (pr.get("lanes") or []):
        return "high"
    if slot is not None:
        hm = slot.astimezone(JST).strftime("%H:%M")
        if hm in (pr.get("slots_jst") or []):
            return "high"
    return "normal"


# ---- UTM ----

def utm_content(ptype: str, pos: str) -> str:
    u = plan()["utm"]
    ptype = ptype if ptype in u["types"] else "video"
    pos = pos if pos in u["positions"] else "body"
    return f"{ptype}_{pos}"


UTM_CONTENT_RE = re.compile(r"^(?:video|hook|card|digest)_(?:body|reply)$")


# ---- 文面の形・リンクの位置（2026-11-05 オーナー承認。ワークフローの既定は 1。環境変数が無い手元・テストでは off） ----

def _flag(name: str) -> bool:
    return os.environ.get(name, "0").strip().lower() in ("1", "on", "true", "yes")


def hook_format_on() -> bool:
    """Muse の型の文面（1行目＝結論＋数字・2行目＝なぜ大事か・3行目＝記事にだけあるもの）。S1 を変えるのでオーナー承認まで off"""
    return _flag("SNS_HOOK_FORMAT")


def link_ab_on() -> bool:
    """Threads のリンクの位置の比べ（S31）。**2026-11-05 夕方 オーナー決定「すべて本文にリンクにしよう今後は」で終了**。
    変数 THREADS_LINK_AB が何であっても常に False（リンクは本文だけ。返信には置かない）"""
    return False


def link_ab_window() -> dict:
    """リンクの位置の比べの記録（2026-11-05 に終了。decided=body）"""
    return dict(plan().get("link_ab") or {})


def link_ab_reminder(now: datetime | None = None) -> str:
    """比べは終わった（decided=body）。いつも "" """
    return ""


THREADS_LINK_POSITIONS = ("reply", "body")


def threads_link_position(posted: dict | None = None) -> str:
    """Threads の記事のリンクの位置（"reply" か "body"）。リポジトリの変数 THREADS_LINK_POS（ワークフローが env に渡す）で決める。
    2026-11-06 オーナー承認のテストの日（台帳 S39「外してもいいよ。…明日はそういったテストをして分析をする日にするんだね」）から、
    11/5 の「リンクは本文だけ」（S31）を一時的に外せる。reply＝本文はリンク無し＋返信1件に記事のリンク（11/3 より前の形）、
    body＝本文の最後にリンク。空・それ以外の値なら body（11/5 の決まりに戻る）。通常の投稿・動画・速報・朝のまとめ・門番・出る前の読み直しが
    すべてここを読む（O13）"""
    raw = os.environ.get("THREADS_LINK_POS", "").strip().lower()
    return raw if raw in THREADS_LINK_POSITIONS else "body"


# ---- Muse の受け渡しの記録 ----

def load_muse_queue(path: Path | None = None) -> dict:
    path = path or MUSE_QUEUE
    try:
        return json.loads(path.read_text("utf-8"))
    except (FileNotFoundError, ValueError):
        return {"items": []}


def muse_item(slug: str, data: dict | None = None) -> dict:
    data = data if data is not None else load_muse_queue()
    return next((i for i in data.get("items", []) if i.get("slug") == slug), {})


def video_wait_hours() -> float:
    """動画を作る記事の投稿が動画を待つ時間（枠から）。2026-11-05 夕方 オーナー決定「動画を待たない」「動画を作る記事を限定」で短く
    （sns_plan.json の muse.wait_hours。変数 MUSE_WAIT_HOURS でも max_wait_hours より長くはできない）"""
    m = plan()["muse"]
    raw = os.environ.get("MUSE_WAIT_HOURS", "").strip()
    try:
        hours = float(raw) if raw else float(m["wait_hours"])
    except ValueError:
        hours = float(m["wait_hours"])
    return max(0.0, min(hours, float(m.get("max_wait_hours", m["wait_hours"]))))


def video_post(slug: str, data: dict | None = None) -> bool:
    """この記事の投稿は動画で出す投稿か（2026-11-05 夕方 オーナー決定・台帳 S13）。
    動画を作るのは、ビューを取れる話題の限られた記事だけ＝ Muse に頼んだ記事（state/muse_queue.json。muse_queue.pick が
    1日 muse.max_per_day 本まで・点数（レーン＋数字＋公式）の高い順に選ぶ）。それ以外の投稿は動画を作らず、記事の写真・カードで枠の時刻に出す"""
    item = muse_item(slug, data)
    if item.get("status") == "delivered":
        return True  # Muse の動画がもう届いている
    # 2026-11-05 夕方より前に「すべての投稿を Muse で」で入れた項目（点数 0）は動画の投稿にしない
    return item.get("status") == "queued" and float(item.get("score") or 0) > 0


def muse_wait_until(slug: str, slot: datetime, breaking: bool = False, data: dict | None = None) -> datetime | None:
    """この記事の投稿が Muse の動画を待つ期限（頼んでいなければ None）。速報は breaking_wait_hours（既定0＝待たない）"""
    item = muse_item(slug, data)
    if item.get("status") != "queued" or not video_post(slug, data if data is not None else {"items": [item]}):
        return None
    hours = float(plan()["muse"]["breaking_wait_hours"]) if breaking else video_wait_hours()
    if hours <= 0:
        return None
    try:
        queued = datetime.fromisoformat(item.get("queuedAt") or "")
    except ValueError:
        queued = slot
    return max(slot, queued) + timedelta(hours=hours)


# ---- 決算・株の話題の1日の上限（2026-11-06 テストの日から・台帳 S39） ----

def finance_topic(record: dict | None) -> bool:
    """決算・株・業績・配当・自社株買い・TOB の話題か（記事でも投稿の記録でもよい。題名・SEO の題名・タグを見る）"""
    record = record or {}
    if record.get("disaster") or record.get("missile") or record.get("kind") == "digest" or record.get("style") == "digest":
        return False
    f = plan().get("finance") or {}
    return bool(f.get("re")) and bool(_re(f["re"]).search(_text(record)))


def finance_cap() -> int:
    return int((plan().get("finance") or {}).get("cap", 2))


def finance_count(posted: dict, day: date, skipped: set[str] | None = None, articles: dict | None = None) -> int:
    """その日（日本時間）に出した・予約した決算・株の話題の投稿の数。記録に題名が無ければ articles（slug → 記事）か記事のファイルを見る"""
    skipped = skipped or set()
    n = 0
    for slug, rec in (posted or {}).items():
        if slug in skipped or not (rec.get("id") or rec.get("status") == "awaiting_video"):
            continue
        when = _when(rec)
        if not when or when.astimezone(JST).date() != day:
            continue
        art = rec if rec.get("title") else (articles or {}).get(slug) or _article(slug)
        if finance_topic(art):
            n += 1
    return n


def finance_full(article: dict, posted: dict, day: date, extra: int = 0, skipped: set[str] | None = None) -> bool:
    """この記事を出すと、その日の決算・株の話題が上限を超えるか（超えるなら Threads には出さない。サイトには載せる）"""
    return finance_topic(article) and finance_count(posted, day, skipped) + extra >= finance_cap()


def _article(slug: str) -> dict:
    try:
        return json.loads((ROOT / "content" / "articles" / f"{slug}.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}
