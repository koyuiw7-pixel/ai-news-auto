"""
A8.net の提携済みプログラム（.claude/a8_partnered.tsv）から、
affiliate_links.json（リンクと計測ピクセル）と content/offers.json（話題ごとのおすすめ枠）を更新する。

TSV は A8 の「参加中プログラム → 広告リンク作成」から取り出した1行1プログラム：
  programId, 名前, カテゴリ, 成果報酬, テキスト広告のa8mat, ピクセルのサーバー番号, アンカー文, バナーサイズ, バナーのサーバー番号, バナー(aid,wid,eno,mid,mc)

どの記事にどの商品を出すかは下の PARTNERS と TOPICS で決める（関係の薄い記事には出さない）。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TSV = ROOT / ".claude" / "a8_partnered.tsv"
LINKS = ROOT / "affiliate_links.json"
OFFERS = ROOT / "content" / "offers.json"

# programId → サイトでの見せ方。key は offers.json の partners のキー
PARTNERS: dict[str, dict] = {
    # レンタルサーバー・VPS（AIアプリやサイトを自分で公開する人向け）
    "s00000001642001": {"key": "xserver", "name": "エックスサーバー", "label": "国内シェアNo.1", "note": "WordPressもAIツールのサイトも、まずはここから。速さと安定性で定番のレンタルサーバー", "shop": "エックスサーバー公式"},
    "s00000001642013": {"key": "xserver-vps", "name": "XServer VPS", "label": "AIアプリを自分で動かす", "note": "Dify・n8n・Ollamaなどを自分専用に動かせるVPS。アプリのテンプレートから数クリックで導入", "shop": "XServer公式"},
    "s00000000018030": {"key": "conoha-vps", "name": "ConoHa VPS", "label": "時間課金で気軽に", "note": "使った時間だけ払える高速VPS。AIのお試し環境づくりに", "shop": "ConoHa公式"},
    "s00000025450001": {"key": "shin-server", "name": "シンレンタルサーバー", "label": "新世代の高速サーバー", "note": "最新の高速化技術を採り入れたエックスサーバー系の新ブランド", "shop": "シン・レンタルサーバー公式"},
    "s00000000404001": {"key": "lolipop", "name": "ロリポップ！", "label": "月額が安い", "note": "はじめてのブログやサイトに。低価格で始められるレンタルサーバー", "shop": "ロリポップ！公式"},
    "s00000001717001": {"key": "sakura", "name": "さくらのレンタルサーバ", "label": "老舗の安心感", "note": "利用件数48万件超。安定運用の老舗レンタルサーバー", "shop": "さくらインターネット公式"},
    "s00000001642019": {"key": "xserver-cloudpc", "name": "XServer クラウドPC", "label": "ブラウザからPCを使う", "note": "クラウド上のWindows PCに、どこからでもアクセスできる仮想デスクトップ", "shop": "XServer公式"},
    # PC・ミニPC・パーツ（ローカルAI・画像生成）
    "s00000027479001": {"key": "gmktec", "name": "GMKtec ミニPC", "label": "AI処理に強い小型PC", "note": "AI処理用のNPUを積んだミニPCも。机の上でローカルAIを試すなら", "shop": "GMKtec公式"},
    "s00000026462001": {"key": "minisforum", "name": "MINISFORUM ミニPC", "label": "高性能ミニPC", "note": "手のひらサイズでも高性能。ローカルLLMの入門機に人気", "shop": "MINISFORUM公式"},
    "s00000025652001": {"key": "mdl", "name": "MDL BTOゲーミングPC", "label": "GPU構成を選べる", "note": "画像生成やローカルLLM向けに、GPUから構成を選べるBTOパソコン", "shop": "MDL公式"},
    "s00000027812001": {"key": "silicon-power", "name": "シリコンパワー SSD・メモリ", "label": "メモリ増設で快適に", "note": "生成AIで足りなくなりがちなメモリとSSDを、メーカー直営で", "shop": "Silicon Power Direct"},
    "s00000019939001": {"key": "parallels", "name": "Parallels Desktop", "label": "MacでWindows", "note": "MacでWindows専用のAIツールも動かせる定番ソフト", "shop": "Parallels公式"},
    # 動画
    "s00000018520001": {"key": "video-editor", "name": "Movavi Video Editor", "label": "初心者でもプロ並み", "note": "AI機能つきの多機能動画編集ソフト。字幕やノイズ除去も自動で", "shop": "Movavi公式"},
    "s00000016141002": {"key": "bandicut", "name": "Bandicut", "label": "無劣化カット", "note": "撮った動画を劣化させずに、速く切って結合できるソフト", "shop": "Bandicam Company"},
    "s00000021455001": {"key": "movie-school", "name": "クリエイターズジャパン", "label": "最短1ヶ月で習得", "note": "動画編集を最短1ヶ月で仕事レベルまで学べるオンラインスクール", "shop": "クリエイターズジャパン"},
    "s00000021268001": {"key": "skillhacks", "name": "SkillHacks", "label": "動画で学ぶプログラミング", "note": "未経験からWebアプリを作れるまで。買い切りの動画講座", "shop": "SkillHacks公式"},
    # 文章・仕事効率化
    "s00000017376003": {"key": "bunken", "name": "文賢", "label": "AIで文章チェック", "note": "AIが誤字・敬語・読みやすさをチェック。ライター・広報の定番ツール", "shop": "ウェブライダー"},
    "s00000027324001": {"key": "doraverse", "name": "Doraverse", "label": "複数のAIを1つで", "note": "ChatGPT・Gemini・Claudeなど15以上のAIを1つの画面で使い分けられる", "shop": "Doraverse公式"},
    "s00000012624009": {"key": "coconala", "name": "ココナラ", "label": "プロに頼む", "note": "AIで作りきれない部分は、デザインや動画のプロに依頼できるスキルマーケット", "shop": "ココナラ"},
    # 英語・翻訳
    "s00000012026001": {"key": "idiy", "name": "英語添削アイディー", "label": "AI＋講師が添削", "note": "AIと500人以上の講師が英作文を添削。英検・IELTS対策にも", "shop": "アイディー公式"},
    "s00000015388006": {"key": "studysapuri-en", "name": "スタディサプリENGLISH", "label": "スマホで毎日", "note": "日常英会話をスマホのレッスンで。AIの発音チェック付き", "shop": "スタディサプリ"},
    "s00000020682003": {"key": "lancul", "name": "LanCul（ランカル）", "label": "月額1,100円から", "note": "話し放題のオンライン英会話。AI翻訳の次は、自分で話せるように", "shop": "LanCul公式"},
    "s00000013934001": {"key": "bestteacher", "name": "ベストティーチャー", "label": "書いて話す英会話", "note": "自分で書いた英文をもとに話す、ライティング起点のオンライン英会話", "shop": "ベストティーチャー公式"},
    "s00000018721001": {"key": "sparta", "name": "スパルタ英会話", "label": "3ヶ月で短期集中", "note": "マンツーマンで会話量を徹底的に増やす、短期集中型の英会話スクール", "shop": "スパルタ英会話"},
    # セキュリティ
    "s00000016371001": {"key": "norton", "name": "ノートン 360", "label": "定番のセキュリティ", "note": "AIを使った詐欺やフィッシングから、PCとスマホをまとめて守る", "shop": "ノートン公式"},
    "s00000015315001": {"key": "virusbuster", "name": "ウイルスバスター クラウド", "label": "販売本数No.1", "note": "詐欺サイトや偽メールをAIで見分けて警告。国内で定番の総合セキュリティ", "shop": "トレンドマイクロ公式"},
    "s00000005993007": {"key": "eset", "name": "ESET HOME セキュリティ", "label": "軽くて強い", "note": "動作が軽いのに検出力が高い総合セキュリティソフト", "shop": "ESET公式"},
    "s00000021488002": {"key": "surfshark", "name": "Surfshark", "label": "軽いウイルス対策", "note": "マルウェアや危険なサイトからPC・スマホを守る、動作の軽いウイルス対策ソフト", "shop": "Surfshark公式"},
    # ガジェット
    "s00000026776002": {"key": "ringconn", "name": "RingConn スマートリング", "label": "AIで睡眠分析", "note": "重さ約2gのリングで、睡眠や心拍をAIが分析。月額料金なし", "shop": "RingConn公式"},
    "s00000024072001": {"key": "e-earphone", "name": "e☆イヤホン", "label": "イヤホン専門店", "note": "AI翻訳イヤホンやノイキャンなど、最新イヤホンを専門店で比較", "shop": "e☆イヤホン"},
    # 子どもの学び
    "s00000018613001": {"key": "digitane", "name": "デジタネ", "label": "小中学生のAI教材", "note": "マイクラなどゲーム感覚で、AIとプログラミングを家で学べる", "shop": "デジタネ公式"},
    "s00000019385001": {"key": "litalico", "name": "LITALICOワンダー", "label": "ITものづくり教室", "note": "ロボットやプログラミングで、子どもの「作る力」を伸ばす教室", "shop": "LITALICOワンダー"},
}

# 新しい話題（記事のタイトル・タグに一致したら、その話題の商品を出す）
NEW_TOPICS = [
    {"key": "server", "match": "Dify|n8n|セルフホスト|VPS|レンタルサーバー|WordPress|デプロイ|ホスティング|Docker", "eyebrow": "この記事の技術を試すなら", "headline": "AIアプリを自分で動かすなら、サーバーから", "lead": "DifyやOllamaなどを自分専用に動かすなら、VPSが近道です。", "partners": ["xserver-vps", "conoha-vps", "xserver"], "search": ["サーバー 構築 入門", "Docker 入門"], "require": "サーバ|Docker|Linux|クラウド|インフラ", "fill": ["coding", "agent"]},
    {"key": "video", "match": "動画生成|動画編集|Sora|Veo|Runway|Kling|動画AI|ショート動画|YouTube|字幕", "eyebrow": "この記事の技術を試すなら", "headline": "AIで動画を作るなら、編集まで一気に", "lead": "生成した動画は、字幕やカットを足すと一気に使えるものになります。", "partners": ["video-editor", "movie-school", "bandicut"], "search": ["動画編集 入門", "動画生成AI"], "require": "動画|映像|YouTube", "fill": ["image", "business"]},
    {"key": "english", "match": "翻訳|英語|英会話|通訳|DeepL|多言語|リアルタイム翻訳|語学", "eyebrow": "AIで英語を伸ばすなら", "headline": "AI翻訳の次は、自分で話せるように", "lead": "AIで訳せる時代でも、自分で話せると仕事の幅が広がります。", "partners": ["idiy", "sparta", "studysapuri-en", "lancul"], "search": ["英語 学習 AI", "英会話 独学"], "require": "英語|英会話|翻訳", "fill": ["chatgpt", "business"]},
    {"key": "security", "match": "セキュリティ|詐欺|フィッシング|マルウェア|ディープフェイク|脆弱性|プライバシー|不正アクセス|ランサム|なりすまし", "eyebrow": "AI時代の自衛策", "headline": "AIを悪用した詐欺から、PCとスマホを守る", "lead": "偽メールや偽サイトはAIで見分けがつきにくくなっています。対策ソフトは入れておくのが安心です。", "partners": ["virusbuster", "norton", "eset", "surfshark"], "search": ["サイバーセキュリティ 入門", "情報セキュリティ"], "require": "セキュリティ|サイバー|ハッカー|情報漏", "fill": ["business"]},
    {"key": "gadget", "match": "スマートリング|ウェアラブル|イヤホン|スマートグラス|Pixel|iPhone|Galaxy|ヘルスケア|睡眠|AIデバイス|スマホ", "eyebrow": "AIガジェットを選ぶなら", "headline": "身につけるAIは、軽さと電池持ちで選ぶ", "lead": "毎日使うものほど、着けているのを忘れるくらいの軽さが大事です。", "partners": ["ringconn", "e-earphone", "plaud-notepin-s"], "search": ["ガジェット AI", "スマートウォッチ"], "require": "ガジェット|スマート|デバイス|AI", "fill": ["voice", "business"]},
    {"key": "kids", "match": "子ども|子供|小学生|中学生|高校生|学校|教師|先生|教育現場|宿題", "eyebrow": "子どもとAIの付き合い方", "headline": "AIを「使われる側」でなく「作る側」に", "lead": "ゲーム感覚でプログラミングに触れると、AIへの理解も自然に深まります。", "partners": ["digitane", "litalico"], "search": ["子ども プログラミング", "AI 教育"], "require": "子ども|こども|プログラミング|教育|AI", "fill": ["coding"]},
]

# 既存の話題に足す提携商品（先頭ほど優先）
ADD_TO_TOPIC = {
    "local": ["gmktec", "minisforum", "mdl", "silicon-power"],
    "semis": ["silicon-power", "mdl"],
    "image": ["mdl", "coconala"],
    "writing": ["bunken"],
    "business": ["doraverse", "coconala"],
    "chatgpt": ["doraverse"],
    "gemini": ["doraverse"],
    "claude": ["doraverse"],
    "coding": ["skillhacks", "xserver-vps"],
    "agent": ["xserver-vps", "doraverse"],
    "llm": ["xserver-vps", "minisforum"],
}


def main() -> int:
    rows = {}
    for line in TSV.read_text("utf-8").splitlines():
        f = line.split("\t")
        if len(f) < 10:
            continue
        rows[f[0]] = f

    links = json.loads(LINKS.read_text("utf-8"))
    offers = json.loads(OFFERS.read_text("utf-8"))
    existing_codes = {str(v.get("url", "")) for v in links.values() if isinstance(v, dict)}

    added = 0
    for pid, meta in PARTNERS.items():
        f = rows.get(pid)
        if not f:
            print(f"[skip] {pid} {meta['name']}: TSVに無い")
            continue
        code, px, bpx, bgt = f[4], f[5] or "13", f[8], f[9]
        url = f"https://px.a8.net/svt/ejp?a8mat={code}"
        program = meta["name"]
        if url not in existing_codes:
            links[program] = {
                "url": url,
                "pixel": f"https://www{px}.a8.net/0.gif?a8mat={code}",
                "label": meta["name"],
                "note": meta["note"],
                "aliases": [],
                "topics": [],
            }
        image = None
        if bpx and bgt:
            aid, wid, eno, mid, mc = bgt.split(",")
            image = f"https://www{bpx}.a8.net/svt/bgt?aid={aid}&wid={wid}&eno={eno}&mid={mid}&mc={mc}"
        offers["partners"][meta["key"]] = {
            "program": program,
            "name": meta["name"],
            "label": meta["label"],
            "note": meta["note"],
            "image": image,
            "link": url,
            "shop": meta["shop"],
        }
        added += 1

    keys = {t["key"] for t in offers["topics"]}
    for topic in NEW_TOPICS:
        if topic["key"] not in keys:
            offers["topics"].append(topic)
        else:
            for t in offers["topics"]:
                if t["key"] == topic["key"]:
                    t.update(topic)
    for key, extra in ADD_TO_TOPIC.items():
        for t in offers["topics"]:
            if t["key"] == key:
                t["partners"] = list(dict.fromkeys(t.get("partners", []) + extra))

    LINKS.write_text(json.dumps(links, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OFFERS.write_text(json.dumps(offers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[a8] {added}件の提携商品を反映、話題 {len(offers['topics'])}件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
