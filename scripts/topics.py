"""タイトル・本文からジャンルを判定するルール（API不要）.

無料枠では Gemini の呼び出し回数が貴重なので、機械的に判定できるものは
ここで処理して API を温存する。

- OFF_TOPIC: どのジャンルにも当てはまらない題材。動画を送る前に弾く。
- GENRE_SIGNALS: ジャンルの再分類に使う手がかり語。
"""

from __future__ import annotations

import re

# --------------------------------------------------------------------------- #
# 対象外の題材
#
# 楽待などの不動産チャンネルが美容・芸能・政治の企画動画を出すため、
# これらは Gemini に動画を投げる前にタイトルだけで落とす（無料枠の節約）。
# --------------------------------------------------------------------------- #

# 無条件で対象外。他にどんな語が含まれていても記事にしない。
# （例:「NISAは新しい信仰か…天皇制の本質」は NISA を含むが思想論であり対象外）
HARD_OFF_TOPIC_RE = re.compile(
    r"美容整形|整形依存|痩せ信仰|脱毛|エステ|コンプレックス産業|"
    r"カジノ|パチンコ|競馬|宝くじ|ギャンブル|"
    r"芸能|不倫|離婚|恋愛|婚活|占い|心霊|"
    r"市長選|知事選|衆院選|参院選|選挙戦|遊説|"
    r"天皇制|宗教|カルト|哲学対談|資本主義の病理|"
    r"食料安全保障|農業政策|米騒動|シンクタンク"
)

# 原則は対象外だが、本来の対象テーマが絡んでいれば救済する
# （例:「熱中症対策で賃貸をバリューアップ」は不動産の話）
SOFT_OFF_TOPIC_RE = re.compile(r"ダイエット|熱中症|サプリ|筋トレ|ジム通い|健康法")

RESCUE_RE = re.compile(
    r"賃貸|物件|大家|アパート|マンション|不動産|利回り|入居|リフォーム|"
    r"住宅ローン|地価|補助金|バリューアップ"
)


def is_off_topic(title: str, summary: str = "") -> bool:
    """どのジャンルにも属さない題材かどうかをタイトルから判定する。"""
    text = f"{title} {summary}"
    if HARD_OFF_TOPIC_RE.search(text):
        return True
    if SOFT_OFF_TOPIC_RE.search(text):
        return not RESCUE_RE.search(text)
    return False


# --------------------------------------------------------------------------- #
# ジャンル判定の手がかり語
# --------------------------------------------------------------------------- #

GENRE_SIGNALS: dict[str, list[str]] = {
    "investment": [
        r"株価|株安|株高|日経平均|個別銘柄|銘柄|決算|増配|配当",
        r"為替|円安|円高|ドル円|為替介入|FX|ロスカット|ナンピン",
        r"ビットコイン|暗号資産|仮想通貨",
        r"投資信託|オルカン|S&P500|インデックス投資|NISA|iDeCo|つみたて",
        r"米国株|新興国株|債券|ETF|REIT の分配|ポートフォリオ",
        r"保険|生命保険|医療保険|FP が|ファイナンシャルプランナー",
        r"高額療養費|年金|退職金|家計|節約|税制優遇",
        r"半導体アナリスト|証券.{0,4}(氏|アナリスト)|運用",
    ],
    "real-estate": [
        r"物件|賃貸|大家|入居者|空室|利回り|収益物件|一棟|区分",
        r"マンション|アパート|戸建て|新築|中古|内見|間取り",
        r"不動産|地価|路線価|相場|エリア|立地|再開発",
        r"住宅ローン|アパートローン|団信|フラット35",
        r"耐震|地盤|活断層|修繕|管理費|リフォーム|建築",
    ],
    "ai": [
        r"OpenAI|ChatGPT|GPT-|Gemini|Claude|Anthropic|DeepMind",
        r"NVIDIA|Hugging Face|LLM|生成AI|AIエージェント|推論モデル",
        r"TypeScript|Android|Azure|API|SDK|オープンソース|パラメータ",
        r"ロボティクス|ロボット|自動運転|半導体設計",
    ],
}

GENRE_RES = {
    slug: re.compile("|".join(patterns)) for slug, patterns in GENRE_SIGNALS.items()
}


def score_genres(text: str) -> dict[str, int]:
    """各ジャンルの手がかり語が何種類ヒットしたかを数える。"""
    scores = {}
    for slug, patterns in GENRE_SIGNALS.items():
        scores[slug] = sum(1 for p in patterns if re.search(p, text))
    return scores


def classify(title: str, description: str = "", body: str = "") -> tuple[str, dict[str, int]]:
    """(最有力ジャンルslug, 全ジャンルのスコア) を返す。

    本文は冒頭のみ見る。長文全体を見ると周辺話題の語を拾って精度が落ちるため。
    タイトルは2回数えて重み付けする。
    """
    text = f"{title}\n{title}\n{description}\n{body[:1500]}"
    scores = score_genres(text)
    best = max(scores, key=lambda k: scores[k])
    return (best if scores[best] > 0 else ""), scores
