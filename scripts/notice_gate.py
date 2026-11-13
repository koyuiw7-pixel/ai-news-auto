#!/usr/bin/env python3
"""お知らせ・告知・統計の転載の記事を作らない門（2026-11-03 オーナー決定）。

オーナーの決定: 発表をそのまま書き写しただけの記事（お知らせ・告知・統計の転載）は、取り下げて、これからも作らない。
例: たばこの小売定価の認可、褒章の受章者、地ビールの出荷量、決算発表日の予告、議事要旨の公開、毎年の啓発月間など、
読者が「自分にどう関係するか・何をすればいいか」を判断する材料を足していない、決まった手続きの知らせ。
報告 out/サイト全体の質の点検_2026-11-03b.md の1位（AdSense の「有用性の低いコンテンツ」に当たる）。

判定は題名（と出典）だけで行う。迷うものは通す（分析・解説の記事、AI の話題、申し込める制度の案内は止めない）。
  - 公開前の門: scripts/indexnow.py の publish_block_reason（"notice"。作り直しても直らないので見送りで確定）
  - 取り下げ: scripts/retire_articles.py --notice（直近7日に SNS に出した記事は残す）
  - 表示: lib/verdict.ts が lib/notice-rules.json（このファイルから書き出す）で、お知らせの記事に「申し込める／使える」の札を出さない
  - 毎日の見張り: scripts/owner_rules_audit.py（[A26]）

  python3 scripts/notice_gate.py                 # 今ある記事のうち、お知らせ・統計の転載に当たるものを表示
  python3 scripts/notice_gate.py --export-rules  # lib/notice-rules.json を書き出す（tests/test_notice_gate.py がずれを見つける）
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "content" / "articles"
RULES_PATH = ROOT / "lib" / "notice-rules.json"

# 区分ごとの題名の目印（題名だけで判断できる、はっきりした型だけ）
NOTICE_PATTERNS: dict[str, re.Pattern] = {
    # 認可・受章などの一覧の転載（たばこの小売定価の認可、褒章・叙勲の受章者）
    "listing": re.compile(r"認可情報|定価の認可|褒章|受章者|叙勲|紺綬|(?:表彰|受賞)者(?:を|の)(?:発表|公表|決定)|[0-9０-９]+(?:グループ|団体|事業者)を(?:決定|採択|選定)"),
    # 会議の議事要旨・議事録・会見の動画の公開
    "minutes": re.compile(r"議事(?:要旨|録|概要)|会見の(?:動画|映像)を公開|会見の(?:要旨|全文)を公開"),
    # 決算発表日の予告（中身の数字がまだ無い）
    "earnings-date": re.compile(
        r"決算(?:発表)?を\s*\d{1,2}月\d{1,2}日[^。　]{0,12}(?:に|で)?発表(?:へ|予定)|決算発表(?:の)?(?:日|日程|予定日?)(?:を|が)?(?:決定|お知らせ|公表)|"
        r"決算(?:を|の)?発表日"
    ),
    # 毎年の啓発・月間・週間・調査への協力のお願い
    "campaign": re.compile(
        r"啓発|(?:の日|月間|週間)(?:で|を|に)(?:啓発|周知|実施|展開)|ねんきん月間|(?:実態|受給者)調査」?を実施|調査への協力|"
        r"申込(?:み)?受付を終了|受付を終了しました|を随時公開|PDFで確認"
    ),
    # 統計の転載（出荷量・生産・販売の実績、定例の統計・調査の公表）
    "statistics": re.compile(
        r"出荷量|出荷数量|出荷実績|生産量|販売量|販売・生産・輸出実績|生産・販売実績|輸出実績を|人口移動報告|消費動向調査|"
        r"経済構造実態調査|[一二三四]次集計|速報値を公表|確報値を公表|統計Today|家計調査を公表|毎月勤労統計を公表|"
        r"(?:認定|登録|選定)[^。　]{0,20}\d+件を公表|コア指標を公表|"
        # 定例の統計の公表（日銀のマネタリーベース・営業毎旬報告など。2026-11-04 すり抜けを塞ぐ）
        r"マネタリーベース|マネーストック|営業毎旬報告|日本銀行勘定|貸出・預金動向|預金・貸出関連統計|企業物価指数|企業向けサービス価格指数|"
        r"資金循環統計|国際収支状況|対外資産負債残高|月例経済報告|景気動向指数|鉱工業指数|機械受注統計|"
        # 題名が「統計の名前（期間）」だけのもの: 「〇〇（10月）」「〇〇（2026年10月分）」「〇〇（10月31日現在）」「〇〇（2026年7〜9月期）」
        r"^(?!.*(?:発表|発売|開始|公開|提供|追加|決定|導入|変更|値上げ|値下げ|引き上げ|引き下げ|終了|延長|中止|買収|提携|リリース))[^（(。、]{2,30}[（(](?:\d{4}年)?\d{1,2}月(?:\d{1,2}日)?(?:[〜～-]\d{1,2}月期?)?(?:分|末|中|現在|期)?(?:・?(?:速報|確報)値?)?[）)]$|"
        r"^(?!.*(?:発表|発売|開始|公開|提供|追加|決定|導入|変更|値上げ|値下げ|引き上げ|引き下げ|終了|延長|中止|買収|提携|リリース))[^（(。、]{2,30}[（(]\d{4}年度?(?:第[1-4１-４]四半期)?(?:分|速報|確報)?[）)]$"
    ),
}
# 止めないもの: 分析・解説を足した記事、AI の話題（AI の利用調査など）、申し込める制度・支援金の案内
ANALYSIS_RE = re.compile(r"分析|解説|読み解|要因|背景|理由|なぜ|指摘|乖離|示唆|見通し|予測|影響")
AI_RE = re.compile(r"(?<![A-Za-z])AI(?![a-z])|人工知能|生成AI|LLM|GPT|Gemini|Claude|Copilot|ChatGPT", re.I)
APPLY_RE = re.compile(r"申請受付|申し込み受付|募集を開始|受付を開始|給付|補助金|助成金|支援金|減税|控除")
# 分析を出すシンクタンク・調査会社の解説記事は、統計の題名でも止めない（ニッセイ基礎研は「〜が分析」と書く）
ANALYSIS_CHANNELS = {"nli-research"}

# --------------------------------------------------------------------------- #
# 2026-11-13 オーナー「とにかく数字。それさえ出るなら結構なんでもいい」「注目する話題がとれていない」（点検 audit_20261113）:
# 検索で読まれた型（褒章の受章者 24人・役所の調査の公表 14人・限定商品やキャンペーン）をこの門が止めていた。
# 題名に「固有名詞」と「年・日付か、金額・数」がそろうものだけ通す。中身の無い知らせ（審議会・検討会・委員会の開催、
# 啓発月間、ライトアップ、認可情報の一覧、決算発表日の予告、議事要旨）は今までどおり止める。
# サイト側の札の決まり（lib/verdict.ts・台帳 A27）は変えない: 通した受章者の一覧・統計の記事にも「申し込める／使える」の札は出さない
# （だから rules() には書き出さない。tests/test_verdict_label.cjs が確かめる）。
# --------------------------------------------------------------------------- #
# どの型でも通さない知らせ
NEVER_PASS_RE = re.compile(
    r"審議会|検討会|委員会|部会|懇談会|研究会|協議会|有識者会議|議事|会見|啓発|月間|週間|ライトアップ|認可情報|定価の認可|"
    r"決算発表|発表日|説明会|セミナー|ウェビナー|講演|入札|調達"
)
# 褒章・叙勲など、名前のある栄典と受章者・受賞者の一覧
HONOUR_RE = re.compile(r"褒章|叙勲|勲章|文化功労者|国民栄誉賞|受章者|(?:受賞|表彰)者")
# 官公庁・自治体・日銀（統計・調査を公表する側）
GOV_ORG_RE = re.compile(
    r"(?:内閣|総務|法務|外務|財務|文部科学|文科|厚生労働|厚労|農林水産|農水|経済産業|経産|国土交通|国交|環境|防衛)省|内閣府|"
    r"(?:デジタル|金融|消費者|こども家庭|気象|国税|警察|観光|特許|中小企業|資源エネルギー|林野|水産|復興|総務省統計)[庁局]|"
    r"日本銀行|日銀|政府|[一-龥]{2,4}(?:都|道|府|県|市|区)(?:庁|役所)?(?![一-龥]*銀行)"
)
SURVEY_RE = re.compile(r"調査|統計|白書|推計|集計|報告|動向|指数|実態")
# 題名が「統計の名前（期間）」だけのもの（中身の数字が無い。今までどおり止める）
BARE_STAT_RE = re.compile(r"^[^（(。、]{2,30}[（(][^）)]{1,24}[）)]$")
YEAR_DATE_RE = re.compile(r"(?:19|20)\d{2}年|令和\d{1,2}年|\d{1,2}月(?:\d{1,2}日|分|期|末)?|\d{1,2}/\d{1,2}|(?:春|秋)の(?:褒章|叙勲)")
AMOUNT_RE = re.compile(
    r"\d[\d,.]*\s?(?:兆|億|万|千)?(?:円|人|名|件|社|団体|世帯|%|％|ポイント|倍|割|台|本|個|店舗?|か所|カ所|戸|歳|種類?)|半額|無料"
)
# 固有名詞の目印（カタカナ3字以上・英字の語・「」の中・会社や組織の名前）。よくある一般の語は先に外す
GENERIC_WORD_RE = re.compile(
    r"キャンペーン|プレゼント|クーポン|セール|ポイント|サービス|イベント|ライトアップ|セミナー|ポスター|アンケート|スタート|"
    r"オンライン|ホームページ|キャッシュバック|プログラム|エントリー|ニュース|リリース|グループ|メンバー|オープン|プラン|"
    r"(?<![A-Za-z])(?:PDF|URL|WEB|HP|PR|NEW|No|Vol|FAQ)(?![A-Za-z])",
    re.I,
)
PROPER_RE = re.compile(
    r"[ァ-ヴー]{3,}|[A-Za-z][A-Za-z0-9&+.\-]{1,}|「[^」]{2,}」|『[^』]{2,}』|"
    r"[一-龥ぁ-んァ-ヶー]{2,8}(?:銀行|大学|電力|ガス|鉄道|航空|証券|保険|製薬|食品|乳業|製菓|ビール|酒造|自動車|電機|百貨店|ホールディングス)"
)
# 「価値の薄いお知らせ」（scripts/web_articles.py の LOW_VALUE_RE）のうち、条件つきで通す語
SALE_WORDS = ("キャンペーン", "プレゼント", "抽選", "クーポン", "セール", "割引", "ポイント還元", "ポイント付与", "福袋")
RECRUIT_WORDS = ("募集", "公募")
HONOUR_WORDS = ("受賞", "表彰")
# 募集・受付は締め切りが題名にあるものだけ
DEADLINE_RE = re.compile(
    r"(?:\d{1,2}月\d{1,2}日|\d{1,2}/\d{1,2})[^。]{0,6}(?:まで|締切|締め切り|〆切|必着|期限)|"
    r"(?:締切|締め切り|〆切|期限|応募期間|受付期間|募集期間)[^。]{0,8}\d{1,2}月\d{1,2}日|[〜～]\s?\d{1,2}月\d{1,2}日"
)


def has_proper_noun(title: str, source_name: str = "") -> bool:
    """題名に固有名詞があるか（会社・商品・制度・役所・栄典の名前）。よくある一般の語（キャンペーンなど）は数えない"""
    text = GENERIC_WORD_RE.sub(" ", f"{title} {source_name}")
    return bool(PROPER_RE.search(text) or GOV_ORG_RE.search(text) or HONOUR_RE.search(title))


def has_fact(title: str) -> bool:
    """題名に年・日付か、金額・数があるか"""
    return bool(YEAR_DATE_RE.search(title) or AMOUNT_RE.search(title))


def winner_exempt(key: str, title: str, source_name: str = "") -> bool:
    """お知らせの区分に当たっても通す、検索で読まれた型か（受章者の一覧・官公庁の調査や統計の公表。固有名詞＋年/日付か数）"""
    if NEVER_PASS_RE.search(title) or not has_fact(title):
        return False
    if key == "listing":
        return bool(HONOUR_RE.search(title))
    if key == "statistics":
        return bool(not BARE_STAT_RE.search(title) and SURVEY_RE.search(title) and GOV_ORG_RE.search(f"{title} {source_name}"))
    return False


def low_value_exempt(title: str, word: str, source_name: str = "") -> bool:
    """「価値の薄いお知らせ」の語（word）に当たっても通す題名か:
    キャンペーン・割引・プレゼントなど＝固有名詞＋（年/日付か金額・数）、募集・公募＝固有名詞＋締め切り、受賞・表彰＝受章者・受賞者の一覧＋年か数"""
    if NEVER_PASS_RE.search(title) or not has_proper_noun(title, source_name):
        return False
    if word in SALE_WORDS:
        return has_fact(title)
    if word in RECRUIT_WORDS:
        return bool(DEADLINE_RE.search(title))
    if word in HONOUR_WORDS:
        return bool(HONOUR_RE.search(title)) and has_fact(title)
    return False


LABELS = {
    "listing": "認可・受章などの一覧の転載",
    "minutes": "議事要旨・会見の動画の公開",
    "earnings-date": "決算発表日の予告",
    "campaign": "毎年の啓発・手続きのお知らせ",
    "statistics": "統計・実績の数字の転載",
}


def notice_reason(record: dict) -> str | None:
    """お知らせ・告知・統計の転載の区分（当たらなければ None）。題名と出典だけで判断する"""
    if record.get("disaster") or record.get("type") == "roundup":
        return None
    # 発表時刻が決まった速報（2026-11-05 オーナー承認・台帳 W35。統計・決算の公式発表を数分で記事にする）は、転載ではなく
    # 読者への意味まで書く型で作り、数字は release_quality の門で資料と照合する。統計の名前の題名でも止めない
    if record.get("scheduledRelease"):
        return None
    title = str(record.get("title") or "")
    if not title or AI_RE.search(title):
        return None
    for key, pattern in NOTICE_PATTERNS.items():
        if not pattern.search(title):
            continue
        if key == "statistics" and (ANALYSIS_RE.search(title) or record.get("channelSlug") in ANALYSIS_CHANNELS):
            return None
        if key == "campaign" and APPLY_RE.search(title):
            return None
        if winner_exempt(key, title, str(record.get("sourceName") or record.get("channel") or "")):
            continue  # 検索で読まれた型（受章者の一覧・官公庁の調査や統計の公表。2026-11-13）
        return key
    return None


def is_notice(record: dict) -> bool:
    return notice_reason(record) is not None


# --------------------------------------------------------------------------- #
# サイト（lib/verdict.ts）が読む材料
# --------------------------------------------------------------------------- #


def _js(pattern: re.Pattern) -> dict:
    return {"source": pattern.pattern, "flags": "i" if pattern.flags & re.I else ""}


def rules() -> dict:
    return {
        "_note": "scripts/notice_gate.py --export-rules で生成。手で直さない（正本は scripts/notice_gate.py）",
        "patterns": {k: _js(v) for k, v in NOTICE_PATTERNS.items()},
        "analysis": _js(ANALYSIS_RE),
        "ai": _js(AI_RE),
        "apply": _js(APPLY_RE),
        "analysisChannels": sorted(ANALYSIS_CHANNELS),
    }


def rules_json() -> str:
    return json.dumps(rules(), ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--export-rules", action="store_true", help="lib/notice-rules.json を書き出す")
    args = parser.parse_args()
    if args.export_rules:
        RULES_PATH.write_text(rules_json(), encoding="utf-8")
        print(f"[notice] → {RULES_PATH.relative_to(ROOT)}")
        return 0
    hits = []
    for path in sorted(ARTICLES_DIR.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if reason := notice_reason(record):
            hits.append((reason, record.get("slug", path.stem), record.get("title", "")))
    for reason, slug, title in sorted(hits):
        print(f"{reason:14} {slug:55} {title}")
    print(f"[notice] {len(hits)} 本")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
