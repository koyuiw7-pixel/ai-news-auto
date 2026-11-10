#!/usr/bin/env python3
"""SNS の伸ばし方の計画を1か所で持つ（2026-11-05 とろいも案 v1。台帳 S27〜S31）。設定は scripts/sns_plan.json。

すべての投稿の経路（threads_post・breaking_post・bluesky_post・morning_digest・sns_video_followup・門番 sns_rules）が
ここを読む。経路ごとに別の決まりを書かない（O13）。

  lane_of(article)        → (レーン名, 点数)。safety（障害・流出・安全）> money（お金・制度・政府）> brand（有名ブランド）> consumer_ai
  excluded(article)       → SNS に出さない理由（海外の企業向け・開発者向け。サイトには載せる）。出してよければ ""
  sns_score(article)      → 並べ順の点数（レーン＋ Muse の動画待ち）
  slots_jst()             → 通常の投稿の時刻 [(時, 分), ...]
  daily_cap() / cap_exempt(article_or_entry)  → 1日の上限と、上限に数えない種類（ミサイル・災害）
  bluesky_daily_cap() / bluesky_slot_window(now) → Bluesky だけの1日の本数と枠（2026-11-08〜 15本・S47）（Threads と別に数える。S40）
  x_on() / x_daily_cap() / x_slot_window(now) / x_topic / x_earnings_only / x_keyword / x_hashtag → X だけの1日の本数と枠（2026-11-08〜 15本・S47）・話題・文面（S42）
  fb_on() / fb_daily_cap() / fb_slot_window(now) / fb_lifestyle → Facebook だけの1日の本数と枠（2026-11-08〜 15本・S47）・暮らしの話題（S43）
  count_today(posted, day, extra) → その日（日本時間）に出した（予約した）自分の投稿の数
  utm_content(ptype, pos) → "video_body" など
  hook_format_on()  → 2026-11-05 オーナー承認でワークフローの既定は on（変数で 0 にすれば止まる）
  threads_link_position() → 変数 THREADS_LINK_POS（reply / body。空なら body）。台帳 S6（リンクの置き場所）
  finance_topic(article)  → 決算・株・業績・配当・自社株買い・TOB の話題か（X の決算の数字だけの投稿を外すのに使う。S42）
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
    """SNS に出さない理由（海外の開発者向けの話題。台帳 S28・2026-11-08 に狭めた）。出してよければ ""。
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
    if not (hit or aud) and ex.get("soft_re") and (soft := _re(ex["soft_re"]).search(text)):
        # 2026-11-08 の台帳の見直し（オーナー承認・S28 を狭めた）: 「API」「法人向け」などは、一般の人に関係する話題（どれかのレーン）なら外さない
        if not lane_of(article)[0]:
            hit = soft
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


# ---- 暮らしとお金の「自分ごと」の記事か（2026-11-10 台帳 S53。X の枠・速報で先に選ぶ） ----
# 11/10 7:02 の X が「OpenAI、AIの研究ジョブを最大35秒で停止」（AI・企業の話）だった。サイトの軸は暮らしとお金で、AI の記事はほとんど読まれない。
# そのまま暮らし・お金の分野（digest.LIFE_MONEY_GENRES から business を除いたもの）
LIFE_MONEY_GENRES = frozenset({"lifestyle", "public", "investment", "real-estate"})
# 安全・お金のレーン（流出・障害・リコール・値上げ・料金・手続き）に当たるときだけ暮らしの記事とみなす分野
CONSUMER_GENRES = frozenset({"business", "tech-gadget", ""})
B2B_TITLE_RE = re.compile(r"法人向け|企業向け|事業者向け|業務向け|開発者向け|BtoB|B2B|SaaS")
B2B_AUDIENCE_RE = re.compile(r"開発|エンジニア|担当|企業|法人|経営者|事業者(?!主)|情報システム|情シス|マーケ|研究者|専門家|(?<![A-Za-z])IT(?![A-Za-z])")
FOREIGN_HEAD_RE = re.compile(r"^(?:【[^】]{1,12}】)?\s*(?:米国?|欧州|ユーロ圏|中国|英国?|独|豪|NY|ECB|FRB|FOMC)")
MACRO_RE = re.compile(r"雇用|失業率|CPI|物価|GDP|PMI|小売売上|利上げ|利下げ|政策金利|長期金利|国債|株価|ダウ|ナスダック|S&P|景気|インフレ|関税")


def b2b(article: dict | None) -> bool:
    """企業・開発者・担当者向けの記事か（見出しの「法人向け」など、判定の読者が開発者・担当・経営者など）"""
    article = article or {}
    audience = str((article.get("verdict") or {}).get("audience") or "")
    return bool(B2B_TITLE_RE.search(str(article.get("title") or "")) or (audience and B2B_AUDIENCE_RE.search(audience)))


def foreign_macro(article: dict | None) -> bool:
    """海外の景気・金利・株の数字の記事か（「米雇用者数16.5万人増」など）"""
    title = str((article or {}).get("title") or "")
    return bool(FOREIGN_HEAD_RE.search(title) and MACRO_RE.search(title))


def life_money(article: dict | None) -> bool:
    """暮らしとお金の「自分ごと」の記事か（台帳 S53）。地震・災害・急ぎの知らせはいつも当たる。
    暮らし・生活／社会・行政／投資・マネー／不動産の記事と、ビジネス・ガジェットのうち流出・障害・値上げ・料金などのレーンに当たる記事。
    AI の記事は日本の一般のサービスの流出・障害（安全のレーン）だけ。企業・開発者向け（b2b）・海外の景気の数字（foreign_macro）は当たらない"""
    article = article or {}
    if _alert(article):
        return True
    if excluded(article) or b2b(article) or foreign_macro(article):
        return False
    genre = str(article.get("genreSlug") or "")
    lane = lane_of(article)[0]
    if genre in LIFE_MONEY_GENRES:
        return True
    if genre in CONSUMER_GENRES:
        return lane in ("safety", "money")
    if genre == "ai":
        return lane == "safety" and japanese_source(article)
    return False


# ---- 枠と1日の上限 ----

def _hm(value: str) -> tuple[int, int]:
    h, m = value.split(":")
    return int(h), int(m)


def per_day() -> int:
    """1日の通常の投稿の本数（Threads・X・Facebook・Bluesky のそれぞれ。2026-11-08 オーナー承認・台帳 S47）。
    リポジトリの変数 SNS_PER_DAY（ワークフローが渡す）。無ければ・数でなければ per_day_max。per_day_max より増やさない"""
    top = int(plan().get("per_day_max") or plan()["daily_cap"])
    raw = os.environ.get("SNS_PER_DAY", "").strip()
    return max(0, min(int(raw), top)) if raw.isdigit() else top


# 投稿の1日の始まり（日本時間）。2026-11-10 オーナー決定（台帳 S54）: 朝6時から夜1時台（1:59）まで出す。0時・1時台の枠は前の日の夜の続き
DAY_START_JST = (6, 0)


def day_order(hm: tuple[int, int], start: tuple[int, int] = DAY_START_JST) -> int:
    """枠の並べ順（start からの分）。0:45・1:30 の枠は 23:45 の後に来る"""
    return (hm[0] * 60 + hm[1] - start[0] * 60 - start[1]) % (24 * 60)


def spread(slots: list[tuple[int, int]], n: int) -> list[tuple[int, int]]:
    """枠を n 個に間引く（1日の中でならす。最初の枠＝朝の枠は必ず残す）。n が枠の数以上ならそのまま。
    並びは1日の始まり（DAY_START_JST・朝6時）から（夜0時・1時台の枠は最後）"""
    slots = sorted(slots, key=day_order)
    if n >= len(slots):
        return slots
    if n <= 0:
        return []
    if n == 1:
        return slots[:1]
    step = (len(slots) - 1) / (n - 1)
    return [slots[int(i * step + 0.5)] for i in range(n)]


def keep_slot(chosen: list[tuple[int, int]], keep: tuple[int, int]) -> list[tuple[int, int]]:
    """間引いた枠に keep（朝のまとめの 7:15）を必ず入れる（いちばん近い枠と入れ替える）"""
    if not chosen or keep in chosen:
        return chosen
    near = min(range(len(chosen)), key=lambda i: abs(day_order(chosen[i]) - day_order(keep)))
    return sorted({*chosen[:near], keep, *chosen[near + 1:]}, key=day_order)


def slots_jst() -> list[tuple[int, int]]:
    slots = [_hm(s) for s in plan()["slots_jst"]]
    digest = _hm(plan().get("digest_slot_jst") or plan()["slots_jst"][0])
    return keep_slot(spread(slots, daily_cap()), digest) if digest in slots else spread(slots, daily_cap())


def digest_slot_jst() -> tuple[int, int]:
    return _hm(plan().get("digest_slot_jst") or plan()["slots_jst"][0])


def daily_cap() -> int:
    raw = os.environ.get("SNS_DAILY_CAP", "").strip()
    top = min(int(plan()["daily_cap"]), per_day())  # 2026-11-08〜 SNS_PER_DAY（台帳 S47）
    cap = int(raw) if raw.isdigit() else top
    return max(0, min(cap, top))  # 変数で減らすことはできるが、計画より増やさない


# ---- Bluesky だけの枠と上限（2026-11-06 オーナー承認・台帳 S40。Threads の daily_cap・slots_jst とは別に数える） ----

def bluesky_plan() -> dict:
    return plan().get("bluesky") or {}


def bluesky_slots_jst() -> list[tuple[int, int]]:
    return spread([_hm(s) for s in bluesky_plan().get("slots_jst") or []], bluesky_daily_cap())


def bluesky_daily_cap() -> int:
    """Bluesky の1日（日本時間）の上限。変数 BLUESKY_PER_DAY で減らすことはできるが、計画より増やさない"""
    cap = min(int(bluesky_plan().get("daily_cap") or 0), per_day())  # 2026-11-08〜 SNS_PER_DAY（台帳 S47）
    raw = os.environ.get("BLUESKY_PER_DAY", "").strip()
    return max(0, min(int(raw), cap)) if raw.isdigit() else cap


def bluesky_slot_window(now: datetime) -> tuple[int, datetime, datetime] | None:
    """今の時刻が入る Bluesky の枠（番号, 始まり, 終わり）。枠は次の枠の前まで、最後の枠は window_end まで。
    朝の最初の枠の前・window_start より前・window_end より後は None（出さない）"""
    return _slot_window({**bluesky_plan(), "slots_jst": [f"{h:02d}:{m:02d}" for h, m in bluesky_slots_jst()]}, now)


def _slot_window(block: dict, now: datetime) -> tuple[int, datetime, datetime] | None:
    """SNS ごとの枠（block の slots_jst・window_start・window_end）で、今の時刻が入る枠（番号, 始まり, 終わり）。外なら None"""
    # 2026-11-10（台帳 S54）: window_end が window_start より早い時刻（"02:00" など）なら次の日のその時刻まで（夜0時・1時台の枠）。
    # window_start より前の時刻は前の日の夜の続きとして見る
    local = now.astimezone(JST)
    start_hm = _hm(block.get("window_start") or "07:00")
    day = local.replace(hour=0, minute=0, second=0, microsecond=0)
    if day_order((local.hour, local.minute), start_hm) > day_order((local.hour, local.minute), (0, 0)):
        day -= timedelta(days=1)  # 0:00〜window_start の前は前の日の夜
    at = lambda hm: day + timedelta(minutes=start_hm[0] * 60 + start_hm[1] + day_order(hm, start_hm))  # noqa: E731
    first = at(start_hm)
    last = at(_hm(block.get("window_end") or "23:00"))
    starts = sorted(max(first, at(hm)) for hm in (_hm(x) for x in block.get("slots_jst") or []))
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
    return spread([_hm(s) for s in x_plan().get("slots_jst") or []], x_daily_cap())


def x_daily_cap() -> int:
    """X の1日（日本時間）の通常の投稿の上限。変数 X_PER_DAY で減らすことはできるが、計画より増やさない"""
    cap = min(int(x_plan().get("daily_cap") or 0), per_day())  # 2026-11-08〜 SNS_PER_DAY（台帳 S47）
    raw = os.environ.get("X_PER_DAY", "").strip()
    return max(0, min(int(raw), cap)) if raw.isdigit() else cap


def x_slot_window(now: datetime) -> tuple[int, datetime, datetime] | None:
    """今の時刻が入る X の枠（番号, 始まり, 終わり）。7:30・12:30・21:00。7時より前・23時より後・最初の枠の前は None"""
    return _slot_window({**x_plan(), "slots_jst": [f"{h:02d}:{m:02d}" for h, m in x_slots_jst()]}, now)


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


# 値段・税の書き方（税込・税抜・税別）。この中の「税」はレーンの言葉に当たっても X の1行目の言葉にしない
PRICE_NOTATION_AFTER = ("込", "抜", "別")


def keyword_like(word: str, text: str, end: int) -> bool:
    """レーン・製品の正規表現に当たった言葉が、X の1行目の頭に置ける検索される言葉か（2文字以上・「税込」などの一部でない）"""
    word = str(word or "").strip()
    if len(word) < 2:
        return False
    return not str(text or "")[end:end + 1].startswith(PRICE_NOTATION_AFTER)


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
            if not keyword_like(m.group(0), body, m.end()):
                continue  # 「税込」の「税」のような1文字・値段の書き方の一部は検索される言葉ではない（2026-11-09 【税】が頭に付いた）
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
    """X のハッシュタグ（1つまで）。災害の知らせ（#地震 など）と大きな行事（WBC など）、いまのトレンドの言葉に当たる記事（台帳 S50）だけ。ほかは付けない"""
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
    return x_trend_tag(article)


# X だけで足す話題の名前のタグ（2026-11-10 台帳 S53。X でいま見られている暮らしの話題。bluesky_post.TOPIC_TAGS のあとに見る）
X_EXTRA_TOPIC_TAGS: list[tuple[str, str]] = [
    (r"ニトリ", "#ニトリ"), (r"灯油", "#灯油"), (r"LPガス|プロパンガス", "#LPガス"), (r"暖房", "#暖房"), (r"給付金", "#給付金"),
]
# 流出・リコールなどの記事には付けない煽る言葉のタグ（台帳 S35・bluesky_post.brief_hashtag と同じ）
SAFETY_SKIP_TAGS = ("#詐欺", "#リコール", "#値上げ")
X_TAG_MAX = 3  # 2026-11-10 台帳 S53: 話題のタグを2〜3つ（S52 の2つまでを3つまでに）
X_TOPIC_TAG_MAX = 2


def x_topic_tags(article: dict | None, limit: int = X_TOPIC_TAG_MAX) -> list[str]:
    """記事の話題の名前のタグ（会社・サービス・制度の名前。#ドコモ #年金 #給付金 など）を limit 個まで。見出し → 記事のタグの順。
    地震・津波・急ぎの知らせには付けない（S35）。流出・リコールの記事は会社・サービスの名前だけ"""
    article = article or {}
    if article.get("disaster") or _alert(article):
        return []
    try:
        import bluesky_post  # noqa: PLC0415
        import sns_rules  # noqa: PLC0415

        table = [*bluesky_post.TOPIC_TAGS, *X_EXTRA_TOPIC_TAGS]
        safety = sns_rules.safety_topic(article)
    except Exception:  # noqa: BLE001
        table, safety = list(X_EXTRA_TOPIC_TAGS), False
    out: list[str] = []
    for source in (str(article.get("title") or ""), " ".join(str(t) for t in article.get("tags") or [])):
        for pattern, tag in table:
            if len(out) >= limit:
                return out
            if (safety and tag in SAFETY_SKIP_TAGS) or tag in out:
                continue
            if re.search(pattern, source, re.I):
                out.append(tag)
    return out


def x_hashtags(article: dict | None) -> list[str]:
    """X のハッシュタグ（2026-11-10 台帳 S52 → S53: 話題のタグを2〜3つまで）。x_hashtag（災害・行事・トレンド）と、
    記事の話題の名前のタグ（x_topic_tags。#ドコモ・#年金・#給付金 など2つまで）。地震・津波・急ぎの知らせは x_hashtag だけ"""
    article = article or {}
    out = [t for t in [x_hashtag(article)] if t]
    for topic in x_topic_tags(article):
        if topic not in out:
            out.append(topic)
    return out[:X_TAG_MAX]


# ---- X の記事のリンクの場所（2026-11-10 オーナー決定・台帳 S52） ----
# 「Xの本文に記事のリンクを入れる形に変えてよい。これが最適ならいいよ」→ 本文にリンク（＋画像）と、自分への返信にリンク（S50）を
# おおよそ半分ずつ出して比べる。リポジトリの変数 X_LINK_MODE（ab＝既定・body＝全部本文・reply＝全部返信）
X_LINK_VARIANTS = ("body", "reply")


def x_link_mode() -> str:
    mode = os.environ.get("X_LINK_MODE", "").strip().lower()
    return mode if mode in ("ab", "body", "reply") else "ab"


def x_link_variant(slug: str, history: dict | None = None, now: datetime | None = None, days: int = 7) -> str:
    """この記事の X の投稿のリンクの場所（"body" か "reply"）。ab のときは直近 days 日に少ない方（同じなら slug で決める）"""
    mode = x_link_mode()
    if mode != "ab":
        return mode
    now = now or datetime.now(timezone.utc)
    counts = {v: 0 for v in X_LINK_VARIANTS}
    for rec in (history or {}).values():
        if not isinstance(rec, dict) or rec.get("link") not in counts:
            continue
        try:
            at = datetime.fromisoformat(str(rec.get("at") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        if now - at <= timedelta(days=days):
            counts[rec["link"]] += 1
    if counts["body"] != counts["reply"]:
        return "body" if counts["body"] < counts["reply"] else "reply"
    import hashlib  # noqa: PLC0415

    return X_LINK_VARIANTS[int(hashlib.sha1(str(slug).encode()).hexdigest(), 16) % 2]


# ---- X のトレンドのタグ（2026-11-09 オーナー承認・台帳 S50） ----
# いま日本で検索・投稿が急上昇している言葉（scripts/trends.py が state/trend_signals.json に書く Googleトレンド・Yahoo!リアルタイム検索）
# に記事の題名が当たるときだけ、その言葉のタグを1つ付けてよい。当たらなければ付けない。
# X の投稿の処理（scripts/x_post.py の main）が use_x_trends() で読み込んだときだけ働く（試験・ほかの SNS の処理では付けない＝結果がぶれない）
TREND_SIGNALS_PATH = ROOT / "state" / "trend_signals.json"
TREND_HOURS = 24
TREND_FILLER = {"確認方法", "確認", "方法", "いつ", "いつから", "いつまで", "なぜ", "理由", "原因", "対象", "最新", "速報", "今日", "現在",
                "まとめ", "情報", "どこ", "とは", "どうなる", "影響", "公式", "一覧", "状況", "今後", "ニュース", "news", "ヤフー", "リアルタイム"}
TREND_TAG_RE = re.compile(r"^[0-9A-Za-z\u3040-\u30ff\u4e00-\u9fff\uff10-\uff19\uff21-\uff3a\uff41-\uff5a]{2,15}$")
_X_TRENDS: list[dict] | None = None


def use_x_trends(path: Path | None = None, now: datetime | None = None) -> int:
    """X のトレンドの言葉を読み込む（芸能のうわさ・事件の話題と、TREND_HOURS より古いものは外す）。読めた数"""
    global _X_TRENDS
    now = now or datetime.now(timezone.utc)
    try:
        items = list(json.loads((path or TREND_SIGNALS_PATH).read_text("utf-8")).get("items") or [])
    except (OSError, ValueError, AttributeError):
        items = []
    out = []
    for item in items:
        if not isinstance(item, dict) or item.get("gossip") or not str(item.get("title") or "").strip():
            continue
        try:
            seen = datetime.fromisoformat(str(item.get("seen_at") or ""))
        except ValueError:
            continue
        seen = seen if seen.tzinfo else seen.replace(tzinfo=JST)
        if now - seen <= timedelta(hours=TREND_HOURS):
            out.append(item)
    out.sort(key=lambda x: -int(x.get("traffic") or 0))
    _X_TRENDS = out
    return len(out)


def clear_x_trends() -> None:
    global _X_TRENDS
    _X_TRENDS = None


def _trend_norm(text: str) -> str:
    import unicodedata  # noqa: PLC0415

    return unicodedata.normalize("NFKC", str(text or "")).lower()


def x_trend_tag(article: dict | None, trends: list[dict] | None = None) -> str:
    """記事の題名がいまのトレンドの言葉に当たれば、そのタグ（1つ）。言葉が複数（「三菱重工 株価」）なら全部の語が題名にあるときだけ、
    最初の語をタグにする。トレンドを読み込んでいなければ \"\""""
    trends = _X_TRENDS if trends is None else trends
    article = article or {}
    if not trends or _alert(article):
        return ""
    title = _trend_norm(article.get("title") or article.get("seoTitle") or "")
    if not title:
        return ""
    for item in trends:
        words = [w for w in re.split(r"[\s\u3000、,・/]+", _trend_norm(item.get("title"))) if w and w not in TREND_FILLER]
        if not words or len(words) > 3 or not TREND_TAG_RE.match(words[0]) or words[0].isdigit():
            continue
        if all(w in title for w in words):
            raw = str(article.get("title") or "")
            # タグは題名に出てくる書き方のまま（全角・大文字小文字をそろえる）
            m = re.search(re.escape(words[0]), _trend_norm(raw))
            tag = raw[m.start():m.end()] if m and len(_trend_norm(raw)) == len(raw) else words[0]
            return "#" + tag
    return ""


# ---- Facebook だけの枠・上限・文面（2026-11-06 オーナー承認・台帳 S43。2026-11-07 から。Threads・X とは別に数える） ----

def fb_plan() -> dict:
    return plan().get("facebook") or {}


def fb_on(when: datetime | None = None) -> bool:
    """Facebook だけの枠で出す日か（sns_plan.json の facebook.start の日から）。この日からは Facebook の投稿は
    scripts/facebook_post.py だけが出す（Threads の予定・速報からは Facebook に出さない）"""
    return _started(fb_plan(), when)


def fb_slots_jst() -> list[tuple[int, int]]:
    return spread([_hm(s) for s in fb_plan().get("slots_jst") or []], fb_daily_cap())


def fb_daily_cap() -> int:
    """Facebook の1日（日本時間）の通常の投稿の上限。変数 FACEBOOK_PER_DAY で減らすことはできるが、計画より増やさない"""
    cap = min(int(fb_plan().get("daily_cap") or 0), per_day())  # 2026-11-08〜 SNS_PER_DAY（台帳 S47）
    raw = os.environ.get("FACEBOOK_PER_DAY", "").strip()
    return max(0, min(int(raw), cap)) if raw.isdigit() else cap


def fb_slot_window(now: datetime) -> tuple[int, datetime, datetime] | None:
    """今の時刻が入る Facebook の枠（番号, 始まり, 終わり）。7:30・12:30・20:00。7時より前・23時より後・最初の枠の前は None"""
    return _slot_window({**fb_plan(), "slots_jst": [f"{h:02d}:{m:02d}" for h, m in fb_slots_jst()]}, now)


def fb_lifestyle(article: dict | None) -> bool:
    """暮らしの話題か（家計・値上げ・暮らし・制度。12:30 の枠で先に選ぶ・問いかけを付けてよい）。災害・ミサイルの知らせは当たらない"""
    article = article or {}
    if _alert(article) or article.get("items"):
        return False
    pat = fb_plan().get("lifestyle_re")
    return bool(pat) and bool(_re(pat).search(f"{_text(article)} {article.get('lede', '')}"))


def min_gap() -> timedelta:
    return timedelta(minutes=int(plan()["min_gap_min"]))


# ---- 記事の自動投稿のスイッチ（2026-11-10 オーナー決定「今後は全て手投稿にしよう」。sns_plan.json の auto_post） ----
AUTO_POST_SERVICES = {"threads": "threads", "twitter": "x", "x": "x", "bluesky": "bluesky", "facebook": "facebook"}
# 手で出す経路（止めない）。人が文面を用意して出す
MANUAL_SOURCES = ("threads_figure_queue", "threads_control_post")


def auto_post_on(service: str, article: dict | None = None) -> bool:
    """この SNS（threads / twitter・x / bluesky / facebook）に、パイプラインが記事を自動で出してよいか。
    sns_plan.json の auto_post.<SNS> が true のときだけ。キーが無い・読めないときは止める（既定は手投稿だけ）。
    地震・ミサイルなどの急ぎの知らせ（article の disaster・missile・urgent・safetyAlert）は auto_post.alerts が true なら出す"""
    try:
        block = plan().get("auto_post") or {}
    except (OSError, ValueError):
        return False
    key = AUTO_POST_SERVICES.get(str(service or "").lower(), str(service or "").lower())
    if bool(block.get(key, False)):
        return True
    return bool(block.get("alerts", False) and article and _alert(article))


def auto_post_off_reason(service: str, article: dict | None = None, source: str = "") -> str:
    """自動投稿を止めている理由（出してよければ ""）。手で出す経路（MANUAL_SOURCES）は止めない"""
    if any(str(source or "").startswith(s) for s in MANUAL_SOURCES) or auto_post_on(service, article):
        return ""
    key = AUTO_POST_SERVICES.get(str(service or "").lower(), str(service or "").lower())
    return (f"{key} への記事の自動投稿は止めています（2026-11-10 オーナー決定「今後は全て手投稿にしよう」。"
            f"scripts/sns_plan.json の auto_post.{key} を true にすれば戻ります）")


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


UTM_CONTENT_RE = re.compile(r"^(?:video|hook|card|digest|reader)_(?:body|reply)$")


# ---- 文面の形・リンクの位置（2026-11-05 オーナー承認。ワークフローの既定は 1。環境変数が無い手元・テストでは off） ----

def _flag(name: str) -> bool:
    return os.environ.get(name, "0").strip().lower() in ("1", "on", "true", "yes")


def hook_format_on() -> bool:
    """Muse の型の文面（1行目＝結論＋数字・2行目＝なぜ大事か・3行目＝記事にだけあるもの）。S1 を変えるのでオーナー承認まで off"""
    return _flag("SNS_HOOK_FORMAT")


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


def peak_no_wait(slot: datetime | None) -> bool:
    """人の多い時間帯の枠か（動画を待たずに枠の時刻で出す。2026-11-09 オーナー承認・muse.no_wait_peak_jst）"""
    if not isinstance(slot, datetime):
        return False
    t = (slot if slot.tzinfo else slot.replace(tzinfo=timezone.utc)).astimezone(JST)
    hour = t.hour + t.minute / 60
    return any(float(a) <= hour < float(b) for a, b in (plan()["muse"].get("no_wait_peak_jst") or []))


def muse_wait_until(slug: str, slot: datetime, breaking: bool = False, data: dict | None = None) -> datetime | None:
    """この記事の投稿が Muse の動画を待つ期限（頼んでいなければ None）。速報は breaking_wait_hours（既定0＝待たない）。
    人の多い時間帯の枠は待たない（peak_no_wait）"""
    if peak_no_wait(slot):
        return None
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


# ---- 決算・株の話題か（X の「決算の数字だけは出さない」S42 が使う。1日の上限は 2026-11-08 に外した） ----

def finance_topic(record: dict | None) -> bool:
    """決算・株・業績・配当・自社株買い・TOB の話題か（記事でも投稿の記録でもよい。題名・SEO の題名・タグを見る）"""
    record = record or {}
    if record.get("disaster") or record.get("missile") or record.get("kind") == "digest" or record.get("style") == "digest":
        return False
    f = plan().get("finance") or {}
    return bool(f.get("re")) and bool(_re(f["re"]).search(_text(record)))


def _article(slug: str) -> dict:
    try:
        return json.loads((ROOT / "content" / "articles" / f"{slug}.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}
