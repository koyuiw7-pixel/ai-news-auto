#!/usr/bin/env python3
"""記事の「なるほど」「公式窓口」「すぐにできること（手順つき）」を、公式ページから書き足す（2026-11-09 オーナー指摘・台帳 A66）。

オーナーの指摘（11/9）: 「今やること」が誰でも知っている一般論ばかりで浅い。読者が「なるほど」と思う一歩深い中身が無いとリピーターにならない。
「公式窓口に問い合わせる」なら、そのページの URL と、どこから辿るかまで示す。そこまで考えるサイトにする。

この段が作る欄（記事の JSON。どれも任意で、無ければ画面に出さない）:
  insight:      [{text, source}]                       1〜3個。誰でも知っている注意ではなく、公式ページにだけある具体的な事実
                                                        （本物の送信元の名前・間違えやすい欄・電話がつながりやすい時間・判断が変わる期限や金額）
  officialDesk: [{name, url, howTo[], hours, note, source}]  公式の窓口（正式名・URL・そのページへの辿り方・受付時間・注意）
  todaySteps:   [{action, steps[], url, source}]       2〜3個。誰が・どこで・何を押す/確かめるかまで書いた行動（todayActions の詳しい版）
  cause:        {text, status, source}                 なぜ起きた？（公式ページが書く原因・背景だけ。未発表なら status=investigating で「原因は調査中と発表」）
  worries:      [{q, a, action, source, general}]      こんな不安ありませんか（3〜5個。記事から自然に出る読者の不安に、出典のある答えと具体的な行動）
                                                        公式発表が答えていない不安は、警察庁・消費者庁・首相官邸などの一般の注意のページ（GENERAL_PAGES）を
                                                        出典にした「一般的な注意」（general: true）として答える
  depthHeadings: {insight, cause, steps, desk, worries, guide}  各欄の見出し（記事ごとの言葉。28字以内。決まり文句の見出しにしない。2026-11-09 オーナー）
                                                        画面は小さな札（なるほど・公式窓口 など）の下に、この見出しを出す
  decisionGuide: [{question, situation, recommend, reason, source, general}]  判断ガイド（読者が選ぶ場面がある記事だけ。
                                                        「乗り換える？」「番号を変える？」などの問いごとに 状況→おすすめ→理由→出どころ の表）

決まり（サイトの唯一の門は「嘘をつかない」）:
  - 各項目は、取りに行った公式ページ（source）の URL を1つ持つ。source は読んだページの URL だけ
  - 数字（電話番号・時刻・金額・日付）と「」で囲んだ名前は、読んだ公式ページの文字か、ページ内のリンクの文字に無ければ外す
  - 窓口・行動の url は、読んだページの URL か、そのページの中のリンクの URL だけ（URL を作らない）
  - 画面の写真（スクリーンショット）は使わない（著作権）。辿り方は文字の手順にし、サイトが自前の図（components/DepthBoxes.tsx）で描く

  python3 scripts/depth_fields.py --slug docomo-online-shop-data-leak            # 試し（結果を表示。書き込まない）
  python3 scripts/depth_fields.py --slug a,b --apply --purpose core              # 書き込む
  python3 scripts/depth_fields.py --recent-hours 36 --max 4 --apply --purpose helper  # 新しい記事（まだの記事だけ。auto_run.yml）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nonanswer  # noqa: E402  答えになっていない答え（「書かれていません」）の式（SEO A4・LLMO-A4）

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "content" / "articles"
SITE_HOST = "ai-tech-express.jp"

# この欄を書くジャンル（web_articles.FAQ_GENRES と同じ。暮らし・お金・制度・AI・製品）
DEPTH_GENRES = {"ai", "investment", "business", "public", "tech-gadget", "lifestyle", "real-estate"}
MAX_SOURCES = 6
PAGE_CAP = 7000  # 1ページあたりにプロンプトへ渡す字数
LINKS_CAP = 60  # 1ページあたりに渡すリンクの数
# 元のページの中で、窓口・確かめ方・被害にあったとき・よくある質問のページへのリンク（同じサイトの中だけ追いかける）
DESK_LINK_RE = re.compile(
    r"お問い合わせ|お問合せ|問い合わせ|窓口|相談|コールセンター|ダイヤル|確認する|確かめ|見分け|本物|被害|万が一|対処|"
    r"よくある(?:ご)?質問|FAQ|手続き(?:の)?(?:方法|案内)|申請(?:の)?(?:方法|手続)|申込(?:み)?(?:方法)?|届出|様式|チェック"
)
MAX_FOLLOW = 3
# 公式発表が答えていない不安に「一般的な注意」として答えるときの出典（公的機関の注意のページ。話題に合うものだけ読む）。
# 2026-11-09 に URL が開けることを確かめた
GENERAL_PAGES = (
    (re.compile(r"流出|漏えい|漏洩|不正アクセス|フィッシング|なりすまし|詐欺|偽(?:の|サイト|メール|SMS)|SMS|不正利用"),
     ("https://www.npa.go.jp/bureau/cyber/countermeasures/phishing.html",  # 警察庁 フィッシング対策
      "https://www.npa.go.jp/bureau/safetylife/sos47/case/")),  # 警察庁 特殊詐欺の手口と対策
    (re.compile(r"地震|震度|津波|余震"),
     ("https://www.kantei.go.jp/jp/headline/bousai/jishin.html",  # 首相官邸 地震への備えと身の守り方
      "https://www.ntt-east.co.jp/saigai/voice171/")),  # NTT東日本 災害用伝言ダイヤル（171）
)

SYSTEM = (
    "あなたは暮らしとお金のニュースサイト「サイソク」の編集者です。読者が「なるほど、そこまでは知らなかった」と思う、"
    "一歩深い実用の情報を、渡された公式ページだけから抜き出します。ページに無いことは一切書きません。出力は指定の JSON だけ。"
)

PROMPT = """# 頼みたいこと
下の「記事」に、3つの欄を足します。材料は「読んだ公式ページ」だけです。ページに書かれていないこと（数字・名前・URL・画面の場所）は作らない。
分からない欄は空にする（無理に埋めない。空なら画面に出ません）。

## insight（なるほどポイント）1〜3個
- 誰でも知っている一般論（「URLを開かない」「パスワードを変える」「公式サイトで確認する」）は入れない。記事の本文にすでにある事実のくり返しも入れない。
- 入れるのは、公式ページにだけある具体的な事実で、読者の行動や判断が変わるもの。例:
  本物の連絡の送信元の名前やリンク先のドメインの一覧／申請で間違えやすい欄／必要な書類の正式名／締切の正確な日時と、過ぎるとどうなるか／
  金額の境目（いくら以上・以下で変わる）／窓口の受付時間・混む時間・別の窓口のほうが早い場合／対象外になる条件。
- text は40〜120字の1〜2文。数字・名前はページの書き方のまま。「」で囲むのはページにある言葉だけ。
- source は、その事実が書かれている「読んだ公式ページ」の URL（下の一覧の URL を1字も変えずに）。

## official_desk（公式窓口）0〜3件
- 読者が実際に連絡・確認・申請する公式の窓口やページ。name は正式名（例「ドコモ インフォメーションセンター」「〇〇市 市民税課」）。
- url は、下の一覧のページの URL か、そのページの「リンク」に出ている URL だけ。無ければその窓口は入れない。
- how_to は、サイトのトップなどからそのページ（または番号）に辿る道順を2〜5段で（例 ["ドコモのトップ", "お知らせ", "重要なお知らせ"]）。
  ページの文字・リンクの文字にある言葉だけを使う。道順がページから分からなければ空配列 []。
- phone は電話番号（ページにあるときだけ。ページの書き方のまま。無ければ ""）。hours は受付時間（ページにあるときだけ。無ければ ""）。note は「つながりやすい時間」「何を手元に用意するか」など、ページにある注意を1文（無ければ ""）。
- source は、この窓口の情報が書かれている読んだページの URL。

## today_steps（すぐにできること）2〜3個
- 記事の「今日やること」を、誰が・どこで・何を押す/確かめるかまで具体的にした版。一般論より、この記事の公式ページにしか無い行動を先に。
- action は20〜60字の1文（何をするか）。steps はその手順を2〜4個（各40字以内。画面・メニューの名前はページにあるときだけ）。
- url は、その行動をするページ（一覧のページか、そのリンクの URL。無ければ ""）。source はその行動の根拠のページの URL。
- 特定の銘柄・物件の売買はすすめない。頭に番号を付けない。

## cause（なぜ起きた？）
- 起きたことの原因・背景を、公式ページが書いている範囲だけで、やさしい言葉で1〜3文（60〜200字）。推測しない。
- 原因が発表されていなければ status を "investigating" にし、text は「原因は調査中と発表されています」のように、公式ページの言い方で書く。
  公式ページが書いている範囲（例「外部からの不正アクセス」まで）があればそれも書く。原因の話が当てはまらない記事（制度の案内など）は
  status を "background" にして、制度が変わる理由・背景をページの範囲で書く。どちらも書けなければ text を "" にする。
- source はその根拠のページの URL。

## worries（こんな不安ありませんか）3〜5個
- この記事を読んだ人が自然に抱く不安を、関係の深い順に3〜5個（全部は書かない。この記事の読者に一番関係のあるものだけ）。
  例（情報流出）: クレジットカードは大丈夫？／口座は大丈夫？／家族に詐欺の電話が来る？／親や子どもの回線は？／乗っ取りは本当に起きる？
- q は読者の言葉で20〜40字の疑問文。a は、公式ページにある事実だけで答える（60〜160字）。答えられない問いは作らない（その問いは捨てる。「このページには書かれていません」「発表されていません」で答えない）。
  action は、その不安に対して今できる具体的な行動を1文（40〜80字）。action の根拠が答えと別のページなら action_source にその URL（同じなら ""）。
- 記事の公式ページが答えていない不安は、「一般的な注意のページ」（下の一覧で【一般】の印のもの）にある一般的に正しい安全な行動で答え、
  general を true にする（source はその一般のページ）。公式ページで答えたものは general を false。
- source は答えの根拠のページの URL。

## decision_guide（判断ガイド）0〜6行
- 読者が「どうするか選ぶ」場面がある記事だけ（例: 情報流出なら「今すぐ他社に乗り換える？」「電話番号を変える？」「パスワードや2段階認証は？」、
  制度なら「今年申請する？来年にする？」「ワンストップ特例か確定申告か」）。選ぶ場面が無ければ空配列 []。
- 1行 = 1つの状況。question は読者の迷い（20〜30字の疑問文）。同じ question に状況違いの行を2つまで（例「不審な電話が何度も来る」「まだ来ていない」）。
- situation は読者の状況（30字以内）。recommend は おすすめ（40字以内。「急がなくてよい」「検討する価値がある」など中立に。宣伝・乗り換えの後押しはしない）。
- reason は理由（60〜140字）。それをすると何が解決し、何は解決しないか。手数料・期限・手続きは読んだページにある数字だけ（いつ時点の金額かも書く）。
- source は理由の根拠のページの URL。一般的な注意のページを根拠にした行は general を true。

## headings（各欄の見出し）
- 画面では各欄に小さな札（「なるほど」「なぜ起きた？」「不安Q&A」「公式窓口」「判断ガイド」）が付く。見出しは札のくり返しにせず、記事ごとの言葉で書く。
- insight / cause / steps / desk / worries / guide の6つ。中身のある欄だけ書き、空の欄は ""。
- 各28字以内。具体的で話し言葉に近く、読者の心配か一番の事実を入れる。中身と合わない誇張・釣りは不可。「｜」「！」は使わない。数字は中身にあるものだけ。
  例（情報流出）: insight「本物のドコモのSMSは、送信元の名前で見分けられる」 cause「なぜ漏れたのか、いま分かっていること」
  worries「カードや口座、家族のスマホは大丈夫？」 guide「乗り換えるか番号を変えるか、迷ったときの決め方」

# 記事
タイトル: {title}
リード: {lede}
今の「今日やること」: {actions}
{muse}
本文（抜粋）:
<<<
{body}
>>>

# 読んだ公式ページ（これだけが材料）
{pages}
"""

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "insight": {
            "type": "ARRAY",
            "items": {"type": "OBJECT", "properties": {"text": {"type": "STRING"}, "source": {"type": "STRING"}},
                      "required": ["text", "source"], "propertyOrdering": ["text", "source"]},
        },
        "official_desk": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {"name": {"type": "STRING"}, "url": {"type": "STRING"}, "how_to": {"type": "ARRAY", "items": {"type": "STRING"}},
                               "phone": {"type": "STRING"}, "hours": {"type": "STRING"}, "note": {"type": "STRING"}, "source": {"type": "STRING"}},
                "required": ["name", "url", "how_to", "hours", "note", "source"],
                "propertyOrdering": ["name", "url", "how_to", "hours", "note", "source"],
            },
        },
        "today_steps": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {"action": {"type": "STRING"}, "steps": {"type": "ARRAY", "items": {"type": "STRING"}},
                               "url": {"type": "STRING"}, "source": {"type": "STRING"}},
                "required": ["action", "steps", "url", "source"],
                "propertyOrdering": ["action", "steps", "url", "source"],
            },
        },
    },
    "required": ["insight", "official_desk", "today_steps", "cause", "worries", "decision_guide"],
    "propertyOrdering": ["insight", "official_desk", "today_steps", "cause", "worries", "decision_guide"],
}
SCHEMA["properties"]["cause"] = {
    "type": "OBJECT",
    "properties": {"text": {"type": "STRING"}, "status": {"type": "STRING", "enum": ["stated", "investigating", "background"]},
                   "source": {"type": "STRING"}},
    "required": ["text", "status", "source"], "propertyOrdering": ["text", "status", "source"],
}
SCHEMA["properties"]["headings"] = {
    "type": "OBJECT",
    "properties": {k: {"type": "STRING"} for k in ("insight", "cause", "steps", "desk", "worries", "guide")},
    "required": ["insight", "cause", "steps", "desk", "worries", "guide"],
    "propertyOrdering": ["insight", "cause", "steps", "desk", "worries", "guide"],
}
SCHEMA["required"].append("headings")
SCHEMA["propertyOrdering"].append("headings")
SCHEMA["properties"]["decision_guide"] = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {"question": {"type": "STRING"}, "situation": {"type": "STRING"}, "recommend": {"type": "STRING"},
                       "reason": {"type": "STRING"}, "source": {"type": "STRING"}, "general": {"type": "BOOLEAN"}},
        "required": ["question", "situation", "recommend", "reason", "source", "general"],
        "propertyOrdering": ["question", "situation", "recommend", "reason", "source", "general"],
    },
}
SCHEMA["properties"]["worries"] = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {"q": {"type": "STRING"}, "a": {"type": "STRING"}, "action": {"type": "STRING"},
                       "source": {"type": "STRING"}, "general": {"type": "BOOLEAN"}, "action_source": {"type": "STRING"}},
        "required": ["q", "a", "action", "source", "general", "action_source"],
        "propertyOrdering": ["q", "a", "action", "source", "general", "action_source"],
    },
}

HEADING_MAX = 28
# 見出しに使わない決まり文句（札と同じ言葉・どの記事にも付く言葉）
TEMPLATE_HEADING_RE = re.compile(
    r"^(?:なるほど(?:ポイント)?|なぜ起きた[？?]?|こんな不安ありませんか[？?]?|公式窓口|(?:迷ったときの)?判断ガイド|すぐにできること|"
    r"概要|ポイント|まとめ|注意点|よくある質問|不安Q&A|問い合わせ先|原因)$"
)

# 誰でも知っている一般論（なるほどポイントには入れない）
GENERIC_RE = re.compile(
    r"(?:URL|リンク)(?:を|は|には)(?:開か|押さ|タップし|クリックし|アクセスし)ない(?:ように|で)?(?:しましょう|ください|こと)?。?$|"
    r"^(?:念のため)?パスワードを(?:変更|変え)(?:しましょう|ましょう|てください)|"
    r"^公式(?:サイト|ページ|アプリ)で(?:確認|確かめ)(?:しましょう|てください)|注意(?:しましょう|してください|が必要です)。?$|最新の情報を(?:確認|ご確認)"
)


def log(message: str) -> None:
    print(message, flush=True)


# --------------------------------------------------------------------------- #
# 文字の照合（数字・「」の名前・URL がページにあるか）
# --------------------------------------------------------------------------- #

def norm(text: str) -> str:
    """照合用: 全角→半角・空白と桁区切りを外す・ハイフンの仲間をそろえる"""
    text = unicodedata.normalize("NFKC", text or "")
    text = re.sub(r"[‐‑‒–—―ー−－]", "-", text)
    return re.sub(r"[\s,、　]", "", text)


NUM_RE = re.compile(r"\d[\d.:\-/]*\d|\d")
QUOTE_RE = re.compile(r"「([^「」]{2,40})」")


def numbers_in(text: str) -> list[str]:
    t = unicodedata.normalize("NFKC", text or "").replace(",", "")
    t = re.sub(r"[‐‑‒–—―ー−－]", "-", t)
    return NUM_RE.findall(t)


TRACK_RE = re.compile(r"([?&])(?:icid|utm_[a-z]+|cid|from)=[^&#]*&?")


def clean_url(url: str) -> str:
    """計測用の引数（icid・utm_…）を外した URL（画面に出す・照合する形）"""
    u = (url or "").strip()
    while TRACK_RE.search(u):
        u = TRACK_RE.sub(r"\1", u)
    return re.sub(r"[?&]$", "", u)


def canon_url(url: str) -> str:
    u = clean_url(url)
    u = re.sub(r"#.*$", "", u)
    u = re.sub(r"^http://", "https://", u)
    return u.rstrip("/")


def host_of(url: str) -> str:
    return re.sub(r"^www\.", "", (urlparse(url).hostname or "").lower())


def unsupported(text: str, corpus_norm: str) -> list[str]:
    """ページ（corpus）に無い数字・「」の名前。空なら照合に通った"""
    bad = []
    for n in numbers_in(text):
        # 1桁の数字（「2つ」「3段目」）は手順の数え方に使うので照合しない
        if len(n) >= 2 and norm(n) not in corpus_norm:
            bad.append(n)
    for q in QUOTE_RE.findall(text or ""):
        if norm(q) not in corpus_norm:
            bad.append(f"「{q}」")
    return bad


# --------------------------------------------------------------------------- #
# 公式ページを読む
# --------------------------------------------------------------------------- #

def source_urls(record: dict) -> list[str]:
    """記事の公式の出典の URL（元記事 → Muse の出典 → 確かめた資料）。報道・当サイトのページは外す"""
    import public_interest  # noqa: PLC0415

    urls = [record.get("sourceUrl") or ""]
    urls += [s.get("url") or "" for s in record.get("museSources") or [] if isinstance(s, dict)]
    urls += [s.get("url") or "" for s in record.get("factSources") or [] if isinstance(s, dict)]
    out: list[str] = []
    for u in urls:
        if not u.startswith("http") or SITE_HOST in u or canon_url(u) in {canon_url(x) for x in out}:
            continue
        try:
            if public_interest.is_press_url(u):
                continue
        except Exception:  # noqa: BLE001 - 判定できなければ残す
            pass
        out.append(u)
    return out[:MAX_SOURCES]


def fetch_pages(urls: list[str], follow: bool = True) -> list[dict]:
    """[{url, name, text, links:[{url,text}]}]。読めないページは飛ばす。
    follow なら、1件目のページの中の窓口・確かめ方・被害・FAQ のリンク（同じサイト）を MAX_FOLLOW 本まで追いかける"""
    import feeds  # noqa: PLC0415
    import source_links  # noqa: PLC0415

    pages: list[dict] = []
    seen: set[str] = set()

    def read(url: str) -> dict | None:
        key = canon_url(url)
        if key in seen:
            return None
        seen.add(key)
        try:
            page = feeds.fetch_article_text(url)
        except Exception as error:  # noqa: BLE001
            log(f"   [depth] 読めません {url[:90]}: {str(error)[:80]}")
            return None
        text = (page.get("text") or "").strip()
        if len(text) < 150:
            return None
        raw = [l for l in page.get("links") or [] if (l.get("url") or "").startswith("http")]
        # 本文の中のリンクだけ（サイト共通のメニューは除く）。本文のリンクが分からないページは全部
        main_links = [l for l in raw if l.get("main")] or raw
        links = [{"url": clean_url(l.get("url") or ""), "text": re.sub(r"\s+", " ", l.get("text") or "").strip()[:60],
                  "main": bool(l.get("main"))}
                 for l in main_links if not re.search(r"twitter\.com/share|plus-msg\.com/share|facebook\.com/share", l.get("url") or "")]
        name = (page.get("title") or "").strip() or source_links.site_name(url)
        return {"url": url, "final_url": page.get("final_url") or url, "name": name[:80], "text": text, "links": links}

    for url in urls:
        if page := read(url):
            pages.append(page)
    if follow and pages:
        base_hosts = {host_of(p["final_url"]) for p in pages} | {host_of(p["url"]) for p in pages}
        extra = []
        for p in pages:
            for link in p["links"]:
                if link.get("main") and host_of(link["url"]) in base_hosts and DESK_LINK_RE.search(link["text"] or "") \
                        and canon_url(link["url"]) not in seen and not link["url"].lower().endswith((".zip", ".xlsx", ".docx")):
                    extra.append(link["url"])
        # 窓口・問い合わせのページを先に（「相談センターからの電話番号」のような FAQ より、問い合わせの窓口の一覧が役に立つ）
        extra.sort(key=lambda u: 0 if re.search(r"inquiry|contact|toiawase|soudan|madoguchi", u, re.I) else 1)
        for url in list(dict.fromkeys(extra))[:MAX_FOLLOW]:
            if page := read(url):
                pages.append(page)
    return pages


QUAKE_RE = re.compile(r"【地震】|震度[1-7１-７]")
QUAKE_PAGES = ("https://www.kantei.go.jp/jp/headline/bousai/jishin.html", "https://www.ntt-east.co.jp/saigai/voice171/",
               "https://www.jma.go.jp/jma/menu/jishin-portal.html")


def general_urls(record: dict) -> list[str]:
    """記事の話題に合う「一般的な注意」のページ（GENERAL_PAGES）"""
    text = f"{record.get('title', '')} {' '.join(record.get('tags') or [])} {record.get('lede', '')}"
    out: list[str] = []
    for pattern, urls in GENERAL_PAGES:
        if pattern.search(text):
            out += [u for u in urls if u not in out]
    return out[:4]


def fetch_general(record: dict) -> list[dict]:
    pages = fetch_pages(general_urls(record), follow=False)
    for p in pages:
        p["general"] = True
    return pages


def pages_block(pages: list[dict]) -> str:
    parts = []
    for i, p in enumerate(pages, 1):
        cap = PAGE_CAP // 2 if p.get("general") else PAGE_CAP
        links = "" if p.get("general") else "\n".join(
            f"  - {l['text'] or '(文字なし)'}: {l['url']}" for l in p["links"][:LINKS_CAP] if l["text"])
        mark = "【一般】一般的な注意のページ（記事の発表元ではない）: " if p.get("general") else ""
        parts.append(f"## ページ{i}: {mark}{p['name']}\nURL: {p['url']}\n本文:\n<<<\n{p['text'][:cap]}\n>>>\nリンク:\n{links or '  （なし）'}")
    return "\n\n".join(parts)


# --------------------------------------------------------------------------- #
# 答えを確かめて整える（嘘を出さない）
# --------------------------------------------------------------------------- #

def _clean(s: object, cap: int) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()[:cap]


def validate(data: dict, pages: list[dict], record: dict | None = None) -> tuple[dict, list[str]]:
    """LLM の答え → (記事に入れる欄 {insight, officialDesk, todaySteps}, 外した理由)。
    source は読んだページの URL だけ。url は読んだページかそのリンクの URL だけ。数字・「」の名前は読んだページの文字かリンクの文字にあるものだけ"""
    by_url = {}
    for p in pages:
        by_url[canon_url(p["url"])] = p
        by_url.setdefault(canon_url(p["final_url"]), p)
    link_urls = {canon_url(l["url"]): l["url"] for p in pages for l in p["links"]}
    page_urls = {canon_url(p["url"]): p["url"] for p in pages}
    corpus = norm("\n".join(p["text"] + "\n" + " ".join(l["text"] for l in p["links"]) for p in pages))
    body_norm = norm(f"{(record or {}).get('body', '')} {(record or {}).get('lede', '')}")
    dropped: list[str] = []

    def src(value: object) -> str | None:
        key = canon_url(str(value or ""))
        p = by_url.get(key)
        return p["url"] if p else None

    def known_url(value: object) -> str:
        key = canon_url(str(value or ""))
        if not key:
            return ""
        return page_urls.get(key) or link_urls.get(key) or ""

    insight = []
    for row in data.get("insight") or []:
        if not isinstance(row, dict):
            continue
        text, source = _clean(row.get("text"), 160), src(row.get("source"))
        if len(text) < 15:
            continue
        if source and by_url[canon_url(source)].get("general"):
            dropped.append(f"insight: 一般のページは出典にしない（{text[:40]}）")
            continue
        if not source:
            dropped.append(f"insight: 出典が読んだページに無い（{str(row.get('source'))[:60]}）")
            continue
        if bad := unsupported(text, corpus):
            dropped.append(f"insight: ページに無い {'・'.join(bad[:3])}（{text[:40]}）")
            continue
        if GENERIC_RE.search(text):
            dropped.append(f"insight: 一般論（{text[:40]}）")
            continue
        if len(text) >= 20 and norm(text)[:30] in body_norm:
            dropped.append(f"insight: 本文のくり返し（{text[:40]}）")
            continue
        insight.append({"text": text, "source": source})
    desks = []
    for row in data.get("official_desk") or []:
        if not isinstance(row, dict):
            continue
        name, url, source = _clean(row.get("name"), 50), known_url(row.get("url")), src(row.get("source"))
        if not name or not url:
            dropped.append(f"desk: URL が読んだページ・そのリンクに無い（{name[:30]} {str(row.get('url'))[:60]}）")
            continue
        how = [_clean(x, 30) for x in row.get("how_to") or [] if _clean(x, 30)][:5]
        hours, note, phone = _clean(row.get("hours"), 60), _clean(row.get("note"), 120), _clean(row.get("phone"), 60)
        if phone and unsupported(phone, corpus):
            dropped.append(f"desk: 電話番号がページに無い（{phone}）")
            phone = ""
        text = " ".join([name, hours, note] + how)
        if bad := unsupported(text, corpus):
            # 受付時間・注意に作った数字があれば、その欄だけ外す（窓口の名前と URL は確かなので残す）
            if unsupported(hours, corpus):
                hours = ""
            if unsupported(note, corpus):
                note = ""
            how = [h for h in how if not unsupported(h, corpus)]
            if unsupported(name, corpus):
                dropped.append(f"desk: 名前がページに無い {'・'.join(bad[:3])}（{name}）")
                continue
        # 辿り方の各段は、ページの文字かリンクの文字にある言葉だけ（作った画面の場所を出さない）
        how = [h for h in how if norm(re.sub(r"[「」『』]", "", h)) in corpus]
        if len(how) < 2:
            how = []
        entry = {"name": name, "url": url, "source": source or url}
        if how:
            entry["howTo"] = how
        if phone:
            entry["phone"] = phone
        if hours:
            entry["hours"] = hours
        if note:
            entry["note"] = note
        if url not in {d["url"] for d in desks}:
            desks.append(entry)
    steps = []
    for row in data.get("today_steps") or []:
        if not isinstance(row, dict):
            continue
        action, source = _clean(row.get("action"), 90), src(row.get("source"))
        action = re.sub(r"^(?:[・\-*]\s*|\d{1,2}\s*[.)）]\s*)", "", action)
        if len(action) < 10:
            continue
        if not source:
            dropped.append(f"step: 出典が読んだページに無い（{action[:40]}）")
            continue
        if bad := unsupported(action, corpus):
            dropped.append(f"step: ページに無い {'・'.join(bad[:3])}（{action[:40]}）")
            continue
        sub = [_clean(x, 60) for x in row.get("steps") or [] if _clean(x, 60)]
        sub = [x for x in sub if not unsupported(x, corpus)][:4]
        entry = {"action": action, "source": source}
        if sub:
            entry["steps"] = sub
        if url := known_url(row.get("url")):
            entry["url"] = url
        steps.append(entry)
    cause = None
    raw = data.get("cause") if isinstance(data.get("cause"), dict) else {}
    ctext, csrc = _clean(raw.get("text"), 260), src(raw.get("source"))
    status = raw.get("status") if raw.get("status") in ("stated", "investigating", "background") else "stated"
    if ctext and csrc and not by_url[canon_url(csrc)].get("general"):
        if bad := unsupported(ctext, corpus):
            dropped.append(f"cause: ページに無い {'・'.join(bad[:3])}（{ctext[:40]}）")
        else:
            cause = {"text": ctext, "status": status, "source": csrc}
    elif ctext:
        dropped.append(f"cause: 出典が記事の公式ページでない（{str(raw.get('source'))[:60]}）")
    worries = []
    for row in data.get("worries") or []:
        if not isinstance(row, dict):
            continue
        q, a, act, source = _clean(row.get("q"), 60), _clean(row.get("a"), 220), _clean(row.get("action"), 120), src(row.get("source"))
        if len(q) < 6 or len(a) < 15:
            continue
        if not source:
            dropped.append(f"worry: 出典が読んだページに無い（{q[:30]}）")
            continue
        if bad := unsupported(f"{a} {act}", corpus):
            dropped.append(f"worry: ページに無い {'・'.join(bad[:3])}（{q[:30]}）")
            continue
        # 答えが「このページには書かれていません」の不安は捨てる（2文目以降のその文は外す。scripts/nonanswer.py。SEO A4・LLMO-A4）
        if not (answer := nonanswer.answer_or_none(a)):
            dropped.append(f"worry: 答えになっていない（{q[:30]}: {a[:30]}）")
            continue
        a = answer
        # 一般のページを出典にした答えは、必ず「一般的な注意」の札を付ける（記事の発表元の答えと見分けられるように）
        general = bool(by_url[canon_url(source)].get("general"))
        entry = {"q": q, "a": a, "source": source}
        if act:
            entry["action"] = act
            if (asrc := src(row.get("action_source"))) and canon_url(asrc) != canon_url(source):
                entry["actionSource"] = asrc
                if by_url[canon_url(asrc)].get("general"):
                    entry["actionGeneral"] = True
        if general:
            entry["general"] = True
        worries.append(entry)
    guide = []
    for row in data.get("decision_guide") or []:
        if not isinstance(row, dict):
            continue
        q, sit, rec, why, source = (_clean(row.get("question"), 50), _clean(row.get("situation"), 50), _clean(row.get("recommend"), 70),
                                    _clean(row.get("reason"), 240), src(row.get("source")))
        if not (q and sit and rec and len(why) >= 15):
            continue
        if not source:
            dropped.append(f"guide: 出典が読んだページに無い（{q[:30]}）")
            continue
        if bad := unsupported(f"{sit} {rec} {why}", corpus):
            dropped.append(f"guide: ページに無い {'・'.join(bad[:3])}（{q[:30]}）")
            continue
        entry = {"question": q, "situation": sit, "recommend": rec, "reason": why, "source": source}
        if by_url[canon_url(source)].get("general"):
            entry["general"] = True
        guide.append(entry)
    out: dict = {}
    # 各欄の見出し（記事ごとの言葉。中身のある欄だけ・28字以内・「｜」なし・決まり文句は外す）
    present = {"insight": bool(insight), "cause": bool(cause), "steps": len(steps) >= 2, "desk": bool(desks),
               "worries": len(worries) >= 2, "guide": bool(guide)}
    heads = {}
    raw_heads = data.get("headings") if isinstance(data.get("headings"), dict) else {}
    for key, ok in present.items():
        h = _clean(raw_heads.get(key), 40).replace("｜", "　").replace("|", " ")
        h = re.sub(r"[！!]+", "", h).strip()
        if not ok or not h:
            continue
        if len(h) > HEADING_MAX:
            dropped.append(f"heading: 長すぎる（{key}: {h}）")
        elif TEMPLATE_HEADING_RE.match(h):
            dropped.append(f"heading: 決まり文句（{key}: {h}）")
        elif bad := unsupported(h, corpus):
            dropped.append(f"heading: ページに無い {'・'.join(bad[:3])}（{h}）")
        else:
            heads[key] = h
    if heads:
        out["depthHeadings"] = heads
    if guide:
        out["decisionGuide"] = guide[:6]
    if cause:
        out["cause"] = cause
    if len(worries) >= 2:
        out["worries"] = worries[:5]
    if insight:
        out["insight"] = insight[:3]
    if desks:
        out["officialDesk"] = desks[:3]
    if len(steps) >= 2:
        out["todaySteps"] = steps[:3]
    return out, dropped


def read_pages(record: dict) -> list[dict]:
    """記事の材料のページ（公式の出典 → 窓口などのリンク先 → 話題に合う一般の注意のページ）"""
    pages = fetch_pages(source_urls(record))
    if not pages and QUAKE_RE.search(record.get("title") or ""):
        # 地震の速報（気象庁の地図のページは文字で読めない）: 政府・気象庁の地震の案内のページを材料にする
        pages = fetch_pages(list(QUAKE_PAGES), follow=False)
    if pages:
        seen = {canon_url(p["url"]) for p in pages}
        pages += [g for g in fetch_general(record) if canon_url(g["url"]) not in seen]
    return pages


def prompt_for(record: dict, pages: list[dict]) -> str:
    return PROMPT.format(
        title=record.get("title", ""), lede=record.get("lede", ""),
        actions=" / ".join(record.get("todayActions") or []) or "（なし）",
        muse=(f"記者（Muse）が調べたメモ（参考。下の公式ページで確かめられることだけ使う）:\n<<<\n{record['museDepthNotes'][:3000]}\n>>>\n"
              if record.get("museDepthNotes") else ""),
        body=(record.get("body") or "")[:5000], pages=pages_block(pages),
    )


def build(record: dict, purpose: str | None = "helper", pages: list[dict] | None = None) -> tuple[dict, list[str], str]:
    """記事 → (足す欄, 外した理由, 使ったモデル)。公式ページが読めなければ ({}, [理由], "")"""
    import llm  # noqa: PLC0415

    if pages is None:
        pages = read_pages(record)
    if not [p for p in pages if not p.get("general")]:
        return {}, ["公式ページを読めない"], ""
    prompt = prompt_for(record, pages)
    data, model = llm.generate_json(SYSTEM, prompt, SCHEMA, temperature=0.2, max_output_tokens=4096, tier="bulk",
                                    **({"purpose": purpose} if purpose else {}))
    fields, dropped = validate(data, pages, record)
    return fields, dropped, model


def apply_fields(record: dict, fields: dict) -> dict:
    """欄を記事に入れる。todaySteps があれば todayActions（ほかの段・SNS・動画が使う短い文）もそろえる"""
    for key in ("insight", "officialDesk", "todaySteps", "cause", "worries", "decisionGuide", "depthHeadings"):
        if fields.get(key):
            record[key] = fields[key]
    if fields.get("todaySteps"):
        record["todayActions"] = [s["action"] for s in fields["todaySteps"]][:3]
    record["depthAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record.pop("museDepthNotes", None)
    # 公式のページで確かめた事実の欄を足したので、公開の準備（公開から30分以内）でなければ更新日時と更新履歴を残す（SEO A16）
    import updated_at  # noqa: PLC0415

    updated_at.touch_depth(record, fields)
    return record


# --------------------------------------------------------------------------- #
# 実行
# --------------------------------------------------------------------------- #

def targets(args) -> list[Path]:
    if args.slug:
        return [ARTICLES_DIR / f"{s.strip()}.json" for s in args.slug.split(",") if s.strip()]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.recent_hours or 36)
    rows = []
    for p in ARTICLES_DIR.glob("*.json"):
        try:
            r = json.loads(p.read_text("utf-8"))
        except ValueError:
            continue
        if r.get("depthAt") or r.get("genreSlug") not in DEPTH_GENRES or r.get("sourceType") == "roundup":
            continue
        stamp = str(r.get("generatedAt") or r.get("publishedAt") or "")
        try:
            when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            continue
        if when >= cutoff:
            rows.append((stamp, p))
    return [p for _, p in sorted(rows, reverse=True)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug")
    ap.add_argument("--recent-hours", type=float)
    ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--budget", type=float, default=0, help="秒。超えたら次の記事に進まない")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--dump", help="（手作業の下書き用）読んだページとプロンプトをこのフォルダに書き出すだけ")
    ap.add_argument("--extra", help="（--dump と）材料に足す公式ページの URL（カンマ区切り。手数料・設定のページなど）")
    ap.add_argument("--answer", help="（手作業の下書き用）--dump のフォルダ。<slug>.answer.json を同じ照合に通して書き込む")
    ap.add_argument("--purpose", default="helper", help="Claude API の段（helper = Haiku・core = Sonnet）。'' で無料モデルだけ")
    args = ap.parse_args(argv)
    if not (args.slug or args.recent_hours):
        ap.print_help()
        return 1
    import llm  # noqa: PLC0415

    llm._load_env_local()  # noqa: SLF001 - 手元の実行用（CI は環境変数）
    started, done = time.time(), 0
    for path in targets(args):
        if args.budget and time.time() - started > args.budget:
            log("[depth] 時間切れ（残りは次の回）")
            break
        if not path.exists():
            log(f"[NG] {path.stem}: 記事がありません")
            continue
        record = json.loads(path.read_text("utf-8"))
        if record.get("depthAt") and not args.redo and not args.slug:
            continue
        if args.dump:
            out = Path(args.dump)
            out.mkdir(parents=True, exist_ok=True)
            pages = read_pages(record)
            if args.extra:
                seen = {canon_url(p["url"]) for p in pages}
                pages += [p for p in fetch_pages([u for u in args.extra.split(",") if u.strip()], follow=False)
                          if canon_url(p["url"]) not in seen]
            (out / f"{path.stem}.pages.json").write_text(json.dumps(pages, ensure_ascii=False, indent=1), "utf-8")
            (out / f"{path.stem}.prompt.txt").write_text(prompt_for(record, pages), "utf-8")
            log(f"[dump] {path.stem}: ページ{len(pages)}本 → {out}")
            continue
        try:
            if args.answer:
                folder = Path(args.answer)
                pages = json.loads((folder / f"{path.stem}.pages.json").read_text("utf-8"))
                fields, dropped = validate(json.loads((folder / f"{path.stem}.answer.json").read_text("utf-8")), pages, record)
                model = "editor"
            else:
                fields, dropped, model = build(record, purpose=args.purpose or None)
        except Exception as error:  # noqa: BLE001 - 1本の失敗で止めない
            log(f"[NG] {path.stem}: {str(error)[:160]}")
            continue
        log(f"[ok] {path.stem}: なるほど{len(fields.get('insight') or [])} 窓口{len(fields.get('officialDesk') or [])} "
            f"手順{len(fields.get('todaySteps') or [])} 原因{'有' if fields.get('cause') else '無'} 不安{len(fields.get('worries') or [])}"
            f" 判断{len(fields.get('decisionGuide') or [])} 外した{len(dropped)}（{model}）")
        for d in dropped[:6]:
            log(f"     外した: {d}")
        if not args.apply:
            print(json.dumps(fields, ensure_ascii=False, indent=2))
        elif fields:
            latest = json.loads(path.read_text("utf-8"))  # 書き込む直前に読み直す（ほかの段の直しに重ねる）
            path.write_text(json.dumps(apply_fields(latest, fields), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        elif args.apply:
            # 書けなかった記事も印を付け、毎回読みに行かない（--redo でやり直せる）
            latest = json.loads(path.read_text("utf-8"))
            latest["depthAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            path.write_text(json.dumps(latest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        done += 1
        if args.max and done >= args.max:
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
