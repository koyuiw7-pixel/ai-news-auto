"""検索結果の題名 searchTitle（<title> だけに使う、人が検索に打つ言葉の形の題名）を作る・確かめる。

2026-11-10 オーナー承認（18:21「全て同意です」・台帳 A29 の変更）。20:45 オーナー「検索用タイトルはかなりいい線行ってると
思うから広げていきたい」で、暮らしとお金の新しい記事にも自動で付ける。

- 使う所: lib/headline.ts の searchResultTitle（<title> だけ）。見出し（h1）・og:title・SNS・画像は title のまま
- 決まり（problems）: 記事の本文にある事実だけ（rewrite_titles.check_title〔reviewed〕と check_seo）・32字以内・
  「｜」なし・「ざっくり」なし・あおりなし・見出しと同じにしない
- 付ける所: scripts/main.py の write_article（どの経路の新しい記事も通る1か所。Muse の記事も）。
  新しく書き出す暮らしとお金の記事だけ（is_target）。案が決まりに落ちたら付けない（記事の題名のまま）。公開は止めない
- 書き直しで決まりに合わなくなった searchTitle は外す（revalidate。LLM を使わない）
- 確かめ: tests/test_search_title_20261110.py
"""
from __future__ import annotations

import json
import os
import re

import article_style
import headline_normalize as hn
import llm
import rewrite_titles

MAX = 32  # lib/headline.ts の SEARCH_TITLE_MAX と同じ

# 暮らしとお金の記事の目印（見出し）。制度・お金の手続き・家計に響く値上げ・リコール・流出の「どうする」
LIFE_MONEY_RE = re.compile(
    r"年金|児童手当|手当金|給付|一時金|年末調整|控除|税|ふるさと納税|電気代|電気料金|ガス代|ガス料金|値上げ|値下げ|料金|運賃|"
    r"リコール|回収|点検交換|流出|漏えい|漏洩|不正アクセス|保険|医療費|療養費|出産|育休|育児休業|失業|雇用保険|相続|マイナ|"
    r"補助金|助成|支援金|最低賃金|ボーナス|手取り|家計|NISA|iDeCo|ローン|金利|介護|扶養|社会保険|申告|還付|ガソリン|灯油|反則金|"
    r"解約|補償|物価"
)
# 企業の決算・市場の話は暮らしの手続きの記事ではない（検索の言葉の形にしない）
NOT_TARGET_RE = re.compile(r"決算|中間期|営業利益|純利益|最終利益|株価|自社株|為替|日銀|ECB|FRB|雇用統計|政策金利|上方修正|下方修正")
LIFE_GENRES = {"暮らし・生活", "投資・マネー", "不動産"}
MAYBE_GENRES = {"社会・行政", "ビジネス・経済", "テクノロジー・ガジェット", ""}
TECH_ONLY_RE = re.compile(r"流出|漏えい|漏洩|不正アクセス|リコール")
# あおり（検索の題名に使わない言い方）
BAIT_RE = re.compile(r"衝撃|驚愕|驚き|必見|ヤバ|やば|知らないと損|大損|激変|まさか|絶対|今すぐ|急げ|【|】|！|!")


def is_target(record: dict) -> bool:
    """searchTitle を自動で付ける記事か（暮らしとお金の記事。速報・決算・AI の話は除く）"""
    title = str(record.get("title") or "")
    if not title or NOT_TARGET_RE.search(title) or record.get("breaking"):
        return False
    genre = str(record.get("genre") or "")
    if genre in LIFE_GENRES:
        return True
    if genre in MAYBE_GENRES:
        return bool(LIFE_MONEY_RE.search(title))
    return bool(TECH_ONLY_RE.search(title))  # AI・テクノロジーなど: 流出・リコールの「どうする」だけ


def problems(record: dict, value: object) -> list[str]:
    """searchTitle の不合格の理由（空なら合格）。LLM は使わない（tests/test_search_title_20261110.py と同じ決まり）"""
    if not isinstance(value, str) or not value.strip():
        return ["空"]
    out = []
    if len(value) > MAX:
        out.append(f"{len(value)}字（{MAX}字まで）")
    if "｜" in value or "|" in value:
        out.append("縦棒")
    if article_style.ZAKKURI_RE.search(value):
        out.append("ざっくり")
    if m := BAIT_RE.search(value):
        out.append(f"あおり（{m.group(0)}）")
    if value.strip() == str(record.get("title") or "").strip():
        out.append("見出しと同じ")
    out += rewrite_titles.check_title(record, value, reviewed=True)
    out += rewrite_titles.check_seo(record, value)
    return out


RULES = """あなたは日本のニュースサイトの編集者です。記事の「検索結果に出す題名」（HTML の <title> だけに使う）を1つ作ります。
見出し（h1）は変えません。人が Google に打つ言葉の形にして、記事がその問いに答えていることが分かる題名にします。

決まり:
- 32字以内（全角も半角も1字）。区切りは全角の空白「　」を1つまで。縦棒「｜」「|」は使わない
- 頭に制度名・商品名・会社名など検索される言葉を置き、そのあとに「いつ・いくら・対象・期限・届かない・どうする」などの答えを書く
- 問いの形（「〜はいくら？」「〜はいつから？」）は、記事が本当に答えているときだけ
- 記事に書いてある事実・数字・名前だけを使う。記事に無い数字・言葉・言い換え（「禁止」を「廃止」にするなど）を足さない
- 制度や機関の名前は記事の表記のまま写す（漢字・カタカナの語は記事にあるものだけ）
- あおり（衝撃・必見・知らないと損・！・【】）、「ざっくり」、「〜とは？〜を解説」の決まり文句は使わない
- 見出しと同じ文にしない
- 令和の年は記事の書き方のまま。西暦に直さない

よい例:
- 児童手当の12月はいくら？　2か月分の振込額を人数別に
- 年金の支払日はいつ？　偶数月15日、12月は10月・11月分
- ふるさと納税の期限は12月31日　ワンストップ特例は1月10日
- ニトリの個人情報が流出の恐れ、対象は？　最大3,762万件
- 年金生活者支援給付金の対象は？　はがきが届かないとき

出力は指定の JSON だけ。"""
SCHEMA = {"type": "OBJECT", "properties": {"search_title": {"type": "STRING"}}, "required": ["search_title"]}


def _payload(record: dict, feedback: str = "") -> str:
    item = {
        "title": record.get("title", ""), "description": str(record.get("description", ""))[:200],
        "lede": str(record.get("lede", ""))[:300], "highlights": (record.get("highlights") or [])[:4],
        "body_head": str(record.get("body", ""))[:1500],
    }
    if feedback:
        item["前回の案の問題"] = feedback
    return json.dumps(item, ensure_ascii=False)


def propose(record: dict) -> tuple[str, str]:
    """(合格した案 or "", 説明)。安いモデル（補助の段＝Haiku）で作り、決まり（problems）と事実の確認を通ったものだけ返す"""
    feedback = ""
    for _ in range(2):
        data, _model = llm.generate_json(RULES, _payload(record, feedback), SCHEMA, temperature=0.3,
                                         max_output_tokens=512, tier="bulk", purpose="helper")
        value = hn.normalize_title(str(data.get("search_title") or "").strip(), record)
        bad = problems(record, value)
        if not bad:
            # 記事に無い主張を足していないかを確かめる（rewrite_titles と同じ確認。確かめられなければ付けない）
            if ungrounded := rewrite_titles.llm_grounding_problems(record, value):
                return "", f"根拠を確かめられない（{value} / {'; '.join(ungrounded)}）"
            return value, value
        feedback = "; ".join(bad)
    return "", f"決まりに合わない（{value} / {feedback}）"


def attach(record: dict) -> str | None:
    """新しい暮らしとお金の記事に searchTitle を付ける（record をその場で書き換える）。説明を返す。
    どんな失敗でも例外を外に出さない（公開を止めない。付けられなければ記事の題名が <title> になる）"""
    if os.environ.get("SEARCH_TITLE_AUTO", "1") == "0" or record.get("searchTitle") or not is_target(record):
        return None
    try:
        value, note = propose(record)
    except Exception as error:  # noqa: BLE001 - 検索の題名で記事を止めない
        return f"検索の題名を作れなかった（{str(error)[:80]}）。記事の題名のまま"
    if not value:
        return f"検索の題名は付けない: {note}"
    record["searchTitle"] = value
    return f"検索の題名を付けた: {value}"


def revalidate(record: dict) -> str | None:
    """書き直しで決まりに合わなくなった searchTitle を外す（LLM を使わない）"""
    value = record.get("searchTitle")
    if value is None:
        return None
    if bad := problems(record, value):
        record.pop("searchTitle", None)
        return f"検索の題名を外した（{value} / {'; '.join(bad)}）"
    return None
