# M5 Ultra / RTX 5090記事の訂正（2026-10-31）

対象: `content/articles/m5-ultra-vs-rtx-5090-local-llm-benchmark.json`。検証機の256GBを製品最大と混同していたため、Apple公表の最大512GBと区別し、画面内に訂正日と理由を記載。Appleの2026/8/25の日本向け発表ではM5 Ultra搭載Mac Studioは税込949,800円から。最小構成の発表価格であり256GBや512GBの価格ではない。512GBは10月後半に加わる予定という当時の発表で、現在の入手状況は未確認。 https://www.apple.com/jp/newsroom/2026/08/apple-introduces-new-mac-studio-with-m5-max-and-m5-ultra/

動画の参照元 https://www.macstories.net/stories/m5-ultra-mac-studio-review-the-dream-mac-for-local-ai-agents/ の6,091入力、同じタスクの1回ずつの比較を確認。M5 Ultra 256GBはMLX oQ4e/oMLX、RTX 5090 32GB VRAM + 96GB RAMのPCはGGUF Q4_K_M/LM Studio。MTPとthinkingはoff。読み込み3031/1701、生成59/48 token/s、初回2.0/4.0秒は別条件の実験値と混ぜない。形式・ランタイムは異なりチップ単体の同条件比較ではない。以前の74/52、136/100を同一条件として並べた断定を除去。 https://huggingface.co/Qwen/Qwen3.8-27B/discussions/112 の136.7 token/sは別のRTX単体設定であり、対Mac同一試行ではない。

NVIDIA公表 https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/ RTX5090は32GB GDDR7、帯域1792GB/s。32GB超のモデルが絶対に実行不可、M5 Ultraだけが唯一の選択肢、ローカルは情報漏えいを排除できる、料金が一律、構成不明の推奨や消費電力を同列比較する等の断定を削除。実機検証は行っていない。

記事のslug・元動画・公開日・生成日・画像・広告設定・SNS文面・投稿履歴は保持。2026/10/31追記：記事データのSNS紹介文を最大512GB・比較機256GBの表現に差し替えた。既存投稿やBuffer予約、投稿履歴は変更・削除・再送していない。Buffer画面の読み取り接続はタイムアウトし、予約一覧に対象が存在するかは未確認。通常動画記事は自動再生成で手修正が失われる可能性があり続報時は再点検。ロールバックはgitの元記事の対象フィールドだけを参照し、最新のbot更新やstateは戻さない。検索流入・収益への効果は未測定。

前回1c05241のAdobe/Gemini改善はdeploy 41100630527成功。後続更新を含む本番で内容を確認し、更新前後でAdobe/GitHubイベントのcanonical・robots・広告属性、Geminiの広告href/rel 10件とA8画像9件が一致。テストは広告先通信を遮断し、クリックや成果を発生させない。イベントに広告が0件であることは広告計測動作の実証ではない。

公開確認: 本文コミット49d4d47、deploy 41152026385成功。初回HTTP応答は古いキャッシュだったが再取得後、訂正文・最大512GB・256GB検証機・59/48トークンを確認。広告href/rel12件とA8画像19件、canonical・robotsは公開前後一致、Cloudflare Web Analyticsコードあり。本番Macの375/1440×light/dark表示は各0違反（新しい本文を取得後に再検査）。前回Adobe/Geminiも本番8条件で各0。広告通信遮断、実際のASPクリック・申込・成果の確認は行っていない。3URLのIndexNow通知HTTP200受理、Googleの再取得や検索順位を保証するものではない。sitemap.xmlにも3URLを確認。

SNS文面の追加検証: 唯一の更新欄は `threadsPost`。タイトル・本文・更新日・画像・SNS型・履歴・予約は変更しない。classic/hook/X詳細/Blueskyのプランをネットワーク禁止の隔離テストで確認。投稿済みのslugが通常候補と速報候補から除外されること、未投稿時には候補になれることを擬似データで確認。実データでは当該slugにposted/extraPendingはなく、生成後14日超で通常候補の対象外、動画IDはprocessedに記録済み。これはBufferの予約や実投稿が存在しない証拠ではない。SNS投稿テストやBuffer下書き作成はしていない。自動再生成や将来の手動再利用について、前提に変化があれば再確認する。
