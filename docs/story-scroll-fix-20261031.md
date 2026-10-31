# ストーリーから記事に移動後、スクロールできない問題（2026-10-31）

## 原因と修正

ホームのStoryRailはストーリーダイアログを開くと`document.body.style.overflow`を`hidden`にして背景を固定していた。閉じるボタンはstateを戻すが、Next.jsのリンクから記事へ移動するとコンポーネントごとアンマウントされるため、解除用のeffectが走らず、記事上でも`overflow:hidden`が残った。実際の本番ホームから「今すぐ読む」で遷移した実測では、記事が画面より長くてもホイール操作前後のscrollYが0のままだった。

`components/story/SwipeDeck.tsx`だけを変更。ダイアログを開いている間だけbodyを固定し、effect cleanupで開く前のoverflow値を復元する。閉じる、束の切替、アンマウント時を含む。bodyの既存値を保存し、無条件に空にしない。記事本文、URL、広告・計測、予約やSNS投稿には手を加えない。

## 検証

- 修正前の本番はストーリー開放時hidden→記事遷移後hidden→ホイール後scrollY 0、修正後のローカルは遷移後のoverflow空・scrollY 0→700。広告/ASP/解析系のネットワークを遮断し、広告リンクを押していない。
- 本番形式のローカルビルドでPC/スマホ各5条件（今すぐ読む、一覧から選ぶ、保存した記事から読む、閉じる、Esc）計10条件すべてでホイール前0→後600。元のbody overflowが`clip`の場合も閉じた後に元値へ復元。対象記事 `/articles/gemini-edit-files-directly` もストーリー一覧から移動後scrollY 600を確認。
- `npm run build -- --webpack`、`npx tsc --noEmit`、ローカルのreadability 44条件0件、広告の隔離テストとガイド導線7テストに成功。対象記事の広告リンク10件とrelは本番/ローカルで最終的に一致。ローカルのcanonicalは環境既定localhostであり本番canonicalとは比較しない。初回比較で広告リンクに差が出たが、再取得では10件の順序・値が一致したため、公開後にも確認する。
- Browser test用の一時スクリプトはwork/story-scroll-regression.mjs、同target.mjs。環境bundled Playwright/Chromeを使用し、自動テスト前に広告ドメインを遮断、利用者のブラウザ・localStorageは使用しない。

## 本番の結果

実装 `fa3d706` のCloudflare公開run `41164791180` が成功。広告通信を遮断した本番ブラウザで、PC/スマホ×上記5経路の計10条件すべてscrollY 0→600。添付対象のGemini記事もストーリー一覧経由でscrollY 600、overflow空。対象記事の公開前後のsponsoredリンク10件、A8画像タグ6件、canonicalとrobotsは一致（リンク・計測先へアクセスせずHTML属性のみ照合）。別条件で元overflow値clipが復元されることも確認。

本番ブラウザの最初の多経路試行は3回目のホーム表示直後にdialog待ちでtimeoutし、ページのhydration完了前クリックが一因の可能性があるが確定していない。ホーム表示後2.5秒待った再試行で10条件すべて成功。特定記事は別の新規ブラウザでも確認。最初の試行を成功と扱わない。

本番のreadability run `41164975267` は成功し、44条件の違反0。
