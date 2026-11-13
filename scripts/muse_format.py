#!/usr/bin/env python3
"""Muse（Meta の AI の書き手）が書く記事のファイルの読み方と、安い形の確かめ（2026-11-08 オーナー承認・台帳 A59）。

標準ライブラリだけで動く（オーナーの Mac の scripts/muse_articles_push.py と、GitHub Actions の scripts/muse_articles.py の両方が使う）。
書式は ~/Downloads/saisoku-articles/FORMAT.md（正本はこのファイルの FORMAT_MD）。

ファイル: 「YYYYMMDD-ジャンル-短い題名.md」。先頭に --- で囲んだ項目（title / genre / sources / notes）、そのあとに本文（Markdown）。
  ---
  title: 会社員の平均給与は487万円　国税庁の2025年分の調査
  genre: お金
  sources:
    - url: https://www.nta.go.jp/....pdf
      name: 国税庁
      facts: 平均給与487万円・前年比1.9%増（1ページ「２ 調査結果の概要」）
  notes: |
    題材を選んだ理由。未確認の点。
  ---
  本文（## の見出し付き）
"""
from __future__ import annotations

import re
import unicodedata

# Muse が書いてよいジャンル（ファイル名と genre の欄）。サイトのジャンルへの対応は scripts/muse_articles.py の LANE_BY_GENRE
GENRES = ("手続き", "お金", "値上げ", "早見表", "速報解説", "暮らし", "AI・テック", "ビジネス", "比較")
TITLE_MIN, TITLE_MAX = 18, 45  # 品質の門（quality.TITLE_RANGE 18〜64）より短く。一覧で切れない長さ（40字の目安）
# 2026-11-09 オーナー「落とす理由は嘘だけ」: 長すぎる題名は落とさず、TITLE_HARD_MAX までに区切りで縮める
TITLE_HARD_MAX = 64


def fit_title(title: str) -> str:
    """長すぎる題名を、区切り（全角の空白・読点）で TITLE_HARD_MAX 字までに縮める。区切りが無ければそのまま切る"""
    title = re.sub(r"[！!]+", "", title).strip()
    if len(title) <= TITLE_HARD_MAX:
        return title
    head = title[:TITLE_HARD_MAX]
    cut = max(head.rfind("　"), head.rfind(" "), head.rfind("、"))
    return (head[:cut] if cut >= TITLE_MIN else head).strip()
BODY_MIN = 1800  # 地の文の字数（見出し・記号を除く）。公開前の門の「薄い」（indexnow.THIN_BODY 1500字）に落ちないよう余裕を持つ
BODY_MAX = 9000
MAX_SOURCES = 10
NAME_RE = re.compile(r"^(\d{8})-([^-]+)-(.+)\.md$")
# 出典にしない URL（報道・まとめ・SNS・検索。事実は公式の一次情報だけ・台帳 W31）。正確な判定は Actions 側で public_interest.is_press_url も使う
NOT_OFFICIAL_RE = re.compile(
    r"(news\.yahoo|yahoo\.co\.jp/news|nikkei\.com|asahi\.com|mainichi\.jp|yomiuri\.co\.jp|sankei\.com|nhk\.or\.jp|jiji\.com|kyodonews|"
    r"itmedia\.co\.jp|impress\.co\.jp|wikipedia\.org|twitter\.com|(?<![a-z0-9.-])x\.com/|facebook\.com|instagram\.com|threads\.(net|com)|"
    r"youtube\.com/(?!premium|intl|t/)|youtu\.be|note\.com|ameblo|hatena|google\.com/search|bing\.com|prtimes\.jp|atpress|newscast|value-press)",
    re.I,
)

# 2026-11-13 オーナー承認（台帳 W31 の Muse の道だけの例外）: 主要な報道機関の記事は、公式の出典に添える「2番目以降の出典」として使ってよい。
# 使えるのはこの一覧のホストだけ（ほかの報道・ブログ・まとめは今までどおり出典にできない）。
# 報道にしか無い事実は「〇〇によると」「〇〇が報じた」と報道として書く（scripts/muse_articles.py の press_problems が確かめる）
PRESS_ALLOWED: tuple[tuple[str, str], ...] = (
    ("news.web.nhk", "NHK"), ("nhk.or.jp", "NHK"),
    ("kyodonews.jp", "共同通信"), ("kyodonews.net", "共同通信"), ("kyodo.co.jp", "共同通信"), ("47news.jp", "共同通信"), ("nordot.app", "共同通信"),
    ("jiji.com", "時事通信"), ("nikkei.com", "日本経済新聞"), ("asahi.com", "朝日新聞"), ("yomiuri.co.jp", "読売新聞"), ("mainichi.jp", "毎日新聞"),
    ("reuters.com", "ロイター"), ("bloomberg.com", "ブルームバーグ"), ("bloomberg.co.jp", "ブルームバーグ"), ("apnews.com", "AP通信"),
    ("newsdig.tbs.co.jp", "TBS NEWS DIG"), ("news.tv-asahi.co.jp", "テレビ朝日"), ("news.ntv.co.jp", "日本テレビ"), ("fnn.jp", "FNN"),
)
# 本文で「どこの報道か」を示す呼び名（「毎日」「AP」だけのような、ふつうの言葉と紛れる短い呼び名は入れない）
PRESS_ALIASES = {
    "NHK": ("NHK",), "共同通信": ("共同通信", "共同"), "時事通信": ("時事通信", "時事"), "日本経済新聞": ("日本経済新聞", "日経"),
    "朝日新聞": ("朝日新聞", "朝日"), "読売新聞": ("読売新聞", "読売"), "毎日新聞": ("毎日新聞",),
    "ロイター": ("ロイター", "Reuters"), "ブルームバーグ": ("ブルームバーグ", "Bloomberg"), "AP通信": ("AP通信",),
    "TBS NEWS DIG": ("TBS",), "テレビ朝日": ("テレビ朝日", "テレ朝", "ANN"), "日本テレビ": ("日本テレビ", "日テレ", "NNN"), "FNN": ("FNN", "フジテレビ"),
}
# いろいろな社の記事が載る配信の場（nordot）。出典の name に共同通信と書いてあるときだけ共同通信の記事として扱う
PRESS_SHARED_HOSTS = {"nordot.app": "共同"}


def press_outlet(url: str, name: str = "") -> str:
    """出典に使ってよい主要な報道機関の URL なら、その名前（「NHK」「ロイター」）。違えば空"""
    m = re.match(r"https?://([^/?#:]+)", (url or "").strip(), re.I)
    host = (m.group(1) if m else "").lower()
    for suffix, outlet in PRESS_ALLOWED:
        if host == suffix or host.endswith("." + suffix):
            need = PRESS_SHARED_HOSTS.get(suffix)
            return outlet if not need or need in (name or "") else ""
    return ""


class FormatError(ValueError):
    """書式の誤り（Muse に返す理由の文）"""


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'「":
        return value[1:-1].strip()
    return value


def parse(text: str) -> dict:
    return _fix_bars(_parse(text))


def _fix_bars(d: dict) -> dict:
    for k in ("title", "body"):
        if isinstance(d.get(k), str):
            d[k] = re.sub(r"\s*[｜|]\s*", "　", d[k]) if k == "title" else d[k].replace("｜", "　")
    return d


def _parse(text: str) -> dict:
    """ファイルの中身 → {title, genre, sources:[{url,name,facts}], notes, body}。形が読めなければ FormatError"""
    text = nfc(text).replace("\r\n", "\n").lstrip("﻿")
    m = re.match(r"\s*---\n(.*?)\n---[ \t]*\n(.*)\Z", text, re.S)
    if not m:
        raise FormatError("先頭の項目（--- で囲んだ title / genre / sources / notes）が読めません。FORMAT.md の見本の形にしてください")
    head, body = m.group(1), m.group(2)
    data: dict = {"title": "", "genre": "", "sources": [], "notes": "", "body": body.strip()}
    lines = head.split("\n")
    extra_notes: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        top = re.match(r"^([A-Za-z_]+):\s*(.*)$", line)
        if not top:
            # 2026-11-12: 「何が変わる：…」のような日本語の行が先頭の項目に入って原稿ごと止まっていた（マクドナルド・ゆうパック・ヨコハマタイヤ）。
            # 書き方の違いで落とさない（落とすのは嘘だけ）。サイトに出ないメモ（notes）の続きとして受け取る
            extra_notes.append(line.strip())
            continue
        key, value = top.group(1).lower(), top.group(2).strip()
        if value in ("|", ">", "|-", ">-"):
            block = []
            while i < len(lines) and (lines[i].startswith((" ", "\t")) or not lines[i].strip()):
                block.append(lines[i].strip())
                i += 1
            value = "\n".join(block).strip()
        if key == "sources":
            items: list[dict] = []
            while i < len(lines) and (lines[i].startswith((" ", "\t", "-")) or not lines[i].strip()):
                row = lines[i].strip()
                i += 1
                if not row:
                    continue
                if row.startswith("- "):
                    row = row[2:].strip()
                    items.append({})
                    if not re.match(r"^[a-z_]+:", row):  # 「- https://...」だけの書き方も受ける
                        items[-1]["url"] = _unquote(row)
                        continue
                if not items:
                    raise FormatError("sources は「- url: …」の箇条書きにしてください")
                kv = re.match(r"^([a-z_]+):\s*(.*)$", row)
                if kv:
                    items[-1][kv.group(1)] = _unquote(kv.group(2))
            data["sources"] = [{"url": s.get("url", ""), "name": s.get("name", ""), "facts": s.get("facts", "")} for s in items]
        elif key in ("title", "genre", "notes", "depth"):
            data[key] = _unquote(value)
    if extra_notes:
        data["notes"] = "\n".join([data["notes"], *extra_notes]).strip()
    return data


def plain_len(body: str) -> int:
    text = re.sub(r"(?m)^\s*#{1,6}.*$", "", body or "")
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return len(re.sub(r"[\s|*`>#\-]", "", text))


def problems(data: dict, filename: str = "") -> list[str]:
    """LLM を使わない形の確かめ。Muse に返す理由の文のリスト（空なら合格）"""
    out: list[str] = []
    if filename and not NAME_RE.match(nfc(filename)):
        out.append("ファイル名は「YYYYMMDD-ジャンル-短い題名.md」にしてください（例 20261108-お金-平均給与487万円.md）")
    title = data.get("title") or ""
    if title:
        # 2026-11-09 オーナー「落とす理由は嘘だけ」: 長さ・感嘆符は落とさず自動で直す
        data["title"] = title = fit_title(title)
    if not title:
        out.append("title がありません")
    elif len(title) < TITLE_MIN:
        out.append(f"title の長さは{TITLE_MIN}〜{TITLE_MAX}字にしてください（いま{len(title)}字）")
    # 「｜」は落とさず自動で全角の空白に直す（parse の段。2026-11-08 オーナー）
    if data.get("genre") and data["genre"] not in GENRES:
        out.append(f"genre は次のどれかにしてください: {'・'.join(GENRES)}（いま「{data['genre']}」）")
    if not data.get("genre"):
        out.append("genre がありません")
    sources = data.get("sources") or []
    if not sources:
        out.append("sources（公式の出典 URL）がありません")
    # 2026-11-09 オーナー: 落とす理由は「嘘」だけ。出典が多いときは落とさず、先頭の MAX_SOURCES 件を使う
    if len(sources) > MAX_SOURCES:
        data["sources"] = sources = sources[:MAX_SOURCES]
    # 2026-11-09 オーナー「落とす理由は嘘だけ」: http:// は https:// に直す。公式でない出典は、ほかに出典があれば外して続ける
    for s in sources:
        if (s.get("url") or "").startswith("http://"):
            s["url"] = "https://" + s["url"][len("http://"):]
    # 2026-11-13: 主要な報道機関（PRESS_ALLOWED）の記事は、報道の出典として残す（s["press"] に名前）。公式の出典を先に並べる
    for s in sources:
        if outlet := press_outlet(s.get("url") or "", s.get("name") or ""):
            s["press"] = outlet
        else:
            s.pop("press", None)
    official = [s for s in sources if not s.get("press") and not NOT_OFFICIAL_RE.search(s.get("url") or "")]
    press = [s for s in sources if s.get("press")]
    if (official or press) and (len(official) + len(press) < len(sources) or (official and press)):
        data["sources"] = sources = official + press
    for s in sources:
        url = s.get("url") or ""
        if not url.startswith("https://"):
            out.append(f"出典の URL は https:// で始まる公式のページにしてください（「{url[:60]}」）")
        elif NOT_OFFICIAL_RE.search(url) and not s.get("press"):
            out.append(f"報道・まとめ・SNS・プレスリリース配信のページは出典にできません。官公庁・会社自身の公式ページにしてください（{url[:80]}）")
        if not (s.get("facts") or "").strip():
            out.append(f"出典ごとに facts（どの数字がそのページのどこに書かれているか）を書いてください（{url[:60]}）")
    body = data.get("body") or ""
    # 2026-11-08 オーナー: 落とす理由は「嘘」だけ。字数・見出しの数・記号は落とさない（「｜」は公開の段で自動で直す）
    if not body.strip():
        out.append("本文がありません")
    return out


FORMAT_MD = """# サイソク 記事の入稿の書式（Muse さん向け）

このフォルダ（ダウンロード/saisoku-articles）に、記事1本につき1つの Markdown ファイルを置いてください。
20〜30分ごとにサイソクの仕組みが取りに来て、事実確認（公式ページとの照合）・重複の確認・画像づけをして、合格したものを公開します。
**公開の作業・ログイン・パスワードはいりません。ファイルを置くだけです。**

## 書く前に

1. 同じフォルダの **ledger.md** を読んでください。この7日にサイトに出た記事と、Muse さんが出した記事の結果が載っています。
   同じ話題（同じ発表・同じ数字）の記事は書かないでください。重複は自動で見送られます。
2. 事実は **官公庁・自治体・会社自身の公式ページ（一次情報）** から書きます。まとめサイト・SNS・プレスリリース配信サイト・Wikipedia は出典にできません。
   **報道は、次の主要な報道機関の記事だけ、2番目以降の出典として使えます（2026-11-13 から）**:
   NHK・共同通信（47NEWS を含む）・時事通信・日本経済新聞・朝日新聞・読売新聞・毎日新聞・ロイター・ブルームバーグ・AP通信・TBS NEWS DIG・テレビ朝日・日本テレビ・FNN。
   - 公式の出典を1件目に置きます。報道にしか無い事実は、文ごとに「NHKによると」「ロイターが報じた」と書き、確定した事実として言い切りません（題名・最初の段落も同じ）。
   - 報道の文は写しません。事実だけを自分の言葉で短くまとめます。Yahoo!ニュースなどに載った転載ではなく、報道機関自身のページの URL を書いてください。
   - 公式の発表がまだ無く、報道だけで書くときは、題名と最初の段落に報道機関の名前を入れてください。記事には「報道をもとにした速報」の札が付き、公式の発表が出たら更新します。
3. 公式ページを自分で開いて、数字・日付・金額・条件をその場で確かめてから書いてください。ページに無いことは書きません。

## ファイル名

`YYYYMMDD-ジャンル-短い題名.md`　例: `20261108-お金-平均給与487万円.md`

## ファイルの中身

先頭に `---` で囲んだ項目、そのあとに本文です。

| 項目 | 書くこと |
|---|---|
| title | 記事の題名。目に留まって読みたくなる強い題名でよい（いちばん驚く本当の数字を先頭に・問いかけも可）。本文にない事実や言い過ぎはだめ。「｜」は使わない |
| genre | 手続き・お金・値上げ・早見表・速報解説・暮らし・AI・テック・ビジネス のどれか1つ |
| sources | 公式の出典（主要な報道機関の記事は2件目以降に）。1〜10件（11件目以降は使いません）。1件目が一番の出典。各件に url（https://）・name（発信元の名前）・facts（どの数字がそのページのどこにあるか） |
| notes | ひと言メモ。題材を選んだ理由と、確かめられなかった点（サイトには出ません） |

本文（--- のあと）:
- 決まりは「嘘をつかない」だけです。数字・金額・日付・対象は、出典の公式ページにあるものだけを書いてください（計算した数字は計算したと分かるように）。
- 計算は式を書いてください（2026-11-13）。公式ページにある数字どうしの足し算・引き算・かけ算・割り算・割合は、式が合っていれば通ります。
  例:「3,000万円×0.7%＝21万円（サイソク編集部の計算）」「1,059,125円÷12≒88,260円（サイソク編集部の計算）」。
  式の材料にする金額・割合は、公式ページに載っている数字だけにします（自分で置いた例の金額「賞与50万円なら」は、公式ページに同じ例が無いと通りません）。
- それ以外の書き方（長さ・見出し・構成）はお任せします。読みたくなって、最後まで読まれる記事にしてください。短いお知らせは短い記事で大丈夫です。
- 公式の発表の書き写しにしないでください（2026-11-12 オーナー）。本文の後半（「## まだ分からないこと」があればその前）に
  「## サイソクの見方：<中身の言葉>」の章を1つ置き、2〜4文で次を書きます（材料のあるものだけ。事実とは書き分けて「〜とみられます」と見方として書く）。
  1. なぜ今か（前回・過去の公式の数字や経緯と比べて何が違うか）
  2. 誰が得をし、誰が損をするか・どのくらいか（計算した数字には「（サイソク編集部の計算）」と式を添える）
  3. 読者の判断の目安（「〜ならA、〜ならB」。確かめる・申し込む・待つ・見送る）
  この章が無い原稿は、サイソクの仕組みが本文の事実から1章だけ足します。相場の予想・特定の会社や商品のすすめは書きません。

## 記事の8つの基準（2026-11-12 オーナー「量を超えることができるレベルの最高の記事」）

AdSense の審査の間（11/26 ごろの再申請まで）、サイソクのすべての新しい記事をこの8つで点検します（scripts/quality_bar.py）。
足りない点は、サイソクの仕組みが公式の資料の事実だけで1回手直しします。Muse さんの原稿は基準では落としません（落とす理由は嘘だけ）が、
はじめから8つを満たしてもらえると、手直しで文が変わらずにそのまま載ります。

1. 最初の3行で、だれに関係するか・どのくらい（金額・割合・件数）・いつから（日付・期限）が分かる。
   数字で言えない発表なら、何が起きて、読者に何を意味するか（何が必要・不要になるか）。
2. 数字はすべて公式の資料から。出典の名前と確認日を添える（例「（国税庁「民間給与実態統計調査」、11/12確認）」）。
3. 「自分の場合」が分かる部分: 早見の表、式つきの計算（例: 月1万円×12か月＝12万円（サイソク編集部の計算））、
   または「〜の人は〜」「〜なら〜」の判断の目安を2〜4行。
4. 「## サイソクの見方：<中身の言葉>」の章（上の決まり）。
5. 読者がすること: 何を・どこで（窓口・ページ・アプリ）・いつまで。することが無いなら「手続きは不要です」とはっきり書く（資料で言えるときだけ）。
6. 公式ページより分かりやすく: 略語・専門用語は初めて出たところで（ ）で言い換える。比べる数字が多いところは表にする。
7. 関連するサイソクの過去記事・日程ページ（/dates）・計算ツール（/tools）・比較（/compare）・ガイド（/guides）へのリンクを2つ以上
   （`[短い題名](/articles/slug)` の形。足りなければサイソクの仕組みが関連記事を足します）。
8. 自然な日本語: 「注目されます」「期待されます」「影響を与える可能性があります」のような、事実の無い決まり文句を書かない。
   同じ文をくり返さない。「まとめ」「概要」のような型の見出しにしない。水増しをしない。

## 見本（このまま真似してください）

```
---
title: 会社員の平均給与は487万円で過去最高　国税庁の2025年分の調査
genre: お金
sources:
  - url: https://www.nta.go.jp/information/release/kokuzeicho/2026/minkan_2026/pdf/01.pdf
    name: 国税庁
    facts: 平均給与487万円・前年比1.9%増・5年連続の増加（1ページ「２ 調査結果の概要」「３ 調査結果のポイント」）、男性597万円・女性342万円（同）、業種別の平均給与（参考の表）
notes: |
  年末に「平均年収」の検索が増えるので選んだ。PDF の2ページ目の表で業種別を確かめた。
  年代別の数字はこの PDF には無いので書いていない。
---
国税庁は2026年9月、「令和7年分民間給与実態統計調査」の結果を公表しました。……

## 平均給与は487万円、5年続けて増えた

1年を通じて勤めた人の平均給与は487万円で、前の年より1.9%増えました（国税庁の調査結果）。……

## 男女・正社員かどうかで見た差

……
```

## 一歩深くする材料（depth・任意・2026-11-09 から）

記事ページには、本文のほかに次の5つの欄が出ます。サイソクの仕組みが公式ページを読み直して作りますが、
Muse さんが調べて見つけたものを `depth: |` の欄に箇条書きで書いてくれると、その中から公式ページで確かめられたものを使います。
**どれも、公式ページのどこに書いてあるか（URL）を必ず添えてください。** ページに無い数字・名前・URL は自動で外れます。

| 欄 | 書くこと |
|---|---|
| なるほど | 誰でも知っている注意（URLを開かない・パスワードを変える）ではなく、公式ページにだけある具体的な事実。例: 本物のSMSの送信元の名前、申請で間違えやすい欄、締切の正確な日時、金額の境目、電話がつながりやすい時間 |
| 公式窓口 | 窓口の正式名・電話番号・受付時間・ページの URL と、サイトのトップからそのページへの辿り方（例 トップ → お知らせ → 重要なお知らせ）。画面の写真は使いません |
| すぐにできること | 誰が・どこで・何を押す／確かめるかまでの手順 |
| なぜ起きた？ | 公式が書いている原因・背景だけ。まだ発表されていなければ「原因は調査中と発表」と書く（推測しない） |
| 不安 Q&A | 読者が抱きそうな不安3〜5個と、公式ページにある答え。公式が答えていない不安は、警察庁・消費者庁・首相官邸などの一般の注意のページを出典に |

```
depth: |
  なるほど: 本物のドコモのSMSの送信元は「NTT DOCOMO」など決まった名前（https://www.docomo.ne.jp/info/anti-phishing/confirmation/）
  窓口: 特設ダイヤル 0120-451-360 午前9時〜午後8時（https://www.docomo.ne.jp/info/notice/page/261106_00_m.html の「３．お問い合わせ」）
  原因: 第三報で「外部からの不正アクセス」。侵入経路は調査中（同じページの「（３）原因」）
```

## 結果の見方

- 公開されたら、ファイルは `done/` に移ります。ledger.md に題名と URL が載ります。
- 見送られたら、ファイルは `rejected/` に移り、同じ名前の `.reason.txt` に理由が書かれます。理由を直して、新しいファイルとして置き直してください。
- 審査中のファイルは `sent/` にあります（ふつうは1時間以内に結果が出ます）。
- その日の記事の本数がいっぱいのときは、次の日の朝に回ります（ledger.md に「順番待ち」と出ます）。
"""
