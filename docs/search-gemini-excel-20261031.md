# Gemini Excelデモ記事の検索入口と信頼性（2026-10-31）

`content/articles/gemini-4-argon-excel-clone-demo.json` を編集。元動画・URL・公開日時・SNS文・広告設定は保持。記事のタイトルと説明で「Excelクローン」「デモ」「利用条件」を示し、動画の主張とGoogleの公式発表を分ける。既存の未根拠な競合比較、実務利用の断定、料金未発表・仮定のアクセス手順を除去。かんたん版も整合。2026-09-30時点のGoogle公表価格は予定と注記し、現在の提供・地域・料金は未確認と明示。動画の詳細操作や生成物の実行は独立再現していない。記事の旧版はgit履歴に残す。

根拠: https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-4-argon/ と https://www.youtube.com/watch?v=YMulO01LMBE （動画タイトルのみ確認。本文を独立再現していない）。公開とGoogle再取得、表示、クリック、収益を別々に判定。検索語・実績は非公開で保存。

動画記事は現行 `lib/indexing.ts` では本文長ではなくsourceTypeの条件でindexableだが、本番のrobotsとsitemapを確認すること。通常ニュースの手動改稿はガイドのeditorial保護と異なり、自動続報による再生成の可能性がある。元動画と旧SNS文の再送はしない。次回、表示された検索語・順位と改善後のクリックを照合する。少数表示でCTR改善を断定しない。

別候補のMac Studio M5 Ultra比較記事では「最大256GB」の記述がAppleの公式最大512GBと食い違う。テスト機の256GB構成と製品の最大仕様は異なる。本文全体に比較・価格の未検証箇所があり、公式資料と動画を照合してから訂正すること。 https://www.apple.com/newsroom/2026/08/apple-introduces-new-mac-studio-with-m5-max-and-m5-ultra/

## Adobe MAX 2026 の入口

`app/events/[slug]/page.tsx` で Adobe MAX 2026 のみに国内開催と米国イベントの違い・オンライン視聴の説明、確認日、出典を表示し、descriptionを検索意図に合わせる。今回確認したAdobeの日本向けイベント案内には日本開催日がなく、「開催されない」とは断定しない。日本版公式ページは2025年東京開催。公式FAQによる米国の会期とオンライン無料は確認、視聴時刻と言語は参加前に公式で確認。既存のEvent・FAQ構造化データ、イベント日時・自動関連記事・広告・計測を保つ。空のkeynotesに対する全イベント共通の文言は「日時が未発表」から「開始時刻を確認情報で確認できない」に修正し、既知の開催日との矛盾を避けた。 https://www.adobe.com/jp/events.html https://www.max.adobe.com/faq/ https://maxjapan.adobe.com/
