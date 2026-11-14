#!/usr/bin/env python3
"""多くの人が読む公共性の高いニュース（情報漏えい・ミサイル・災害・リコール・詐欺の注意喚起・暮らしのお金の変更）。

2026-11-04 オーナー決定（台帳 A39・A40）:
  会社の発表だけでは反応が少ない。働く人に広く読まれるニュース（不正アクセスによる大規模な流出・北朝鮮のミサイル発射・
  災害・大きなリコール・詐欺・税や年金の変更など）も、公式の一次情報があるものは拾う。
  ただし土台の決まりは変えない: 事実は官公庁・本人（会社）・警察・規制当局の発表だけ（報道は出典にしない。W31）。

このファイルが1か所で持つもの:
  1. category()            … 題名が公共性の高い話題のどれに当たるか（breach / missile / disaster / recall / scam / money）
  2. candidate_problem()   … 公共性の候補として扱わない理由（政党の申し入れ・個人の事件・採用・統計の転載・報道が出典）
  3. is_candidate()        … 公式の一次情報で、公共性の高い候補か（web_articles が「大きなニュース」として先に処理する）
  4. breaking_ok()         … 速報（すぐ SNS へ）にしてよい種類か（ミサイル・災害と、官公庁の大規模な流出の発表だけ）
  5. sensitive_problems()  … どの経路の記事にも当てる門（quality.every_path_problems から呼ぶ）:
       煽る言葉・推測の言い方・私人の実名・「分かっていること／分かっていないこと」の区別・政治の中立・公式の安全情報へのリンク
  6. autofix()             … ミサイル・災害の記事の本文の頭に、公式の安全情報（首相官邸・防衛省・国民保護ポータル・気象庁）への
       リンクを決まった形で入れる（LLM に任せない）
  7. focus_topic()         … 検索に出す主題（indexnow.is_focus・lib/indexing.ts）に公共性の高い話題を入れる目印

API を使わない・通信しない。
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))


def _nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


# --------------------------------------------------------------------------- #
# 1. 話題の種類（題名で判定。NFKC 後の文字に当てる）
# --------------------------------------------------------------------------- #
CATEGORY_RES: dict[str, re.Pattern] = {
    # 北朝鮮などのミサイル発射・Jアラート（防衛省「北朝鮮のミサイル等関連情報」・首相官邸の総理指示）
    "missile": re.compile(r"弾道ミサイル|ミサイル(?:の)?発射|ミサイル等関連情報|Jアラート|全国瞬時警報"),
    # 不正アクセス・情報漏えい・ランサムウェア（会社の発表・官公庁の注意喚起）
    "breach": re.compile(
        r"不正アクセス|情報漏え?い|情報漏洩|個人情報.{0,8}(?:流出|漏え?い|漏洩)|(?:流出|漏え?い)の(?:可能性|おそれ|恐れ)|"
        r"ランサムウェア|サイバー攻撃|標的型攻撃|不正ログイン"
    ),
    # 災害（地震・津波の速報そのものは scripts/quake.py の型だけ。A15。ここは大雨・台風・噴火と、被災者の手続き・支援）
    "disaster": re.compile(
        r"大雨|豪雨|線状降水帯|台風第?\d*号?|噴火|特別警報|土砂災害|避難指示|"
        r"(?:地震|豪雨|台風|災害).{0,12}(?:罹災証明|り災証明|被災者|支援|申請|特例)|罹災証明|り災証明"
    ),
    # リコール・製品事故（消費者庁の重大製品事故・国交省のリコールの届出・会社の自主回収）
    # 2026-11-07（台帳 A51）: 消費者庁のリコール情報サイトの「返金／回収」・PMDA の「クラスI回収」もリコールとして数える
    # 2026-11-07（台帳 A56）: 同じサイトの「〜 - 回収」（返金なしの回収）も数える
    "recall": re.compile(r"リコール|自主回収|製品事故|使用(?:を)?中止|回収(?:の)?お知らせ|発火|発煙|返金[／/・]回収|クラス\s*[IⅠ1]+\s*回収|\s[-－‐]\s*回収\s*$"),
    # 詐欺・なりすましの注意喚起
    "scam": re.compile(r"詐欺|フィッシング|なりすまし|悪質商法|架空請求|偽(?:の)?(?:サイト|メール|SMS)|サポート詐欺"),
    # 働く人の家計に直接かかわる制度・料金の変更（税・年金・保険料・最低賃金・電気ガス・ガソリン）
    "money": re.compile(
        r"税制改正|定額減税|所得税.{0,6}(?:改正|引き上げ|引き下げ|減税)|年金.{0,8}(?:改定|引き上げ|引き下げ|支給額|改正)|"
        r"保険料.{0,6}(?:引き上げ|引き下げ|改定)|最低賃金|電気(?:・ガス)?(?:料金|代).{0,6}(?:補助|支援|値上げ|値下げ)|"
        r"ガソリン.{0,6}(?:補助|価格|税)|物価高.{0,4}対策|給付金"
    ),
}
# 地震・津波の発生そのものの記事は LLM に書かせない（A15。scripts/quake.py）
QUAKE_REPORT_RE = re.compile(r"(?:震度\d|を震源とする地震|津波(?:警報|注意報)|大津波)")
# 選び方の調整値は scripts/public_interest_rules.json（後から重みを変えやすいように、コードに書き込まない）
RULES_PATH = ROOT / "scripts" / "public_interest_rules.json"
DEFAULT_RULES = {
    "daily_cap": 0,  # 0＝上限なし（2026-11-08 の台帳の見直し・オーナー承認で 12本の上限〔旧 A40〕を外した）
    "priority": {"missile": 0, "disaster": 1, "breach": 2, "scam": 3, "money": 4, "recall": 5},
    "kinds": {"missile": ["gov"], "disaster": ["gov"], "scam": ["gov"], "money": ["gov"],
              "breach": ["gov", "official", "company"], "recall": ["gov", "official", "company"]},
    "breaking": ["missile", "disaster"],
    "trend_first": True,
    "short_body": 800,
    "min_source_chars": 1200,
}


def load_rules(path: Path | None = None) -> dict:
    """調整値（読めない・壊れているときは既定値。記事づくりを止めない）"""
    try:
        data = json.loads((path or RULES_PATH).read_text("utf-8"))
    except (OSError, ValueError):
        data = {}
    return {**DEFAULT_RULES, **{k: v for k, v in data.items() if k in DEFAULT_RULES}}


RULES = load_rules()
# 同じ実行で先に作る順（既定: 命と安全 → 多くの人の個人情報 → 詐欺 → お金 → リコール）
PRIORITY: dict[str, int] = {str(k): int(v) for k, v in RULES["priority"].items()}
# 速報（すぐ SNS へ）にしてよい種類（S2・S15。災害・ミサイルは遅れると読者が困る）
BREAKING_CATEGORIES = tuple(RULES["breaking"])
# 1日に公共性の枠で作る本数の上限。0＝上限なし（2026-11-08 から。1日の記事の段 A58 の上限の中で作る）
DAILY_CAP = int(os.environ.get("PUBLIC_INTEREST_DAILY_CAP") or RULES["daily_cap"] or 0)
UNLIMITED = 10**9


def left_today(state: dict, now: datetime | None = None) -> int:
    """今日まだ公共性の枠で作れる本数（上限なしなら UNLIMITED）"""
    if DAILY_CAP <= 0:
        return UNLIMITED
    return max(DAILY_CAP - done_today(state, now), 0)
TREND_FIRST = bool(RULES["trend_first"])
# 流出・リコール・詐欺・お金の候補は、資料（公式の発表の本文）がこの字数より短ければ書かない（本文の下限に届かず、作り直しで費用だけ使うため。
# ミサイル・災害は本文の下限が短いので対象外）
MIN_SOURCE_CHARS = int(RULES["min_source_chars"])


def source_too_short(cat: str, text: str) -> bool:
    return cat not in ("missile", "disaster") and len(text or "") < MIN_SOURCE_CHARS


def category(title: str, summary: str = "") -> str | None:
    """題名が当たる公共性の話題の種類。当たらなければ None。
    概要は見ない（概要の一言で寄贈・見学ツアー・大臣会見が「災害」「流出」になったため。2026-11-04 の試し）"""
    text = _nfkc(title)
    for name, pattern in CATEGORY_RES.items():
        if pattern.search(text):
            return name
    return None


# 種類ごとに、一次情報として扱う発信元の種類（feeds.py の kind）。
# 流出・リコールは会社自身の発表も一次情報。ミサイル・災害・詐欺・制度は官公庁の発表だけ（会社の分析記事・調査会社のコラムは外す）
CATEGORY_KINDS = {str(k): tuple(v) for k, v in RULES["kinds"].items()}


# --------------------------------------------------------------------------- #
# 2. 候補として扱わないもの
# --------------------------------------------------------------------------- #
# 政党・議員の申し入れ・提言・選挙（政治は中立。官房長官が政党の提言を受けた、のような記事は作らない）
POLITICS_RE = re.compile(
    r"自民党|自由民主党|立憲民主党|日本維新の会|維新の会|公明党|国民民主党|共産党|れいわ新選組|参政党|社民党|日本保守党|"
    r"申入れ|申し入れ|緊急提言|提言を受け|選挙|候補者|立候補|政党|議員連盟"
)
# 個人の事件（犯罪。私人の名前・推測を避ける）。2026-11-08 オーナー決定（台帳 A23）: 事故・災害は暮らしの安全として扱うので外さない（A39 の書き方）
PERSONAL_CRIME_RE = re.compile(r"逮捕|容疑者|被告|送検|起訴|判決|殺人|殺害|遺体|書類送検|指名手配")
# 採用・会議・訓練・叙勲など、公共の話題の語を含んでも読者の役に立たない告知
NOT_NEWS_RE = re.compile(
    r"採用|募集|職員|任期付|会議|審議会|検討会|委員会|部会|議事|訓練|演習|叙勲|褒章|表彰|講演|セミナー|説明会|研修|"
    r"月間|週間|キャンペーン|ポスター|動画を公開|入札|公募|会見要旨|記者会見|人事|掲載しました|"
    # 定例の統計の公表（A26）
    r"認知・検挙状況|状況等について|統計|速報値|確定値|件数の推移"
)
# 報道機関（W17・W31）。報道が出典の候補は回さない（公式の発表が出てから）
OUTLET_HOST_RE = re.compile(
    r"(?:nhk\.or\.jp|nikkei\.com|asahi\.com|yomiuri\.co\.jp|mainichi\.jp|sankei\.com|jiji\.com|kyodonews|tbs\.co\.jp|"
    r"fnn\.jp|news\.ntv|tv-asahi|itmedia\.co\.jp|mynavi\.jp|impress\.co\.jp|bloomberg|reuters|yahoo\.co\.jp|"
    r"news\.google|gori\.me|9to5|cnn\.|bbc\.)",
    re.I,
)
# 公式の一次情報とみなすフィードの種類（feeds.py の kind）。配信（wire）・他社の告知（derivative）は除く
PRIMARY_KINDS = ("gov", "official", "company")


# 対策の製品・サービスの宣伝（「サイバー攻撃対策サービスを提供開始」「発火しにくい電池」）は事件の発表ではない
PRODUCT_RE = re.compile(r"ソリューション|提供開始|発売|導入|製品化|サービスを|プラットフォーム|対策(?:サービス|製品|ソフト)|と提携|協業|しにくい|を防ぐ|防止機能")
INCIDENT_RE = re.compile(r"注意喚起|お詫び|おわび|お知らせ|発生|被害|判明|可能性|届出|発射|指示|警戒|呼びかけ")


def _outlet_hosts() -> list[str]:
    """速報レーンのレーダーが見る報道機関（scripts/fast_lane_rules.json の radar.outlets）"""
    try:
        rules = json.loads((ROOT / "scripts" / "fast_lane_rules.json").read_text("utf-8"))
        return [str(o["host"]).lower() for o in (rules.get("radar") or {}).get("outlets") or [] if o.get("host")]
    except (OSError, ValueError, KeyError):
        return []


OUTLET_HOSTS = _outlet_hosts()


def is_press_url(url: str) -> bool:
    """報道機関・ニュースブログの URL か（W31: 記事の出典にしない）"""
    from urllib.parse import urlsplit  # noqa: PLC0415

    try:
        host = urlsplit((url or "").strip()).netloc.lower()
    except ValueError:
        return False
    if any(host == h or host.endswith("." + h) for h in OUTLET_HOSTS):
        return True
    return bool(host and OUTLET_HOST_RE.search(host))


def muse_press_ok(record: dict) -> bool:
    """Muse の入稿の道だけの例外（2026-11-13 オーナー承認）: 編集部が依頼した記事で、主要な報道機関（scripts/muse_format.py の
    PRESS_ALLOWED）の記事だけを出典にし、報道として書いて札（pressOnly）を付けたもの。scripts/muse_articles.py だけがこの印を付ける。
    自動の記事（writer が muse でない・印が無い）は今までどおり W31 で止める"""
    if record.get("writer") != "muse" or record.get("pressOnly") is not True:
        return False
    import muse_format  # noqa: PLC0415

    return bool(muse_format.press_outlet(str(record.get("sourceUrl") or ""), str(record.get("sourceName") or "")))


# --------------------------------------------------------------------------- #
# 2026-11-13 オーナー「とにかく数字。それさえ出るなら結構なんでもいい」「注目する話題がとれていない」:
# 急上昇の話題で公式の発表がまだ無いものだけ、主要な報道機関の報道を出典にした短い記事を通す（W31 の例外はこの形だけ）。
#   - 出典は下の一覧の報道機関だけ。独立した2社以上（共同通信の配信を載せる 47NEWS・nordot は1社、NHK の2つのドメインも1社と数える）
#   - 「NHKなどが報じた」と報道であることを書き、公式の発表として断定しない（pressReport の印・awaitingOfficial で公式が出たら更新）
#   - それ以外の報道が出典の記事（ニュースブログ・レーダーの報道・一覧に無い媒体・1社だけ）は今までどおり書かない・公開しない
# --------------------------------------------------------------------------- #
TREND_PRESS_OUTLETS: dict[str, str] = {
    "nhk.or.jp": "NHK", "news.web.nhk": "NHK",
    "47news.jp": "共同通信", "nordot.app": "共同通信",
    "jiji.com": "時事通信", "nikkei.com": "日本経済新聞", "asahi.com": "朝日新聞", "yomiuri.co.jp": "読売新聞",
    "mainichi.jp": "毎日新聞", "reuters.com": "ロイター", "jp.reuters.com": "ロイター",
    "bloomberg.com": "ブルームバーグ", "bloomberg.co.jp": "ブルームバーグ", "apnews.com": "AP通信",
    "newsdig.tbs.co.jp": "TBS NEWS DIG", "news.tv-asahi.co.jp": "テレ朝NEWS", "news.ntv.co.jp": "日テレNEWS", "fnn.jp": "FNN",
}
TREND_PRESS_MIN_OUTLETS = 2
PRESS_ATTRIBUTION_RE = re.compile(r"報じ|によると|が伝え|と伝え")


def press_outlet(url: str) -> str | None:
    """話題のレーンで出典にしてよい主要な報道機関の URL なら、その報道機関の名前（独立の数え方の単位）。違えば None"""
    from urllib.parse import urlsplit  # noqa: PLC0415

    try:
        parts = urlsplit((url or "").strip())
    except ValueError:
        return None
    if parts.scheme not in ("http", "https"):
        return None
    host = parts.netloc.lower().split(":")[0]
    for base, name in TREND_PRESS_OUTLETS.items():
        if host == base or host.endswith("." + base):
            return name
    return None


def trend_press_ok(record: dict) -> bool:
    """話題のレーンの、主要な報道機関2社以上を出典にした報道の記事か（W31 の例外の形を全部満たすか）"""
    if record.get("channelSlug") != "trends" or record.get("pressReport") is not True or not record.get("trendKeyword"):
        return False
    sources = [s for s in record.get("sources") or [] if isinstance(s, dict)]
    outlets = [press_outlet(str(s.get("url") or "")) for s in sources]
    if not outlets or any(o is None for o in outlets) or len(set(outlets)) < TREND_PRESS_MIN_OUTLETS:
        return False
    if press_outlet(str(record.get("sourceUrl") or "")) is None:
        return False
    # 報道であることを本文とリードに書いている（公式の発表として断定しない）
    return bool(PRESS_ATTRIBUTION_RE.search(f"{record.get('lede') or ''}\n{record.get('body') or ''}"))


def press_source_problems(record: dict) -> list[str]:
    """（2026-11-04 W31 の全経路化）記事の出典が報道機関・ニュースブログ・話題の報道まとめ（trends）なら不合格。
    事実は官公庁・会社自身など公式の一次情報だけ。報道しか無い話題は、公式の発表が出るまで書かない。
    調査会社・情報会社（A37。東京商工リサーチなど）の自社データの記事はオーナーの決定どおり「報道」の札で扱い、ここでは止めない。
    2026-11-13: Muse の入稿の道で、主要な報道機関だけを出典に報道として書いた記事（muse_press_ok）は止めない"""
    if muse_press_ok(record):
        return []
    channel = str(record.get("channelSlug") or "")
    url = str(record.get("sourceUrl") or "")
    if trend_press_ok(record):
        return []  # 話題のレーンの報道の記事（主要な報道機関2社以上・報道と明記。2026-11-13）
    if channel == "trends" or (channel.startswith("radar-") and channel != "radar-official") or is_press_url(url):
        return [f"報道機関の記事が出典（{channel or url[:60]}）。事実は公式の一次情報だけ（W31）。公式の発表が出てから書く"]
    return []


def candidate_problem(title: str, summary: str = "", url: str = "") -> str | None:
    """公共性の候補として扱わない理由（文字列）か None"""
    text = _nfkc(f"{title} {summary[:200]}")
    head = _nfkc(title)
    if PRODUCT_RE.search(head) and not INCIDENT_RE.search(head):
        return "対策の製品・サービスの宣伝（事件・注意喚起の発表ではない）"
    if POLITICS_RE.search(text):
        return "政治（政党・申し入れ・選挙）は扱わない"
    if PERSONAL_CRIME_RE.search(text):
        return "個人の事件（犯罪）は扱わない"
    if NOT_NEWS_RE.search(head):
        return "告知（採用・会議・訓練・表彰など）"
    if QUAKE_REPORT_RE.search(head) and not re.search(r"罹災|り災|支援|申請|特例|被災者", head):
        return "地震・津波の発生の記事は scripts/quake.py の型だけ（A15）"
    if url and is_press_url(url):
        return "報道が出典（公式の発表を待つ。W31）"
    return None


def is_candidate(item: dict, kind: str = "") -> bool:
    """公式の一次情報で、公共性の高い候補か（web_articles が大きなニュースとして先に処理する）。
    kind は feeds.feed_kind(item)。配信・他社の告知・報道・レーダーの報道は対象外"""
    kind = kind or item.get("kind") or ""
    if kind not in PRIMARY_KINDS:
        return False
    if item.get("radar") or item.get("secondary"):
        return False
    title, summary = item.get("title") or "", item.get("summary") or ""
    cat = category(title, summary)
    if not cat or kind not in CATEGORY_KINDS.get(cat, ()):
        return False
    return candidate_problem(title, summary, item.get("url") or "") is None


# 手続き・支援の案内（罹災証明の申請・支援金・特例など）。災害の話題でも速報にはしない
PROCEDURE_RE = re.compile(r"罹災証明|り災証明|申請|支援|特例|手続|給付|貸付|相談窓口|受付")


def breaking_ok(item: dict, kind: str = "") -> bool:
    """速報にしてよいか。ミサイル・災害（官公庁の発表）だけ。流出・リコール・詐欺は通常の記事（すぐ出すが【速報】にはしない）"""
    title = _nfkc(item.get("title") or "")
    if PROCEDURE_RE.search(title):
        return False  # 被災者の手続き・支援の案内は急ぎの速報ではない（2026-11-04 の初回で罹災証明の案内が速報になった）
    return (kind or item.get("kind")) == "gov" and category(title, "") in BREAKING_CATEGORIES


def done_today(state: dict, now: datetime | None = None) -> int:
    """今日（JST）公共性の枠で作った本数（processed_web の publicInterest の印）"""
    today = (now or datetime.now(JST)).astimezone(JST).date()
    n = 0
    for rec in (state.get("processed_web") or {}).values():
        if not isinstance(rec, dict) or not rec.get("publicInterest") or not rec.get("slug"):
            continue
        try:
            at = datetime.fromisoformat(str(rec.get("at") or ""))
        except ValueError:
            continue
        if (at if at.tzinfo else at.replace(tzinfo=timezone.utc)).astimezone(JST).date() == today:
            n += 1
    return n


# --------------------------------------------------------------------------- #
# Googleトレンドの合図（scripts/trends.py が state/trend_signals.json に書く。記事の出典にはしない）
# --------------------------------------------------------------------------- #
SIGNALS_PATH = ROOT / "state" / "trend_signals.json"


def load_signals(path: Path | None = None) -> list[dict]:
    try:
        items = list(json.loads((path or SIGNALS_PATH).read_text("utf-8")).get("items") or [])
    except (OSError, ValueError):
        return []
    # 芸能のうわさ・事件（犯罪）の話題は、公式の候補の順番を上げる合図に使わない（台帳 A63）
    return [s for s in items if isinstance(s, dict) and not s.get("gossip")]


# 2026-11-08（台帳 A63）: 検索の言葉は「ドコモ 情報流出 確認方法」のように複数の語で来る。語ごとに当てる
# （前は語句まるごとが題名に含まれるときだけ当たり、複数の語の検索はほぼ当たらなかった）
# 検索の言葉の中で、公式の題名に出てこない「調べ方」の語（当てるときは外す）
QUERY_FILLER = {
    "確認方法", "確認", "方法", "やり方", "いつ", "いつから", "いつまで", "なぜ", "理由", "原因", "対象", "対象者", "対象か",
    "最新", "最新情報", "速報", "今日", "今", "現在", "まとめ", "情報", "どこ", "何", "なに", "とは", "どうなる", "影響",
    "公式", "一覧", "状況", "見方", "調べ方", "わかる", "知る", "今後", "続報", "news", "ニュース",
}
# 同じものを指す言い方（どれか1つが題名か発信元にあれば当たり）
QUERY_ALIASES: dict[str, tuple[str, ...]] = {
    "ドコモ": ("ドコモ", "docomo", "NTTドコモ"),
    "docomo": ("ドコモ", "docomo"),
    "流出": ("流出", "漏えい", "漏洩", "漏れ"),
    "情報流出": ("流出", "漏えい", "漏洩"),
    "情報漏洩": ("流出", "漏えい", "漏洩"),
    "情報漏えい": ("流出", "漏えい", "漏洩"),
    "漏洩": ("流出", "漏えい", "漏洩"),
    "個人情報": ("個人情報", "お客さま情報", "お客様情報", "顧客情報", "会員情報"),
    "jma": ("気象庁",),
    "気象庁": ("気象庁",),
    "停電": ("停電",),
    "運休": ("運休", "運転見合わせ", "運転を見合わせ", "計画運休"),
    "遅延": ("遅延", "遅れ", "運転見合わせ"),
    "リコール": ("リコール", "回収"),
    "回収": ("リコール", "回収"),
    "値上げ": ("値上げ", "価格改定", "改定", "引き上げ"),
    "給付金": ("給付金", "給付"),
    "障害": ("障害", "つながりにくい", "繋がりにくい", "利用できない"),
    "通信障害": ("障害", "つながりにくい", "繋がりにくい"),
    "地震": ("地震", "震度"),
    "警報": ("警報", "警戒情報", "注意報"),
}


def query_terms(query: str) -> list[str]:
    """検索の言葉を、題名に当てる語に分ける（調べ方の語・1文字の語・年の数字は外す）"""
    words = [w for w in re.split(r"[\s　、,・/]+", _nfkc(query).strip()) if w]
    out = []
    for word in words:
        if word.lower() in QUERY_FILLER or word in QUERY_FILLER or re.fullmatch(r"(?:19|20)\d\d年?", word):
            continue
        if len(word) < 2:
            continue
        out.append(word)
    return out


LATIN_TERM_RE = re.compile(r"[\x20-\x7e]+")


def contains_term(term: str, text: str) -> bool:
    """語が文に出てくるか。英数字だけの語は、語の区切りで当てる（2026-11-13: 急上昇の「bet」が「Alphabet」に当たり、
    関係の無い AlphaGenome 2 の記事に急上昇の印が付いた）。日本語を含む語は今までどおり部分一致"""
    term = _nfkc(term).strip().lower()
    low = _nfkc(text).lower()
    if not term:
        return False
    if LATIN_TERM_RE.fullmatch(term):
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", low))
    return term in low


def _term_in(term: str, text: str) -> bool:
    for alt in QUERY_ALIASES.get(term.lower(), QUERY_ALIASES.get(term, (term,))):
        if contains_term(alt, text):
            return True
    return False


def trend_hit(title: str, signals: list[dict], source_name: str = "") -> dict | None:
    """公式の候補（題名と発信元の名前）が、いま検索で急上昇している話題に当たるか。当たればその合図。
    語が1つなら、その語（言い換えを含む）が題名か発信元にあること。2つ以上なら、全部の語が当たること
    （3つ以上なら1つ外れてもよい）。発信元の名前だけで当たる（題名に語が1つも無い）ものは数えない"""
    text = _nfkc(f"{title} {source_name}")
    head = _nfkc(title)
    for sig in signals:
        word = _nfkc(str(sig.get("title") or "")).strip()
        if len(word) >= 2 and contains_term(word, head):
            return sig  # 語句まるごと（前からの当て方。英数字だけの語は語の区切りで当てる）
        terms = query_terms(word)
        if not terms:
            continue
        hits = [t for t in terms if _term_in(t, text)]
        need = len(terms) if len(terms) <= 2 else len(terms) - 1
        if len(hits) >= need and any(_term_in(t, head) for t in hits):
            return sig
    return None


def search_title_note(query: str) -> str:
    """検索で急上昇している言葉に当たった候補の題名の書き方（台帳 A63。A60 の見出しの決まりの中で）"""
    return (
        "\n\n## 検索されている言葉（題名に使う）\n"
        f"- いま Google で「{query}」が急上昇しています。読者はこの言葉で調べてこの記事に来ます。\n"
        "- 題名に、この言葉の中心の語（会社名・地名・制度の名前など）を自然な日本語で入れる。"
        "例: 「ドコモ 情報流出 確認方法」→「ドコモの情報流出、自分が対象か確かめる方法は」。\n"
        "- 本文の最初の章で「自分は対象か・何をすればいいか」に資料の範囲で答える。資料で答えられない問いを題名にしない。\n"
        "- 強く目を引く題名にしてよいが、資料に無い事実・数字は書かない（うそをつかない）。「｜」は使わない。"
    )


PROMPT_NOTES = {
    "breach": "不正アクセス・情報漏えいの記事です。発表した組織・漏えいした可能性のある情報の種類と件数・発覚の日・対象者への連絡と問い合わせ先・"
              "読者が今できること（パスワードの変更・不審なメールへの注意など、資料にあるもの）を書く。",
    "missile": "ミサイル発射の記事です。発射の時刻・落下の推定地点・日本の領域や EEZ への飛来の有無・被害の確認状況・政府の指示を、"
               "防衛省・首相官邸の発表のとおりに書く。軍事の評価・今後の予想・外交の意見は書かない。",
    "disaster": "災害の記事です。被害の状況・自治体や国の支援・手続き（罹災証明の申請など）を発表のとおりに書く。被害の大きさを推測しない。",
    "recall": "リコール・製品事故の記事です。対象の製品名・型番・期間・台数・起きた事故・持っている人がすること（使用中止・無償修理の申し込み先）を書く。",
    "scam": "詐欺・なりすましの注意喚起の記事です。手口・被害の傾向（資料にある数字だけ）・見分け方・相談先（警察相談専用電話 #9110・消費者ホットライン 188 など資料にあるもの）を書く。",
    "money": "暮らしのお金の制度・料金の変更の記事です。何が・いつから・誰に・いくら変わるかと、自分の場合の確かめ方を書く。",
}


def prompt_note(cat: str) -> str:
    """公共性の枠の候補に足す書き方（事件・災害・政治。台帳 A39）"""
    return (
        "\n\n## 公共性の高いニュースの書き方（必ず守る）\n"
        f"- {PROMPT_NOTES.get(cat, '')}\n"
        "- 事実は資料（公式の発表）にあることだけ。報道・SNS の情報は書かない。推測・噂・「おそらく」は書かない。\n"
        "- 確かなこと（発表されたこと）と、まだ分かっていないこと（調査中・現時点では公表されていない）を分けて書く。\n"
        "- 私人の名前は書かない。煽る言葉（衝撃・恐怖・パニックなど）を使わず、落ち着いた報道の文体で書く。\n"
        "- 政治は中立に書く（政党・政権を評価しない）。\n"
        "- 未確定のことは「## まだ分からないこと」の章にまとめてよい（この章は見出しの数に数えない）。\n"
        "- 資料が短いときは短い記事でよい。資料に無い背景・一般論で水増ししない。"
    )


# --------------------------------------------------------------------------- #
# 5. どの経路の記事にも当てる門（台帳 A39）
# --------------------------------------------------------------------------- #
SENSATIONAL_RE = re.compile(r"衝撃|恐怖|戦慄|震撼|ヤバ[いイ]|緊迫の|パニック|大惨事|最悪の事態|一触即発|戦争前夜|絶望的|驚愕|閲覧注意")
# 推測の言い方（公式の「可能性があるもの」「推定」は発表の言葉なので許す）
SPECULATION_RE = re.compile(r"おそらく|と思われ|に違いない|ではないか(?:と|。)|憶測|噂では|うわさでは|と推測され|とささやかれ")
# 私人の実名（容疑者・被告の名前、「〇〇さん（34）」の形）
PRIVATE_NAME_RE = re.compile(
    r"[一-龥]{1,4}\s?[一-龥ぁ-ん]{1,4}(?:容疑者|被告(?:人)?|受刑者)|(?:容疑者|被告)\s?[（(]\d{1,3}[）)]|"
    r"[一-龥ぁ-んァ-ン]{1,6}さん\s?[（(]\d{1,3}(?:歳)?[）)]"
)
# 分かっていないことを書いた目印（流出・ミサイル・災害・詐欺の記事は、確かなことと未確定のことを分けて書く）
UNKNOWN_RE = re.compile(
    r"(?:分かって|わかって|明らかになって|明らかにして|確認されて|公表されて|発表されて|示されて)(?:い|おり)?(?:ません|ない)|"
    r"調査中|確認中|分析中|現時点で|現時点では|今後の調査|続報|未定"
)
UNKNOWN_CATEGORIES = ("breach", "missile", "disaster", "scam")
# 対策の手引き・相談先の案内（起きた事件の記事ではない）は「分かっていないこと」の区別を求めない
GUIDE_RE = re.compile(r"対策を公開|対処法|手引き|ガイド|チェックリスト|相談先を|見分け方|注意点を")
# 政治の意見（政党・政権を持ち上げる・攻める言葉）
POLITICAL_OPINION_RE = re.compile(r"暴挙|愚策|失政|弱腰|売国|英断|許しがたい|断じて許|無責任な政府|政府の怠慢|評価すべき|称賛に値")
# ミサイル・災害の記事に必ず置く公式の安全情報
SAFETY_LINKS = {
    "missile": [
        ("首相官邸（北朝鮮のミサイル発射など）", "https://www.kantei.go.jp/"),
        ("防衛省「北朝鮮のミサイル等関連情報」", "https://www.mod.go.jp/j/press/news/index.html"),
        ("内閣官房 国民保護ポータルサイト（弾道ミサイル落下時の行動）", "https://www.kokuminhogo.go.jp/"),
    ],
    "disaster": [
        ("気象庁 防災情報（警報・注意報・キキクル）", "https://www.jma.go.jp/bosai/"),
        ("首相官邸（災害・危機管理情報）", "https://www.kantei.go.jp/"),
        ("内閣府 防災情報のページ", "https://www.bousai.go.jp/"),
    ],
}
SAFETY_HOST_RE = re.compile(r"kantei\.go\.jp|mod\.go\.jp|kokuminhogo\.go\.jp|jma\.go\.jp|bousai\.go\.jp|fdma\.go\.jp")
SAFETY_MARK = "安全に関する公式情報"


def record_category(record: dict) -> str | None:
    """記事の公共性の種類。publicInterest の印（公共性の枠で作った記事）が先。
    印の無い記事（速報レーン・レーダー・書き直しなど別の経路）は題名で見る。ただしミサイル・災害以外は、事件の発表の形
    （発生・被害・判明・可能性・お詫び・注意喚起など）の題名だけ（「ランサムウェア対策の新機能」のような製品の記事を止めない）"""
    mark = record.get("publicInterest")
    if isinstance(mark, str) and mark in CATEGORY_RES:
        return mark
    title = str(record.get("title") or "")
    cat = category(title)
    if cat in ("missile", "disaster"):
        return cat if candidate_problem(title) is None else None
    if cat and INCIDENT_RE.search(_nfkc(title)) and not PRODUCT_RE.search(_nfkc(title)):
        return cat
    return None


def _prose(record: dict) -> str:
    parts = [str(record.get(k) or "") for k in ("title", "seoTitle", "lede", "body", "easy")]
    parts += [str(x) for x in (record.get("highlights") or [])]
    return "\n".join(parts)


def sensitive_problems(record: dict) -> list[str]:
    """公共性の高い話題・事件・政治の記事の門。どの経路の記事にも当てる（quality.every_path_problems）。
    当てはまらない記事（ふつうの製品の発表など）は、私人の実名と政治の意見だけを見る"""
    text = _nfkc(_prose(record))
    body = _nfkc(str(record.get("body") or ""))
    problems: list[str] = alcohol_problems(record)  # お酒の記事の注意書き（A56。公共性の話題でなくても見る）
    cat = record_category(record)
    if m := PRIVATE_NAME_RE.search(text):
        problems.append(f"私人の実名を書かない（「{m.group(0)[:20]}」）。事件・事故は会社・官公庁の発表の範囲で、個人を特定しない")
    if POLITICS_RE.search(text) and (m := POLITICAL_OPINION_RE.search(text)):
        problems.append(f"政治は中立に書く（政党・政権を評価する言葉「{m.group(0)}」を使わない）")
    if not cat:
        return problems
    if m := SENSATIONAL_RE.search(text):
        problems.append(f"不安を煽る言葉を使わない（「{m.group(0)}」）。起きたことと公式の発表を落ち着いて書く")
    if m := SPECULATION_RE.search(text):
        problems.append(f"推測で書かない（「{m.group(0)}」）。公式の発表にあることだけを書き、分からないことは分からないと書く")
    if cat in UNKNOWN_CATEGORIES and body and not GUIDE_RE.search(_nfkc(str(record.get("title") or ""))) and not UNKNOWN_RE.search(body):
        problems.append("確かなことと、まだ分かっていないこと（調査中・現時点では公表されていない など）を分けて書く")
    if cat in SAFETY_LINKS and not SAFETY_HOST_RE.search(body):
        problems.append("ミサイル・災害の記事は、本文に公式の安全情報（首相官邸・防衛省・国民保護ポータル・気象庁）へのリンクを置く")
    return problems


# --------------------------------------------------------------------------- #
# 6. 公式の安全情報のリンクを決まった形で入れる
# --------------------------------------------------------------------------- #
def safety_block(cat: str) -> str:
    links = "・".join(f"[{name}]({url})" for name, url in SAFETY_LINKS[cat])
    return f"> {SAFETY_MARK}: {links}"


def autofix(record: dict) -> list[str]:
    """ミサイル・災害の記事の本文の頭に、公式の安全情報のリンクを入れる（すでにあれば何もしない）。行ったことの説明を返す。
    お酒の記事には本文の終わりに決まった注意書きを入れる（A56）"""
    done = alcohol_autofix(record)
    cat = record_category(record)
    if cat not in SAFETY_LINKS:
        return done
    body = str(record.get("body") or "")
    if SAFETY_MARK in body:
        return done
    record["body"] = f"{safety_block(cat)}\n\n{body}" if body else safety_block(cat)
    return done + [f"公式の安全情報のリンクを本文の頭に入れた（{cat}）"]


# --------------------------------------------------------------------------- #
# 7. 検索に出す主題（indexnow.is_focus・lib/indexing.ts。lib/index-rules.json に書き出す）
# --------------------------------------------------------------------------- #
# 公共性の話題を主題に入れるジャンル（社会・行政／暮らし／テクノロジー・ガジェット／ビジネス）
FOCUS_GENRES = ("public", "lifestyle", "tech-gadget", "business")
FOCUS_TOPIC_RE = re.compile("|".join(f"(?:{p.pattern})" for p in CATEGORY_RES.values()))


# ミサイル・災害の記事は公式の発表そのものが短い（防衛省の続報は700字ほど）。水増しせずに出せるよう、本文の下限を下げる
# （地震・津波の型の記事 disaster と同じ考え）。2026-11-04 オーナー承認（台帳 A10）で、速報（breaking・種類 breaking）と
# お知らせ・注意喚起（障害・サービス停止・緊急の更新・詐欺の注意喚起など）にも広げた。ほかの種類は通常の下限 indexnow.THIN_BODY のまま
SHORT_BODY = int(RULES["short_body"])
SHORT_TOPIC_RE = re.compile(f"(?:{CATEGORY_RES['missile'].pattern})|(?:{CATEGORY_RES['disaster'].pattern})")
# お知らせ・注意喚起の題名（ジャンルを問わない）。お知らせ・統計の書き写し（A26・notice_gate）は別の門で止める
SHORT_NOTICE_RE = re.compile(
    f"(?:{CATEGORY_RES['scam'].pattern})|"
    r"注意喚起|お知らせ|障害(?!者)|不具合|つながりにくい|サービス(?:の)?(?:停止|中断)|緊急(?:メンテナンス|の)?(?:更新|アップデート|パッチ|メンテナンス)|"
    r"ゼロデイ|悪用(?:が確認|された|の報告)"
)


def incident_short(article: dict) -> bool:
    """事故の見張り（scripts/incident_watch.py・台帳 W44）が見つけた会社自身のお知らせから作った記事か（記事の incident の印。
    速報レーンが付ける）。回収・情報流出のお知らせは短くても対象・窓口・やることがそろっているので、この経路の記事だけ
    本文の下限を SHORT_BODY（800字）にする（2026-11-14 オーナー承認）。印の無い記事（ほかの経路）は今までどおり"""
    incident = article.get("incident")
    return isinstance(incident, dict) and bool(incident.get("kind"))


def short_ok(article: dict) -> bool:
    """本文の下限を SHORT_BODY（800字）に下げてよい記事か。lib/indexing.ts の isShortArticle と同じ。
    速報（breaking が真か、種類が breaking）／お知らせ・注意喚起の題名／ミサイル・災害の題名（公共性のジャンル）／
    事故の見張りの記事（incident_short。サイト側の isShortArticle は robots に使わない説明用で、この印は見ない）"""
    if article.get("breaking") is True or (article.get("newsType") or "") == "breaking":
        return True
    if incident_short(article):
        return True
    head = _nfkc(f"{article.get('title', '')} {article.get('seoTitle', '')}")
    if SHORT_NOTICE_RE.search(head):
        return True
    if (article.get("genreSlug") or "") not in FOCUS_GENRES:
        return False
    return bool(SHORT_TOPIC_RE.search(head))


def focus_topic(article: dict) -> bool:
    """公共性の高い話題の記事か（検索に出す主題に入れる。lib/indexing.ts の isPublicInterest と同じ）。
    2026-11-07 から、広げた暮らしの話題（wide_category。題名だけで見る）も入れる"""
    if (article.get("genreSlug") or "") not in FOCUS_GENRES:
        return False
    text = _nfkc(f"{article.get('title', '')} {article.get('seoTitle', '')} {' '.join(article.get('tags') or [])}")
    if FOCUS_TOPIC_RE.search(text):
        return True
    head = f"{article.get('title', '')} {article.get('seoTitle', '')}"
    return wide_category(head, str(article.get("channelSlug") or "")) is not None


# --------------------------------------------------------------------------- #
# 8. 拾う話題を広げる（2026-11-07 オーナー「広めていいよ」・台帳 A56）
# --------------------------------------------------------------------------- #
# 日本で多くの人が気にする暮らしの話題を、主題外として捨てずに拾う（生成前の足切り indexnow.candidate_off_focus と
# 検索に出す主題 focus_topic の両方。lib/index-rules.json で lib/indexing.ts にも同じ値を渡す）。
# 公共性の枠（CATEGORY_RES・1日の本数・速報）には入れない。品質の門（本文の下限・事実確認・お知らせの転載）は変えない。
# 2026-11-08 オーナー決定（台帳 A23）: 事故・災害は暮らしの安全として扱う。芸能はお金・暮らし（値段・チケット・発売・配信・サービス）に
# 関係するときだけ（ゴシップの語は外す）。事件（犯罪）・不祥事は対象外のまま（WIDE_EXCLUDE_RE）。題名だけで判定する（概要の一言で当たらないように）
WIDE_TOPIC_RES: dict[str, re.Pattern] = {
    # 交通（鉄道の運休・遅延・運賃・ダイヤ改正、航空の欠航、道路の通行止め・規制・高速料金）
    "transport": re.compile(
        r"計画運休|運休|運転(?:を)?見合わせ|運転(?:を)?再開|列車の遅れ|大幅な遅れ|遅延|ダイヤ(?:改正|変更|乱れ)|臨時列車|終電(?:の)?(?:繰り上げ|繰上げ|延長)|"
        r"運賃|乗車券|定期券|きっぷ|新幹線.{0,12}(?:増発|臨時|運休|遅れ|運転|指定席|料金|予約)|廃線|(?:路線)?バス.{0,6}(?:減便|廃止|運休|路線)|"
        r"欠航|減便|増便|運航(?:を)?(?:停止|見合わせ|休止|再開)|"
        r"通行止|通行規制|交通規制|チェーン規制|冬用タイヤ|渋滞(?:予測|予想)|高速(?:道路)?(?:の)?料金|ETC.{0,8}割引|深夜割引|休日割引"
    ),
    # 感染症の流行（インフルエンザ・ノロ・感染性胃腸炎・麻しんなど）と鳥インフルエンザ・豚熱（2026-11-07 オーナー承認の追加・A56）。
    # 厚労省・国立健康危機管理研究機構・農水省・自治体の公式の発表。病気が治る・効くといった医療効果の主張は扱わない話題で落とす（web_articles.HARD_EXCLUDE_RE）
    "health": re.compile(
        r"インフルエンザ|ノロウイルス|感染性胃腸炎|感染症.{0,10}(?:流行|発生|注意|警報|動向)|流行(?:警報|注意報)|集団感染|"
        r"麻しん|麻疹|はしか|風しん|百日せき|百日咳|手足口病|RSウイルス|溶連菌|マイコプラズマ|新型コロナ|食中毒|豚熱|口蹄疫|家畜伝染病"
    ),
    # 天気（気象庁の警報・注意報・台風・大雪・猛暑・寒波・花粉・季節の予報）。地震・津波の発生そのものは scripts/quake.py の型だけ（A15）
    "weather": re.compile(
        r"警報(?!器|機|装置)|注意報|台風|大雪|豪雪|暴風|猛暑|酷暑|熱中症(?:警戒|特別警戒|に注意|の予防)|寒波|強い寒気|"
        r"低温(?:に関する|に注意)|高温(?:に関する|に注意)|早期天候情報|季節予報|[13１３]か月予報|暖候期|寒候期|梅雨(?:入り|明け)|"
        r"花粉|黄砂|竜巻|落雷|積雪|降雪|雪崩|なだれ|天気|気象情報|桜の開花|紅葉の見頃"
    ),
    # 暮らしの値上げ・料金改定（電気・ガス・郵便・食品メーカー・通信など）
    "price": re.compile(
        r"値上げ|値下げ|価格改定|料金改定|(?:料金|価格|運賃|送料)(?:を|の)?(?:一部)?(?:改定|引き上げ|引き下げ|変更)|出荷価格|希望小売価格|"
        r"有料化|無料化|手数料(?:を)?(?:改定|引き上げ|引き下げ|新設|無料)|電気料金|電気代|ガス料金|燃料費調整|郵便料金"
    ),
    # サービスの終了（提供・販売・サポートの終了、受付の停止）
    "service-end": re.compile(
        r"サービス(?:の)?終了|提供(?:を)?終了|サポート(?:を)?終了|販売(?:を)?終了|受付(?:を)?終了|新規受付(?:を)?(?:停止|終了)|"
        r"終了のお知らせ|打ち切り|(?:サービス|アプリ|プラン)(?:の)?廃止"
    ),
    # 障害（携帯キャリア・銀行・決済・クラウド・電気・水道）と復旧
    "outage": re.compile(
        r"通信障害|システム障害|サービス障害|大規模障害|障害(?!者)(?:が|の)?(?:発生|復旧|について|に関する|に関して|のお知らせ|のお詫び|のおわび)|"
        r"【復旧】|復旧(?:しました|のお知らせ)|つながりにくい|繋がりにくい|つながらない|ログインできない|利用できない(?:状態|事象)|"
        r"決済(?:が)?できない|不具合(?:が発生|の発生|により|のお知らせ|について)|サービス(?:の)?(?:停止|中断|一時停止)|停電|断水|"
        r"通話.{0,6}(?:できない|しづらい)"
    ),
    # 自治体・国の給付・補助・助成（手当・商品券・無償化・減免）
    "benefit": re.compile(
        r"給付|補助|助成|支援金|手当|商品券|プレミアム付|無償化|減免|奨学|子育て支援|物価高(?:騰)?対策|生活支援"
    ),
}
# 新商品・発売（コンビニ・外食・家電・スマホ・食品メーカー）。「発売」の語だけでは広すぎるので、対象の業態・製品の語か、その発信元の発表に限る
LAUNCH_RE = re.compile(r"新発売|発売|販売開始|新商品|新メニュー|新製品|新フレーバー|新味|予約(?:受付)?開始|先行販売|期間限定|数量限定|登場")
LAUNCH_CONTEXT_RE = re.compile(
    r"コンビニ|ローソン|ファミリーマート|ファミマ|セブン[-‐ー－]?イレブン|ミニストップ|外食|マクドナルド|マック|モスバーガー|ケンタッキー|"
    r"すき家|吉野家|松屋|スターバックス|スタバ|ミスタードーナツ|ミスド|サイゼリヤ|ガスト|くら寿司|スシロー|はま寿司|丸亀製麺|コメダ|"
    r"家電|冷蔵庫|洗濯機|エアコン|テレビ|掃除機|炊飯器|電子レンジ|ドライヤー|イヤホン|ヘッドホン|"
    r"スマホ|スマートフォン|iPhone|iPad|Android|Galaxy|Xperia|AQUOS|Pixel|arrows|タブレット|スマートウォッチ|"
    # 食品メーカーの新商品・新フレーバー（2026-11-07 オーナー承認の追加・A56）
    r"カップ麺|即席麺|カップヌードル|ポテトチップス|ポテトチップ|スナック|チョコレート|アイス|グミ|ヨーグルト|チューハイ|ビール|ノンアルコール|清涼飲料"
)
# 発表そのものがコンビニ・外食・家電・スマホの会社の公式の発信元（scripts/feeds.py の slug）
LAUNCH_SOURCES = (
    "lawson", "familymart", "sharp", "sony-jp", "samsung-jp", "apple-newsroom-jp-all", "google-japan-blog-all",
    "docomo-product", "au-topics", "softbank-news", "kddi-news",
    # 食品メーカーの公式の発表（2026-11-07 オーナー承認の追加・A56: 単品の新商品・新フレーバーも拾う）
    "nissin", "kewpie", "house-foods", "nipponham", "kirin", "suntory", "meiji", "morinaga", "yamazaki",
    "asahi", "morinaga-milk", "megmilk", "fujiya",
)
# 広げた話題でも扱わないもの（事件〔犯罪〕・不祥事・芸能のゴシップ。2026-11-08 オーナー決定・台帳 A23 で事故・災害と芸能のお金・暮らしの話は外した）
WIDE_EXCLUDE_RE = re.compile(
    r"事件|逮捕|容疑|送検|起訴|判決|"
    r"不祥事|不適切(?:な|事案)|改ざん|隠蔽|隠ぺい|横領|着服|懲戒|ハラスメント|パワハラ|セクハラ|謝罪会見|"
    r"熱愛|交際|結婚|離婚|不倫|妊娠|出産|活動休止|"
    # 医療効果の主張（感染症の話題を足しても扱わない）
    r"治る|治療効果|完治|特効|効く|予防効果|"
    # 鳥インフルエンザの検査で陰性だった報告（読者に影響が無い）
    r"陰性確定"
)
# 化粧品・健康食品・サプリは発売の話題に入れない（効能の主張が薬機法・AdSense の心配になる。2026-11-07 11:30 オーナー決定・A56）
LAUNCH_EXCLUDE_RE = re.compile(
    r"化粧品|コスメ|スキンケア|化粧水|美容液|乳液|美容|美肌|エイジング|ファンデーション|日焼け止め|"
    r"サプリ|サプリメント|機能性表示食品|特定保健用食品|トクホ|健康食品|栄養機能食品|薬膳|"
    r"ビフィズス菌|乳酸菌|腸活|睡眠の質|免疫|血圧|血糖|体脂肪|内臓脂肪|プロテイン"
)
# 障害の語を含むが障害のお知らせではないもの（障害対応の製品・研究・訓練）
WIDE_NOT_OUTAGE_RE = re.compile(r"障害対応|自動復旧|復旧ツール|障害を(?:自動|予測|検知)|デモ|脆弱性|ツール|エージェント|研究|調査|訓練|演習")


def wide_category(title: str, source_slug: str = "") -> str | None:
    """題名が広げた暮らしの話題のどれに当たるか（transport / weather / price / service-end / outage / benefit / launch）。
    当たらない・扱わない話題（事件〔犯罪〕・不祥事・ゴシップ）なら None。lib/indexing.ts の wideCategory と同じ"""
    text = _nfkc(title)
    if not text or WIDE_EXCLUDE_RE.search(text):
        return None
    for name, pattern in WIDE_TOPIC_RES.items():
        if pattern.search(text):
            if name == "outage" and WIDE_NOT_OUTAGE_RE.search(text):
                continue
            return name
    if LAUNCH_RE.search(text) and not LAUNCH_EXCLUDE_RE.search(text) and (LAUNCH_CONTEXT_RE.search(text) or source_slug in LAUNCH_SOURCES):
        return "launch"
    return None


# --------------------------------------------------------------------------- #
# 9. お酒の新商品の記事（2026-11-07 11:30 オーナー決定・A56）
# --------------------------------------------------------------------------- #
# お酒の新商品は製品のニュースとして書いてよい。飲むことをすすめない。どの記事にも決まった注意書きを入れる（autofix が入れ、sensitive_problems が確かめる）
ALCOHOL_RE = re.compile(
    r"ビール|発泡酒|チューハイ|酎ハイ|ハイボール|ウイスキー|ウィスキー|ワイン|日本酒|焼酎|サワー(?!クリーム)|梅酒|シードル|テキーラ|リキュール|"
    r"(?<![ァ-ヶー])ジン(?![ァ-ヶー])|ラム酒|ウォッカ|スピリッツ|清酒|地酒|蒸留酒|醸造酒|缶酎|酒類|お酒|アルコール度数|"
    # 題名にお酒の語が無いことの多い主なブランド
    r"スーパードライ|一番搾り|プレミアム・?モルツ|プレモル|黒ラベル|ヱビス|エビスビール|氷結|[-－]196|ストロングゼロ|ほろよい|角ハイ|贅沢搾り|梅星屋|ザ・ビタリスト|翠ジン"
)
# ノンアルコールだけの商品はお酒ではない（「のんある酒場」「ノンアルコールビール」など）
NON_ALCOHOL_RE = re.compile(r"ノンアルコール|ノンアル|のんある|アルコール\s*0|アルコールゼロ|0\.00\s*%")
ALCOHOL_NOTE = "お酒は20歳になってから。飲酒運転は法律で禁止されています。"
ALCOHOL_NOTE_RE = re.compile(r"20歳.{0,12}(?:から|未満)[\s\S]{0,60}飲酒運転|飲酒運転[\s\S]{0,60}20歳")
# 飲むことをすすめる言い方
ALCOHOL_PUSH_RE = re.compile(r"一気飲み|飲み過ぎても|飲みすぎても|どんどん飲|たくさん飲(?:もう|んで|みたい)|飲まなきゃ損|飲むべき|ぐいぐい|浴びるほど|酔っ払お")


def is_alcohol(record: dict) -> bool:
    """お酒の記事か（題名・SEO 題名・リード・タグで見る。ノンアルコールだけの商品は除く）"""
    head = _nfkc(f"{record.get('title', '')} {record.get('seoTitle', '')} {record.get('lede', '')} {' '.join(record.get('tags') or [])}")
    if not ALCOHOL_RE.search(head):
        return False
    return not NON_ALCOHOL_RE.search(head)  # ノンアルコールの商品の題名は、お酒の語（ビール・サワー）を含んでもお酒ではない


def alcohol_problems(record: dict) -> list[str]:
    """お酒の記事の門: 決まった注意書き（20歳から・飲酒運転の禁止）があるか、飲むことをすすめていないか"""
    if not is_alcohol(record):
        return []
    problems = []
    body = _nfkc(str(record.get("body") or ""))
    if body and not ALCOHOL_NOTE_RE.search(body):
        problems.append(f"お酒の記事は本文に注意書き「{ALCOHOL_NOTE}」を入れる")
    if m := ALCOHOL_PUSH_RE.search(_nfkc(_prose(record))):
        problems.append(f"お酒を飲むことをすすめない（「{m.group(0)}」）。製品のニュースとして書く")
    return problems


def alcohol_autofix(record: dict) -> list[str]:
    """お酒の記事の本文の終わりに決まった注意書きを入れる（すでにあれば何もしない）"""
    if not is_alcohol(record):
        return []
    body = str(record.get("body") or "")
    if ALCOHOL_NOTE_RE.search(_nfkc(body)):
        return []
    record["body"] = f"{body.rstrip()}\n\n> {ALCOHOL_NOTE}" if body else f"> {ALCOHOL_NOTE}"
    return ["お酒の記事の注意書きを本文の終わりに入れた"]


ALCOHOL_PROMPT_NOTE = (
    "\n\n## お酒の新商品の書き方（必ず守る）\n"
    "- 製品のニュースとして、発売日・価格・容量・アルコール度数・販売地域など発表にある事実だけを書く。\n"
    "- 飲むことをすすめない（「たくさん飲もう」「飲まなきゃ損」などを書かない）。飲酒の効果・健康によいとは書かない。\n"
    f"- 本文の終わりに「{ALCOHOL_NOTE}」を1行で入れる。"
)


def alcohol_prompt_note(title: str) -> str:
    return ALCOHOL_PROMPT_NOTE if is_alcohol({"title": title}) else ""


WIDE_TOPIC_RE = re.compile("|".join(f"(?:{p.pattern})" for p in WIDE_TOPIC_RES.values()))
