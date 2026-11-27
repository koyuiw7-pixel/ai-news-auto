#!/usr/bin/env python3
"""「あなたの数字のニュース」の門（2026-11-28 オーナー承認の見直し。out/strategy_20261128/review_ja.md）。

サイソクは「何が変わったか」で終わらず、「あなたの家はいくら・いつまで・何をするか」まで答える。そのための2つの門:

1. 話題の門（topic_block。記事を書く前・LLM を使わない。GitHub の変数 AXIS_TOPIC_GATE: 1＝止める / log＝止めずに記録（既定）/ 0＝使わない）
   自動の記事は、暮らしとお金の軸（給付・税・年金・手当・保険料・料金や値段の変更・手続きの期限、
   リコール・情報流出・障害・詐欺のように「自分は対象か・何をするか」がある話）だけ作る。
   AI・技術・海外・スポーツ・エンタメ・会社の業績や提携（家計のお金の話が無いもの）は自動で作らない。
   地震・津波・台風・大雨・ミサイルなどの安全の速報と、大きな障害は今までどおり止めない。
   2026-11-28 オーナー「本数を減らさない」: 軸の外を止める分を、軸の発信元を広げて埋めるまでは止めずに記録だけ
   （content/your_number_topic_log.json）。埋まったら AXIS_TOPIC_GATE=1 にする。

2. 中身の門（check / ensure / hold_reason。書いたあと・公開の前）。軸の記事に次の4つを求める:
   a. あなたの数字: 自分の場合が分かる表か計算の例（世帯・年収・年齢などの別の額）、またはサイトの計算ページ（lib/calculators.ts）への案内を前のほうに。
      リコール・流出・障害は「自分が対象か確かめる方法」（型番・ロット・期間・確認のページ）でよい
   b. 期限・日付（または「期限は無い」「手続きは不要」）
   c. 窓口・手続き（どこで・どうやって）と公式の URL
   d. 公式の出典のリンク（報道だけを出典にしない）
   足りなければ、公式の資料の事実だけで1回だけ手直しする（LLM。数字・URL を作らない。計算ページの案内はプログラムで足す）。
   手直しのあとも足りなければ出さない（保留。理由を content/your_number_log.json に残す。止めないのは AXIS_CONTENT_GATE=0）。
   速報・災害は出してからあとで直す。

scripts/quality_bar.py の ensure / hold_reason から呼ぶので、自動の記事・速報レーン・Muse・深掘り・別の切り口・動画のどの経路も同じ門を通る。

  python3 scripts/your_number.py --measure --days 3            # 直近3日の公開記事にこの門を当てた結果（試し・LLM なし）
  python3 scripts/your_number.py --slug a,b                    # 記事ごとの結果
  python3 scripts/your_number.py --titles "題名1" "題名2"       # 話題の門だけ
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

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "content" / "your_number_log.json"
LOG_KEEP = 400
JST = timezone(timedelta(hours=9))
SITE_HOST = "ai-tech-express.jp"

REQUIREMENTS = {
    "a": "あなたの数字（自分の場合が分かる表・計算の例・計算ページ／対象かどうかの確かめ方）",
    "b": "期限・日付（または期限が無いこと）",
    "c": "窓口・手続きと公式の URL",
    "d": "公式の出典のリンク",
}


def _nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


# --------------------------------------------------------------------------- #
# 1. 話題の門
# --------------------------------------------------------------------------- #
# 安全の速報（止めない）
SAFETY_RE = re.compile(
    r"地震|震度|津波|噴火|火山|台風|大雨|豪雨|線状降水帯|大雪|暴風|高潮|洪水|土砂災害|警報|特別警報|避難|ミサイル|Jアラート|緊急地震|"
    r"熱中症警戒|停電|断水|鳥インフル|インフルエンザ|食中毒|感染症|豚熱|口蹄疫|運転見合わせ|運休|欠航|通行止め")
# 「自分は対象か・何をするか」がある注意の話
ALERT_RE = re.compile(
    r"リコール|自主回収|回収|使用(?:を)?中止|交換|無償修理|改善対策|流出|漏え?い|漏洩|不正アクセス|不正利用|不正ログイン|情報の?持ち出し|"
    r"個人情報|ランサム|サイバー攻撃|(?<!視覚|聴覚|身体|知的|精神|発達)障害(?!者|児|福祉|施策|年金|基礎年金|厚生年金|手当|給付)|不具合|つながりにくい|通信障害|システム障害|"
    r"(?:サービス|提供|運転|販売|出荷|利用|供給|配送)(?:の)?(?:一時)?停止|停止中|詐欺|フィッシング|なりすまし|偽(?:サイト|メール|SMS)|"
    r"脆弱性|注意喚起|誤表示|表示違反|異物|健康被害|発火|発煙|火災|事故|水質|無登録|不審な勧誘|悪質商法|架空請求|サービス(?:の)?終了|提供(?:を)?終了|廃止|サポート(?:の)?終了")
ALERT_EN_RE = re.compile(r"outage|breach|recall|vulnerabilit|exploit|incident|disruption|data leak|security update", re.I)
# 注意の語のうち、題名が催し・広報・採用でも「自分は対象か」の話と言える強い語
ALERT_STRONG_RE = re.compile(
    r"リコール|自主回収|回収|流出|漏え?い|漏洩|不正アクセス|不正利用|不正ログイン|詐欺|フィッシング|なりすまし|脆弱性|重大(?:製品)?事故|"
    r"使用(?:を)?中止|通信障害|システム障害|健康被害|無登録")
# 家計のお金・制度
MONEY_RE = re.compile(
    r"給付|手当|補助|助成|支援金|支援策|一時金|還付|還元|減税|増税|控除|非課税|課税|税(?:金|率|制|額)?|年金|保険料|医療費|窓口負担|自己負担|負担|"
    r"高額療養費|介護|出産|育休|育児休業|児童(?:手当|扶養)|子育て(?:支援|世帯)|教育費|授業料|奨学金|学費|無償化|最低賃金|賃金|給与|給料|手取り|ボーナス|賞与|退職金|"
    r"ふるさと納税|NISA|iDeCo|マイナ(?:ンバー|保険証|ポイント)|ポイント(?:還元|付与|の?上乗せ)|キャッシュレス|金利|住宅ローン|預金|貯金|家賃|"
    r"電気(?:代|料金)|ガス(?:代|料金)|水道(?:代|料金)|光熱費|ガソリン|灯油|燃料費|物価|値上げ|値下げ|価格改定|料金改定|料金|運賃|通行料|"
    r"手数料|月額|年額|プラン(?:の)?(?:料金|変更|改定)|無料化|有料化|値段|価格|円(?:に|へ|から|分)|割引|定額|受信料|"
    r"生活保護|失業|雇用保険|ハローワーク|就職氷河期|住民税|所得税|消費税|固定資産税|相続|贈与|登記|罰金|反則金|"
    r"申請|手続き|締め?切|期限|受付(?:開始|期間)?|義務化|改正|施行|制度|支給|振込|振り込|福袋|当選|抽選販売")
# 家計のお金に見えて、会社の話だけのもの（業績・提携・人事・市場）
CORP_RE = re.compile(
    r"決算|業績|増収|減収|増益|減益|売上高|営業利益|純利益|中期経営計画|M&A|買収|合併|経営統合|資本(?:提携|業務提携)|業務提携|提携|協業|出資|"
    r"子会社|株主総会|上場|株価|株式|社債|IR|人事|就任|退任|新社長|組織変更|受注|導入事例|実証実験|共同研究|新工場|設立")
# 家計の語のうち、会社の話の中でも「家計のお金」と言える強い語（これがあれば会社の発表でも作る）
HOUSEHOLD_STRONG_RE = re.compile(
    r"値上げ|値下げ|価格改定|料金改定|料金|運賃|手数料|月額|無料化|有料化|ポイント(?:還元|付与)|還元|割引|金利|預金|住宅ローン|"
    r"給付|手当|補助|助成|年金|保険料|税|受信料|電気(?:代|料金)|ガス(?:代|料金)|リコール|回収|流出|漏え?い|障害|詐欺")
# 軸の外の分野（家計の語が無ければ作らない）
OFF_SECTIONS = frozenset({"ai", "sports", "entertainment", "science", "tech-gadget", "auto"})
OFF_TOPIC_RE = re.compile(
    r"試合|優勝|決勝|勝利|敗れ|ゴール|得点|ホームラン|代表(?:メンバー|選手)|移籍|監督|リーグ|大会|選手権|五輪|オリンピック|W杯|ワールドカップ|"
    r"映画|ドラマ|アニメ|声優|主題歌|ライブ|公演|ツアー|アルバム|シングル|MV|PV|トレーラー|キャラクター|ゲーム|コラボ|"
    r"生成AI|ChatGPT|Gemini|Claude|Copilot|LLM|大規模言語モデル|AIモデル|AIエージェント|API|SDK|開発者|研究成果|論文|新素材|量子|"
    r"新製品|新型|新モデル|新商品|新発売|発売|新メニュー|期間限定|新登場|リニューアル|オープン|開業|イベント|キャンペーン|"
    r"セミナー|説明会|講演|フォーラム|展示会|シンポジウム|募集|公募|入札|統計|調査結果|動向|審議会|部会|分科会|検討会|会議|懇談会|"
    r"開催|資料|議事|授賞|表彰|受賞|コンクール|寄付|寄附|PR|広報|コラボ|動画を(?:配信|公開)|突破|ロシア|ユーロ圏|米国の|中国の")
# 役所・会社の中の話（どんな語があっても作らない）
HARD_OFF_RE = re.compile(r"採用情報|職員(?:の)?募集|募集情報|人事異動|任期付職員|業務停止処分|懲戒|入札公告|補助員|事務員|調達情報|意見招請|企業版ふるさと納税|財政融資|国債金利|不当廉売|貸出約定|"
    r"企業向けサービス価格|特別付利|当座預金|記者会見(?:の)?(?:概要|要旨)?$|官房長官記者会見")


def _no_reader_action(title: str) -> bool:
    try:
        import persona  # noqa: PLC0415

        return persona.no_reader_action(title)
    except Exception:  # noqa: BLE001
        return False


def topic_kind(title: str, summary: str = "", *, section: str = "", lang: str = "ja") -> str | None:
    """話題の種類: "safety"（安全の速報）/ "alert"（対象か確かめる注意の話）/ "money"（家計のお金・制度）/ None（軸の外）。
    題名で決める（要約は、題名に語が無いときの補い。会社の話か・分野の外かは題名だけで見る）"""
    t = _nfkc(title)
    s = _nfkc(summary)[:300]
    if SAFETY_RE.search(t):
        return "safety"
    if (lang or "ja").lower() != "ja":
        # 海外の発表は、日本の利用者にも関わる障害・流出・リコールだけ
        return "alert" if ALERT_EN_RE.search(t) or ALERT_RE.search(t) else None
    if _no_reader_action(t) or HARD_OFF_RE.search(t):
        return None
    alert, money = bool(ALERT_RE.search(t)), bool(MONEY_RE.search(t))
    if CORP_RE.search(t) and not HOUSEHOLD_STRONG_RE.search(t):
        return None  # 会社の業績・提携・人事（家計のお金の話が題名に無い）
    if (section in OFF_SECTIONS or OFF_TOPIC_RE.search(t)) and not (HOUSEHOLD_STRONG_RE.search(t) or ALERT_STRONG_RE.search(t)):
        return None  # AI・技術・スポーツ・エンタメ・新製品（値段・料金・注意の話が無い）
    if alert:
        return "alert"
    if money:
        return "money"
    if s and section in ("public", "lifestyle", "business", "investment", "real-estate") and HOUSEHOLD_STRONG_RE.search(s):
        return "money"
    return None


def item_kind(item: dict) -> str | None:
    return topic_kind(str(item.get("title") or ""), str(item.get("summary") or ""),
                      section=str(item.get("section") or item.get("genreSlug") or ""), lang=_lang_of(item))


def _lang_of(item: dict) -> str:
    lang = str(item.get("lang") or "").lower()
    if lang:
        return lang
    try:
        import feeds  # noqa: PLC0415

        slug = str(item.get("source_slug") or item.get("channelSlug") or "")
        return str((feeds.FEEDS_BY_SLUG.get(slug) or {}).get("lang") or "ja").lower()
    except Exception:  # noqa: BLE001
        return "ja"


TOPIC_REASON = "あなたの数字の軸の外（家計のお金・制度・注意の話ではない。2026-11-28 見直し・scripts/your_number.py）"


TOPIC_LOG_PATH = ROOT / "content" / "your_number_topic_log.json"


def topic_mode() -> str:
    """話題の門の動き方（GitHub の変数 AXIS_TOPIC_GATE）: "1"＝止める / "log"＝止めずに記録だけ（既定）/ "0"＝使わない。
    2026-11-28 オーナー「質も上がる保証ないのに本数減らすってサボってるだけじゃん」: 軸の外を止める分の本数を、軸の発信元を広げて
    埋められるまでは止めない（記録だけ）。埋められたら AXIS_TOPIC_GATE=1 にする"""
    import os  # noqa: PLC0415

    value = (os.environ.get("AXIS_TOPIC_GATE") or "log").strip().lower()
    return value if value in ("1", "0", "log") else "log"


def topic_reason(item: dict, *, breaking: bool = False) -> str | None:
    """軸の外なら理由（動き方に関係なく判定だけ）。速報の候補でも、安全・注意・お金の話でなければ理由を返す
    （速報を戻すときは環境変数 AXIS_GATE_BREAKING=0）"""
    import os  # noqa: PLC0415

    if item_kind(item):
        return None
    if breaking and os.environ.get("AXIS_GATE_BREAKING", "1") == "0":
        return None
    return TOPIC_REASON


def topic_block(item: dict, *, breaking: bool = False, log=None) -> str | None:
    """自動の記事にしない理由（作ってよいなら None）。動き方が "log" なら止めずに記録だけ残す（content/your_number_topic_log.json）"""
    mode = topic_mode()
    if mode == "0":
        return None
    reason = topic_reason(item, breaking=breaking)
    if not reason:
        return None
    if mode == "log":
        if log:
            log(f"   [axis] 軸の外（試しの期間なので止めない）: {str(item.get('title') or '')[:60]}")
        _append_log({"title": str(item.get("title") or "")[:120], "url": item.get("url") or item.get("sourceUrl"),
                     "source": item.get("source_slug") or item.get("channelSlug"), "mode": "log"}, TOPIC_LOG_PATH, dedupe="url")
        return None
    return reason


def _append_log(row: dict, path: Path, dedupe: str = "") -> None:
    """記録を残す（直近 LOG_KEEP 件）。GitHub Actions の中か、YOUR_NUMBER_LOG=1 のときだけ（テストや手元の試しで書かない）"""
    import os  # noqa: PLC0415

    if not (os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("YOUR_NUMBER_LOG") == "1"):
        return
    try:
        rows = json.loads(path.read_text("utf-8")) if path.exists() else []
    except (OSError, ValueError):
        rows = []
    if dedupe and row.get(dedupe) and any(r.get(dedupe) == row[dedupe] for r in rows):
        return  # 同じ候補は1回だけ（止めない動き方では、同じ候補が毎回の実行で出てくる）
    rows.append({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **row})
    try:
        path.write_text(json.dumps(rows[-LOG_KEEP:], ensure_ascii=False, indent=1) + "\n", "utf-8")
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# 2. 中身の門（LLM を使わない点検）
# --------------------------------------------------------------------------- #
TABLE_SEP_RE = re.compile(r"(?m)^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
CALC_RE = re.compile(r"サイソク編集部の計算|編集部の計算|[0-9][^。\n]{0,30}[×÷][^。\n]{0,30}[＝=]")
TOOLS_LINK_RE = re.compile(r"\]\((?:https://ai-tech-express\.jp)?/tools/[a-z0-9-]+\)")
# リコール・流出・障害の「自分が対象か」の確かめ方
CHECK_RE = re.compile(
    r"型番|品番|型式|製造番号|シリアル|ロット|製造所固有記号|賞味期限|消費期限|JAN|車台番号|対象(?:の)?(?:製品|商品|型式|機種|車種|期間|ロット|番号|地域|エリア|サービス|会員|利用者)|"
    r"対象(?:か|かどうか)|確認(?:方法|ページ|サイト|ツール|フォーム)|照会|確かめ(?:られ|る方法)|影響(?:を受け|の)(?:た|ある)(?:人|利用者|範囲)")
# 自分の額の確かめ方（資料に人ごとの額の表が無い制度で、自分の額が書いてある書類・ページを示す）
LOOKUP_RE = re.compile(
    r"(?:保険料|金額|額|税額|支給額|年金額|給付額|手当の額|還付額|料金|上限額|自己負担|点数|ポイント)[^。]{0,40}"
    r"(?:通知書|納付書|納入通知|決定通知|明細|請求書|検針票|マイページ|会員ページ|アプリ|ねんきんネット|ねんきん定期便|マイナポータル|源泉徴収票|"
    r"給与明細|領収書|保険証|資格確認書|窓口|ページ|サイト)[^。]{0,20}(?:確か|確認|分か|見られ|載って|書かれ|記載)")
DATE_RE = re.compile(
    r"\d{1,2}月\d{1,2}日|\d{1,2}月(?:末|中|上旬|中旬|下旬|分|から|まで|以降|使用分|支給|請求)|\d{4}年\d{1,2}月|\d{4}年度|令和\d+年|\d{1,2}/\d{1,2}|"
    r"\d+(?:日|か月|カ月|ヶ月|年)(?:以内|まで|間)")
DEADLINE_WORD_RE = re.compile(
    r"まで|期限|締め?切|から|開始|以降|支給|振込|振り込|受付|申請|施行|適用|使用分|期間|始ま|終了|予定|変わ|改定|実施|時点|発生|復旧|回収|交換|対象")
NO_DEADLINE_RE = re.compile(
    r"期限(?:は|の)?(?:ありません|ない|なく|設けられていません|定められていません|決まっていません|示されていません|未定)|期限なし|いつでも|随時|"
    r"手続き(?:は|の)?(?:必要(?:は)?(?:ありません|ない)|不要|いりません)|申請(?:は)?不要|申し込み(?:は)?不要|手続き不要|自動で(?:適用|反映|切り替|変わ|引き下げ|引き上げ|支給|振り込|値引き)")
DESK_RE = re.compile(
    r"窓口|市区町村|市役所|区役所|町村役場|役場|役所|税務署|年金事務所|ねんきんダイヤル|ねんきんネット|ハローワーク|保健所|労働基準監督署|消費生活センター|188|"
    r"コールセンター|ダイヤル|お客様(?:相談)?(?:窓口|センター|室)|相談(?:窓口|室|センター)|問い合わせ|問合せ|電話|フリーダイヤル|0120|0570|"
    r"申請(?:ページ|サイト|フォーム)|マイナポータル|e-Tax|e-Gov|専用(?:ページ|サイト|ダイヤル|窓口)|受付(?:窓口|センター)|会員ページ|マイページ|アプリ|"
    r"店舗|店頭|販売店|ディーラー|金融機関|銀行|郵便局|勤務先|会社の(?:担当|人事|総務)|健康保険組合|協会けんぽ|保険者|学校|自治体|都道府県|"
    r"手続き|申請|申し込|届け出|届出|返金|交換|回収")
URL_RE = re.compile(r"https?://[^\s)\]<>」』）]+")


def _host(url: str) -> str:
    host = urllib.parse.urlsplit(url or "").netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _press(url: str) -> bool:
    try:
        import indexnow  # noqa: PLC0415

        return indexnow.press_host(url)
    except Exception:  # noqa: BLE001
        return False


def official_url(url: str) -> bool:
    """公式の URL か（報道・集約サイト・このサイト・SNS・動画でない http の URL）"""
    host = _host(url)
    if not host or not url.startswith("http"):
        return False
    if host == SITE_HOST or host.endswith(("youtube.com", "youtu.be", "x.com", "twitter.com", "facebook.com", "instagram.com", "threads.net",
                                            "threads.com", "line.me", "note.com", "prtimes.jp", "atpress.ne.jp")):
        return False
    return not _press(url)


def _list(value) -> list:
    return value if isinstance(value, list) else []


def _sentences(text: str) -> list[str]:
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.extend(s for s in re.split(r"(?<=[。！？])", line) if s.strip())
    return out


def record_kind(record: dict) -> str | None:
    """記事の話題の種類（題名・検索用の題名・タグ）。中身の門を求めるのは "money" と "alert"""
    # 題名だけで見る（検索用の題名は「料金は？」のような語が付きやすく、話題の判定に使わない）
    title = str(record.get("title") or "")
    return topic_kind(title, " ".join(str(t) for t in _list(record.get("tags"))),
                      section=str(record.get("genreSlug") or ""), lang=str(record.get("lang") or "ja"))


def urgent_record(record: dict) -> bool:
    """止めずに出す記事（速報・速報レーン・地震や災害・安全の話）"""
    if record.get("disaster") or record.get("breaking") is True or (record.get("newsType") or "") == "breaking" or record.get("fastLane"):
        return True
    return str(record.get("slug") or "").startswith(("quake-", "tsunami-")) or record_kind(record) == "safety"


def applies(record: dict) -> bool:
    """中身の門を求める記事か（軸の money・alert の記事。読者がすることの無い発表は除く）"""
    if str(record.get("type") or "") == "roundup":
        return False
    return record_kind(record) in ("money", "alert")


# --- 計算ページ（lib/calculators.ts の calculatorForArticle と同じ語。tests/test_your_number.py で TS の種類と揃っているか確かめる）---
CALCULATORS = {
    "defense-tax": ("/tools/defense-tax", "防衛特別所得税の計算", re.compile(r"防衛特別所得税|防衛増税|防衛税|復興特別所得税")),
    "furusato-limit": ("/tools/furusato-limit", "ふるさと納税の上限額の計算", re.compile(r"ふるさと納税")),
    "child-allowance": ("/tools/child-allowance", "児童手当の支給額の計算", re.compile(r"児童手当")),
    "pension-support-benefit": ("/tools/pension-support-benefit", "年金生活者支援給付金の計算", re.compile(r"年金生活者支援給付金")),
    "denki-gas-discount": ("/tools/denki-gas-discount", "冬の電気代・ガス代の値引き額の計算",
                           re.compile(r"電気・ガス料金(の)?支援|電気・ガス(料金|代)の?(補助|値引き)|電気代.{0,30}(値引き|円引き|補助|支援)|ガス代.{0,30}(値引き|円引き|補助|支援)")),
    "kogaku-ryoyohi": ("/tools/kogaku-ryoyohi", "高額療養費の自己負担の上限額の計算", re.compile(r"高額療養費")),
    "ikukyu-kyufu": ("/tools/ikukyu-kyufu", "育休中にもらえるお金の計算", re.compile(r"育児休業給付|育休給付|出生後休業支援給付金|出生時育児休業給付金")),
    "bonus-tedori": ("/tools/bonus-tedori", "冬のボーナスの手取りの計算", re.compile(r"ボーナス|賞与")),
}
CALC_ORDER = ("defense-tax", "furusato-limit", "child-allowance", "pension-support-benefit", "denki-gas-discount", "kogaku-ryoyohi",
              "ikukyu-kyufu", "bonus-tedori")


def calculator_for(record: dict) -> str | None:
    """記事に合う計算ページ（lib/calculators.ts の calculatorForArticle と同じ順。税はタグでも当てる）"""
    title = f"{record.get('title') or ''} {record.get('seoTitle') or ''}"
    tags = [str(t) for t in _list(record.get("tags"))]
    for kind in CALC_ORDER:
        rx = CALCULATORS[kind][2]
        if rx.search(title) or (kind == "defense-tax" and any(rx.search(t) for t in tags)):
            return kind
    return None


TOP_SHARE = 0.4  # 計算ページの案内は、本文の前のほう（はじめの4割か1,500字まで）に
TOP_CHARS = 1500


def _near_top(body: str, pos: int) -> bool:
    return pos <= max(TOP_CHARS, int(len(body) * TOP_SHARE))


def _table_rows(body: str) -> int:
    """表の中身の行の数（区切りの行の下の行）"""
    best = 0
    for m in TABLE_SEP_RE.finditer(body):
        rows = 0
        for line in body[m.end():].lstrip("\n").splitlines():
            if not line.strip().startswith("|"):
                break
            rows += 1
        best = max(best, rows)
    return best


def need_a(record: dict) -> str | None:
    body = record.get("body") or ""
    if _table_rows(body) >= 2 or CALC_RE.search(_nfkc(body)):
        return None
    if (m := TOOLS_LINK_RE.search(body)) and _near_top(body, m.start()):
        return None
    if record_kind(record) == "alert":
        nb = _nfkc(body)
        if CHECK_RE.search(nb) and (URL_RE.search(body) or _table_rows(body) >= 1 or "](" in body):
            return None
        return "対象かどうかの確かめ方（型番・ロット・期間・確認のページ）が無い"
    if LOOKUP_RE.search(_nfkc(body)) and _official_links(record):
        return None  # 人ごとの額の表が資料に無い制度: 自分の額が載っている書類・ページの確かめ方と公式の URL
    if TOOLS_LINK_RE.search(body):
        return "計算ページの案内が本文の後ろのほうにしか無い"
    return "自分の場合が分かる表・計算の例・計算ページの案内が無い"


def need_b(record: dict) -> str | None:
    text = _nfkc(f"{record.get('lede') or ''}\n{record.get('body') or ''}")
    if NO_DEADLINE_RE.search(text):
        return None
    alert = record_kind(record) == "alert"
    for s in _sentences(text):
        # リコール・流出・障害は、起きた日・対象の期間・公表の日のような日付でよい（申し込みの期限が無い話が多い）
        if DATE_RE.search(s) and (alert or DEADLINE_WORD_RE.search(s)):
            return None
    return "期限・日付（いつから・いつまで）も「期限は無い」も書いていない"


def _official_links(record: dict) -> list[str]:
    urls = [u.rstrip(".,。") for u in URL_RE.findall(record.get("body") or "")]
    for desk in _list(record.get("officialDesk")):
        if isinstance(desk, dict) and desk.get("url"):
            urls.append(str(desk["url"]))
    for step in _list(record.get("todaySteps")):
        if isinstance(step, dict) and step.get("url"):
            urls.append(str(step["url"]))
    return [u for u in urls if official_url(u)]


def need_c(record: dict) -> str | None:
    body = _nfkc(record.get("body") or "")
    desks = [d for d in _list(record.get("officialDesk")) if isinstance(d, dict) and d.get("url") and official_url(str(d["url"]))]
    if desks:
        return None
    links = _official_links(record)
    has_desk = bool(DESK_RE.search(body)) or bool(NO_DEADLINE_RE.search(body))
    if has_desk and links:
        return None
    if not has_desk:
        return "窓口・手続き（どこで・どうやって）が無い"
    return "窓口・手続きの公式の URL が本文に無い"


def source_urls(record: dict) -> list[str]:
    urls = [str(record.get("sourceUrl") or ""), str(record.get("officialSourceUrl") or "")]
    for key in ("factSources", "museSources", "officialSources"):
        for row in _list(record.get(key)):
            urls.append(str(row.get("url") if isinstance(row, dict) else row))
    return [u for u in urls if u]


def need_d(record: dict) -> str | None:
    if record.get("pressReport") is True and not record.get("officialSourceUrl"):
        return "報道だけが出典（公式の発表のリンクが無い）"
    if any(official_url(u) for u in source_urls(record)):
        return None
    if record.get("videoUrl") and not record.get("sourceUrl"):
        return "動画だけが出典（公式の文章のリンクが無い）"
    return "公式の出典のリンクが無い"


def check(record: dict) -> dict:
    """{"applies": bool, "kind": 種類, "missing": ["a", ...], "notes": {点: 理由}}"""
    kind = record_kind(record)
    notes: dict[str, str] = {}
    if applies(record):
        for key, fn in (("a", need_a), ("b", need_b), ("c", need_c), ("d", need_d)):
            if problem := fn(record):
                notes[key] = problem
    return {"applies": applies(record), "kind": kind, "missing": sorted(notes), "notes": notes}


def summary_line(result: dict) -> str:
    if not result["applies"]:
        return f"あなたの数字の門: 対象外（{result['kind'] or '軸の外'}）"
    if not result["missing"]:
        return "あなたの数字の門: 4つともあり"
    return "あなたの数字の門: 足りない " + " / ".join(f"{k}.{result['notes'][k][:50]}" for k in result["missing"])


# --------------------------------------------------------------------------- #
# 手直し（プログラムで足せるもの → 1回だけ LLM）
# --------------------------------------------------------------------------- #
def calculator_line(kind: str) -> str:
    href, title, _ = CALCULATORS[kind]
    return f"自分の家の場合の額は、[{title}]({href})で確かめられます。"


def _first_h2(body: str) -> int:
    m = re.search(r"(?m)^##\s", body)
    return m.start() if m else -1


def insert_near_top(body: str, block: str) -> str:
    """本文の最初の段落のあと（最初の章の見出しの前）に足す"""
    pos = _first_h2(body)
    if pos <= 0:
        parts = re.split(r"\n\s*\n", body.strip(), maxsplit=1)
        return parts[0] + "\n\n" + block.strip() + ("\n\n" + parts[1] if len(parts) > 1 else "") + "\n"
    return body[:pos].rstrip() + "\n\n" + block.strip() + "\n\n" + body[pos:]


def insert_before_view(body: str, block: str) -> str:
    import own_view  # noqa: PLC0415

    anchor = own_view.VIEW_HEADING_RE.search(body)
    if anchor:
        return body[:anchor.start()].rstrip() + "\n\n" + block.strip() + "\n\n" + body[anchor.start():]
    return body.rstrip() + "\n\n" + block.strip() + "\n"


def fix_without_llm(record: dict) -> list[str]:
    """LLM を使わずに足せるもの: 計算ページの案内を前のほうに（a）。足したものの説明を返す"""
    notes = []
    kind = calculator_for(record)
    body = record.get("body") or ""
    if kind and need_a(record):
        href = CALCULATORS[kind][0]
        if href not in body or not _near_top(body, body.find(href)):
            record["body"] = insert_near_top(body, calculator_line(kind))
            notes.append(f"計算ページ（{href}）の案内を本文の前のほうに足した")
    return notes


REPAIR_SYSTEM = """あなたはニュースサイトのデスクです。読者が「自分の家はいくら・いつまで・何をするか」を記事だけで分かるように手直しします。
使ってよい事実は、元の資料（公式の発表）・確認済みの文脈・いまの記事にあるものだけ。数字・日付・固有名詞・窓口・電話番号・URL を作りません。
出力は指定の JSON だけ。"""

HOWTO = {
    "a": ("「あなたの数字」を足す: 資料の数字だけで、読者が自分の場合を探せる早見の表（Markdown の表。世帯の形・年収・年齢・子どもの数・使用量・契約の種類などの行）"
          "か、式つきの計算の例（例: 月1万円×12か月＝12万円。「（サイソク編集部の計算）」と添える）を1つ。計算は資料の数字どうしの四則だけ。"
          "リコール・情報流出・障害の記事なら、自分が対象か確かめる方法（対象の型番・品番・ロット・製造の期間・対象の地域や会員・確認のページの URL）を表か箇条書きで。"
          "資料に人ごとの額の数字が無い制度なら、自分の額がどの書類・ページで分かるか（納付書・通知書・マイページ・ねんきんネットなど、資料にあるもの）を公式の URL と書く。"),
    "b": "期限・日付を書く: いつから・いつまで（申請の期限、支給日、使用分の期間、対象の製造期間など）を資料の表記どおりに。資料に期限が無いと書いてあるときだけ「期限はありません」と書く。",
    "c": ("窓口・手続きを書く: どこで（窓口・ページ・電話）・どうやって（必要なもの・手順）を、資料にある名前と URL で。手続きが要らないと資料で分かるときは「手続きは不要です」と書き、確かめる公式のページの URL を添える。"
          "報道・取材・講演の問い合わせ先は、読者の窓口として書かない。"),
}

REPAIR_PROMPT = """次の記事には、サイソクの「あなたの数字のニュース」の基準のうち、次のものが足りません。足りないものだけを足す差分を返してください（記事の全文は返さない）。
# 足りないものと足し方
{howto}

# 守ること
- 元の資料と確認済みの文脈に材料が無いものは足さない（作らない。その欄は空のままにする）。とくに数字・日付・電話番号・URL は資料にあるものだけ。
- 直さない文は1字も変えない。「## サイソクの見方」の章には手を付けない。
- 足す章の見出しは中身の言葉にする（例「## 3歳未満の子がいる家は、12月に月1万5千円×2か月分」「## 申請は市区町村の窓口で、2月27日まで」）。「あなたの数字」「早見表」「まとめ」のような型の見出しにしない。
- 平易な、落ち着いた です・ます調。縦の区切りの記号（全角の縦線）、矢印の記号、太字の記号（**）は使わない。
# 出力（足さない欄は空の文字列・空の配列）
- number_markdown: a の章（「## 見出し」から始め、表か計算の例か確かめ方）。本文の最初の段落のすぐあとに入る
- desk_markdown: b・c の章（「## 見出し」から始め、期限と窓口・手続き・公式の URL）。「サイソクの見方」の章の前に入る
- replacements: 今の本文の文をそのまま before に写し、直した文を after に書く（日付を足すなど。ほかは使わない）

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
        "number_markdown": {"type": "STRING"},
        "desk_markdown": {"type": "STRING"},
        "replacements": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"before": {"type": "STRING"}, "after": {"type": "STRING"}},
                                                    "required": ["before", "after"]}},
    },
    "required": ["number_markdown", "desk_markdown", "replacements"],
}

BAD_MARK_RE = re.compile("\\*\\*|\\uff5c|\\u2192|\\u3056\\u3063\\u304f\\u308a")  # 太字・縦の区切り・矢印・使わない言葉


def _clean(text: str) -> str:
    text = re.sub(r"^#(?!#)\s*", "## ", str(text or "").strip(), flags=re.M)
    return BAD_MARK_RE.sub(lambda m: "" if m.group(0) == "**" else ("、" if m.group(0) == "→" else "　"), text)


def apply_patch(body: str, data: dict) -> tuple[str, list[str]]:
    import own_view  # noqa: PLC0415

    skipped: list[str] = []
    new = body
    for row in data.get("replacements") or []:
        old, rep = str((row or {}).get("before") or "").strip(), _clean((row or {}).get("after") or "")
        if not old or old == rep:
            continue
        if new.count(old) != 1 or own_view.view_section(new).find(old) >= 0:
            skipped.append(f"置き換えの元の文が本文に1つだけ無い（「{old[:24]}」）")
            continue
        new = new.replace(old, rep, 1)
    for key, place in (("number_markdown", insert_near_top), ("desk_markdown", insert_before_view)):
        block = _clean(data.get(key) or "")
        if not block:
            continue
        if not block.startswith("## "):
            skipped.append(f"{key} が見出しから始まっていない")
            continue
        new = place(new, block)
    return re.sub(r"\n{3,}", "\n\n", new).strip() + "\n", skipped


def links_block(page: dict | None, limit: int = 20) -> str:
    """元の資料の本文の中のリンク（窓口・申請のページ）。事実確認と手直しに渡し、記事に書いてよい URL にする"""
    rows = []
    for link in _list((page or {}).get("links")):
        if isinstance(link, dict) and link.get("main") and str(link.get("url") or "").startswith("http") and official_url(str(link["url"])):
            rows.append(f"- {str(link.get('text') or '').strip()[:40]}: {link['url']}")
        if len(rows) >= limit:
            break
    return ("\n\n[元の資料の本文の中のリンク]\n" + "\n".join(rows)) if rows else ""


def new_urls(new: str, *known: str) -> set[str]:
    """手直しで出てきた、資料・文脈・今の記事に無い URL（作った URL は使わない）"""
    seen = {u.rstrip("/.,。") for text in known for u in URL_RE.findall(text or "")}
    # 知っている URL のサイトのトップ（https://www.mhlw.go.jp のように、知っている URL の頭の部分）はよい
    return {u for u in {x.rstrip("/.,。") for x in URL_RE.findall(new or "")} - seen
            if not any(k.startswith(u + "/") for k in seen)}


def ensure(record: dict, source_text: str, context: str = "", *, urgent: bool = False, log=print, generate=None) -> dict:
    """点検して、足りないものがあれば足す（record をその場で書き換える）。まずプログラムで（計算ページの案内）、
    それでも a・b・c が足りなければ1回だけ LLM で（公式の資料の事実だけ。数字・URL を作っていないか確かめる）。
    急ぐ記事（速報・災害）は LLM を使わない（あとで直す印 yourNumber.repairLater）。結果は record["yourNumber"] に残す"""
    before = check(record)
    notes: list[str] = []
    if not before["applies"] or generate == "skip":
        return before  # "skip"＝テストで8つの基準の手直しだけを試すとき（記事を書き換えない）
    if before["missing"]:
        notes += fix_without_llm(record)
    mid = check(record)
    todo = [k for k in mid["missing"] if k in HOWTO]
    urgent = urgent or urgent_record(record)
    repaired = bool(notes)
    if todo and not urgent and generate != "skip":
        if generate is None:
            import llm  # noqa: PLC0415

            generate = llm.generate_json
        body = record.get("body") or ""
        howto = "\n".join(f"{k}. {REQUIREMENTS[k]}（いま: {mid['notes'][k][:80]}）\n   {HOWTO[k]}" for k in todo)
        ctx = f"\n# 確認済みの文脈（事実の束・計算済みの数字・過去記事）\n<<<\n{context[:8000]}\n>>>\n" if (context or "").strip() else ""
        prompt = REPAIR_PROMPT.format(howto=howto, source=(source_text or "")[:14000], context=ctx, title=record.get("title", ""),
                                      lede=record.get("lede", ""), body=body)
        try:
            # 救済の段（repair）: 月の予算から使う。OpenAI が先の設定なら GPT のクレジットで（scripts/llm.py の provider_order）
            data, model = generate(REPAIR_SYSTEM, prompt, REPAIR_SCHEMA, temperature=0.2, max_output_tokens=6000, tier="quality", purpose="repair")
            new_body, skipped = apply_patch(body, data)
            notes += [f"差分を当てなかった: {x}" for x in skipped[:2]]
            import quality_bar  # noqa: PLC0415

            added_nums = quality_bar.new_numbers(new_body, body, record.get("lede") or "", source_text, context)
            added_urls = new_urls(new_body, body, source_text, context)
            bad_calc = [c for c in quality_bar.calc_results(new_body)[1] if c not in quality_bar.calc_results(body)[1]]
            trial = check({**record, "body": new_body})
            if added_nums:
                notes.append(f"手直しに資料に無い数字が出たので使わない（{', '.join(sorted(added_nums)[:4])}・{model}）")
            elif added_urls:
                notes.append(f"手直しに資料に無い URL が出たので使わない（{', '.join(sorted(added_urls)[:2])}・{model}）")
            elif bad_calc:
                notes.append(f"手直しの計算が合わないので使わない（「{bad_calc[0][:40]}」・{model}）")
            elif len(trial["missing"]) >= len(mid["missing"]):
                notes.append(f"手直ししても足りないものが減らなかったので使わない（{trial['missing']}・{model}）")
            else:
                record["body"] = new_body
                repaired = True
                notes.append(f"足りないもの（{'・'.join(todo)}）を公式の資料の事実で足した（{model}）")
        except Exception as error:  # noqa: BLE001 - 直せなくても、このあとの hold_reason で決める
            notes.append(f"手直しに失敗（{str(error)[:100]}）")
    result = check(record)
    later = bool(urgent and result["missing"])
    record["yourNumber"] = {"kind": result["kind"], "missing": result["missing"], "before": before["missing"], "repaired": repaired,
                            "notes": {k: v[:120] for k, v in result["notes"].items()},
                            "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), **({"repairLater": True} if later else {})}
    for note in notes:
        log(f"   [num] {note}")
    log(f"   [num] {summary_line(result)}{'（速報なので出してから直す）' if later else ''}")
    return result


def hold_reason(record: dict, *, urgent: bool = False) -> str | None:
    """出さない理由（出してよいなら None）。軸の記事で、手直しのあとも4つのどれかが足りなければ出さない。速報・災害は止めない"""
    import os  # noqa: PLC0415

    result = check(record)
    if not result["applies"] or not result["missing"] or urgent or urgent_record(record):
        return None
    reason = "あなたの数字の門に足りない（自動で手直ししても残った）: " + " / ".join(
        f"{k}.{REQUIREMENTS[k].split('（')[0]}（{result['notes'][k][:50]}）" for k in result["missing"])
    log_hold(record, reason, result)
    if os.environ.get("AXIS_CONTENT_GATE", "1") == "0":
        return None  # 止めるのをやめるとき（記録だけ残す）
    return reason


def log_hold(record: dict, reason: str, result: dict, path: Path | None = None) -> None:
    """保留した記事を残す（会議で読む。content/your_number_log.json の直近 LOG_KEEP 件）"""
    _append_log({"title": str(record.get("title") or "")[:120], "slug": record.get("slug"), "sourceUrl": record.get("sourceUrl"),
                 "kind": result.get("kind"), "missing": result.get("missing"), "reason": reason[:300]}, path or LOG_PATH)


# --------------------------------------------------------------------------- #
# 書くときの決まり（プロンプト）
# --------------------------------------------------------------------------- #
PROMPT_RULE = """
# あなたの数字のニュース（2026-11-28 見直し。公開の前にプログラムが点検する）
サイソクは「何が変わったか」で終わらず、「あなたの家はいくら・いつまで・何をするか」まで答える。原稿は次の順に書く:
1. 最初の3行（リードと本文の最初の段落）で読者の答え: だれが対象か・いくら（どのくらい）・いつまで（いつから）・何をすればよいか。
2. そのすぐあとに「あなたの数字」: 資料の数字だけで、読者が自分の場合を探せる早見の表（世帯の形・年収・年齢・子どもの数・使用量・契約の種類などの行）か、
   式つきの計算の例（「（サイソク編集部の計算）」と添える）。リコール・情報流出・障害なら、自分が対象か確かめる方法（型番・ロット・期間・対象の会員・確認のページの URL）。
3. そのあとに窓口と手続き: どこで（窓口・ページ・電話）・どうやって・期限を、資料にある名前と公式の URL で。手続きが要らないなら「手続きは不要です」と書く。
   期限が資料に無いときは、資料に「期限は無い」とあるときだけそう書く（推測しない）。
{calc}- 数字・日付・URL は資料にあるものだけ。無いものは書かない。
"""


def prompt_block(title: str = "") -> str:
    """記事を書くプロンプトに足す決まり。題名に合う計算ページがあれば、前のほうで案内するよう伝える"""
    kind = calculator_for({"title": title}) if title else None
    calc = (f"- この話題にはサイトの計算ページがある: 本文の最初の段落のあとに「{calculator_line(kind)}」の1文を入れる。\n" if kind else
            "- サイトの計算ページ（/tools/）に合う話題なら、本文の前のほうで案内する。\n")
    return PROMPT_RULE.format(calc=calc)


# --------------------------------------------------------------------------- #
# 試し（公開済みの記事にこの門を当てる）
# --------------------------------------------------------------------------- #
def _published(a: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(str(a.get("publishedAt") or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def measure(articles: list[dict], now: datetime, days: int = 3) -> dict:
    since = now - timedelta(days=days)
    rows = [a for a in articles if (t := _published(a)) and since <= t <= now and a.get("type") != "roundup"]
    out = {"articles": len(rows), "days": days, "topic": {}, "pass": 0, "fixable_no_llm": 0, "needs_llm": 0, "missing": {}, "examples": {}}
    for a in rows:
        kind = record_kind(a)
        out["topic"][kind or "off"] = out["topic"].get(kind or "off", 0) + 1
        if not applies(a):
            continue
        r = check(a)
        if not r["missing"]:
            out["pass"] += 1
            continue
        trial = json.loads(json.dumps(a, ensure_ascii=False))
        fix_without_llm(trial)
        r2 = check(trial)
        if not r2["missing"]:
            out["fixable_no_llm"] += 1
            continue
        out["needs_llm"] += 1
        for k in r2["missing"]:
            out["missing"][k] = out["missing"].get(k, 0) + 1
            out["examples"].setdefault(k, [])
            if len(out["examples"][k]) < 3:
                out["examples"][k].append({"slug": a.get("slug"), "why": r2["notes"][k]})
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--measure", action="store_true")
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--slug", default="")
    parser.add_argument("--titles", nargs="*")
    args = parser.parse_args()
    import quality_bar  # noqa: PLC0415

    articles = quality_bar.load_articles()
    if args.measure:
        print(json.dumps(measure(articles, datetime.now(timezone.utc), args.days), ensure_ascii=False, indent=2))
    for slug in [s for s in args.slug.split(",") if s]:
        a = next((x for x in articles if x.get("slug") == slug), None)
        print(f"{slug}: {summary_line(check(a)) if a else '記事が無い'}")
    for title in args.titles or []:
        print(f"{title}: {topic_kind(title) or '軸の外'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
