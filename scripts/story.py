#!/usr/bin/env python3
"""同じ発表（同じ話題）の記事を見分ける判定と、重複記事への印付け（duplicateOf）。

サイト（lib/indexing.ts・lib/article-index.mjs）と IndexNow（scripts/indexnow.py）は、ここで記事 JSON に書いた
duplicateOf を読むだけにする（判定を TypeScript と Python で二重に持たない）。

同じ話題とみなす条件（どれか1つ。比べるのは「サイソクに載せた時刻」か「元の発表の時刻」が5日以内の記事だけ）:
  1. 出典 URL が同じ（クエリ・utm・末尾の /・www・言語の段（/ja-jp/ など）を除いて比べる。
     openai.com/blog/X → /index/X のような既知の転送も同じにする。YouTube は動画 ID で比べる）で、切り口も同じ
     （2026-11-13: 題名の類似度 0.3 以上か keywords の重なり 0.3 以上。同じ公式のページから別のことを書いた記事
     〔医療費控除の「明細書の書き方」と「10万円の壁」、NVIDIA の「CEO退任」と「決算は11月18日」〕は重複にしない。
     生成前の候補の確認（candidate=True）は今までどおり出典 URL だけで見る＝同じ発表から自動でもう1本作らない）
  0. 題名の中心の日付が食い違う記事（「決算は11月18日」と「17日に退任」のように、両方の題名に日付があり1つも合わない）は、
     出典・会社・製品名が同じでも別の出来事として扱う（題名がまったく同じ・ほぼ同じ〔類似度 0.6 以上〕ときを除く）
  2. 正規化した題名が同じ
  3. 同じ会社（radar の entities）で、
     a. 題名に同じ「名前＋版数」の製品名（genie4・gemini4carbon など）がある
     b. 日本語の題名に英字のまま同じ珍しい固有名詞（Legora・Zendesk など。全記事で6本以下にしか出てこない語）がある
     c. 同じ発信元が6時間以内に出し、題名に同じ珍しい固有名詞がある（1つの事例を何本にも分けた公開。題名か keywords の重なり 0.2 以上）
     d. 日本語の題名の文字バイグラムの類似度が 0.6 以上、または元の題名（動画・元記事）がまったく同じ
  4. 同じ発信元（channelSlug か出典のホスト）が12時間以内に出した同じジャンルの記事で、題名の類似度 0.3 以上かつ keywords の重なり 0.3 以上
     （日本語だけの題名で珍しい英字の固有名詞が無いもの。例: 国交省の「秋の叙勲」と「秋の褒章」、同じ機能のデモ動画の続き。2026-11-03）。
     題名の英字の語が両方に「相手に無い語」を持つとき（MacBook Pro と iMac）は別の製品なので同じ話題にしない。
     元の題名が両方あるときは、それも似ていること（類似度 0.45 以上。同じ製品のデモ動画の別の回は重複にしない）
     会社が両方わかっていて1社も重ならないとき・ジャンルが違うときは同じ話題にしない。
     製品名は「名前＋版数＋名前」をひとまとめにする（GPT-6 Astra と GPT-6 Sol は別。PS5 のような短い型番は数えない）。
     a は題名か keywords も似ていること（類似度 0.15 以上か keywords の重なり 0.3 以上）、
     b は類似度 0.35 以上か（0.2 以上かつ keywords の重なり 0.3 以上）。
同じ話題でも重複にしないもの（意図して角度を変えた解説）:
  - angleOf が付いた記事（scripts/angle_articles.py が付ける）
  - 後の記事が先の記事にリンク（relatedSlugs と本文の /articles/<slug>）し、題名が解説の形（使い方・比較・違い・誰が使える 等）
同じ話題でも重複にしないもの（2026-11-09 オーナー承認・台帳 A68「同じ発表の重複」ではなく「同じ疑問の重複」でまとめる）:
  - 記事の役割（page_role: とは・料金/プラン・比較・使い方・ニュース）が違う記事。同じ発表でも「〜とは」「料金・プラン」「〜と比較」
    「使い方」は別の疑問で、それぞれ検索で1位を取れていた（11/3 に Terra・Sol・Astra の比較とプラン別の記事を発表の記事へまとめ、
    1位の検索語を失った）。役割ごとに1本だけ残し（同じ役割どうしは今までどおり重複）、mark が互いに関連記事（relatedSlugs）で結ぶ。
  - 2026-11-10（台帳 A71）: 読者がやることのガイド（家族の分・対象の確かめ方・やること。題名か、本文の見出しの3本以上で見る）も
    別の役割。ドコモの流出で「今日やるのは明細とdアカウントの確認」「家族の回線はどうなる」が発表の記事の重複にされ、
    前日いちばん読まれた記事が検索から外れていた。役割の違う同じ出典の記事には mark が angleOf を付ける（予備の判定から外す）。
代表（canonical）: 同じ話題のうち、ほかの理由で検索から外れない記事の中でいちばん強いページ（2026-11-13 オーナー「とにかく数字」）:
  検索に表示があった記事（scripts/search_protected.py。台帳 A46・A68）→ Muse が書いた記事（writer == "muse"）→ 本文が長い → 出典が多い → 新しい の順（keeper_rank）。先に載せただけの薄い自動記事を代表にしない。
  手動で indexable: true にした記事は代表にし、印を付けない。まとめ記事（roundup）・地震の記事は対象外。
一度付けた duplicateOf は、--recompute を付けない限り外さない（検索のページが揺れないように）。ただし代表が入れ替わったとき
（新しく強い記事ができた）は、新しい代表の印を外し、前の代表を指していた印を新しい代表へ付け替える（canonical を重複の記事へ向けない）。

  python3 scripts/story.py mark --dry-run        # 全記事を調べて、付ける印を表示するだけ
  python3 scripts/story.py mark                  # 印を付ける（直近 --days 日に載せた記事だけ見直す。0=全記事）
  python3 scripts/story.py mark --days 14 --recompute   # 直近14日に載せた記事の印だけ付け直す（外れたものは消す。手で付けた印は残す）
  python3 scripts/story.py check "題名" [--url URL] [--keywords a,b]   # 候補が直近5日の記事と同じ話題か
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dedupe  # noqa: E402
import radar  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "content" / "articles"
WINDOW = timedelta(days=5)
RARE_DF = 6
SIM_STRONG = 0.6
SIM_WITH_TOKEN = 0.2
SIM_RARE = 0.35
KW_OVERLAP = 0.3
# 1. 出典 URL が同じ記事を「切り口も同じ」とみなす題名の類似度・keywords の重なり（2026-11-13。同じ出典の記事 47 組を見て決めた:
# 別の切り口の記事は題名 0.03〜0.29、同じ発表の言い換えは 0.31・0.43）
SAME_URL_SIM = 0.3
SAME_URL_KW = 0.3
# 4. 同じ発信元が近い時刻に出した似た記事
SAME_PUBLISHER_GAP = timedelta(hours=12)
SAME_PUBLISHER_SIM = 0.3
SAME_PUBLISHER_KW = 0.3
SAME_PUBLISHER_SOURCE_SIM = 0.45
# 解説の形の題名（角度を変えた記事の目印。これだけでは重複を外さない。先の記事へのリンクも要る）
EXPLAINER_RE = re.compile(r"使い方|比較|違い|選び方|誰が使える|使える？|とは[？?]|始め方|できること|料金.*(整理|まとめ)|プラン別|解説|徹底|まとめ|FAQ|Q&A")
LOCALE_SEG = re.compile(r"^(?:[a-z]{2}(?:[-_][a-z]{2,4})?|intl)$", re.I)
KNOWN_LOCALES = {"ja", "jp", "ja-jp", "ja_jp", "en", "en-us", "en_us", "en-gb", "us", "intl", "global"}
# 記事の役割（答える疑問の種類）。題名だけで見る（本文の言い回しでは決めない）。上から順に当てる
ROLE_PATTERNS = (
    ("about", re.compile(r"^.{0,40}?とは(?:[？?\s　、]|$)")),
    ("compare", re.compile(r"比較|違い|どっち|どれを選ぶ|選び方|(?<![A-Za-z])vs\.?(?![A-Za-z])|と比べ", re.I)),
    ("pricing", re.compile(r"料金(?:プラン|体系|表|一覧|と使い方|・プラン)|プラン別|どのプラン|誰が使える|使えるのは誰|いくらかかる|料金.{0,8}(?:整理|まとめ)")),
    ("howto", re.compile(r"使い方|始め方|使うには|設定方法|導入手順|手順を解説|やり方|申し込み方|申請方法")),
    # 2026-11-10（台帳 A71）: 発表の記事とは別の疑問に答える「読者がやること」のガイド。同じ出典でも重複にしない
    # （ドコモの流出の「今日やるのは明細とdアカウントの確認」が発表の記事の重複にされ、前日いちばん読まれた記事が検索から外れていた）
    ("family", re.compile(r"家族の(?:回線|分|契約|確認)|家族(?:は|も)対象|子ども(?:の回線|名義)|親名義|法定代理人")),
    ("eligibility", re.compile(r"対象(?:か(?:どうか)?[？?\s　、のをはがも]|かどうか|になる(?:か|人)|の確かめ方|者の確かめ方)|(?:自分|あなた|わが家)は対象|確かめ方|調べ方|見分け方|要確認")),
    # 月・週の発表のまとめ（Google の「10月のAI発表」など）は、まとめに入った1つの製品の記事とは別の疑問（台帳 A71）
    ("recap", re.compile(r"(?:[0-9０-９]{1,2}月|今月|先月|今週|先週|月間|週間)の.{0,15}(?:発表|ニュース|アップデート|新機能).{0,10}(?:まとめ|総括|一覧)")),
    ("action", re.compile(r"やること|やるべき|やるのは|すべきこと|すること[はを]|今すぐ(?:確認|変更|やる)|対処法|対処の仕方|備え方|手続き(?:方法|の仕方|の流れ)|確認(?:方法|の仕方|ポイント|すべき)|どうすれば|何をすれば|注意点")),
)
GUIDE_ROLES = ("family", "eligibility", "action")
# 題名がニュースの形でも、本文の見出しの多くが読者の疑問・行動に答えるガイドの記事（見出しで役割を決める）
GUIDE_HEADS = {
    "family": re.compile(r"家族|子ども|子供|親名義|法定代理人|未成年"),
    "eligibility": re.compile(r"対象(?:か|になる|かどうか)|確かめ|調べ|見分け|ですか[？?]?$|ますか[？?]?$"),
    "action": re.compile(r"やること|何をする|まず何|取る行動|状況別|備え|対処|入力してしまったら|手続き(?:の|を)"),
}
GUIDE_HEAD_MIN = 3
HEADING_RE = re.compile(r"^#{2,3}\s*(.+?)\s*$", re.M)
ROLE_LABELS = {"about": "とは", "compare": "比較", "pricing": "料金・プラン", "howto": "使い方", "news": "ニュース",
               "family": "家族の分", "eligibility": "対象の確かめ方", "action": "やること", "recap": "月・週のまとめ"}
YOUTUBE_RE = re.compile(r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|live/|embed/)|youtu\.be/)([A-Za-z0-9_-]{11})")


# --------------------------------------------------------------------------- #
# 出典 URL
# --------------------------------------------------------------------------- #


def url_keys(url: str) -> set[str]:
    """同じページとみなす鍵。クエリ（utm など）・末尾の /・www・言語の段を落とす。
    #entry-YYYY-MM-DD（scripts/page_watch.py が付けるリリースノートの1項目）だけは残す"""
    url = str(url or "").strip()
    if not url:
        return set()
    m = YOUTUBE_RE.search(url)
    if m:
        return {f"yt:{m.group(1)}"}
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return set()
    host = parts.netloc.lower().removeprefix("www.")
    if not host:
        return set()
    segs = [s for s in parts.path.split("/") if s]
    while segs and segs[0].lower() in KNOWN_LOCALES:
        segs = segs[1:]
    if host == "openai.com" and segs[:1] == ["blog"]:
        segs = ["index", *segs[1:]]
    frag = parts.fragment if parts.fragment.startswith("entry-") else ""
    path = "/".join(segs).lower()
    # 毎月同じ URL に上書きされる資料（家計調査など）は ?period= で月を分けている。月が違えば別のページ（SEO A10）
    period = urllib.parse.parse_qs(parts.query).get("period", [""])[0].lower()
    keys = {f"{host}/{path}" + (f"?period={period}" if period else "") + (f"#{frag}" if frag else "")}
    last = segs[-1].lower() if segs else ""
    if not frag and not period and len(last) >= 12 and re.search(r"[a-z]-[a-z0-9]", last):
        keys.add(f"{host}|{last}")
    return keys


# --------------------------------------------------------------------------- #
# 記事の手がかり
# --------------------------------------------------------------------------- #


def _time(value) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def title_key(title: str) -> str:
    return dedupe.normalize(title)


class Story:
    """記事（または候補）1本ぶんの手がかり"""

    __slots__ = ("slug", "title", "head_titles", "gen", "src", "keys", "ents", "head", "tokens", "products", "latin", "kw", "genre", "sources", "data",
                 "role")

    def __init__(self, data: dict) -> None:
        self.data = data
        self.slug = str(data.get("slug") or "")
        self.title = str(data.get("title") or "")
        heads = [self.title]
        for k in ("videoTitle", "originalTitle"):
            v = str(data.get(k) or "")
            if v and v not in heads and not v.startswith("YouTube video "):
                heads.append(v)
        self.head_titles = heads
        # 元の題名（動画・元記事）。題名と同じでも残す（同じ動画の再投稿を見分ける）
        self.sources = [str(data.get(k)) for k in ("videoTitle", "originalTitle") if data.get(k) and not str(data.get(k)).startswith("YouTube video ")]
        self.gen = _time(data.get("generatedAt")) or _time(data.get("publishedAt"))
        self.src = _time(data.get("sourcePublishedAt")) or _time(data.get("publishedAt")) or self.gen
        keys: set[str] = set()
        keys |= url_keys(str(data.get("sourceUrl") or ""))
        if data.get("videoId"):
            keys.add(f"yt:{data['videoId']}")
        for u in data.get("updates") or []:
            if isinstance(u, dict) and u.get("sourceUrl"):
                keys |= url_keys(str(u["sourceUrl"]))
        self.keys = keys
        keywords = [str(k) for k in (data.get("keywords") or [])][:10]
        text = " | ".join(heads + keywords + [str(data.get("channel") or ""), str(data.get("sourceName") or "")])
        self.ents = set(radar.entities_of(text))
        head: set[str] = set()
        for h in heads:
            head |= radar.features(h, strong=True)
        self.head = head
        self.tokens = head | radar.features(" | ".join(keywords), strong=True)
        self.products = set()
        for h in heads:
            self.products |= product_tokens(h)
        # 日本語の題名に英字のまま残った語（固有名詞。一般語は訳されるので残りにくい）
        self.kw = {dedupe.normalize(k) for k in keywords if k}
        self.genre = str(data.get("genreSlug") or "")
        self.latin = {t for t in radar.features(self.title, strong=True) if t.isascii() and t.isalpha() and len(t) >= 4}
        self.role = article_role(data)


COMPOUND_RE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z][A-Za-z]+)[ \-]?(\d+(?:\.\d+)?)[ \-]([A-Z][A-Za-z]{2,})")
YEARISH_RE = re.compile(r"(?:19|20)\d\d$|^(?:top|in|no|vol|ep|part|sj|q|fy)\d")


def product_tokens(title: str) -> set[str]:
    """題名の製品名（「名前＋版数」。後ろに名前が続けば3語でひとまとめ: GPT-6 Astra → gpt6astra）。
    名前が続くものは版数だけ（gpt6）では数えない（GPT-6 Astra と GPT-6 Sol を同じにしない）"""
    t = unicodedata.normalize("NFKC", title or "")
    out: set[str] = set()
    compound_heads: set[str] = set()
    for m in COMPOUND_RE.finditer(t):
        alpha, num, word = m.group(1).lower(), m.group(2), m.group(3).lower()
        if word in radar.STOP or alpha in radar.STOP:
            continue
        out.add(f"{alpha}{num}{word}")
        compound_heads.add(f"{alpha}{num}")
    for tok in radar.features(t, strong=True):
        if (radar._special(tok) and not tok.startswith(radar.EVENT_PREFIX) and tok not in compound_heads
                and not YEARISH_RE.search(tok) and len(re.match(r"[a-z]*", tok).group(0)) >= 3):
            out.add(tok)
    return out


def gap(a: Story, b: Story) -> timedelta:
    out = []
    if a.gen and b.gen:
        out.append(abs(a.gen - b.gen))
    if a.src and b.src:
        out.append(abs(a.src - b.src))
    return min(out) if out else timedelta(days=9999)


def title_sim(a: Story, b: Story) -> float:
    """日本語の題名どうしの類似度（元動画の題名はシリーズの定型が多く、似ていても別の話のことがあるので使わない）"""
    return dedupe.jaccard(dedupe.bigrams(a.title), dedupe.bigrams(b.title))


def same_source_title(a: Story, b: Story) -> bool:
    """元の題名（動画・元記事）がまったく同じ（同じ動画の再投稿・同じ発表の別URL）"""
    xa = {dedupe.normalize(t) for t in a.sources if len(dedupe.normalize(t)) >= 12}
    return bool(xa & {dedupe.normalize(t) for t in b.sources})


def is_angle(later: Story, earlier: Story) -> bool:
    """後の記事が先の記事を意図して別の角度から書いたもの（重複にしない）"""
    d = later.data
    if d.get("angleOf") == earlier.slug:
        return True
    if earlier.slug in (d.get("relatedSlugs") or []) and EXPLAINER_RE.search(later.title):
        return f"/articles/{earlier.slug}" in str(d.get("body") or "")
    return False


def page_role(title: str) -> str:
    """記事の役割（about とは / compare 比較 / pricing 料金・プラン / howto 使い方 / news ニュース）。台帳 A68"""
    t = unicodedata.normalize("NFKC", str(title or "")).strip()
    for role, pattern in ROLE_PATTERNS:
        if pattern.search(t):
            return role
    return "news"


def guide_role_of_body(body: str) -> str | None:
    """本文の見出しのうち GUIDE_HEAD_MIN 本以上が読者の疑問・行動に答えるなら、いちばん多い型（family / eligibility / action）"""
    heads = HEADING_RE.findall(str(body or ""))
    hits = [h for h in heads if any(p.search(h) for p in GUIDE_HEADS.values())]
    if len(hits) < GUIDE_HEAD_MIN:
        return None
    counts = {role: sum(1 for h in hits if GUIDE_HEADS[role].search(h)) for role in GUIDE_ROLES}
    return max(GUIDE_ROLES, key=lambda role: counts[role])  # 同じ数なら GUIDE_ROLES の順


def article_role(data: dict) -> str:
    """記事の役割。題名で決め（page_role）、題名がニュースの形なら本文の見出しでガイドかを見る（台帳 A71）"""
    role = page_role(data.get("title") or "")
    if role == "news" and data.get("body"):
        role = guide_role_of_body(data["body"]) or role
    return role


def split_drop(a: Story, b: Story) -> bool:
    """同じ発信元が6時間以内に、別の出典（別の動画・別のページ）として出したもの（1つの事例を何本にも分けた公開）。
    役割の違う題名を付けていても同じ話題として見る（2026-11-03 の Legora の事例の分割。同じ出典から役割を変えて書いた記事とは違う）"""
    return bool(a.data.get("channelSlug") and a.data.get("channelSlug") == b.data.get("channelSlug") and a.src and b.src
                and abs(a.src - b.src) <= timedelta(hours=6) and not (a.keys & b.keys))


TITLE_DATE_RE = re.compile(r"(?:(\d{1,2})月)?(\d{1,2})日(?!間|目|以内|以上|未満|分|連続|ごと|おき|に1|あたり)")


def title_dates(title: str) -> set[tuple[int, int]]:
    """題名に書いた日付 {(月, 日)}（月が無ければ 0）。「3日間」「15日以内」のような期間は数えない"""
    t = unicodedata.normalize("NFKC", str(title or ""))
    return {(int(m.group(1) or 0), int(m.group(2))) for m in TITLE_DATE_RE.finditer(t)}


def date_conflict(a: Story, b: Story) -> bool:
    """両方の題名に日付があり、1つも合わない（別の日の出来事を中心にした記事。月の無い日付は日だけで比べる）"""
    da, db = title_dates(a.title), title_dates(b.title)
    if not da or not db:
        return False
    return not any(x[1] == y[1] and (x[0] == y[0] or not x[0] or not y[0]) for x in da for y in db)


def same_angle(a: Story, b: Story) -> bool:
    """出典が同じ2本が、同じ切り口（同じことを中心に書いた記事）か。題名か keywords が似ているときだけ同じ切り口とみなす。
    元の題名（videoTitle・originalTitle）は出典が同じなら同じになるので、ここでは見ない"""
    return title_sim(a, b) >= SAME_URL_SIM or dedupe.jaccard(a.kw, b.kw) >= SAME_URL_KW


def same_story(a: Story, b: Story, df: dict[str, int], window: timedelta = WINDOW, candidate: bool = False,
               ignore_role: bool = False) -> str | None:
    """同じ話題なら理由、違えば None。
    candidate=True は生成前の候補（英語の元の題名だけで keywords が無い）。製品名と会社が一致すれば同じ話題とみなす
    （大きなニュースは web_articles.py が続報の判定（LLM）に回すので、別の発表なら新しい記事になる）。
    役割（page_role）が違う記事は、同じ発表でも別の疑問に答えるので同じ話題にしない（ignore_role=True は互いに結ぶ相手を探すとき）"""
    if gap(a, b) > window:
        return None
    if not ignore_role and a.role != b.role and not split_drop(a, b):
        return None
    if title_key(a.title) and title_key(a.title) == title_key(b.title):
        return "同じ題名"
    # 題名の中心の日付が食い違う記事は別の出来事（2026-11-13。生成前の候補は題名が英語の元の題名なので見ない）
    # 役割違いの記事を結ぶ相手を探すとき（ignore_role）も今までどおり出典 URL だけで見る
    if not candidate and not ignore_role and date_conflict(a, b) and title_sim(a, b) < SIM_STRONG:
        return None
    # 生成前の候補は出典 URL だけで見る（同じ発表から自動でもう1本作らない）。載せた記事どうしは切り口も同じときだけ。
    # 切り口が違うときは、出典が別の記事と同じように下の判定（製品名・固有名詞・題名の類似）へ進む
    if a.keys & b.keys and (candidate or ignore_role or same_angle(a, b)):
        return "同じ出典URL"
    if a.genre and b.genre and a.genre != b.genre:
        return None  # 投資の解説の中で AI に触れた、など
    if a.ents and b.ents and not (a.ents & b.ents):
        return None
    if same_source_title(a, b):
        return "元の題名が同じ"
    ents = a.ents & b.ents
    sim = title_sim(a, b)
    products = sorted(a.products & b.products)
    # 発信元自身の名前（Databricks のブログの「Databricks」など）は話題の手がかりにしない
    publisher = {w.lower() for x in (a, b) for k in ("channel", "sourceName", "channelSlug")
                 for w in re.findall(r"[A-Za-z]{3,}", str(x.data.get(k) or ""))}
    rare = sorted(t for t in a.latin & b.latin
                  if df.get(t, 0) <= RARE_DF and t not in radar.ALIASES and t not in radar.STOP and t not in publisher)
    kw = dedupe.jaccard(a.kw, b.kw)
    if products and ents and (candidate or sim >= 0.15 or kw >= KW_OVERLAP):
        return f"製品名が一致（{'・'.join(products[:2])}）"
    same_drop = (a.data.get("channelSlug") and a.data.get("channelSlug") == b.data.get("channelSlug")
                 and a.src and b.src and abs(a.src - b.src) <= timedelta(hours=6))
    kw = dedupe.jaccard(a.kw, b.kw)
    if rare and same_drop and (sim >= SIM_WITH_TOKEN or kw >= SIM_WITH_TOKEN):
        return f"同じ発信元が同時に出した同じ話題（{'・'.join(rare[:2])}）"
    if rare and (ents or not (a.ents or b.ents)) and (sim >= SIM_RARE or (sim >= SIM_WITH_TOKEN and kw >= KW_OVERLAP)):
        return f"珍しい固有名詞が一致（{'・'.join(rare[:2])} / {sim:.2f}）"
    if sim >= SIM_STRONG and (ents or not (a.ents or b.ents)):
        return f"題名が類似（{sim:.2f}）"
    if (sim >= SAME_PUBLISHER_SIM and kw >= SAME_PUBLISHER_KW and a.genre == b.genre and same_publisher(a, b)
            and gap(a, b) <= SAME_PUBLISHER_GAP and not latin_conflict(a, b) and source_titles_close(a, b)):
        return f"同じ発信元の似た発表（題名 {sim:.2f}・キーワード {kw:.2f}）"
    return None


def _host(story: Story) -> str:
    try:
        return urllib.parse.urlsplit(str(story.data.get("sourceUrl") or "")).netloc.lower().removeprefix("www.")
    except ValueError:
        return ""


def same_publisher(a: Story, b: Story) -> bool:
    """同じ発信元（同じチャンネル・同じフィード、または出典 URL のホストが同じ）"""
    ca, cb = a.data.get("channelSlug"), b.data.get("channelSlug")
    if ca and cb and ca == cb:
        return True
    ha, hb = _host(a), _host(b)
    return bool(ha) and ha == hb


def _title_latin(story: Story) -> set[str]:
    return {w.lower() for w in re.findall(r"[A-Za-z]{3,}", unicodedata.normalize("NFKC", story.title))}


def source_titles_close(a: Story, b: Story) -> bool:
    """元の題名（動画・元記事）が両方あるときは、それも似ていること（同じ製品のデモ動画の別の回を重複にしない）"""
    if not (a.sources and b.sources):
        return True
    return dedupe.jaccard(dedupe.bigrams(a.sources[0]), dedupe.bigrams(b.sources[0])) >= SAME_PUBLISHER_SOURCE_SIM


def latin_conflict(a: Story, b: Story) -> bool:
    """題名の英字の語が、両方とも相手に無い語を持つ（MacBook Pro と iMac のように別の製品の可能性が高い）"""
    la, lb = _title_latin(a), _title_latin(b)
    return bool(la - lb) and bool(lb - la)


def doc_freq(stories: list[Story]) -> dict[str, int]:
    df: dict[str, int] = {}
    for s in stories:
        for t in s.tokens:
            df[t] = df.get(t, 0) + 1
    return df


# --------------------------------------------------------------------------- #
# 代表の選び方（検索から外れる理由が他に無い記事を優先）
# --------------------------------------------------------------------------- #


def _other_noindex(data: dict) -> str | None:
    import indexnow  # noqa: PLC0415

    return indexnow.noindex_reason({k: v for k, v in data.items() if k not in ("duplicateOf",)})


def source_count(data: dict) -> int:
    """記事が根拠にした出典の数（Muse の記事は museSources、ほかは出典 URL と続報の出典）"""
    muse = data.get("museSources")
    if isinstance(muse, list) and muse:
        return len(muse)
    urls = {str(data.get("sourceUrl") or "")} | {str(u.get("sourceUrl") or "") for u in (data.get("updates") or []) if isinstance(u, dict)}
    return len(urls - {""})


def keeper_rank(story: "Story") -> tuple:
    """代表にする強さ（大きいほど強い）: Muse の記事 → 本文が長い → 出典が多い → 新しい"""
    d = story.data
    return (d.get("writer") == "muse", len(str(d.get("body") or "")), source_count(d),
            (story.gen or datetime.min.replace(tzinfo=timezone.utc)).timestamp(), story.slug)


def _search_protected() -> set[str]:
    """検索に表示があった記事の slug（読めなければ空）"""
    try:
        import search_protected  # noqa: PLC0415

        return search_protected.protected_slugs()
    except Exception:  # noqa: BLE001 一覧が読めなくても印付けは止めない
        return set()


def eligible(data: dict) -> bool:
    if data.get("type") == "roundup" or data.get("disaster") or data.get("quakeEventId"):
        return False
    return bool(data.get("slug") and data.get("title"))


def plan(stories: list[Story], df: dict[str, int], recheck_since: datetime | None = None) -> dict[str, tuple[str, str]]:
    """{重複の slug: (代表の slug, 理由)}。stories は載せた順（古い順）に並べておく。
    recheck_since があれば、それより後に載せた記事だけを「重複かもしれない側」として見る"""
    groups: list[list[tuple[Story, str]]] = []  # 先頭が話題の最初の記事
    seen: list[Story] = []
    for s in stories:
        # 意図して角度を変えた解説は、どの話題にも入れない（ほかの記事の代表にもならない）。
        # 読まれた記事の深掘り（angleOf と deepDive。scripts/deep_dive.py が同じ型を二度作らない）も同じ
        if (s.data.get("angleOf") and s.data.get("deepDive")) or any(is_angle(s, x) for x in seen):
            seen.append(s)
            continue
        seen.append(s)
        hit = None
        for g in groups:
            head = g[0][0]
            why = same_story(s, head, df)
            if why:
                hit = (g, why)
                break
        if hit:
            hit[0].append((s, hit[1]))
        else:
            groups.append([(s, "")])
    out: dict[str, tuple[str, str]] = {}
    protected = _search_protected() if any(len(g) > 1 for g in groups) else set()
    for g in groups:
        if len(g) < 2:
            continue
        members = [x for x, _ in g]
        manual = [x for x in members if x.data.get("indexable") is True]
        # 代表はいちばん強いページ（keeper_rank）。ほかの理由で検索から外れる記事は、ほかに候補があれば代表にしない
        # 検索に表示があった記事（content/search_protected.json ほか。台帳 A46・A68「転送しない」）は、いちばん先に代表にする
        pool = [x for x in members if _other_noindex(x.data) is None] or members
        keeper = manual[0] if manual else max(pool, key=lambda x: (x.slug in protected, *keeper_rank(x)))
        # 見直す期間に載せた記事が1本も無い話題は、今の印のまま動かさない（古い話題の代表を入れ替えない）
        if recheck_since and not any(x.gen and x.gen >= recheck_since for x in members):
            keeper = next((x for x in members if not x.data.get("duplicateOf") and x.data.get("indexable") is not False), keeper)
        for x, why in g:
            if x is keeper or x.data.get("indexable") is True:
                continue
            if recheck_since and x.gen and x.gen < recheck_since and not x.data.get("duplicateOf") and keeper.gen and keeper.gen < recheck_since:
                continue
            out[x.slug] = (keeper.slug, why or same_story(x, keeper, df) or "同じ話題")
    return out


def load_all() -> list[tuple[Path, dict]]:
    rows = []
    for path in sorted(ARTICLES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            data.setdefault("slug", path.stem)
            rows.append((path, data))
    return rows


def mark(dry_run: bool = False, days: int = 0, recompute: bool = False) -> dict[str, tuple[str, str]]:
    rows = [(p, d) for p, d in load_all() if eligible(d)]
    stories = [Story(d) for _, d in rows]
    order = sorted(range(len(stories)), key=lambda i: (stories[i].gen or datetime.max.replace(tzinfo=timezone.utc), stories[i].slug))
    stories = [stories[i] for i in order]
    rows = [rows[i] for i in order]
    df = doc_freq(stories)
    since = datetime.now(timezone.utc) - timedelta(days=days) if days else None
    # --recompute と --days を両方付けたら、直近 days 日に載せた記事の印だけ付け直す（古い話題の代表は動かさない）
    result = plan(stories, df, since)
    by_slug = {d["slug"]: (p, d) for p, d in rows}
    changed = 0
    for slug, (keep, why) in sorted(result.items()):
        path, data = by_slug[slug]
        print(f"[dup] {slug} → {keep}（{why}）")
        if data.get("duplicateOf") == keep:
            continue
        # 前に付けた印を保つ。ただし前の代表が今は重複の側（代表が入れ替わった）なら、新しい代表へ付け替える
        if data.get("duplicateOf") and not recompute and data["duplicateOf"] not in result:
            continue
        changed += 1
        if not dry_run:
            data["duplicateOf"] = keep
            data["duplicateReason"] = why[:120]
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # 代表になった記事に前の印が残っていたら外す（代表が重複の印を持つと、canonical が互いを向く）
    for keep in sorted({k for k, _ in result.values()}):
        path, data = by_slug[keep]
        if data.get("duplicateOf") and keep not in result:
            print(f"[keep] {keep}（代表にした。前の印 {data['duplicateOf']} を外す）")
            changed += 1
            # dry-run でも下の「外れた印」の集計に二重に出さない
            data.pop("duplicateOf", None)
            data.pop("duplicateReason", None)
            if not dry_run:
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if recompute:
        for (path, data), s in zip(rows, stories):
            if since and not (s.gen and s.gen >= since):
                continue
            # 手で付けた印（理由 duplicateReason が無い。例: 障害の復旧の記事を代表にした）は外さない
            if data.get("duplicateOf") and data["slug"] not in result and data.get("duplicateReason"):
                print(f"[undup] {data['slug']}（同じ話題の判定から外れた）")
                changed += 1
                if not dry_run:
                    data.pop("duplicateOf", None)
                    data.pop("duplicateReason", None)
                    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    linked = link_siblings(stories, df, since, dry_run, by_slug, result)
    print(f"[story] 重複 {len(result)} 本（今回の変更 {changed} 本・役割違いの記事を結んだ {linked} 本{'・dry-run' if dry_run else ''}）")
    return result


SIBLING_MAX = 6


def siblings(stories: list[Story], df: dict[str, int], since: datetime | None = None,
             duplicates: dict | None = None) -> dict[str, list[str]]:
    """同じ発表で役割（とは・料金・比較・使い方・ニュース）が違う記事どうし {slug: [相手の slug]}（台帳 A68）。
    since があれば、それより後に載せた記事を含む組だけ"""
    duplicates = duplicates or {}
    live = [s for s in stories if s.slug and s.slug not in duplicates and not s.data.get("duplicateOf")]
    out: dict[str, list[str]] = {}
    for i, a in enumerate(live):
        for b in live[i + 1:]:
            if since and not ((a.gen and a.gen >= since) or (b.gen and b.gen >= since)):
                continue
            if a.role == b.role or not same_story(a, b, df, ignore_role=True):
                continue
            out.setdefault(a.slug, []).append(b.slug)
            out.setdefault(b.slug, []).append(a.slug)
    return out


def link_siblings(stories: list[Story], df: dict[str, int], since: datetime | None, dry_run: bool,
                  by_slug: dict, duplicates: dict) -> int:
    """役割違いの記事を relatedSlugs の先頭に入れて互いに結ぶ（すでに入っていれば何もしない）"""
    changed = 0
    keys = {s.slug: s.keys for s in stories}
    roles = {s.slug: s.role for s in stories}
    for slug, others in siblings(stories, df, since, duplicates).items():
        path, data = by_slug[slug]
        related = [str(x) for x in (data.get("relatedSlugs") or [])]
        add = [o for o in others if o not in related][:SIBLING_MAX]
        # 同じ出典から別の疑問に答える記事（ニュース以外）には angleOf を付ける。サイトと IndexNow の予備の重複判定
        # （同じ出典URLは1本だけ）から外し、関連記事の一覧で互いに出す（lib/article-index.mjs・lib/related.ts・scripts/indexnow.py）
        angle = ""
        if roles.get(slug) != "news" and not data.get("angleOf"):
            same_src = [o for o in others if keys.get(slug, set()) & keys.get(o, set())]
            news = [o for o in same_src if roles.get(o) == "news"]
            angle = (news or same_src or [""])[0]
        if not add and not angle:
            continue
        changed += 1
        print(f"[link] {slug}（{ROLE_LABELS[roles.get(slug, 'news')]}）→ {', '.join(add) or '（結び済み）'}{f' / angleOf {angle}' if angle else ''}")
        if not dry_run:
            data["relatedSlugs"] = add + related
            if angle:
                data["angleOf"] = angle
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed


# --------------------------------------------------------------------------- #
# 生成前の確認（パイプラインが使う）
# --------------------------------------------------------------------------- #


class Recent:
    """直近 days 日の記事の索引。候補が同じ話題か調べる"""

    def __init__(self, days: int = 5) -> None:
        since = datetime.now(timezone.utc) - timedelta(days=days + 1)
        all_rows = [d for _, d in load_all() if eligible(d)]
        self.df = doc_freq([Story(d) for d in all_rows])
        self.stories = [s for s in (Story(d) for d in all_rows) if s.gen and s.gen >= since]

    def add(self, data: dict) -> None:
        self.stories.append(Story(data))

    def match(self, title: str, url: str = "", keywords: list[str] | None = None, published: datetime | None = None,
              video_id: str = "", extra_titles: list[str] | None = None, channel_slug: str = "",
              genre: str = "") -> tuple[str, str] | None:
        """同じ話題の記事があれば (slug, 理由)"""
        now = datetime.now(timezone.utc)
        cand = Story({
            "slug": "", "title": title, "videoTitle": (extra_titles or [""])[0], "sourceUrl": url, "videoId": video_id,
            "keywords": keywords or [], "generatedAt": now.isoformat(),
            "publishedAt": (published or now).isoformat(), "channelSlug": channel_slug, "genreSlug": genre,
        })
        best = None
        for s in self.stories:
            why = same_story(cand, s, self.df, candidate=True)
            if why:
                score = 3 if why == "同じ出典URL" else (2 if why.startswith("製品名") else 1)
                if best is None or score > best[0]:
                    best = (score, s.slug, why)
        return (best[1], best[2]) if best else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd")
    p_mark = sub.add_parser("mark")
    p_mark.add_argument("--dry-run", action="store_true")
    p_mark.add_argument("--days", type=int, default=0, help="直近この日数に載せた記事だけ見直す（0=全記事）")
    p_mark.add_argument("--recompute", action="store_true", help="前に付けた印も付け直す（外れたものは消す）")
    p_check = sub.add_parser("check")
    p_check.add_argument("title")
    p_check.add_argument("--url", default="")
    p_check.add_argument("--keywords", default="")
    args = parser.parse_args()
    if args.cmd == "mark":
        mark(args.dry_run, args.days, args.recompute)
        return 0
    if args.cmd == "check":
        hit = Recent().match(args.title, args.url, [k for k in args.keywords.split(",") if k])
        print(f"{hit[0]}（{hit[1]}）" if hit else "同じ話題の記事なし")
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
