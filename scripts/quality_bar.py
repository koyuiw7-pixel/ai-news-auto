#!/usr/bin/env python3
"""新しい記事の「8つの基準」の点検・1回の自動の手直し・保留（2026-11-12 オーナー。AdSense「有用性の低いコンテンツ」の2回目の不承認）。

オーナー: 審査の間（再申請 11/26 ごろまで）は自動のニュースを暮らしとお金の30本/日にしぼり、残す記事はすべて
「量を超えることができるレベルの最高の記事」にする。すべての新しい記事（自動の記事 web_articles・速報レーン・Muse・深掘り/別の切り口・
動画 main・短い記事の書き足し thicken_short）に、次の8つを求める:

  1. 最初の3行（リード＋本文の最初の段落の3文）で、だれに関係するか・どのくらいか・いつからか（または何が起きて読者に何を意味するか）が分かる
  2. 数字はすべて公式の資料から（出典の名前と確認日。今までの事実の束・事実確認の門 quality.evaluate をそのまま使う）
  3. 「自分の場合」: 早見の表・式つきの計算（「（サイソク編集部の計算）」）・判断の目安（「〜の人は〜」）のどれか
  4. 「サイソクの見方」の章（scripts/own_view.py の点検をそのまま使う）
  5. 読者がすること: 何を・どこで（窓口・手続き・期限）。することが無いなら「手続きは不要」とはっきり書く
  6. 公式ページより分かりやすい: 略語・専門用語の言い換え、比べる数字が多いときは表か図
  7. 関連する記事・ページへの内部リンクが2つ以上（本文のリンクと記事末の関連記事 relatedSlugs。/dates・/tools・/compare・/guides も数える）
  8. 自然な日本語: 決まり文句（「注目されます」「影響を与える可能性があります」を事実なしで）・つなぎの文・水増しのくり返しが無い

LLM を使わずに点検する（2 は事実確認の門の結果、4 は own_view.view_problems を使う）。
手直し（ensure）: 足りない点があれば、公式の資料と確認済みの文脈の事実だけで1回だけ手直しする（7 はプログラムで関連記事を足す）。
手直しした原稿も、ふつうの事実確認（嘘だけを落とす門）をそのまま通す。門は緩めない。
保留（hold_reason）: 手直しのあとも 1・3・5 のどれかが足りない暮らしとお金の記事は出さない。速報・大きなニュース・速報レーン・地震や災害は
止めずに出し、記事に repairLater を付けて、あとで手直しする（--repair-later。auto_run.yml）。

しきい値と保留の決まりは 2026-11-12 に直近7日の暮らしとお金の記事で測って決めた（tests/test_quality_bar_20261112.py に数字）。

  python3 scripts/quality_bar.py --measure --days 7          # 直近7日の分布（どの点が足りないか）
  python3 scripts/quality_bar.py --daily 2026-11-12          # その日の5本を選んで点検（夜の会議。out/strategy_20261110/quality_daily/）
  python3 scripts/quality_bar.py --repair-later --max 3 --apply  # 速報で出した記事の、足りない点の手直し
  python3 scripts/quality_bar.py --slug a,b                  # 記事ごとの結果
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import own_view  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "content" / "articles"
DAILY_DIR = ROOT / "out" / "strategy_20261110" / "quality_daily"
JST = timezone(timedelta(hours=9))

POINTS = {
    1: "最初の3行で、だれに・どのくらい・いつから",
    2: "数字は公式の資料から（出典と確認日）",
    3: "自分の場合（早見の表・計算・判断の目安）",
    4: "サイソクの見方",
    5: "読者がすること（何を・どこで・期限）",
    6: "公式ページより分かりやすい（言い換え・表や図）",
    7: "関連する記事・ページへの内部リンク2つ以上",
    8: "自然な日本語（決まり文句・水増しなし）",
}
HOLD_POINTS = (1, 3, 5)  # 手直しのあとも足りなければ出さない点（速報・災害は除く）
MIN_INTERNAL_LINKS = 2
COMPARE_NUMBERS = 10  # 単位つきの数字がこれ以上あるのに表も図も無ければ、6 は足りない

PROMPT_RULE = """
# 記事の8つの基準（2026-11-12 オーナー「量を超えることができるレベルの最高の記事」。公開の前にプログラムが点検する）
- 最初の3行（リードと本文の最初の段落）で、だれに関係するか・どのくらい（金額・割合・件数）・いつから（日付・期限）を答える。
  数字で言えない発表なら、何が起きて読者に何を意味するか（何が必要・不要になるか）を書く。
- 「自分の場合」が分かる部分を1つ入れる: 資料の数字の早見の表、式つきの計算（「（サイソク編集部の計算）」。計算済みの数字の決まりを守る）、
  または「〜の人は〜」「〜なら〜」の判断の目安を2〜4行。
- 読者がすることを書く: 何を・どこで（窓口・ページ・アプリ）・いつまで（資料にある URL・窓口の名前で）。資料で手続きが要らないと分かるときは「手続きは不要です」と書く。
- 公式ページより分かりやすく: 略語・専門用語は初めて出たところで（ ）で言い換える。比べる数字が多いところは資料の数字だけで表にする。
- 「注目されます」「期待されます」「影響を与える可能性があります」のような事実の無い決まり文句、同じ文のくり返し、「まとめ」「概要」のような型の見出しを使わない。
"""


def prompt_block() -> str:
    """記事を書くプロンプトに足す決まり（4 の「サイソクの見方」は own_view.prompt_block、2 は事実の束と事実確認の決まりにある）"""
    return PROMPT_RULE


# --------------------------------------------------------------------------- #
# 点検に使う式
# --------------------------------------------------------------------------- #
_SENT_RE = re.compile(r"(?<=[。！？!?])")
# 1: だれに（対象の人・契約・事業者）
WHO_RE = re.compile(
    r"人|方|世帯|家庭|家族|利用者|加入者|契約者|受給者|事業者|事業主|会社員|会員|保護者|学生|高齢者|子ども|子供|親|住民|ユーザー|お客|顧客|"
    r"消費者|納税者|患者|ドライバー|所有者|購入者|申請者|居住者|労働者|従業員|雇用者|株主|投資家|中小企業|企業|自治体|市区町村|対象|全国|国民|"
    r"持っている|使っている|住んで|働く|払って|乗る")
# 1: どのくらい（単位つきの数字・割合）
AMOUNT_RE = re.compile(
    r"\d[\d,，.]*\s?(?:%|％|円|万|億|兆|割|倍|ポイント|pt|件|人|社|世帯|歳|か月|カ月|ヶ月|年|日|時間|分|回|台|本|戸|店|GB|kWh|キロ|km|m|トン|t|ドル|ユーロ|万人|点)"
    r"|全額|無料|半額|上限|最大|無償|据え置")
# 1: いつから（日付・期間・時点）
WHEN_RE = re.compile(
    r"\d{1,2}月|\d{1,2}日|\d{4}年|年度|令和|平成|から|まで|以降|以前|開始|始ま|始め|期限|締め切|今日|本日|明日|今年|来年|今月|来月|今週|来週|"
    r"春|夏|秋|冬|当面|順次|すでに|現在|発表しました|公表しました|決まりました|決定しました|決めました")

# 1: 読者にとっての意味（何が必要・不要になるか・使えなくなるか・呼びかけ）
MEANING_RE = re.compile(r"必要|不要|できます|できなく|使え|変わ|始ま|終わ|止ま|対象|届|受け|呼びかけ|確かめ|確認|注意|返金|交換|無料|値上げ|値下げ|上が|下が|増え|減")

# 3: 自分の場合（早見の表・式つきの計算・判断の目安）
TABLE_SEP_RE = re.compile(r"(?m)^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
CALC_RE = re.compile(r"サイソク編集部の計算|編集部の計算|[0-9０-９][^。\n]{0,30}[×÷][^。\n]{0,30}[＝=]")
CASE_LINE_RE = re.compile(r"(?:人|方|世帯|家庭|会社|企業|事業者|場合)(?:は|なら|では)[、,]?|なら[、,]|場合は[、,]?|ときは[、,]?")

# 5: 読者がすること（何を）と、どこで・いつまで
# 読者への行動の書き方（「〜してください」「〜しましょう」「〜が必要です」「〜できます」）。「受け取っている人」のような説明の文は数えない
ACTION_RE = re.compile(
    r"(?:申し込|申込|申請|手続|届け出|届出|確かめ|確認|問い合わせ|問い合わせ|相談|予約|解約|切り替え|乗り換え|登録|更新|受け取|請求|提出|支払|"
    r"払い込|振り込|ログイン|開|見直|比べ|選|保存|控え|準備|持参|持って|行|電話|記入|入力|返金|交換|点検|使用を中止|使うのをやめ)"
    r"[^。]{0,8}?(?:てください|ましょう|る必要|が必要|が要り|が要る|できます|られます|します|しておく|ておく|ておき|と安心|のが目安|るのが|"
    r"すること|が大切|が欠かせ|てもらえ|ことができ|を忘れず)"
    r"|(?:申し込み|申込み|申請|手続き|届け出|問い合わせ|相談|予約|更新)は[^。]{0,30}?(?:行います|行えます|受け付けます|できます)")
WHERE_RE = re.compile(
    r"窓口|市区町村|市役所|区役所|役場|役所|税務署|年金事務所|ハローワーク|保健所|警察|消費生活センター|188|金融機関|銀行|郵便局|証券会社|店舗|店頭|"
    r"コールセンター|ダイヤル|電話|ホームページ|公式サイト|公式ページ|サイト|ページ|マイページ|マイナポータル|アプリ|e-Tax|e-Gov|ねんきんネット|"
    r"会員ページ|オンライン|メール|郵送|書面|https?://|\]\(")
DEADLINE_RE = re.compile(r"\d{1,2}月\d{1,2}日|\d{1,2}月(?:末|中)|まで|期限|締め切|以内|前に|うちに|年度内|今月中")
NO_ACTION_RE = re.compile(
    r"手続き(?:は|の)(?:必要(?:は)?(?:ありません|ない)|不要|いりません)|申請(?:は)?不要|申し込み(?:は)?不要|手続き不要|"
    r"何も(?:しなくて|する必要は|手続き)|自動で(?:適用|反映|切り替|変わ|引き下げ|引き上げ|支給|振り込)|特別な手続き")

# 6: 公式ページより分かりやすい（略語の言い換え）
_FIGURE_FIELDS = ("charts", "figures")

# 6: 暮らしの記事でよく出て、言い換えが無くても読者がつまずかない英字（article_style.KNOWN_ACRONYMS に足して使う）
COMMON_ACRONYMS = {"IC", "IP", "WEB", "HOME", "CM", "JR", "JA", "ATM", "ETC", "NISA", "LED", "DM", "SMS", "TEL", "FAX", "NG", "JAL", "ANA",
                   "JT", "LP", "NY", "GK", "DB", "UP", "WG"}

# 7: 内部リンク
INTERNAL_RE = re.compile(r"\]\((/(?:articles|dates|tools|compare|guides|choose|roundups|howto|ai-pricing|products)/[A-Za-z0-9][A-Za-z0-9_\-/]*)\)")

# 8: 決まり文句（事実を書かずに使う言い回し）。scripts/article_style.py のつなぎの文の式も使う
BOILER_RE = re.compile(
    r"注目され(?:ます|ています|そうです)|注目が集ま|注目を集め(?:そう|ています)|影響を与える可能性があ|影響が出る可能性があ|"
    r"期待され(?:ます|ています)|期待が(?:高まり|寄せられ)|今後の(?:動向|展開|行方)(?:に|が)(?:注目|気にな)|動向を注視|"
    r"と言えるでしょう|といえるでしょう|ではないでしょうか|いかがでしたか|ぜひ(?:チェック|参考に)|重要なポイントです|大きな一歩|"
    r"目が離せません|見逃せません|一石を投じ")
TEMPLATE_HEADS = {"まとめ", "概要", "はじめに", "背景", "詳細", "ポイント", "おわりに", "結論", "最後に", "注目点"}
FORBIDDEN_RE = re.compile("\\uff5c|\\u3056\\u3063\\u304f\\u308a")  # 縦の区切りの記号と、使わない言葉（オーナーの決まり）


def _nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def _plain(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text or "")
    return re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)


def _sentences(text: str) -> list[str]:
    out = []
    for line in _plain(text).splitlines():
        line = re.sub(r"^\s*(?:[-*+・]|\d+[.)．])\s+", "", line).strip()
        if not line or line.startswith(("#", "|", ">")):
            continue
        out.extend(s.strip() for s in _SENT_RE.split(line) if len(s.strip()) >= 6)
    return out


def _first_paragraph(body: str) -> str:
    for block in re.split(r"\n\s*\n", body or ""):
        b = block.strip()
        if not b:
            continue
        if b.startswith("#"):
            continue  # 見出しから始まる記事は、その下の最初の段落
        if b.startswith(("|", "!", "<")):
            continue
        return b
    return ""


def _list(value) -> list:
    return value if isinstance(value, list) else []


def _actions(record: dict) -> list[str]:
    """記事ページの「すぐにできること」（todayActions・todaySteps）と公式の窓口（officialDesk）の文"""
    out = [str(x) for x in _list(record.get("todayActions")) if str(x).strip()]
    for step in _list(record.get("todaySteps")):
        if isinstance(step, dict):
            out.append(" ".join([str(step.get("action") or ""), *[str(s) for s in _list(step.get("steps"))], str(step.get("url") or "")]))
    for desk in _list(record.get("officialDesk")):
        if isinstance(desk, dict) and desk.get("url"):
            out.append(f"{desk.get('name') or ''}の窓口 {desk.get('url')}")
    return out


def applies(record: dict) -> bool:
    """3（自分の場合）と5（読者がすること）を求める記事か: 読者がすることの無い発表（面会・式典・人事・表彰）は求めない"""
    return not own_view._no_reader_action(record)  # noqa: SLF001 - 同じ判定を使う


def life(record: dict) -> bool:
    """暮らしとお金のジャンルの記事か（保留はこのジャンルだけ。審査の間の自動のニュースはこのジャンルだけ）"""
    return (record.get("genreSlug") or "") in own_view.LIFE_GENRES


# --------------------------------------------------------------------------- #
# 8つの点の点検（LLM を使わない）
# --------------------------------------------------------------------------- #
def lead_text(record: dict) -> str:
    """最初の3行: リードと本文の最初の段落の、はじめの3文"""
    sents = _sentences(record.get("lede") or "") + _sentences(_first_paragraph(record.get("body") or ""))
    return " ".join(sents[:3])


def p1_lead(record: dict) -> str | None:
    lead = _nfkc(lead_text(record))
    if not lead:
        return "リードも本文の最初の段落も無い"
    miss = [name for name, rx in (("だれに", WHO_RE), ("どのくらい", AMOUNT_RE), ("いつから", WHEN_RE)) if not rx.search(lead)]
    # 何が起きて読者に何を意味するか: だれにが分かり、どのくらい・いつからの片方と、読者にとっての意味（必要・不要・使えなくなる等）があれば足りる
    # （漏えい・リコールのように「いつから」が要らない発表、数字で言えない制度の変更）
    if len(miss) == 1 and miss[0] != "だれに" and MEANING_RE.search(lead):
        miss = []
    return f"最初の3行に{'・'.join(miss)}が無い" if miss else None


def p2_sources(record: dict, verdict: dict | None = None) -> str | None:
    """事実確認の門（quality.evaluate）に合格し、出典が記事に残っているか（今までの門の結果をそのまま使う）"""
    if verdict is not None and not (verdict.get("ok") or verdict.get("soft")):
        return "事実確認の門に合格していない"
    has_source = bool(record.get("sourceUrl") or _list(record.get("museSources")) or _list(record.get("factSources")) or record.get("videoUrl"))
    if not has_source:
        return "出典（公式の資料）が記事に無い"
    score = record.get("qualityScore")
    try:
        if verdict is None and score not in (None, "") and float(score) < 70:
            return f"事実確認の点数が{score}（70未満）"
    except (TypeError, ValueError):
        pass
    return None


def p3_case(record: dict, body_only: bool = False) -> str | None:
    if not applies(record):
        return None
    body = record.get("body") or ""
    if TABLE_SEP_RE.search(body) or CALC_RE.search(_nfkc(body)):
        return None
    if not body_only and (_list(record.get("decisionGuide")) or any(_list(record.get(k)) for k in _FIGURE_FIELDS)):
        return None
    # 判断の目安: 「〜の人は」「〜なら、」の文・行が2つ以上（「サイソクの見方」の章の中も数える）
    cases = [s for s in _sentences(body) if CASE_LINE_RE.search(s)]
    if len(cases) >= 2:
        return None
    return "早見の表・式つきの計算・「〜の人は〜」の判断の目安が無い"


def p4_view(record: dict) -> str | None:
    if not own_view.required(record):
        return None
    problems = own_view.view_problems(record)
    return problems[0][:80] if problems else None


def p5_actions(record: dict, body_only: bool = False) -> str | None:
    if not applies(record):
        return None
    body = _nfkc(record.get("body") or "")
    if NO_ACTION_RE.search(body):
        return None
    texts = [s for s in _sentences(body) if ACTION_RE.search(s)]
    acts = [] if body_only else [_nfkc(a) for a in _actions(record)]
    concrete = [s for s in texts + acts if WHERE_RE.search(s) or DEADLINE_RE.search(s)]
    if concrete:
        return None
    if texts or acts:
        return "することは書いてあるが、どこで（窓口・ページ）・いつまでが無い"
    return "読者がすること（何を・どこで・期限）も「手続きは不要」も無い"


def numbers_with_units(text: str) -> set[str]:
    return set(re.findall(r"\d[\d,，.]*\s?(?:%|％|円|万円|億円|兆円|割|倍|ポイント|件|人|社|世帯|歳|か月|カ月|年|日|時間|回|台|kWh|ドル)", _nfkc(text)))


def _glossed(body: str, term: str) -> bool:
    """略語が、日本語の正式名のあとの（ ）の中に初めて出ている（「地方公共団体情報システム機構（J-LIS）」）"""
    i = body.find(term)
    return i > 0 and bool(re.search(r"[（(][A-Za-z\-]{0,4}$", body[max(0, i - 6):i]))


def p6_clear(record: dict) -> str | None:
    body = record.get("body") or ""
    try:
        import article_style  # noqa: PLC0415

        terms = article_style.unexplained_terms(body)
    except Exception:  # noqa: BLE001
        terms = []
    # 題名・タグにある名前（GRMN・TOYOTA など製品や会社の名前）と5字以上の英字の名前は略語として数えない
    named = _nfkc(" ".join([str(record.get("title") or ""), *[str(t) for t in _list(record.get("tags"))]]))
    terms = [t for t in terms if len(t) <= 4 and t not in named and t not in COMMON_ACRONYMS and not _glossed(body, t)]
    out = []
    if terms:
        out.append(f"言い換えの無い略語（{'・'.join(terms[:3])}）")
    figure = bool(TABLE_SEP_RE.search(body)) or any(_list(record.get(k)) for k in _FIGURE_FIELDS)
    nums = numbers_with_units(re.sub(r"(?m)^\s*\|.*$", "", body))
    if len(nums) >= COMPARE_NUMBERS and not figure:
        out.append(f"数字が{len(nums)}個あるのに表も図も無い")
    return "・".join(out) or None


_DATES: list[tuple[str, re.Pattern, set]] | None = None


def money_dates() -> list[tuple[str, re.Pattern, set]]:
    """暮らしとお金の日程ページ（/dates/<slug>）と、記事ページが案内に使う式（lib/money-dates.ts の moneyDateForArticle と同じ）"""
    global _DATES  # noqa: PLW0603
    if _DATES is None:
        _DATES = []
        try:
            data = json.loads((ROOT / "content" / "money-dates.json").read_text("utf-8"))
            for row in data.get("dates") or []:
                try:
                    _DATES.append((str(row["slug"]), re.compile(str(row.get("match") or "(?!)")), set(row.get("articles") or [])))
                except (KeyError, re.error):
                    continue
        except (OSError, ValueError):
            pass
    return _DATES


def date_page(record: dict) -> str | None:
    """記事ページに出る日程ページの案内（題名・検索用の題名・タグが当たるか、日程ページの関連記事に載っている記事）"""
    text = " ".join([str(record.get("title") or ""), str(record.get("seoTitle") or ""), *[str(t) for t in _list(record.get("tags"))]])
    for slug, rx, articles in money_dates():
        if record.get("slug") in articles or rx.search(text):
            return f"/dates/{slug}"
    return None


# 記事ページの「関連記事」（lib/related.ts の relatedArticles）の選び方の写し（同じ話題と言える記事だけ数える）。
# 話題の手がかりにならない語は lib/related.ts の GENERIC・NAME_STOP と同じ
RELATED_GENERIC = {unicodedata.normalize("NFKC", w).lower() for w in (
    "AI AIツール AIニュース 生成AI 人工知能 テクノロジー テック AIエージェント LLM 使い方 料金 無料 日本語 とは 開発 アップデート ニュース 発表 調査 "
    "ビジネス ビジネス・経済 経済 統計 統計情報 行政 社会・行政 社会 暮らし 暮らし・生活 生活 ライフスタイル スポーツ エンタメ テクノロジー・ガジェット "
    "ガジェット 投資・マネー 金融 IT DX アプリ 通信 セキュリティ 提携 業務提携 連携 協定 地域 イベント キャンペーン セール 新製品 新サービス デザイン "
    "トレンド 環境 政策 教育 日本 国内 海外 企業 サービス 公式 発表会 2026年 2027年 令和8年 家電 小売 飲食 食品 流通 製造業 家計 "
    "PDF API SNS CEO URL PC OS サービス システム データ ネット ユーザー プラン モデル ツール ガイドライン プログラム プロジェクト "
    "イベント オンライン デジタル コンテンツ サポート リリース パートナー グループ ホールディングス センター クラウド ポイント").split()}
_CORPUS: dict | None = None


def _title_terms(title: str) -> list[str]:
    t = _nfkc(title)
    out = [m.group(1) for m in re.finditer(r"[「『]([^」』]{2,24})[」』]", t)]
    out += re.findall(r"[A-Za-z][A-Za-z0-9.+\-]*[A-Za-z0-9+]", t) + re.findall(r"[ァ-ヴー]{3,}", t)
    return [w.lower() for w in out]


def _terms(a: dict) -> set[str]:
    words = [*map(str, _list(a.get("tags"))), *map(str, _list(a.get("keywords"))), *_title_terms(str(a.get("title") or ""))]
    return {w for w in (_nfkc(x).strip().lower() for x in words) if len(w) >= 2 and w not in RELATED_GENERIC and not w.isdigit()}


def corpus(articles: list[dict] | None = None) -> dict:
    """関連記事の候補（公開中の記事の語と、語が付いている記事の数）。記事の一覧を渡さなければ content/articles を1回だけ読む"""
    global _CORPUS  # noqa: PLW0603
    if articles is None and _CORPUS is not None:
        return _CORPUS
    rows = []
    for a in (articles if articles is not None else load_articles()):
        if a.get("slug") and not a.get("duplicateOf"):
            rows.append({"slug": a["slug"], "genreSlug": a.get("genreSlug") or "", "terms": _terms(a),
                         "tags": {_nfkc(str(t)).lower() for t in _list(a.get("tags"))}, "sourceUrl": str(a.get("sourceUrl") or "")})
    df: dict[str, int] = {}
    for row in rows:
        for w in row["terms"]:
            df[w] = df.get(w, 0) + 1
    built = {"rows": rows, "df": df, "cap": max(8, round(len(rows) * 0.04))}
    if articles is None:
        _CORPUS = built
    return built


def page_related(record: dict, pool: dict | None = None, limit: int = 4) -> list[str]:
    """記事ページの関連記事に出る記事（具体的な語が2つ以上重なるか、同じジャンルでタグの話題の語が重なる記事。lib/related.ts の strong に近い）"""
    pool = pool or corpus()
    mine, tags = _terms(record), {_nfkc(str(t)).lower() for t in _list(record.get("tags"))}
    disaster = bool(re.match(r"(?:quake|tsunami)-", str(record.get("slug") or "")))
    out = []
    for row in pool["rows"]:
        if row["slug"] == record.get("slug") or (record.get("sourceUrl") and row["sourceUrl"] == record.get("sourceUrl")):
            continue
        if bool(re.match(r"(?:quake|tsunami)-", row["slug"])) != disaster:
            continue
        shared = [w for w in mine & row["terms"] if pool["df"].get(w, 1) <= pool["cap"]]
        need = row["genreSlug"] == record.get("genreSlug") and any((w in tags or w in row["tags"]) and not re.fullmatch(r"[a-z0-9 .+\-]+", w)
                                                                   for w in shared)
        if len(shared) >= 2 or need:
            out.append(row["slug"])
            if len(out) >= limit:
                break
    return out


def internal_links(record: dict, pool: dict | None = None) -> list[str]:
    """本文の内部リンク・記事末の関連記事（relatedSlugs と、ページが話題の重なりで選ぶ記事）・まとめ・元の記事・日程ページの案内"""
    links = list(dict.fromkeys(INTERNAL_RE.findall(record.get("body") or "")))
    if page := date_page(record):
        links.append(page)
    for slug in _list(record.get("relatedSlugs")):
        links.append(f"/articles/{slug}")
    for key in ("roundupSlug", "angleOf"):
        if record.get(key):
            links.append(f"/articles/{record[key]}")
    if pool is not False:
        links += [f"/articles/{slug}" for slug in page_related(record, pool or None)]
    own = f"/articles/{record.get('slug')}"
    return [x for x in dict.fromkeys(links) if x != own]


def p7_links(record: dict, pool: dict | bool | None = None) -> str | None:
    n = len(internal_links(record, pool))
    return None if n >= MIN_INTERNAL_LINKS else f"内部リンクが{n}本（{MIN_INTERNAL_LINKS}本以上）"


def boilerplate(record: dict) -> list[str]:
    """事実（数字）を含まない決まり文句の文・つなぎの文"""
    try:
        import article_style  # noqa: PLC0415

        filler = article_style.FILLER_RE
    except Exception:  # noqa: BLE001
        filler = None
    out = []
    for s in _sentences(record.get("body") or ""):
        plain = re.sub(r"「[^」]*」", "", s)
        if (BOILER_RE.search(plain) or (filler and filler.search(plain))) and not re.search(r"\d", plain):
            out.append(s)
    return out


def repeated(record: dict) -> list[str]:
    """同じ文を2回書いた水増し（出典の注記「（〇〇、11/9確認）」と「価格：」のような項目の行は数えない）"""
    seen, out = set(), []
    for s in _sentences(record.get("body") or ""):
        key = re.sub(r"[（(][^）)]*[）)]|[\s、。]", "", _nfkc(s))
        if re.match(r"^[^:：]{1,12}[:：]", key):
            continue
        if len(key) >= 30 and key in seen:
            out.append(s)
        seen.add(key)
    return out


def p8_natural(record: dict) -> str | None:
    body = record.get("body") or ""
    out = []
    if m := FORBIDDEN_RE.search(f"{record.get('title') or ''}\n{record.get('lede') or ''}\n{body}"):
        out.append(f"使わない文字（「{m.group(0)}」）")
    if found := boilerplate(record):
        out.append(f"決まり文句の文（「{found[0][:30]}」など{len(found)}か所）")
    if found := repeated(record):
        out.append(f"同じ文のくり返し（「{found[0][:30]}」）")
    heads = [h.strip() for h in re.findall(r"(?m)^#{2,3}\s+(.+?)\s*$", body)]
    if bad := [h for h in heads if h in TEMPLATE_HEADS or re.fullmatch(r"(?:自分の場合|判断の目安)(?:[（(][^）)]*[）)])?", h)]:
        out.append(f"決まった型の見出し（「{bad[0]}」）")
    return "・".join(out) or None


def check(record: dict, verdict: dict | None = None, *, at_publish: bool = False, pool: dict | bool | None = None) -> dict:
    """{"passed": [..], "missing": [..], "notes": {点: 理由}, "score": 足りている点の数}。
    at_publish=True は公開の前の点検（あとで足す欄〔判断ガイド・手順・窓口〕はまだ無いので本文と todayActions で見る）。
    pool は関連記事の候補（corpus()。省略で content/articles、False で数えない）"""
    notes: dict[int, str] = {}
    checks = {
        1: p1_lead(record),
        2: p2_sources(record, verdict),
        3: p3_case(record, body_only=at_publish),
        4: p4_view(record),
        5: p5_actions(record, body_only=False),
        6: p6_clear(record),
        7: p7_links(record, pool),
        8: p8_natural(record),
    }
    for point, problem in checks.items():
        if problem:
            notes[point] = problem
    missing = sorted(notes)
    return {"score": 8 - len(missing), "missing": missing, "passed": [p for p in POINTS if p not in notes], "notes": notes}


def summary_line(result: dict) -> str:
    if not result["missing"]:
        return "8点中8点"
    return f"8点中{result['score']}点 足りない: " + " / ".join(f"{p}.{result['notes'][p][:60]}" for p in result["missing"])


def stamp(record: dict, result: dict, **extra) -> dict:
    """記事に点検の結果を残す（qualityBar）"""
    record["qualityBar"] = {
        "score": result["score"], "missing": result["missing"],
        "notes": {str(k): v[:120] for k, v in result["notes"].items()},
        "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), **extra,
    }
    return record["qualityBar"]


# --------------------------------------------------------------------------- #
# 手直し（1回だけ。公式の資料と確認済みの文脈の事実だけ）
# --------------------------------------------------------------------------- #
REPAIR_SYSTEM = """あなたはニュースサイトのデスクです。記事を、読者が公式ページを読むより早く・正しく自分のことが分かる記事に手直しします。
使ってよい事実は、元の資料（公式の発表）・確認済みの文脈・いまの記事にあるものだけ。事実・数字・日付・固有名詞・窓口・URL を作りません。
出力は指定の JSON だけ。"""

POINT_HOWTO = {
    1: "リード（lede）を2〜3文で書き直し、最初の3文で「だれに関係するか・どのくらい（金額・割合・件数）・いつから（日付・期限）」が分かるようにする。"
       "今のリードの良い所（読者への呼びかけ・具体的な数字）は残す。"
       "数字で言えない発表なら「何が起きて、読者に何を意味するか（何が必要・不要になるか）」を書く。本文の最初の段落も、同じ答えから始める。",
    3: "「自分の場合」が分かる部分を1つ足す: 資料の数字で作る早見の表（Markdown の表。上に1行の太字の結論）か、"
       "「〜の人は〜」「〜なら〜」の形の判断の目安を2〜4行。計算を書くときは式も書き（例: 月1万円×12か月＝12万円）、「（サイソク編集部の計算）」と添える。"
       "計算は資料の数字どうしの、かけ算・わり算・足し算・引き算だけ。",
    5: "読者がすることを書く: 何を・どこで（窓口・ページ・アプリ）・いつまで（期限）を、資料にある URL・窓口の名前で。"
       "資料で手続きが要らないと分かる（自動で適用される等）ときだけ「手続きは不要です」と書く。資料に無い手順・窓口は書かない。",
    6: "公式ページより分かりやすくする: 略語・専門用語は初めて出たところで（ ）で短く言い換える。比べる数字が多いところは、資料の数字だけで表にする。",
    8: "決まり文句（「注目されます」「期待されます」「影響を与える可能性があります」など、事実の無い文）は、資料の事実で書き直すか消す。"
       "同じ文のくり返しは1つにする。「まとめ」「概要」のような型の見出しは、その章の中身の言葉に変える。",
}

REPAIR_PROMPT = """次の記事は、サイソクの記事の基準のうち、次の点が足りません。足りない点だけを直す「差分」を返してください（記事の全文は返さない）。
# 足りない点と直し方
{howto}

# 守ること
- 直さない文は1字も変えない（直すのは、足りない点に要る所だけ）。「## サイソクの見方」の章には手を付けない（別の段が書く）。
- リードはニュースの書き出しとして自然に書く（「〜を対象に、〜が判明した」のような機械的な並べ方にしない）。関係する人が限られるなら、その人をはっきり書く。
- 足す章の見出しは、その章の中身の言葉にする（例「## 年金を受け取っている人は、12月の振込から増える」）。「自分の場合」「判断の目安」「まとめ」のような型の見出しにしない。
- 新しい事実・数字・日付・固有名詞・URL は、元の資料と確認済みの文脈にあるものだけ。資料に材料が無い点は直さない（作らない。空のままにする）。
- 水増しをしない: くり返し・一般論・だれにでも当てはまる注意・つなぎの文で長くしない。
- 見方を事実のように書かない。相場や価格の予想、特定の会社・商品のすすめはしない。
- 縦の区切りの記号（全角の縦線）は使わない。です・ます調の、落ち着いた大人向けの文にする。誤字・脱字が無いか読み直す。
# 出力（直さない欄は空の文字列・空の配列）
- lede: 新しいリード（2〜3文）。1 を直すときだけ
- first_paragraph: 本文の最初の段落（見出しの前の段落）の書き直し。1 を直すときだけ
- insert_markdown: 本文に足す章・表・箇条書き（3・5・6 の表）。「## 中身の言葉の見出し」から始める。足すものが無ければ空
- replacements: 今の本文の文をそのまま before に写し、直した文を after に書く（6 の言い換え・8 の決まり文句の書き直し。消すなら after は空）

# 元の資料（公式の発表）
<<<
{source}
>>>
{context}
# いまの記事
タイトル: {title}
リード: {lede}
本文:
<<<
{body}
>>>"""

REPAIR_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "lede": {"type": "STRING"},
        "first_paragraph": {"type": "STRING"},
        "insert_markdown": {"type": "STRING"},
        "replacements": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"before": {"type": "STRING"}, "after": {"type": "STRING"}},
                                                    "required": ["before", "after"]}},
    },
    "required": ["lede", "first_paragraph", "insert_markdown", "replacements"],
}
LLM_POINTS = (1, 3, 5, 6, 8)  # LLM で手直しする点（2 は事実確認の門、4 は own_view、7 はプログラムで足す）
_NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")
_CALC_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(万|億|%)?\s*[^\d×÷+＋\-−＝=\n]{0,8}?\s*([×÷+＋\-−])\s*(\d[\d,]*(?:\.\d+)?)\s*(万|億|%)?[^\d＝=\n]{0,8}?\s*[＝=]\s*約?\s*(\d[\d,]*(?:\.\d+)?)\s*(万|億|%)?")


def _num(value: str, unit: str | None) -> float:
    return float(value.replace(",", "")) * {"万": 1e4, "億": 1e8, "%": 0.01}.get(unit or "", 1)


def calc_results(text: str) -> tuple[set[str], list[str]]:
    """「A×B＝C」の形の計算（「サイソク編集部の計算」の文）を確かめる。(正しい計算の答えの数字, 間違った計算の文)"""
    ok, bad = set(), []
    for line in _nfkc(text).splitlines():
        if "計算" not in line:
            continue
        for m in _CALC_RE.finditer(line):
            a, ua, op, b, ub, c, uc = m.groups()
            x, y, want = _num(a, ua), _num(b, ub), _num(c, uc)
            got = {"×": x * y, "÷": x / y if y else float("nan"), "+": x + y, "＋": x + y, "-": x - y, "−": x - y}[op]
            if want and abs(got - want) <= max(abs(want) * 0.01, 0.5):
                ok.add(c)
            else:
                bad.append(m.group(0))
    return ok, bad


def new_numbers(new: str, *known: str) -> set[str]:
    """手直しで出てきた、資料・文脈・今の記事に無い数字（正しく計算した答えは除く。1字の数字は数えない）"""
    seen: set[str] = set()
    for text in known:
        seen |= set(_NUM_RE.findall(_nfkc(text)))
    calc_ok, _ = calc_results(new)
    return {n for n in set(_NUM_RE.findall(_nfkc(new))) - seen - calc_ok if len(n) > 1}


_ARCHIVE = None


def related_rows(record: dict) -> list[dict]:
    global _ARCHIVE  # noqa: PLW0603
    try:
        if _ARCHIVE is None:
            import archive  # noqa: PLC0415

            _ARCHIVE = archive.Archive()
        rows = _ARCHIVE.related(str(record.get("title") or ""), str(record.get("body") or ""), str(record.get("sourceUrl") or ""),
                                str(record.get("genreSlug") or ""))
    except Exception:  # noqa: BLE001 - 関連記事が取れなくても記事は止めない
        return []
    return [r for r in rows if r.get("slug") and r["slug"] != record.get("slug")]


def fill_links(record: dict, rows: list[dict] | None = None) -> list[str]:
    """7: 内部リンクが足りなければ、話題の重なる過去記事を記事末の関連記事（relatedSlugs）に足す（LLM を使わない。
    記事ページは lib/related.ts の基準を満たすものだけを先に出す）。足した slug を返す"""
    have = internal_links(record)
    if len(have) >= MIN_INTERNAL_LINKS:
        return []
    rows = related_rows(record) if rows is None else [r for r in rows if r.get("slug") != record.get("slug")]
    current = [str(s) for s in _list(record.get("relatedSlugs"))]
    added = []
    for row in rows:
        if len(have) + len(added) >= MIN_INTERNAL_LINKS + 2:
            break
        slug = row["slug"]
        if slug in current or f"/articles/{slug}" in have:
            continue
        added.append(slug)
    if added:
        record["relatedSlugs"] = current + added
    return added


def _clean(text: str) -> str:
    return re.sub(r"^#(?!#)\s*", "## ", str(text or "").strip(), flags=re.M).replace("\uff5c", "\u3000")


def apply_patch(body: str, lede: str, data: dict) -> tuple[str, str, list[str]]:
    """手直しの差分を本文に当てる。(新しい本文, 新しいリード, 当てられなかった差分の説明)。
    直さない文は1字も変えない（全文を書き直させると、関係の無い文の言い回しが変わり誤字も入った。2026-11-12 の試し）"""
    skipped: list[str] = []
    new_body, new_lede = body, _clean(data.get("lede")) or lede
    first = _first_paragraph(body)
    if (para := _clean(data.get("first_paragraph"))) and not para.startswith(("#", "|")):
        if first and new_body.count(first) == 1:
            new_body = new_body.replace(first, para, 1)
        else:
            new_body = para + "\n\n" + new_body.lstrip()
    for row in data.get("replacements") or []:
        old, new = str((row or {}).get("before") or "").strip(), str((row or {}).get("after") or "").strip().replace("\uff5c", "\u3000")
        if not old or old == new:
            continue
        if new_body.count(old) != 1 or own_view.view_section(new_body).find(old) >= 0:
            skipped.append(f"置き換えの元の文が本文に1つだけ無い・見方の章の中（「{old[:24]}」）")
            continue
        new_body = new_body.replace(old, new, 1)
    if insert := _clean(data.get("insert_markdown")):
        if not insert.startswith("## "):
            skipped.append("足す章が見出しから始まっていない")
        else:
            anchor = own_view.VIEW_HEADING_RE.search(new_body) or own_view.UNKNOWN_H2_RE.search(new_body)
            if anchor:
                new_body = new_body[:anchor.start()].rstrip() + "\n\n" + insert + "\n\n" + new_body[anchor.start():]
            else:
                new_body = new_body.rstrip() + "\n\n" + insert + "\n"
    new_body = re.sub(r"\n{3,}", "\n\n", new_body).strip() + "\n"
    return new_body, new_lede, skipped


def improved(before: list[int], after: list[int]) -> bool:
    """手直しで、LLM で直す点（1・3・5・6・8）の足りない数が減り、新しく足りなくなった点が無いか"""
    b, a = set(before) & set(LLM_POINTS), set(after) & set(LLM_POINTS)
    return len(a) < len(b) and not (a - b)


def urgent_record(record: dict) -> bool:
    """止めずに出す記事（速報・大きなニュース・地震や災害）"""
    return bool(record.get("disaster") or record.get("breaking") is True or (record.get("newsType") or "") == "breaking"
                or record.get("fastLane") or str(record.get("slug") or "").startswith(("quake-", "tsunami-")))


def ensure(record: dict, source_text: str, context: str = "", *, urgent: bool = False, related: list[dict] | None = None,
           log=print, generate=None) -> dict:
    """点検して、足りない点があれば1回だけ手直しする（record をその場で書き換える）。結果（check の形）を返し、qualityBar を記事に残す。
    急ぐ記事（速報・大きなニュース・速報レーン）は LLM の手直しをしない（速報を遅らせない。repairLater を付けてあとで直す）。
    このあとふつうの事実確認（quality.evaluate）を通す。generate は llm.generate_json と同じ形（テスト用に差し替える）"""
    before = check(record, at_publish=True)
    notes: list[str] = []
    if 7 in before["missing"] and (added := fill_links(record, related)):
        notes.append(f"関連記事を{len(added)}本足した（{', '.join(added[:3])}）")
    todo = [p for p in before["missing"] if p in LLM_POINTS and (p not in (3, 5) or applies(record))]
    urgent = urgent or urgent_record(record)
    repaired = False
    if todo and not urgent:
        if generate is None:
            import llm  # noqa: PLC0415

            generate = llm.generate_json
        body, lede = record.get("body") or "", record.get("lede") or ""
        howto = "\n".join(f"{p}. {POINTS[p]}（いま: {before['notes'][p][:80]}）\n   {POINT_HOWTO[p]}" for p in todo)
        ctx = f"\n# 確認済みの文脈（事実の束・計算済みの数字・過去記事。ここにある事実も使ってよい）\n<<<\n{context[:8000]}\n>>>\n" \
            if (context or "").strip() else ""
        prompt = REPAIR_PROMPT.format(howto=howto, source=(source_text or "")[:12000], context=ctx, title=record.get("title", ""),
                                      lede=lede, body=body)
        try:
            data, model = generate(REPAIR_SYSTEM, prompt, REPAIR_SCHEMA, temperature=0.3, max_output_tokens=8192, tier="bulk", purpose="helper")
            new_body, new_lede, skipped = apply_patch(body, lede, data)
            notes += [f"差分を当てなかった: {x}" for x in skipped[:2]]
            trial = {**record, "body": new_body, "lede": new_lede}
            after = check(trial, at_publish=True)
            added_nums = new_numbers(f"{new_lede}\n{new_body}", body, lede, source_text, context)
            # 今の記事にもとからある計算は、事実確認の門が見る（ここでは手直しで新しく増えた計算だけ確かめる）
            bad_calc = [c for c in calc_results(new_body)[1] if c not in calc_results(body)[1]]
            kept_view = own_view.view_section(new_body) == own_view.view_section(body)
            if len(new_body) < len(body) * 0.85:
                notes.append(f"手直しで本文が短くなりすぎたので使わない（{len(body)}→{len(new_body)}字・{model}）")
            elif added_nums:
                notes.append(f"手直しに資料に無い数字が出たので使わない（{', '.join(sorted(added_nums)[:4])}・{model}）")
            elif bad_calc:
                notes.append(f"手直しの計算が合わないので使わない（「{bad_calc[0][:40]}」・{model}）")
            elif not kept_view:
                notes.append(f"手直しで「{own_view.VIEW_LABEL}」の章が変わったので使わない（{model}）")
            elif not improved(before["missing"], after["missing"]):
                notes.append(f"手直ししても足りない点が減らなかったので使わない（{after['missing']}・{model}）")
            else:
                record["body"], record["lede"] = new_body, new_lede
                repaired = True
                notes.append(f"足りない点（{'・'.join(map(str, todo))}）を公式の資料の事実で手直しした（{model}）")
        except Exception as error:  # noqa: BLE001 - 直せなくても、このあとの門（hold_reason）で決める
            notes.append(f"手直しに失敗（{str(error)[:100]}）")
    result = check(record, at_publish=True)
    later = bool(urgent and any(p in result["missing"] for p in (*HOLD_POINTS, 8)) and applies(record))
    stamp(record, result, before=before["missing"], repaired=repaired, **({"repairLater": True} if later else {}))
    for note in notes:
        log(f"   [bar] {note}")
    log(f"   [bar] {summary_line(result)}{'（速報なので出してから直す）' if later else ''}")
    return result


def hold_reason(record: dict, *, urgent: bool = False, verdict: dict | None = None) -> str | None:
    """事実確認に合格したあとの最後の確かめ。出さない理由（出してよいなら None）。
    暮らしとお金の記事で、手直しのあとも 1・3・5 のどれかが足りなければ出さない。速報・大きなニュース・速報レーン・災害は止めない"""
    result = check(record, verdict, at_publish=True)
    stamp(record, result, **{k: v for k, v in (record.get("qualityBar") or {}).items() if k in ("before", "repaired", "repairLater")})
    if urgent or urgent_record(record) or not life(record) or not applies(record):
        return None
    if missing := [p for p in HOLD_POINTS if p in result["missing"]]:
        return ("記事の基準に足りない（自動で手直ししても残った）: "
                + " / ".join(f"{p}.{POINTS[p]}（{result['notes'][p][:50]}）" for p in missing))
    return None


# --------------------------------------------------------------------------- #
# 測る・夜の会議の抜き取り・速報のあとの手直し
# --------------------------------------------------------------------------- #
def _published(a: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(str(a.get("publishedAt") or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def load_articles(articles_dir: Path = ARTICLES_DIR) -> list[dict]:
    retired: set[str] = set()
    try:
        data = json.loads((articles_dir.parent / "retired.json").read_text("utf-8"))
        rows = data.get("retired", data) if isinstance(data, dict) else data
        retired = {str(r.get("slug") if isinstance(r, dict) else r) for r in rows}
    except (OSError, ValueError, AttributeError):
        pass
    out = []
    for path in articles_dir.glob("*.json"):
        try:
            a = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if a.get("slug") in retired or a.get("duplicateOf"):
            continue
        out.append(a)
    return out


def measure(articles: list[dict], now: datetime, days: int = 7, at_publish: bool = False) -> dict:
    """直近 days 日の暮らしとお金の記事の分布（全部を満たす本数・足りない点の多い順・保留になる本数と1日あたり）"""
    since = now - timedelta(days=days)
    rows = [a for a in articles if life(a) and (t := _published(a)) and since <= t <= now]
    counts = {p: 0 for p in POINTS}
    full = held = 0
    per_day: dict[str, list[int]] = {}
    pool = corpus(articles)
    for a in rows:
        r = check(a, at_publish=at_publish, pool=pool)
        for p in r["missing"]:
            counts[p] += 1
        full += not r["missing"]
        day = _published(a).astimezone(JST).strftime("%Y-%m-%d")
        per_day.setdefault(day, [0, 0])[0] += 1
        hold = not urgent_record(a) and applies(a) and any(p in r["missing"] for p in HOLD_POINTS)
        held += hold
        per_day[day][1] += hold
    return {"articles": len(rows), "all8": full, "missing": counts, "hold": held, "perDay": dict(sorted(per_day.items()))}


def daily_report(articles: list[dict], day: str, k: int = 5, seed: int | None = None) -> str:
    """その日（JST）に公開した記事から k 本を選び、8つの点の結果を Markdown で返す（夜の会議の資料）"""
    rows = [a for a in articles if (t := _published(a)) and t.astimezone(JST).strftime("%Y-%m-%d") == day]
    rows.sort(key=lambda a: a.get("publishedAt") or "")
    rng = random.Random(seed if seed is not None else day)
    pick = rng.sample(rows, min(k, len(rows))) if rows else []
    lines = [f"# 記事の8つの基準の抜き取り（{day}）", "",
             f"この日に公開した記事 {len(rows)} 本から {len(pick)} 本を選びました（暮らしとお金の記事は保留の対象。速報・災害は出してから直す）。", ""]
    pool = corpus(articles)
    if rows:
        all_results = [check(a, pool=pool) for a in rows]
        full = sum(1 for r in all_results if not r["missing"])
        counts = {p: sum(1 for r in all_results if p in r["missing"]) for p in POINTS}
        top = sorted((c, p) for p, c in counts.items() if c)[::-1][:3]
        lines += [f"この日の全体: 8つ全部を満たした記事 {full}/{len(rows)} 本。足りない点の多い順: "
                  + ("、".join(f"{p}.{POINTS[p]}（{c}本）" for c, p in top) or "なし"), ""]
    for a in pick:
        r = check(a, pool=pool)
        mark = "・".join(str(p) for p in r["missing"]) or "なし"
        lines += [f"## {a.get('title')}", "", f"- URL: https://ai-tech-express.jp/articles/{a.get('slug')}",
                  f"- 書き手: {a.get('writer') or '自動'}・ジャンル: {a.get('genre') or a.get('genreSlug')}・本文 {len(a.get('body') or '')}字",
                  f"- 結果: 8点中{r['score']}点（足りない点: {mark}）", ""]
        lines += ["| 点 | 基準 | 結果 |", "|---|---|---|"]
        for p, name in POINTS.items():
            lines.append(f"| {p} | {name} | {'○' if p not in r['notes'] else '× ' + r['notes'][p][:70]} |")
        lines.append("")
    if not pick:
        lines.append("この日に公開した記事はまだありません。")
    return "\n".join(lines).rstrip() + "\n"


def repair_later(articles: list[dict], now: datetime, limit: int = 3, apply: bool = False, log=print) -> list[dict]:
    """速報で出した記事（repairLater）の足りない点を、公式の資料を読み直して1回だけ手直しする。
    手直しした記事も、ふつうの事実確認（quality.evaluate）に合格したときだけ書き込む（門は緩めない）。1本につき1回だけ試す"""
    todo = []
    for a in articles:
        bar = a.get("qualityBar") or {}
        t = _published(a)
        if bar.get("repairLater") and not bar.get("laterTriedAt") and a.get("sourceUrl") and t and now - t >= timedelta(minutes=30):
            todo.append(a)
    todo.sort(key=lambda a: a.get("publishedAt") or "", reverse=True)
    done = []
    for a in todo[:limit]:
        slug = a["slug"]
        log(f"[later] {slug}: 足りない点 {bar_missing(a)}")
        outcome = {"slug": slug, "before": bar_missing(a)}
        try:
            import feeds  # noqa: PLC0415
            import quality  # noqa: PLC0415
            import rewrite_types  # noqa: PLC0415
            import web_articles as w  # noqa: PLC0415

            item = rewrite_types.item_from_article(a)
            page = feeds.fetch_article_text(item["url"])
            text = page.get("text") or ""
            if len(text) < 300:
                outcome["why"] = f"元の資料が読めない（{len(text)}字）"
            else:
                source_text = f"{w.source_header(item)}\n\n{text}"
                context = w.check_context_for(item["title"], text, [])
                rec = json.loads(json.dumps(a, ensure_ascii=False))
                rec.pop("qualityBar", None)
                rec["breaking"], rec["fastLane"] = False, False  # 手直しのための仮の値（書き込む記事では元に戻す）
                result = ensure(rec, source_text, context, log=log)
                verdict = quality.evaluate(rec, source_text, "broad", context) if rec["qualityBar"].get("repaired") else {}
                # 公開中の記事と同じ門: 事実確認（嘘だけを落とす門）・公開前の門・手直しで新しく増えた文体の問題が無いこと
                if verdict.get("ok") or verdict.get("soft"):
                    if blocked := w.publish_blocked(rec):
                        verdict = {"ok": False, "problems": [f"公開前の門: {blocked}"]}
                    elif added := quality.added_problems(a, rec):
                        verdict = {"ok": False, "problems": [f"手直しで増えた問題: {added[0]}"]}
                if rec["qualityBar"].get("repaired") and (verdict.get("ok") or verdict.get("soft")):
                    for key in ("breaking", "fastLane"):
                        if key in a:
                            rec[key] = a[key]
                        else:
                            rec.pop(key, None)
                    stamp(rec, check(rec, verdict), before=outcome["before"], repaired=True, repairedLaterAt=now.isoformat(timespec="seconds"))
                    import updated_at  # noqa: PLC0415

                    updated_at.touch_updated(rec, "facts", at=now, title="公式の資料を読み直し、対象・数字・手続きを書き足しました",
                                             source_url=a.get("sourceUrl") or "", source_name=a.get("sourceName") or "")
                    outcome.update(after=rec["qualityBar"]["missing"], saved=apply)
                    if apply:
                        (ARTICLES_DIR / f"{slug}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", "utf-8")
                    log(f"   [later] 手直しを事実確認に通して{'保存した' if apply else '保存できる（試し）'}: {outcome['before']} → {result['missing']}")
                    done.append(outcome)
                    continue
                outcome["why"] = "手直しできなかった" if not rec["qualityBar"].get("repaired") else \
                    f"手直しが事実確認に合格しなかった（{' | '.join((verdict.get('problems') or [])[:2])[:120]}）"
        except Exception as error:  # noqa: BLE001 - 1本の失敗で止めない
            outcome["why"] = f"失敗: {str(error)[:160]}"
        log(f"   [later] 今の版のまま（{outcome['why']}）")
        if apply:
            a.setdefault("qualityBar", {})["laterTriedAt"] = now.isoformat(timespec="seconds")
            (ARTICLES_DIR / f"{slug}.json").write_text(json.dumps(a, ensure_ascii=False, indent=2) + "\n", "utf-8")
        done.append(outcome)
    return done


def bar_missing(a: dict) -> list[int]:
    return list((a.get("qualityBar") or {}).get("missing") or check(a)["missing"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--measure", action="store_true")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--at-publish", action="store_true", help="公開の前の点検（あとで足す欄を数えない）")
    parser.add_argument("--daily", nargs="?", const="today", help="YYYY-MM-DD（省略で今日・JST）")
    parser.add_argument("--out", help="--daily の書き出し先（省略で out/strategy_20261110/quality_daily/YYYY-MM-DD.md）")
    parser.add_argument("--repair-later", action="store_true")
    parser.add_argument("--max", type=int, default=3)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--slug", default="")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    articles = load_articles()
    if args.measure:
        print(json.dumps(measure(articles, now, args.days, args.at_publish), ensure_ascii=False, indent=2))
    if args.daily:
        day = now.astimezone(JST).strftime("%Y-%m-%d") if args.daily == "today" else args.daily
        text = daily_report(articles, day)
        out = Path(args.out) if args.out else DAILY_DIR / f"{day}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, "utf-8")
        print(text)
        print(f"[done] {out}")
    if args.repair_later:
        rows = repair_later(articles, now, args.max, args.apply)
        print(f"[done] 速報のあとの手直し: 試した {len(rows)} 本・直した {sum(1 for r in rows if r.get('after') is not None)} 本")
    for slug in [s for s in args.slug.split(",") if s]:
        a = next((x for x in articles if x.get("slug") == slug), None)
        print(f"{slug}: {summary_line(check(a)) if a else '記事が無い'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
