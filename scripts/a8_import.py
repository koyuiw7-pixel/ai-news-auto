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
    "s00000001642001": {"key": "xserver", "name": "エックスサーバー", "label": "WordPressでサイト運営", "note": "WordPressを使ったサイトの運営を検討する人向け。料金と契約条件を確認できます。", "shop": "エックスサーバー公式"},
    "s00000001642013": {"key": "xserver-vps", "name": "XServer VPS", "label": "AIアプリを自分で動かす", "note": "Difyなどを自分で運用したい人向けのVPS。対応環境と費用を確認。", "shop": "XServer公式"},
    "s00000000018030": {"key": "conoha-vps", "name": "ConoHa VPS", "label": "サーバーを借りる", "note": "AIアプリなどを動かすVPS。プランごとの料金・条件を確認。", "shop": "ConoHa公式"},
    "s00000025450001": {"key": "shin-server", "name": "シンレンタルサーバー", "label": "新世代の高速サーバー", "note": "最新の高速化技術を採り入れたエックスサーバー系の新ブランド", "shop": "シン・レンタルサーバー公式"},
    "s00000000404001": {"key": "lolipop", "name": "ロリポップ！", "label": "月額が安い", "note": "はじめてのブログやサイトに。低価格で始められるレンタルサーバー", "shop": "ロリポップ！公式"},
    "s00000001717001": {"key": "sakura", "name": "さくらのレンタルサーバ", "label": "Webサイトを運営", "note": "サイト運営向けのレンタルサーバー。プランと費用を確認できます。", "shop": "さくらインターネット公式"},
    "s00000001642019": {"key": "xserver-cloudpc", "name": "XServer クラウドPC", "label": "ブラウザからPCを使う", "note": "クラウド上のWindows PCに、どこからでもアクセスできる仮想デスクトップ", "shop": "XServer公式"},
    # PC・ミニPC・パーツ（ローカルAI・画像生成）
    "s00000027479001": {"key": "gmktec", "name": "GMKtec ミニPC", "label": "小型PCを選ぶ", "note": "小型PCの選択肢。使いたいAIの動作要件と製品の構成を確認。", "shop": "GMKtec公式"},
    "s00000026462001": {"key": "minisforum", "name": "MINISFORUM ミニPC", "label": "小型PCを選ぶ", "note": "小型PCの選択肢。使いたいAIの動作要件と製品の構成を確認。", "shop": "MINISFORUM公式"},
    "s00000025652001": {"key": "mdl", "name": "MDL BTOゲーミングPC", "label": "GPU構成を選べる", "note": "画像生成やローカルLLM向けに、GPUから構成を選べるBTOパソコン", "shop": "MDL公式"},
    "s00000027812001": {"key": "silicon-power", "name": "シリコンパワー SSD・メモリ", "label": "SSD・メモリを選ぶ", "note": "容量や接続規格を確かめ、使っているPCに対応するSSD・メモリを選べます。", "shop": "Silicon Power Direct"},
    "s00000019939001": {"key": "parallels", "name": "Parallels Desktop", "label": "MacでWindowsを利用", "note": "Mac上でWindowsを利用するソフト。アプリの互換性と別途必要な費用を確認。", "shop": "Parallels公式"},
    # 動画
    "s00000018520001": {"key": "video-editor", "name": "Movavi Video Editor", "label": "動画編集を始めたい人へ", "note": "動画のカットや字幕付けなどを行う編集ソフト。対応機能と料金を確認できます。", "shop": "Movavi公式"},
    "s00000016141002": {"key": "bandicut", "name": "Bandicut", "label": "無劣化カット", "note": "撮った動画を劣化させずに、速く切って結合できるソフト", "shop": "Bandicam Company"},
    "s00000021455001": {"key": "movie-school", "name": "クリエイターズジャパン", "label": "動画編集を学ぶ", "note": "動画編集のオンライン講座。講座内容や費用を確認できます。", "shop": "クリエイターズジャパン"},
    "s00000021268001": {"key": "skillhacks", "name": "SkillHacks", "label": "動画で学ぶプログラミング", "note": "未経験からWebアプリを作れるまで。買い切りの動画講座", "shop": "SkillHacks公式"},
    # 文章・仕事効率化
    "s00000017376003": {"key": "bunken", "name": "文賢", "label": "文章を見直す", "note": "文章の推敲や校閲を支援するツール。機能と料金を確認できます。", "shop": "ウェブライダー"},
    "s00000027324001": {"key": "doraverse", "name": "Doraverse", "label": "複数のAIをまとめて", "note": "複数のAIモデルを選べる別サービス。利用できる機能や料金はプランによります。", "shop": "Doraverse公式"},
    "s00000012624009": {"key": "coconala", "name": "ココナラ", "label": "プロに頼む", "note": "AIで作りきれない部分は、デザインや動画のプロに依頼できるスキルマーケット", "shop": "ココナラ"},
    # 英語・翻訳
    "s00000012026001": {"key": "idiy", "name": "英語添削アイディー", "label": "英作文を添削", "note": "英作文の添削サービス。利用できる添削方法と料金を確認。", "shop": "アイディー公式"},
    "s00000015388006": {"key": "studysapuri-en", "name": "スタディサプリENGLISH", "label": "スマホで毎日", "note": "日常英会話をスマホのレッスンで。AIの発音チェック付き", "shop": "スタディサプリ"},
    "s00000020682003": {"key": "lancul", "name": "LanCul（ランカル）", "label": "英会話の機会を探す", "note": "英会話のサービス。利用できる形式・料金・条件を確認できます。", "shop": "LanCul公式"},
    "s00000013934001": {"key": "bestteacher", "name": "ベストティーチャー", "label": "書いて話す英会話", "note": "自分で書いた英文をもとに話す、ライティング起点のオンライン英会話", "shop": "ベストティーチャー公式"},
    "s00000018721001": {"key": "sparta", "name": "スパルタ英会話", "label": "3ヶ月で短期集中", "note": "マンツーマンで会話量を徹底的に増やす、短期集中型の英会話スクール", "shop": "スパルタ英会話"},
    # セキュリティ
    "s00000016371001": {"key": "norton", "name": "ノートン 360", "label": "端末の安全対策", "note": "PCやスマホ向けのセキュリティ製品。機能と対象端末はプランで確認。", "shop": "ノートン公式"},
    "s00000015315001": {"key": "virusbuster", "name": "ウイルスバスター クラウド", "label": "端末のセキュリティ対策", "note": "パソコンやスマホのセキュリティ対策を検討する人向け。対応端末と料金を確認できます。", "shop": "トレンドマイクロ公式"},
    "s00000005993007": {"key": "eset", "name": "ESET HOME セキュリティ", "label": "セキュリティを検討", "note": "端末向けセキュリティ製品。対応端末とプランを確認できます。", "shop": "ESET公式"},
    "s00000021488002": {"key": "surfshark", "name": "Surfshark", "label": "ネット利用の安全対策", "note": "VPNなどを提供するサービス。機能は契約プランにより異なります。", "shop": "Surfshark公式"},
    # ガジェット
    "s00000026776002": {"key": "ringconn", "name": "RingConn スマートリング", "label": "睡眠を記録するリング", "note": "睡眠や日々の体調管理に使うスマートリング。サイズと機能を確認。", "shop": "RingConn公式"},
    "s00000024072001": {"key": "e-earphone", "name": "e☆イヤホン", "label": "イヤホン専門店", "note": "AI翻訳イヤホンやノイキャンなど、最新イヤホンを専門店で比較", "shop": "e☆イヤホン"},
    # 子どもの学び
    "s00000018613001": {"key": "digitane", "name": "デジタネ", "label": "子どものプログラミング", "note": "ゲームなどを題材にプログラミングを学ぶ教材。対象年齢と内容を確認。", "shop": "デジタネ公式"},
    "s00000019385001": {"key": "litalico", "name": "LITALICOワンダー", "label": "ITものづくり教室", "note": "ロボットやプログラミングで、子どもの「作る力」を伸ばす教室", "shop": "LITALICOワンダー"},
    # 2026-10-27 追加
    "s00000026713001": {"key": "coloso", "name": "Coloso", "label": "プロに学ぶ講座", "note": "イラスト・3D・映像など、第一線のクリエイターが教えるオンライン講座", "shop": "Coloso公式"},
    "s00000008659009": {"key": "gomcam", "name": "GOM Cam", "label": "画面録画ソフト", "note": "パソコン画面の録画と簡単な編集ができる。操作説明やAIツールの解説動画づくりに", "shop": "GOM＆Company"},
    "s00000027820001": {"key": "aio-diagnosis", "name": "AIO診断サービス", "label": "AI検索での見え方を調べる", "note": "AI検索における自社の見え方を調べるサービス。内容と利用条件を確認できます。", "shop": "ドットアンドノード"},
    "s00000001418002": {"key": "office-english", "name": "6週間チャレンジ オフィス英会話", "label": "仕事の英会話に絞る", "note": "会議や電話など、仕事で使う英語のフレーズを6週間で練習する教材", "shop": "IQ-Strategy"},
    "s00000018318001": {"key": "matsui", "name": "松井証券", "label": "老舗のネット証券", "note": "株式・投資信託・NISAに対応した、創業100年超の証券会社", "shop": "松井証券公式"},
    "s00000008903007": {"key": "dmm-kabu", "name": "DMM 株", "label": "アプリで取引", "note": "日本株・米国株・NISAをアプリで取引できる。取引でポイントもたまる", "shop": "DMM.com証券"},
    # 2026-10-29 追加：通信回線（光回線・WiMAX・ホームWi-Fi）。BIGLOBE は公式サイトの素材NG（A8の素材のみ使う）
    "s00000000018040": {"key": "gmo-hikari", "name": "GMOとくとくBB光", "label": "縛りなしの光回線", "note": "契約期間の縛りがない光回線。今のフレッツ光やドコモ光からの乗り換え（転用・事業者変更）もWebで完結", "shop": "GMOとくとくBB"},
    "s00000000040016": {"key": "biglobe-hikari", "name": "BIGLOBE光", "label": "1ギガも10ギガも", "note": "1ギガと10ギガから選べる光回線。auやUQ mobileのスマホとまとめると割引あり", "shop": "BIGLOBE"},
    "s00000000018021": {"key": "gmo-wimax", "name": "GMOとくとくBB WiMAX", "label": "持ち歩けるWi-Fi", "note": "工事なしで使えるWiMAX +5G。家でも外出先でも、ノートPCやタブレットをすぐネットにつなげる", "shop": "GMOとくとくBB"},
    "s00000000040014": {"key": "biglobe-wimax", "name": "BIGLOBE WiMAX +5G", "label": "端末つきで始める", "note": "データ端末つきで申し込めるWiMAX +5G。工事不要で、届いたその日から使える", "shop": "BIGLOBE"},
    "s00000000018046": {"key": "gmo-home-wifi", "name": "GMOとくとくBB ホームWi-Fi", "label": "工事不要の家Wi-Fi", "note": "コンセントに挿すだけで使える置き型Wi-Fi。光回線の工事ができない部屋や、引っ越し直後に", "shop": "GMOとくとくBB"},
    # 2026-11-08 追加：暮らしの手続き・備え（記事の「すぐにできること」のそばに出す。下の ACTION_ADS）。
    # TSV に無いものは A8 の「広告リンク作成」で取った素材を a8 に持つ（テキストのa8mat, ピクセルのサーバー番号, アンカー文, バナーサイズ, バナーのサーバー番号, バナー）
    "s00000025743001": {"key": "furusato-honpo", "name": "ふるさと本舗", "label": "ふるさと納税サイト", "note": "全国の特産品を返礼品として選べるふるさと納税サイト。", "shop": "ふるさと本舗公式",
                        "a8": ["4BGGBL+BZNACY+5IMU+5YRHE", "19", "ふるさと本舗", "300×250", "21", "261108129725,001,01,s00000025743001012000,1"]},
    "s00000023934001": {"key": "aupay-furusato", "name": "au PAY ふるさと納税", "label": "ふるさと納税", "note": "返礼品を探して寄付できるふるさと納税サイト。", "shop": "au PAY ふるさと納税公式",
                        "a8": ["4BGCEZ+3DGG6Q+54OC+5ZMCH", "13", "au PAY ふるさと納税", "300×250", "26", "261103067204,001,01,s00000023934001006000,1"]},
    "s00000020080001": {"key": "elpio", "name": "エルピオでんき", "label": "電気の契約先を見直す", "note": "家庭向けの電気の契約先を切り替えられる電力会社。料金プランと対象エリアは公式サイトで確認できます。", "shop": "エルピオでんき公式",
                        "a8": ["4BGGBL+C9RNN6+4AXS+5Z6WY", "19", "エルピオでんき", "300×250", "26", "261108129742,001,01,s00000020080001010000,1"]},
    "s00000025626001": {"key": "akamaru-bousai", "name": "あかまる防災 防災グッズ44点セット", "label": "防災グッズのセット", "note": "防災士が監修した44点入りの防災セット。中身と価格は公式サイトで確認できます。", "shop": "あかまる防災公式",
                        "a8": ["4BGGBL+CI3Q42+5HQC+5YJRM", "16", "防災士監修の防災グッズ44点セット", "300×250", "21", "261108129756,001,01,s00000025626001003000,1"]},
    "s00000027418001": {"key": "stoole", "name": "スツーレ", "label": "防災の備え", "note": "防災士が監修した備えの用品。内容とサイズは公式サイトで確認できます。", "shop": "スツーレ公式",
                        "a8": ["4BGGBL+B2B0HE+5VK4+5YRHE", "18", "スツーレ", "300×250", "23", "261108129669,001,01,s00000027418001003000,1"]},
    "s00000023371001": {"key": "alpha-foods", "name": "安心米（アルファー食品）", "label": "非常食・保存食", "note": "水やお湯を注いで食べられるご飯などの保存食。保存期間は商品ごとに確認できます。", "shop": "アルファー食品公式",
                        "a8": ["4BGGBL+CHIAIA+50BY+5YRHE", "18", "アルファー食品", "300×250", "22", "261108129755,001,01,s00000023371001022000,1"]},
    "s00000022499001": {"key": "bluetti", "name": "BLUETTI ポータブル電源", "label": "停電に備える電源", "note": "コンセントが使える大容量のポータブル電源。容量と出力は製品ごとに確認できます。", "shop": "BLUETTI JAPAN公式",
                        "a8": ["4BGGBL+CGBFAQ+4TLQ+5YRHE", "18", "BLUETTI JAPAN", "300×250", "29", "261108129753,001,01,s00000022499001082000,1"]},
    "s00000021712001": {"key": "jackery", "name": "Jackery ポータブル電源", "label": "停電に備える電源", "note": "アウトドアや防災に使える、コンセント付きのポータブル電源。容量は製品ごとに確認できます。", "shop": "Jackery Japan公式"},
    "s00000000979014": {"key": "bb-excite", "name": "BB.exciteモバイル", "label": "格安SIMを検討", "note": "スマホの料金を見直すときの格安SIM。料金プランと対応端末は公式サイトで確認できます。", "shop": "BB.excite公式",
                        "a8": ["4BGGBL+CO225U+7JY+2BD44I", "19", "格安SIMのBB.exciteモバイル", "300×250", "23", "261108129766,001,01,s00000000979014019000,1"]},
    "s00000017718057": {"key": "freee", "name": "freee会計", "label": "確定申告・会計", "note": "帳簿づけから確定申告の書類づくりまでできるクラウド会計ソフト。料金プランは公式サイトで確認できます。", "shop": "freee公式",
                        "a8": ["4BGGBL+CQFSKY+3SPO+9FDAJ6", "18", "freee会計", "300×250", "24", "261108129770,001,01,s00000017718057011000,1"]},
    "s00000021185002": {"key": "mf-kakutei", "name": "マネーフォワード クラウド確定申告", "label": "確定申告をラクに", "note": "銀行やカードの明細を取り込んで、帳簿づけから確定申告書の作成までできるクラウドソフト。副業・個人事業の申告に。", "shop": "マネーフォワード公式",
                        "a8": ["4BGCEY+GBMUUQ+4JGQ+BXYE9", "14", "マネーフォワード クラウド確定申告", "300×250", "26", "261103066987,001,01,s00000021185002006000,1"]},
    "s00000014765001": {"key": "yayoi-kakutei", "program": "弥生シリーズ", "name": "弥生のクラウド確定申告ソフト", "label": "個人事業主の確定申告", "note": "個人事業主・副業の人向けのクラウド確定申告ソフト（青色申告・白色申告）。", "shop": "弥生公式",
                        "a8": ["4BGCEZ+2QTZ76+35XE+6DZBM", "18", "弥生シリーズ", "", "", ""]},
    "s00000015110002": {"key": "epos", "name": "エポスカード", "label": "クレジットカード", "note": "丸井グループのクレジットカード。年会費やポイントの条件は公式サイトで確認できます。", "shop": "エポスカード公式",
                        "a8": ["4BGGBL+D2XWAA+38L8+BY641", "17", "エポスカード", "", "", ""]},
    "s00000004657003": {"key": "hikkoshi-samurai", "name": "引越し侍", "label": "引越しの見積もり", "note": "複数の引越し業者にまとめて見積もりを依頼できる比較サービス。", "shop": "引越し侍公式",
                        "a8": ["4BGGBL+D7PD4I+ZXM+HYNBM", "19", "引越し侍", "300×250", "20", "261108129799,001,01,s00000004657003059000,1"]},
    "s00000019543001": {"key": "sourcenext", "name": "ソースネクスト", "label": "パソコン用ソフト", "note": "PDF編集やセキュリティなどのパソコン用ソフトを扱う販売サイト。対応OSと価格は公式サイトで確認できます。", "shop": "ソースネクスト公式"},
    # 2026-11-08 夜の追加（すぐ提携できたもの）
    "s00000013511010": {"key": "enepi", "name": "エネピ", "label": "電気料金を比べる", "note": "住所や使用量をもとに、電力会社の料金プランを比べられる比較サービス。", "shop": "エネピ（じげん）",
                        "a8": ["4BGGBM+BWOVM+2W92+1NJK7M", "18", "エネピ", "300×250", "21", "261108130020,001,01,s00000013511010003000,1"]},
    "s00000010685001": {"key": "tainavi", "name": "タイナビ", "label": "太陽光・蓄電池の見積もり", "note": "太陽光発電や蓄電池の設置について、複数の業者に見積もりを依頼できるサービス。", "shop": "タイナビ公式",
                        "a8": ["4BGGBM+TRP0Y+2AG2+63H8I", "17", "【タイナビ】太陽光発電一括見積りナビゲーション", "300×250", "23", "261108130050,001,01,s00000010685001036000,1"]},
    "s00000000489041": {"key": "bang-kasai", "name": "保険スクエアbang！ 火災保険", "label": "火災保険を見直す", "note": "条件を入れて、複数の保険会社の火災保険の見積もりを比べられるサービス。", "shop": "保険スクエアbang！",
                        "a8": ["4BGGBM+M125U+3RU+6S3XQQ", "16", "火災保険の無料診断サービス", "300×250", "27", "261108130037,001,01,s00000000489041014000,1"]},
    "s00000007476001": {"key": "oken-water", "name": "オーケンウォーター", "label": "宅配の天然水", "note": "天然水を宅配で届けるウォーターサーバー。料金と配送エリアは公式サイトで確認できます。", "shop": "オーケンウォーター公式",
                        "a8": ["4BGGBL+GC8AGI+1LOO+5ZU2A", "13", "宅配天然水ならオーケンウォーター", "300×250", "25", "261108129988,001,01,s00000007476001106000,1"]},
    "s00000010789007": {"key": "frecious", "name": "every frecious（エブリィフレシャス）", "label": "浄水型ウォーターサーバー", "note": "水道水を入れて使う浄水型のウォーターサーバー。料金と設置条件は公式サイトで確認できます。", "shop": "FRECIOUS公式",
                        "a8": ["4BGGBM+EVUWI+2B8Y+15OK2A", "12", "every frecious", "300×250", "21", "261108130025,001,01,s00000010789007046000,1"]},
    "s00000000040018": {"key": "biglobe-hikari-plus", "name": "BIGLOBE光プラス by auひかりプラス", "label": "光回線を検討", "note": "BIGLOBEの光回線サービス。提供エリアと料金は公式サイトで確認できます。", "shop": "BIGLOBE",
                        "a8": ["4BGGBL+GFSW36+B4+2Z68LU", "12", "BIGLOBE光プラス by auひかりプラス", "300×250", "29", "261108129994,001,01,s00000000040018011000,1"]},
    "s00000005230001": {"key": "jalan", "name": "じゃらんnet", "label": "宿を探す", "note": "国内の宿泊施設を探して予約できる旅行サイト。", "shop": "じゃらんnet",
                        "a8": ["4BGGBM+HV0XE+14CS+64JTE", "18", "じゃらんnet", "300×250", "23", "261108130030,001,01,s00000005230001054000,1"]},
    "s00000000218001": {"key": "ikyu", "name": "一休.com", "label": "ホテル・旅館を予約", "note": "ホテルや旅館を探して予約できる宿泊予約サイト。", "shop": "一休.com",
                        "a8": ["4BGGBM+T69F6+1OK+5YRHE", "11", "一休.com", "300×250", "28", "261108130049,001,01,s00000000218001185000,1"]},
    "s00000023754001": {"key": "ohya", "name": "Oh!Ya（オーヤ）", "label": "面談をまとめて予約", "note": "不動産投資の会社との面談を、まとめて比較・予約できるサービス", "shop": "セレス"},
}

# 新しい話題（記事のタイトル・タグに一致したら、その話題の商品を出す）
NEW_TOPICS = [
    {"key": "server", "match": "Dify|n8n|セルフホスト|VPS|レンタルサーバー|WordPress|デプロイ|ホスティング|Docker", "eyebrow": "この記事の技術を試すなら", "headline": "AIアプリを自分で動かすなら、サーバーから", "lead": "自分で運用する場合の選択肢です。無料で使える公式サービスと、必要な管理・料金を比較しましょう。", "partners": ["xserver-vps", "conoha-vps", "xserver"], "search": ["サーバー 構築 入門", "Docker 入門"], "require": "サーバ|Docker|Linux|クラウド|インフラ", "fill": ["coding", "agent"]},
    {"key": "video", "match": "動画生成|動画編集|Sora|Veo|Runway|Kling|動画AI|ショート動画|YouTube|字幕", "eyebrow": "この記事の技術を試すなら", "headline": "AIで動画を作るなら、編集まで一気に", "lead": "生成した動画は、字幕やカットを足すと一気に使えるものになります。", "partners": ["video-editor", "movie-school", "bandicut"], "search": ["動画編集 入門", "動画生成AI"], "require": "動画|映像|YouTube", "fill": ["image", "business"]},
    {"key": "english", "match": "翻訳|英語|英会話|通訳|DeepL|多言語|リアルタイム翻訳|語学", "eyebrow": "AIで英語を伸ばすなら", "headline": "AI翻訳の次は、自分で話せるように", "lead": "AIで訳せる時代でも、自分で話せると仕事の幅が広がります。", "partners": ["idiy", "sparta", "studysapuri-en", "lancul"], "search": ["英語 学習 AI", "英会話 独学"], "require": "英語|英会話|翻訳", "fill": ["chatgpt", "business"]},
    {"key": "security", "match": "セキュリティ|詐欺|フィッシング|マルウェア|ディープフェイク|脆弱性|プライバシー|不正アクセス|ランサム|なりすまし", "eyebrow": "AI時代の自衛策", "headline": "詐欺や不正アクセスから、PCとスマホを守る", "lead": "必要な対策は脅威や端末によって異なります。各サービスの対応範囲と条件を確認しましょう。", "partners": ["virusbuster", "norton", "eset", "surfshark"], "search": ["サイバーセキュリティ 入門", "情報セキュリティ"], "require": "セキュリティ|サイバー|ハッカー|情報漏", "fill": ["business"], "alsoMatch": "サイバー攻撃|攻撃者|侵入|ハッキング|情報漏え?い|サイバー(?!エージェント)|情報流出|漏洩|件流出|流出の恐れ|情報が流出|データが流出|個人情報|不正ログイン|不正利用|乗っ取り|不審メール|偽SMS|迷惑メール|偽サイト"},
    {"key": "telecom", "match": "光回線|ネット回線|インターネット回線|固定回線|回線速度|通信速度|通信障害|WiMAX|ポケットWi-?Fi|モバイルWi-?Fi|ホームルーター|置くだけWi-?Fi|Wi-?Fiルーター|Wi-?Fi ?7|格安SIM|楽天モバイル|ahamo|povo|LINEMO|UQ mobile|ワイモバイル|携帯キャリア|携帯料金|スマホ料金|通信料金|プロバイダ|テザリング|Starlink|スターリンク|10ギガ", "eyebrow": "ネット環境を見直すなら", "headline": "AIを快適に使うなら、まず回線から", "lead": "動画やクラウドのAIを毎日使うなら、速くて安定した回線がいちばん効きます。工事不要のWi-Fiという選び方もあります。", "partners": ["gmo-hikari", "biglobe-hikari", "gmo-home-wifi", "gmo-wimax", "biglobe-wimax"], "search": ["ネットワーク 入門", "通信 5G"], "require": "ネットワーク|通信|5G|回線|インターネット", "fill": ["gadget", "business"]},
    {"key": "telecom-gadget", "genre": "tech-gadget", "match": "光回線|ネット回線|インターネット回線|固定回線|回線速度|通信速度|通信障害|WiMAX|ポケットWi-?Fi|モバイルWi-?Fi|ホームルーター|置くだけWi-?Fi|Wi-?Fiルーター|Wi-?Fi ?7|格安SIM|楽天モバイル|ahamo|povo|LINEMO|UQ mobile|ワイモバイル|携帯キャリア|携帯料金|スマホ料金|通信料金|プロバイダ|テザリング|Starlink|スターリンク|10ギガ|5G回線|5G通信|モバイル通信", "eyebrow": "ネット環境を見直すなら", "headline": "スマホもPCも、つなぐ回線で快適さが変わる", "lead": "家の光回線か、工事不要のWi-Fiか。使い方に合う回線を選ぶと、毎日のストレスが減ります。", "partners": ["gmo-hikari", "biglobe-hikari", "gmo-home-wifi", "gmo-wimax", "biglobe-wimax"], "search": ["ネットワーク 入門", "通信 5G"], "require": "ネットワーク|通信|5G|回線|インターネット", "fill": ["gadget", "business"]},
    {"key": "gadget", "match": "スマートリング|ウェアラブル|イヤホン|スマートグラス|睡眠", "eyebrow": "AIガジェットを選ぶなら", "headline": "身につけるAIは、軽さと電池持ちで選ぶ", "lead": "毎日使うものほど、着けているのを忘れるくらいの軽さが大事です。", "partners": ["ringconn", "e-earphone", "plaud-notepin-s"], "search": ["ガジェット AI", "スマートウォッチ"], "require": "ガジェット|スマート|デバイス|AI", "fill": ["voice", "business"]},
    # 携帯会社の名前と、流出・障害・値上げ・料金・乗り換えの語が同じ欄（見出し・タグ・要約）に並ぶ記事だけ。契約先を見直す人向け。
    # 会社名だけの記事（新端末・社会貢献・法人向けの協業）や、決算・出資・AIの事業の記事には出さない
    {"key": "mobile-switch", "genres": ["business", "public", "lifestyle", "tech-gadget"], "min": 5, "match": "格安SIM|携帯料金|スマホ料金|通信料金|(?:NTTドコモ|ドコモ|docomo|ソフトバンク(?!グループ|G|・ビジョン)|楽天モバイル|ahamo|povo|LINEMO|UQ ?mobile|ワイモバイル|KDDI|携帯会社|携帯大手|携帯キャリア)(?=[\\s\\S]*?(?:情報流出|流出|漏えい|漏洩|不正アクセス|不正ログイン|通信障害|障害|不具合|つながりにくい|値上げ|料金|新プラン|乗り換え|MNP|解約))|(?:情報流出|流出|漏えい|漏洩|不正アクセス|不正ログイン|通信障害|障害|不具合|つながりにくい|値上げ|料金|新プラン|乗り換え|MNP|解約)(?=[\\s\\S]*?(?:NTTドコモ|ドコモ|docomo|ソフトバンク(?!グループ|G|・ビジョン)|楽天モバイル|ahamo|povo|LINEMO|UQ ?mobile|ワイモバイル|KDDI|携帯会社|携帯大手|携帯キャリア))", "articleExclude": "決算|業績|株価|出資|買収|上場|(?<![A-Za-z])AI(?![A-Za-z])|生成AI|半導体|ロボット|データセンター|基地局", "eyebrow": "スマホの契約を見直すなら", "headline": "スマホの回線は、乗り換えで料金と条件を比べられる", "lead": "流出や障害、値上げをきっかけに契約先を比べる人もいます。料金・条件・手続きは各公式サイトで確認しましょう。", "partners": ["bb-excite", "biglobe-hikari-plus"], "search": ["スマホ 料金 節約"], "require": "スマホ|携帯|通信|格安SIM", "name": "スマホ回線の見直し"},
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
    "video": ["gomcam", "coloso"],
    "image": ["coloso"],
    "english": ["office-english"],
    "business": ["aio-diagnosis"],
    "writing": ["aio-diagnosis"],
    "invest-stocks": ["dmm-kabu", "matsui"],
    "invest-nisa": ["matsui", "dmm-kabu"],
    "invest": ["matsui", "dmm-kabu"],
    "re-invest": ["ohya"],
    "furusato": ["furusato-honpo"],
    "tax-filing": ["freee"],
}

# 記事の「すぐにできること」（読者がこのあと取る行動）のすぐ下に出す、PR の囲み1つ（components/ActionAd.tsx）。
# 上から順に、見出し・タグ・要約で match が基準点を超えた最初の行を使う（lib/offers.ts の relevanceScore と同じ点数）。
# 見出しにも match の語があること（タグや要約だけで当てない）。まとめ記事と、見出しが exclude に当たる記事には出さない。genres があればそのジャンルの記事だけ（AI の業界ニュースに家計の広告を出さない）。
# 出すのは提携リンクのある商品だけ、最大 max 件。名前と1行の説明は PARTNERS（公式の名前と中立な説明）のまま
ACTION_ADS = [
    {"key": "leak", "title": "端末とアカウントの安全対策", "reason": "流出した情報を使った偽メール・偽SMSや、不正ログインへの備えに", "match": "情報流出|情報漏え?い|漏え?い|漏洩|件流出|流出の恐れ|が流出|不審メール|個人情報|不正アクセス|不正ログイン|不正利用|詐欺|フィッシング|なりすまし|ランサム|マルウェア|サイバー攻撃|乗っ取り", "partners": ["norton", "virusbuster", "eset"], "max": 2, "exclude": "ガードレール|AIガバナンス|脱獄|LLM"},
    {"key": "fire-insurance", "title": "火災保険を見直す", "reason": "保険料や補償の変更をきっかけに、今の契約と比べるために", "match": "火災保険|地震保険|水災補償|損害保険料", "partners": ["bang-kasai"], "max": 1, "genres": ["public", "lifestyle", "business", "tech-gadget", "real-estate", "investment"]},
    {"key": "water", "title": "飲み水の備え", "reason": "断水や災害で水道が止まったときの飲み水の備えに", "match": "断水|備蓄水|飲料水|給水|水道料金|水道代", "partners": ["oken-water", "frecious"], "max": 2, "genres": ["public", "lifestyle", "business", "tech-gadget", "real-estate", "investment"]},
    {"key": "disaster", "title": "停電・災害への備え", "reason": "停電・断水が続いたときの電源や食料の備えに", "match": "地震|津波|台風|大雨|豪雨|土砂災害|洪水|氾濫|噴火|停電|防災|避難|警報|大雪|線状降水帯|緊急地震速報|災害|備蓄", "partners": ["jackery", "bluetti", "akamaru-bousai", "alpha-foods", "stoole", "bang-kasai"], "max": 2},
    {"key": "furusato", "title": "ふるさと納税の寄附先を探す", "reason": "寄附先の返礼品と、控除の上限額を確かめるために", "match": "ふるさと納税|返礼品|ワンストップ特例", "partners": ["furusato-honpo", "aupay-furusato"], "max": 2, "genres": ["public", "lifestyle", "business", "tech-gadget", "real-estate", "investment"]},
    {"key": "tax", "title": "確定申告・年末調整の準備", "reason": "申告や年末調整の書類づくりを早めに進めるために", "match": "年末調整|確定申告|青色申告|白色申告|e-Tax|インボイス|源泉徴収|医療費控除|扶養控除|所得税", "partners": ["freee", "mf-kakutei", "yayoi-kakutei"], "max": 2, "genres": ["public", "lifestyle", "business", "tech-gadget", "real-estate", "investment"]},
    {"key": "energy", "title": "電気の契約を見直す", "reason": "電気・ガス代が上がるときに、契約先を比べるために", "match": "電気代|電気料金|電力料金|ガス代|ガス料金|電気・ガス|新電力|電力会社|燃料費調整|再エネ賦課金|節電", "partners": ["elpio", "enepi", "tainavi"], "max": 2, "genres": ["public", "lifestyle", "business", "tech-gadget", "real-estate", "investment"]},
    {"key": "moving", "title": "引越しの準備", "reason": "引越しの見積もりと、新居のネット回線の手配に", "match": "引っ越し|引越し|引越|転居|住所変更|転入届|転出届", "partners": ["hikkoshi-samurai", "biglobe-hikari-plus"], "max": 2, "genres": ["public", "lifestyle", "business", "tech-gadget", "real-estate", "investment"]},
    {"key": "mobile", "title": "スマホの回線を見直す", "reason": "障害や料金の変更をきっかけに、回線の契約を比べるために", "match": "携帯料金|スマホ料金|通信障害|通信の障害|つながりにくい|格安SIM|携帯キャリア|乗り換え|MNP|楽天モバイル|ahamo|povo|LINEMO|UQ mobile|ワイモバイル|料金プラン|光回線|ネット回線|固定回線", "partners": ["bb-excite", "biglobe-hikari-plus"], "max": 2, "genres": ["public", "lifestyle", "business", "tech-gadget", "real-estate", "investment"]},
    {"key": "travel", "title": "旅行の宿を探す", "reason": "連休や旅行の予定に合わせて、宿の空きと料金を比べるために", "match": "旅行|連休|ホテル|旅館|宿泊|観光|旅行支援", "partners": ["jalan", "ikyu"], "max": 2, "genres": ["public", "lifestyle", "business", "tech-gadget", "real-estate", "investment"], "exclude": "株価|決算|業績|訪日客数"},
    {"key": "household", "title": "家計の固定費を見直す", "reason": "値上げが続くときに、スマホ代や電気代の契約を比べるために", "match": "値上げ|値上がり|物価高|節約|固定費|生活費|家計の負担|家計を圧迫|家計防衛", "partners": ["bb-excite", "elpio", "enepi"], "max": 2, "genres": ["public", "lifestyle", "business", "tech-gadget", "real-estate", "investment"], "exclude": "株価|決算|業績|上場|時価総額|(?<![A-Za-z])AI(?![A-Za-z])|半導体|GPU|API|ユーロ|欧州|米国|中国|英国|景気|業況|GDP|統計|貯蓄率|消費支出"},
    {"key": "payment", "title": "支払い方法を見直す", "reason": "支払い方法やポイントの条件が変わるときに、カードを比べるために", "match": "キャッシュレス|クレジットカード|ポイント還元|ポイ活|QRコード決済|PayPay|楽天ペイ|d払い|au PAY|電子マネー|タッチ決済", "partners": ["epos"], "max": 1, "genres": ["public", "lifestyle", "business", "tech-gadget", "real-estate", "investment"]},
]


# 「すぐにできること」の話題（ACTION_ADS）を、右側・本文中・記事末の商品枠でも使う話題にする（キーは life-<key>）。
# 暮らしの記事（地震・電気代・引越しなど）で、商品枠がジャンルの既定の広告（会計ソフトなど）にならないようにする。
# 見出しだけの1語では当てない（基準点 5: 見出し＋タグ、またはタグ＋要約の複数語）
LIFE_GENRES = ["public", "lifestyle", "business", "tech-gadget", "real-estate", "investment", "science"]
# 枠の見出しを作る短い名前。既存の話題と同じ商品を扱うものは同じ名前にして、「ふるさと納税とふるさと納税の…」のように重ねない
LIFE_NAMES = {"leak": "セキュリティ対策", "furusato": "ふるさと納税", "tax": "確定申告・節税", "mobile": "スマホ回線の見直し"}


def life_topics() -> list[dict]:
    topics = []
    for rule in ACTION_ADS:
        topic = {
            "key": f"life-{rule['key']}",
            "genres": rule.get("genres", LIFE_GENRES),
            "min": 5,
            "match": rule["match"],
            "eyebrow": "この記事のあとにできること",
            "headline": rule["title"],
            "lead": f"{rule['reason']}。料金・条件は各公式サイトで確認してください。",
            "partners": rule["partners"],
            "name": LIFE_NAMES.get(rule["key"], rule["title"]),
        }
        if rule.get("exclude"):
            topic["articleExclude"] = rule["exclude"]
        topics.append(topic)
    return topics


def apply_life_topics(offers: dict) -> None:
    derived = life_topics()
    keys = {t["key"] for t in derived}
    offers["topics"] = [t for t in offers["topics"] if t["key"] not in keys] + derived


def apply_topics(offers: dict) -> None:
    """話題（NEW_TOPICS・ADD_TO_TOPIC）・行動欄そばの PR（ACTION_ADS）・暮らしの話題（life-*）を offers に反映する"""
    keys = {t["key"] for t in offers["topics"]}
    for topic in NEW_TOPICS:
        if topic["key"] not in keys:
            offers["topics"].append(topic)
        else:
            for t in offers["topics"]:
                if t["key"] == topic["key"]:
                    t.update(topic)
    # 上から順に照合するので、通信回線の話題は「スマホ」で当たるガジェットより前に置く
    order = [t["key"] for t in offers["topics"]]
    for key in ("telecom", "telecom-gadget"):
        if key in order and "gadget" in order and order.index(key) > order.index("gadget"):
            t = offers["topics"].pop(order.index(key))
            offers["topics"].insert([x["key"] for x in offers["topics"]].index("gadget"), t)
            order = [x["key"] for x in offers["topics"]]
    for key, extra in ADD_TO_TOPIC.items():
        for t in offers["topics"]:
            if t["key"] == key:
                t["partners"] = list(dict.fromkeys(t.get("partners", []) + extra))

    offers["actionAds"] = ACTION_ADS
    apply_life_topics(offers)


def main() -> int:
    rows = {}
    for line in (TSV.read_text("utf-8").splitlines() if TSV.exists() else []):
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
        if not f and meta.get("a8"):
            # TSV に無い提携は、A8 の「広告リンク作成」で取った素材（a8）から同じ形の行を作る
            f = [pid, meta["name"], "", "", *meta["a8"]]
        if not f:
            print(f"[skip] {pid} {meta['name']}: TSVに無い")
            continue
        code, px, bpx, bgt = f[4], f[5] or "13", f[8], f[9]
        url = f"https://px.a8.net/svt/ejp?a8mat={code}"
        program = meta.get("program", meta["name"])
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
            **offers["partners"].get(meta["key"], {}),
            # 選び方ガイド（lib/choose.ts）が提携済みかを programId で引く
            "programId": pid,
            "program": program,
            "name": meta["name"],
            "label": meta["label"],
            "note": meta["note"],
            "image": image,
            "link": url,
            "shop": meta["shop"],
        }
        added += 1

    apply_topics(offers)
    LINKS.write_text(json.dumps(links, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OFFERS.write_text(json.dumps(offers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[a8] {added}件の提携商品を反映、話題 {len(offers['topics'])}件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
