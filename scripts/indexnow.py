#!/usr/bin/env python3
"""IndexNow で検索エンジンに更新を通知する。

Google Search Console は所有者のログインが必要で登録が進まないが、
IndexNow はアカウント不要で Bing / DuckDuckGo / Yandex などに直接通知できる。
新規サイトが「発見されない」状態を、こちら側だけで動かせる唯一の手段。

  python3 scripts/indexnow.py --all      # 全記事を送信（初回用）
  python3 scripts/indexnow.py --hours 12 # 直近12時間に生成された記事だけ
  python3 scripts/indexnow.py --urls https://ai-tech-express.jp/guides/a,...  # 指定した URL だけ
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import persona  # noqa: E402  読者像（検索に出す話題の基準）
import public_interest  # noqa: E402  公共性の高い話題（台帳 A40）
import notice_gate  # noqa: E402  お知らせ・告知・統計の転載を作らない（公開前の門）
import genre_focus  # noqa: E402  エンタメはビジネス・テックの目線だけ（2026-11-03）

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "content" / "articles"
HOWTO_DIR = ROOT / "content" / "howto"
PUBLIC_DIR = ROOT / "public"
ENDPOINT = "https://api.indexnow.org/indexnow"
MAX_URLS = 10000  # 1リクエストあたりの上限


def site_url() -> str:
    url = os.environ.get("NEXT_PUBLIC_SITE_URL") or "https://ai-tech-express.jp"
    return url.rstrip("/")


def find_key() -> str | None:
    """public/<key>.txt からキーを読む。ファイル名とその中身が一致している必要がある。"""
    for path in PUBLIC_DIR.glob("*.txt"):
        key = path.stem
        if path.read_text().strip() == key:
            return key
    return None


def latest_guide_timestamp(guide: dict) -> datetime | None:
    """全体確認日を維持した部分更新も拾う。時差を揃え、有効な最新日時を使う。"""
    timestamps = []
    for field in ("checkedAt", "updatedAt", "createdAt"):
        value = guide.get(field)
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            touched = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            # タイムゾーンのない値は日付を推測しない。他の有効な日時へフォールバックする。
            if touched.tzinfo is not None:
                timestamps.append(touched.astimezone(timezone.utc))
        except (ValueError, OverflowError):
            continue
    return max(timestamps) if timestamps else None


def collect_urls(base: str, hours: int | None) -> list[str]:
    """インデックス対象（noindex_reason が None）の記事URLを集める。

    noindex にしている記事を送っても意味がないため、対象から外す。
    """
    threshold = (
        datetime.now(timezone.utc) - timedelta(hours=hours) if hours else None
    )
    urls = [base, f"{base}/articles", f"{base}/genres/ai"]

    articles = []
    for path in sorted(ARTICLES_DIR.glob("*.json")):
        try:
            articles.append(json.loads(path.read_text("utf-8")))
        except json.JSONDecodeError:
            continue
    dups = duplicate_slugs(articles)
    for article in articles:
        if not is_indexable(article, dups):
            continue
        if threshold:
            try:
                # 続報を足した記事も送り直す
                generated = datetime.fromisoformat(article.get("updatedAt") or article.get("generatedAt", ""))
            except ValueError:
                continue
            if generated < threshold:
                continue
        urls.append(f"{base}/articles/{article['slug']}")

    # 使い方ガイド（/guides/<slug>）。作成・全体確認・部分更新の最新日時で選ぶ。
    guides = []
    for path in sorted(HOWTO_DIR.glob("*.json")):
        try:
            guide = json.loads(path.read_text("utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(guide, dict):
            continue
        touched = latest_guide_timestamp(guide)
        if touched is None:
            continue
        if threshold is None or touched >= threshold:
            guides.append(f"{base}/guides/{guide['slug']}")
    if guides:
        urls += [f"{base}/guides", *guides]

    return urls[:MAX_URLS]


def submit(base: str, key: str, urls: list[str]) -> int:
    payload = {
        "host": base.split("://", 1)[-1],
        "key": key,
        "keyLocation": f"{base}/{key}.txt",
        "urlList": urls,
    }
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status


# lib/indexing.ts の isIndexable と同じ基準（検索に出さない記事は通知しない。条件の説明はそちら）
WIRE_SOURCES = {"prtimes", "prtimes-all", "atpress", "value-press", "kyodo-prwire", "dreamnews"}
# 個人・他媒体の YouTube チャンネル（scripts/channels.py のうち、企業・機関の公式チャンネルではないもの）。
# 他人の動画の内容を要約した記事は、独自の価値が出しにくく「複製されたコンテンツ」（AdSense）や翻案の心配があるので検索に出さない。
# サイト内では読める。公式チャンネル（OpenAI・NVIDIA・楽天証券など）の発表動画は従来どおり対象
CREATOR_CHANNELS = {
    "ai-explained", "two-minute-papers", "bycloud", "matthew-berman",
    "rakumachi", "uraken-fudosan", "yukkuri-fudosan", "mansion-mania", "ienomikata",
    "liberal-arts", "bank-academy", "nikkei",
}


THIN_BODY = 1500
# いつでも主題として扱うジャンル（AI・テック）。お金・不動産・起業・制度は persona.is_persona_topic、スポーツは persona.sports_scope
FOCUS_GENRES = {"ai", "tech-gadget"}
SPORTS_GENRES = {"sports"}
# エンタメはビジネス・テックの目線（料金・決算・販売本数・市場規模・AI・規約）のものだけ主題に入れる（2026-11-03 オーナー決定。scripts/genre_focus.py）
ENTERTAINMENT_GENRES = {"entertainment"}
AI_TOPIC = re.compile(
    r"(?<![A-Za-z])AI(?![a-z])|人工知能|生成|LLM|GPT|Gemini|Claude|Copilot|機械学習|エージェント|ロボット|半導体|NVIDIA",
    re.I,
)
JAPAN_VALUE = re.compile(r"^#{2,3}.*(日本|無料|使い方|料金|始め方|使える)", re.M)
TITLE_NOISE = re.compile(r"[\s「」『』【】()（）・、。！？!?:：|｜\-—〜~\"'“”]")


def _url_key(url: str) -> str:
    return re.sub(r"[?#].*$", "", str(url or "").strip().lower()).rstrip("/")


def duplicate_slugs(articles: list[dict]) -> set[str]:
    """重複記事（lib/article-index.mjs の markDuplicates と同じ）。
    1. duplicateOf（scripts/story.py が付ける）  2. 予備: 同じ題名・出典URLのうち代表以外（本文の長い方、同じなら先に載った方が代表）"""
    keep: set[str] = set()
    out: set[str] = {a.get("slug", "") for a in articles if a.get("duplicateOf") and a.get("duplicateOf") != a.get("slug")}
    items = [a for a in articles if a.get("type") != "roundup" and a.get("slug") not in out and not a.get("angleOf")]
    items.sort(key=lambda a: a.get("generatedAt", ""))
    items.sort(key=lambda a: -len(a.get("body", "")))
    for a in items:
        keys = ["t:" + TITLE_NOISE.sub("", a.get("title", "")).lower()]
        if a.get("sourceUrl"):
            keys.append("u:" + _url_key(a["sourceUrl"]))
        if any(k in keep for k in keys):
            out.add(a.get("slug", ""))
        else:
            keep.update(keys)
    return out


def is_focus(article: dict) -> bool:
    """読者像（scripts/persona.py）の話題か。lib/indexing.ts の isFocus と同じ。
    1. AI・テック（ジャンル ai / tech-gadget、または題名・タグにAI関連語）
    2. 読者像の話題（persona.is_persona_topic: ビジネス・投資・不動産のジャンル、制度・暮らし・テックのジャンルでお金・税・補助金・起業の話題）
    3. エンタメのビジネス・テックの目線（genre_focus.entertainment_focus: 料金・決算・販売本数・市場規模・AI・規約。告知・ゴシップは外す）
    4. 日本のスポーツ（persona.sports_scope。海外のリーグで活躍する日本人選手〔大谷翔平など〕も入る＝台帳 A13。海外の選手・リーグだけの話題は外す。世界的な大会は海外選手も可）
    5. 公共性の高い話題と、広げた暮らしの話題（public_interest.focus_topic。交通・天気・値上げ・サービス終了・障害・給付・
       コンビニ/外食/家電/スマホの発売・事故と災害。2026-11-07 台帳 A56・2026-11-08 A23。事件〔犯罪〕・不祥事・ゴシップは外す）
    それ以外（作品の告知だけのエンタメ・ゲーム、お金に関係しない新商品や研究成果など）は主題外。"""
    text = article.get("title", "") + " " + " ".join(article.get("tags") or [])
    if article.get("genreSlug") in FOCUS_GENRES or AI_TOPIC.search(text):
        return True
    if persona.is_persona_topic(article):
        return True
    # 公共性の高い話題（情報漏えい・ミサイル・災害・リコール・詐欺・暮らしのお金の変更。2026-11-04 オーナー決定・台帳 A40）
    if public_interest.focus_topic(article):
        return True
    if article.get("genreSlug") in ENTERTAINMENT_GENRES:
        return genre_focus.entertainment_focus(article.get("title", ""), article.get("tags"), article.get("channelSlug", ""))
    if article.get("genreSlug") in SPORTS_GENRES:
        # 発信元が海外かは記事に残らない。海外のフィードは生成時に sports_scope(japanese_source=False) で落としているので、ここでは目印だけで見る
        return persona.sports_scope(text)[0]
    return False


# 2026-11-08 オーナー承認（台帳 A61「全て承認する」）: 検索に出さないのは、本当の重複（duplicateOf・同じ題名/出典の代表以外）と
# 本文が無い記事だけ。主題外（off-focus）・「日本の読者向けの章」が無い（no-japan-value）・短い公式のお知らせ（thin）・
# 配信サービス（wire）・動画の要約（creator-video）でも、公開している記事は検索に出す（幅広い話題の方針。台帳 A56）。
# 公開前の門（publish_block_reason）の「主題外」も 2026-11-08 の台帳の見直しから同じ軸（on_axis）で見る
NO_BODY = 200  # これより短い本文は「本文が無い」として検索に出さない（字数。公式の短いお知らせは 800字ほどあるので当たらない）

# 2026-11-08 オーナー決定（台帳 A61）: サイトの軸は「暮らしとお金の『自分ごと』ニュース」（あなたのお金と暮らしに、何が変わる？）。
# 検索に出す・取り下げた記事を戻すの基準は「お金か暮らしにつながる話題か」を題名で見る（エンタメ・ゲーム・スポーツも、値段・料金・
# 発売日・チケット・サブスク・サービスの話なら出す）。出さないのは、お金にも暮らしにもつながらない話題（ゴシップだけ・ゲームの物語や
# キャラクターだけ・海外のリーグの試合結果など）だけ。1) お金の語が題名にあればつながる 2) 無ければ、つながらない話題の語で外す
# 3) それも無ければ、暮らし・サービス・仕事の語でつながる 4) どれも無ければつながらない
LIFE_MONEY_RE = re.compile(
    r"料金|価格|値上げ|値下げ|値段|\d[\d,.]*(?:万|億)?円|円から|ドル|無料|有料|課金|サブスク|月額|年額|定額|手数料|税|給付|補助|助成|"
    r"年金|保険|ローン|金利|株価|株主|株式市場|株式分割|投資|NISA|iDeCo|決算|売上|業績|赤字|黒字|ポイント|還元|セール|割引|キャンペーン|発売|販売|予約|"
    r"チケット|入場|観戦|放送|配信(?:開始|予定|日)|見放題|視聴|加入|契約|解約|プラン|手続き|申請|届出|期限|締切|リコール|回収|"
    r"障害|不具合|停止|終了|廃止|改定|賃金|給料|ボーナス|家賃|住宅|不動産|マンション|電気|ガス|水道|運賃|運休|台風|大雨|地震|津波|"
    r"災害|詐欺|流出|漏え?い|漏洩|不正アクセス|個人情報|協賛金|費用|予算|原産地|表示違反|偽装|"
    r"お金|資産|資本|金融|日銀|日本銀行|国債|GDP|物価|景気|経済|退職金|預金|貯金|貯め|財務省|金融庁|消費者庁|重大事故|事故|広告|"
    r"経営|ビットコイン|暗号資産|仮想通貨|相続|登記|療養費|医療費|負担|賃貸|購入|買取|在庫|出荷|消費|物流|診療|薬物|限定メニュー|新メニュー|"
    r"新登場|リニューアル|期間限定|賃料|空室|条例|施行|義務化|避難|ミサイル|銘柄|株安|株高|株急落|支援事業"
)
NO_LIFE_LINK_RE = re.compile(
    r"熱愛|交際|結婚|離婚|破局|不倫|ゴシップ|スキャンダル|炎上|ストーリー|物語|キャラクター|新キャラ|声優|主題歌|キービジュアル|"
    r"PV|トレーラー|(?:試合|対戦)結果|勝利|敗戦|敗れ|ゴール|得点|ホームラン|優勝|移籍|プレミアリーグ|NBA|MLB|NFL|ラ・リーガ|セリエA|ブンデスリーガ"
)
LIFE_GENERAL_RE = re.compile(
    r"サービス|アプリ|機能|使え|使い方|始め方|対応|搭載|提供|開始|スタート|導入|新製品|新型|新モデル|スマホ|iPhone|iPad|Android|"
    r"パソコン|PC|Mac|Windows|AI|ChatGPT|Gemini|Claude|Copilot|仕事|業務|働き方|就職|転職|副業|採用|教育|学校|病院|医療|健康|"
    r"食品|食|商品|グッズ|買い物|楽天|Amazon|コンビニ|外食|スーパー|通販|旅行|ホテル|空港|鉄道|交通|道路|車|EV|自動車|天気|気象|防災|"
    r"暮らし|生活|家計|子育て|介護|マイナ|資格|試験|学習|省エネ|脱炭素|イベント|花火|祭り|トレンド|ツール|予防|大気|ライトアップ|開催|コラボ|メニュー|面接|育児|オンライン|登場|団地|建て替え|DX"
)


def life_link(title: str) -> bool:
    """題名がお金か暮らしにつながる話題か（台帳 A61。lib/indexing.ts の lifeLink と同じ）"""
    text = unicodedata.normalize("NFKC", title or "")
    if LIFE_MONEY_RE.search(text):
        return True
    if NO_LIFE_LINK_RE.search(text):
        return False
    return bool(LIFE_GENERAL_RE.search(text))


def noindex_reason(article: dict, dups: set[str] | frozenset = frozenset()) -> str | None:
    """検索に出さない理由（出すなら None）。サイトの lib/indexing.ts の noindexReason と同じ"""
    if isinstance(article.get("indexable"), bool):
        return None if article["indexable"] else "manual"
    if article.get("type") == "roundup":
        return None
    if len(str(article.get("body", "")).strip()) < NO_BODY:
        return "no-body"
    if article.get("slug") in dups or (article.get("duplicateOf") and article.get("duplicateOf") != article.get("slug")):
        return "duplicate"
    # 今まで検索に出していた主題（is_focus）はそのまま出す（ゆるめるだけで、出していた記事を外さない）
    if not (article.get("disaster") or life_link(article.get("title") or "") or is_focus(article)):
        return "no-life-link"
    return None


def focus_reason(article: dict, dups: set[str] | frozenset = frozenset()) -> str | None:
    """2026-11-08 までの検索の基準（主題・日本の読者向け・本文の長さ）。今は公開前の門（publish_block_reason）だけが使う"""
    if isinstance(article.get("indexable"), bool):
        return None if article["indexable"] else "manual"
    if article.get("type") == "roundup":
        return None
    if article.get("channelSlug") in WIRE_SOURCES:
        return "wire"
    if article.get("channelSlug") in CREATOR_CHANNELS:
        return "creator-video"
    body = article.get("body", "")
    # 速報・お知らせ・注意喚起・ミサイル・災害の記事は公式の発表が短いので下限を800字に下げる（scripts/public_interest.py の short_ok。台帳 A10・A40）
    if len(body) < (public_interest.SHORT_BODY if public_interest.short_ok(article) else THIN_BODY):
        return "thin"
    if not is_focus(article):
        return "off-focus"
    # 日本の会社の決算短信・国の統計の速報（scheduledRelease。台帳 W35）は、それ自体が日本の読者の話なので「日本で使える？」の章を求めない
    if not article.get("verdict") and not article.get("scheduledRelease") and not JAPAN_VALUE.search(body):
        return "no-japan-value"
    if article.get("slug") in dups or (article.get("duplicateOf") and article.get("duplicateOf") != article.get("slug")):
        return "duplicate"
    return None


# ---- 公開前の門（2026-11-03 オーナー承認。AdSense「有用性の低いコンテンツ」への対策） -------------------
# 検索に出せない記事（主題外・日本の読者に役立つ情報がない・薄い・配信の言い換え・他人の動画の要約）は、作っても取り下げるだけなので公開しない。
# 重複（duplicate）は公開後に scripts/story.py が付けて代表へ canonical を向けるので、ここでは止めない。地震・津波の速報（disaster）は短くても出す。
# 2026-11-08 オーナー決定（台帳 A60）: 短い（thin）・「日本の読者向けの章」が無い（no-japan-value）では公開を止めない・作り直さない。
# 公式の短いお知らせは短い記事でよい。検索に出すか（noindex_reason・サイトの lib/indexing.ts）はこれまでどおり別に決める。
PUBLISH_BLOCK = ("wire", "creator-video", "off-focus")
# 作り直せば直る見込みのあるもの。2026-11-08 から作り直しはしないので空
PUBLISH_RETRYABLE: tuple[str, ...] = ()
PUBLISH_FEEDBACK = {
    "wire": "プレスリリース配信の言い換えは公開しません",
    "creator-video": "個人・他媒体の動画の要約は公開しません",
    "off-focus": "サイトの軸（暮らしとお金の「自分ごと」ニュース）から外れた話題（お金にも暮らしにもつながらないゴシップ・物語やキャラクターだけ・海外の試合結果だけ）は公開しません",
    "no-japan-value": (
        "日本の読者に役立つ情報が足りません。日本の読者が自分に関係あるか判断できる章を、資料にある事実だけで書いてください。"
        "見出しは決まった質問（「日本で使える？」「料金は？」）にせず中身の言葉にし、日本・無料・料金・使い方・始め方・使える のどれかを含める"
        "（例「日本で使えるのは12月から」「料金は月200ドルのまま」「日本の売上は1%減」）"
    ),
    "press": "報道機関・ニュースブログの記事を出典にした記事は公開しません（事実は公式の一次情報だけ。W31）",
    "notice": "お知らせ・告知・統計の転載（認可・受章者・議事要旨・決算発表日の予告・啓発月間・出荷量など）は公開しません",
    "thin": f"本文が短すぎます。元記事にある事実だけで、背景・要点・読者への影響を補い、本文を{THIN_BODY}字以上にしてください",
}


def on_axis(article: dict) -> bool:
    """サイトの軸（暮らしとお金の「自分ごと」ニュース・台帳 A61）の上の記事か。検索に出す基準（noindex_reason）と同じ見方:
    地震・津波の速報・お金か暮らしにつながる題名（life_link）・今まで出していた主題（is_focus）"""
    return bool(article.get("disaster") or life_link(article.get("title") or "") or is_focus(article))


def publish_block_reason(article: dict) -> str | None:
    """公開しない理由（公開してよいなら None）。配信の言い換え・動画の要約は focus_reason で見る。
    主題外（off-focus）は 2026-11-08 の台帳の見直し（オーナー承認・A61 の最後の一文を外した）から、検索に出す基準と同じ軸（on_axis）で見る:
    軸の上（お金か暮らしにつながる・今までの主題）なら公開する。軸から外れたもの（ゴシップだけ・物語やキャラクターだけ・海外の試合結果だけ）だけ止める"""
    if article.get("disaster") or article.get("type") == "roundup" or isinstance(article.get("indexable"), bool):
        return None
    # お知らせ・告知・統計の転載（2026-11-03 オーナー決定・台帳 A26）。検索の基準（noindex_reason）とは別に、作らない
    if notice_gate.is_notice(article):
        return "notice"
    # 報道機関・ニュースブログが出典の記事（2026-11-04 W31 をすべての経路に。scripts/public_interest.py）。作り直さず見送り
    if public_interest.press_source_problems(article):
        return "press"
    reason = focus_reason(article)
    if reason == "off-focus" and on_axis(article):
        return None
    return reason if reason in PUBLISH_BLOCK else None


def candidate_off_focus(lane: str, title: str, summary: str = "", source_slug: str = "") -> bool:
    """生成の前に、幅広い話題の候補がサイトの主題外と分かるか（LLM を使わずに見送る。迷うものは通して公開前の門で見る）。
    レーン（フィードの分野）がジャンルの目安。AI の話題・読者像のジャンル・お金/制度の話題・スポーツ（別の足切りあり）・分野不明は通す"""
    if not lane or lane.startswith("_") or lane in FOCUS_GENRES or lane in SPORTS_GENRES or lane in persona.PERSONA_GENRES:
        return False
    text = f"{title} {summary[:300]}"
    if AI_TOPIC.search(text):
        return False
    # 題名がお金か暮らしにつながる候補は通す（公開前の門・検索に出す基準と同じ軸。台帳 A61・2026-11-08 の見直し。
    # エンタメも値段・チケット・発売・配信・サービスの話なら扱う＝A23）
    if life_link(title):
        return False
    if lane in ENTERTAINMENT_GENRES:
        return genre_focus.candidate_problem(lane, title, summary, source_slug) is not None
    if lane in persona.PERSONA_EXTRA_GENRES and persona.PRIORITY_TOPIC_RE.search(text):
        return False
    if lane in public_interest.FOCUS_GENRES and public_interest.FOCUS_TOPIC_RE.search(public_interest._nfkc(text)):
        return False
    # 広げた暮らしの話題（交通・天気・値上げ・サービス終了・障害・給付・コンビニ/外食/家電/スマホの発売。2026-11-07 オーナー承認・台帳 A56）
    if lane in public_interest.FOCUS_GENRES and public_interest.wide_category(title, source_slug):
        return False
    return True


# サイト側（lib/indexing.ts）が読む判定の材料。正本はこのファイルと scripts/persona.py で、
# 変えたら `python3 scripts/indexnow.py --export-rules` で書き出す（tests/test_index_rules.py がずれを検出する）
RULES_PATH = ROOT / "lib" / "index-rules.json"


def _js_regex(pattern: re.Pattern) -> dict:
    return {"source": pattern.pattern, "flags": "i" if pattern.flags & re.I else ""}


def index_rules() -> dict:
    return {
        "_note": "scripts/indexnow.py --export-rules で生成。手で直さない（正本は scripts/indexnow.py・scripts/persona.py・scripts/genre_focus.py）",
        "thinBody": THIN_BODY,
        "noBody": NO_BODY,
        "lifeMoney": _js_regex(LIFE_MONEY_RE),
        "noLifeLink": _js_regex(NO_LIFE_LINK_RE),
        "lifeGeneral": _js_regex(LIFE_GENERAL_RE),
        "creatorChannels": sorted(CREATOR_CHANNELS),
        "focusGenres": sorted(FOCUS_GENRES),
        "aiTopic": _js_regex(AI_TOPIC),
        "personaGenres": list(persona.PERSONA_GENRES),
        "personaExtraGenres": list(persona.PERSONA_EXTRA_GENRES),
        "priorityTopic": _js_regex(persona.PRIORITY_TOPIC_RE),
        "entertainmentGenres": sorted(ENTERTAINMENT_GENRES),
        "entertainmentBusiness": _js_regex(genre_focus.ENTERTAINMENT_BUSINESS_RE),
        "entertainmentExclude": _js_regex(genre_focus.ENTERTAINMENT_EXCLUDE_RE),
        "gameOfficialSources": sorted(genre_focus.GAME_OFFICIAL_SOURCES),
        "gamePlatform": _js_regex(genre_focus.GAME_PLATFORM_RE),
        "gameAnnounce": _js_regex(genre_focus.GAME_ANNOUNCE_RE),
        "gameExclude": _js_regex(genre_focus.GAME_EXCLUDE_RE),
        "sportsGenres": sorted(SPORTS_GENRES),
        "globalEvent": _js_regex(persona.GLOBAL_EVENT_RE),
        "japanSports": _js_regex(persona.JAPAN_SPORTS_RE),
        "foreignSports": _js_regex(persona.FOREIGN_SPORTS_RE),
        "publicInterestGenres": list(public_interest.FOCUS_GENRES),
        "publicInterestTopic": _js_regex(public_interest.FOCUS_TOPIC_RE),
        "publicInterestShortTopic": _js_regex(public_interest.SHORT_TOPIC_RE),
        "shortNoticeTopic": _js_regex(public_interest.SHORT_NOTICE_RE),
        "thinBodyPublicInterest": public_interest.SHORT_BODY,
        # 広げた暮らしの話題（public_interest.wide_category。台帳 A56）。順番どおりに当てる
        "wideTopics": [{"name": k, **_js_regex(v)} for k, v in public_interest.WIDE_TOPIC_RES.items()],
        "wideExclude": _js_regex(public_interest.WIDE_EXCLUDE_RE),
        "wideNotOutage": _js_regex(public_interest.WIDE_NOT_OUTAGE_RE),
        "launchTopic": _js_regex(public_interest.LAUNCH_RE),
        "launchContext": _js_regex(public_interest.LAUNCH_CONTEXT_RE),
        "launchSources": list(public_interest.LAUNCH_SOURCES),
    }


def rules_json() -> str:
    return json.dumps(index_rules(), ensure_ascii=False, indent=2) + "\n"


def rules_drift() -> bool:
    """lib/index-rules.json が今の基準とずれているか（サイトと IndexNow の判定が食い違う）"""
    try:
        return RULES_PATH.read_text("utf-8") != rules_json()
    except OSError:
        return True


NEWS_WINDOW = timedelta(days=2)
NEWS_MAX_SOURCE_AGE = timedelta(hours=48)


def _parse(value) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def news_reason(article: dict, dups: set[str] | frozenset = frozenset(), now: datetime | None = None) -> str | None:
    """ニュース用サイトマップに載せない理由（lib/indexing.ts の newsSitemapReason と同じ）"""
    reason = noindex_reason(article, dups)
    if reason:
        return reason
    if article.get("type") == "roundup":
        return "roundup"
    if article.get("angleOf"):
        return "angle"
    if article.get("late"):
        return "late"
    now = now or datetime.now(timezone.utc)
    published = _parse(article.get("generatedAt") or article.get("publishedAt"))
    if published is None or now - published >= NEWS_WINDOW:
        return "old"
    source = _parse(article.get("sourcePublishedAt") or article.get("publishedAt"))
    if source and published - source > NEWS_MAX_SOURCE_AGE:
        return "stale-source"
    return None


def is_indexable(article: dict, dups: set[str] | frozenset = frozenset()) -> bool:
    return noindex_reason(article, dups) is None


def is_distribution_eligible(article: dict) -> bool:
    """既存の配信選定を維持する。検索の文字数制限とは別の基準。"""
    if isinstance(article.get("indexable"), bool):
        return article["indexable"]
    if article.get("sourceType") != "web" or article.get("type") == "roundup":
        return True
    if article.get("channelSlug") in WIRE_SOURCES:
        return False
    return len(article.get("body", "")) >= 2000


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="全記事を送信")
    parser.add_argument("--hours", type=int, default=12, help="直近N時間の記事のみ")
    parser.add_argument("--dry-run", action="store_true", help="送信せず対象を表示")
    parser.add_argument("--urls", default="", help="カンマ区切りの URL だけを送る")
    parser.add_argument("--export-rules", action="store_true", help="サイト側の判定材料 lib/index-rules.json を書き出す")
    args = parser.parse_args()

    if args.export_rules:
        RULES_PATH.write_text(rules_json(), "utf-8")
        print(f"[done] {RULES_PATH.relative_to(ROOT)} を書き出しました")
        return 0
    if rules_drift():
        print("[warn] lib/index-rules.json が scripts/indexnow.py・persona.py の基準とずれています。"
              "python3 scripts/indexnow.py --export-rules で直してください（サイトの noindex と通知対象が食い違います）", file=sys.stderr)

    key = find_key()
    if not key:
        print("[NG] public/<key>.txt が見つかりません", file=sys.stderr)
        return 1

    base = site_url()
    explicit = [u.strip() for u in args.urls.split(",") if u.strip().startswith(base)]
    urls = explicit or collect_urls(base, None if args.all else args.hours)

    print(f"[info] 送信先ホスト: {base} / 対象 {len(urls)} 件")
    for url in urls[:5]:
        print("   ", url)
    if len(urls) > 5:
        print(f"    …ほか {len(urls) - 5} 件")

    if args.dry_run:
        print("[dry-run] 送信しませんでした")
        return 0
    if not explicit and len(urls) <= 3:
        print("[skip] 新規URLがないため送信しません")
        return 0

    try:
        status = submit(base, key, urls)
    except Exception as error:  # noqa: BLE001 - 通知失敗で全体を落とさない
        print(f"[NG] 送信失敗: {error}", file=sys.stderr)
        return 0

    print(f"[done] HTTP {status}（200/202 なら受理）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
