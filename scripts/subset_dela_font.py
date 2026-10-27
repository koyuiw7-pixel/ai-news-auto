"""
サイトのロゴ・見出し用の Dela Gothic One を、使う文字だけに絞った WOFF2 を作る（app/fonts.ts が読む）。

Google Fonts のまま読むと @font-face が 120 個以上になり、全ページで描画を止める CSS が約 30KB 増える。
Dela は「サイソク」のロゴと決まった見出しにしか使わないので、その文字・かな・英数字だけを入れる。

font-display クラスで新しい漢字を出すときは、下の KANJI に足してから実行する
（入っていない字は本文の Zen Kaku Gothic New で表示される）。

  pip install fonttools brotli
  python3 scripts/subset_dela_font.py
"""
from pathlib import Path

from fontTools import subset

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "fonts" / "DelaGothicOne-Regular.ttf"
OUT = ROOT / "app" / "_fonts" / "dela-gothic-one-subset.woff2"

# いま font-display で出している漢字（RailRanking の見出し、compare の「迷ったらこれ」など）
KANJI = "今日話題深知選迷"

options = subset.Options()
options.flavor = "woff2"
options.layout_features = ["*"]
options.name_IDs = ["*"]
font = subset.load_font(str(SRC), options)
subsetter = subset.Subsetter(options)
subsetter.populate(
    text=KANJI,
    # 英数字・ひらがな・カタカナ
    unicodes=[*range(0x20, 0x7F), *range(0x3040, 0x3100)],
)
subsetter.subset(font)
OUT.parent.mkdir(parents=True, exist_ok=True)
subset.save_font(font, str(OUT), options)
print(f"{OUT.relative_to(ROOT)}: {OUT.stat().st_size} bytes")
