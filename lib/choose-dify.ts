import type { ChooseGuide } from "./choose-data";

const docs = "https://docs.dify.ai/en/self-host/deploy/quick-start/docker-compose";
const pricing = "https://dify.ai/pricing";
const xprice = "https://vps.xserver.ne.jp/price.php";
const xapp = "https://vps.xserver.ne.jp/dify.php";

/** 手動編集。根拠と更新手順は docs/revenue-funnel-2026-10-30.md。報酬額で並べない。 */
export const difyHosting: ChooseGuide = {
  slug: "dify-hosting",
  title: "DifyにVPSは必要？無料クラウド・自分のPC・VPSの費用と選び方",
  h1: "DifyにVPSは必要？無料で試してから選ぶ",
  description: "Difyの試用ならVPS契約は不要。クラウドの無料枠、手元のPC、常時運用するVPSを比較。公式の最低要件、XServer VPSの1か月契約と長期契約の支払額、API料金・保守の負担まで整理します。",
  keywords: ["Dify VPS 必要", "Dify 無料", "Dify セルフホスト 費用", "Dify 4GB", "Dify クラウド 違い"],
  lead: "Difyでチャットボットや作業の自動化を試すだけなら、VPSを契約する必要はありません。まず無料のDify Cloudで目的を試し、自分で環境を管理する理由がある場合に、手元のPCやVPSを検討します。このページでは、始めやすさ・支払額・管理の負担を分けて比べます。",
  publishedAt: "2026-10-30T11:00:00+09:00",
  updatedAt: "2026-10-30T11:00:00+09:00",
  checkedAt: "2026-10-30",
  tableNote: "無料の試用、手元での検証、常時運用は用途が異なります。最安順位ではなく、必要な使い方から選んでください。VPS料金は税込、AIモデルの利用料は別です。",
  columns: [
    { key: "cost", label: "支払額・追加費用" },
    { key: "fit", label: "向いている用途" },
    { key: "manage", label: "自分で管理すること" },
    { key: "limit", label: "制限・注意点" },
  ],
  groups: [
    { label: "まず契約なしで検討", ids: ["dify-cloud", "local-pc"] },
    { label: "自分の環境で常時動かす必要がある場合", ids: ["xserver-dify"] },
  ],
  services: [
    {
      id: "dify-cloud", name: "Dify Cloud Sandbox", maker: "LangGenius", kind: "クラウドの無料枠",
      officialUrl: pricing,
      cells: {
        cost: { text: "Sandboxは無料。外部APIキーを使う場合のモデル利用料などは別。", tone: "good" },
        fit: { text: "機能を試す・小さなアプリを作って目的に合うか確かめる。" },
        manage: { text: "アプリ・データ・APIキー。サーバーの設置は不要。" },
        limit: { text: "200メッセージクレジット、1人、5アプリ。クレジットを毎月付与とは記載していません。" },
      },
      bestFor: "サーバー管理を始める前に、作りたいものがDifyで実現できるか確認したい人。",
      cautions: ["無料枠にもデータ量やAPI回数などの制限があります。仕事の要件を満たすかは料金表全体で確認してください。", "機密情報を入れる前に、組織のルールとサービスのデータ取り扱いを確認してください。"],
      sources: [{ label: "Dify公式料金表", url: pricing }],
    },
    {
      id: "local-pc", name: "手元のPCでセルフホスト", maker: "Dify Community", kind: "自分で設置・管理",
      officialUrl: docs,
      cells: {
        cost: { text: "手持ちのPCを使えばVPSの月額は不要。電気・機器・外部APIの費用は別。" },
        fit: { text: "自分だけの検証。Dockerや更新作業に慣れる。" },
        manage: { text: "設置、更新、バックアップ、アクセス制限を自分で管理。", tone: "bad" },
        limit: { text: "PCの停止・スリープで利用できなくなる。手軽な常時公開向けではありません。" },
      },
      bestFor: "Dockerを扱え、公開する前に自分の環境で検証したい人。",
      cautions: ["公式の最低要件は2 CPUコア・4 GiB RAM。macOSではDocker仮想マシンに2 vCPU・8 GiB以上を割り当てる案内があります。", "最低要件は快適な動作の保証ではありません。文書量、同時利用、使うモデルにより必要な資源は変わります。"],
      sources: [{ label: "Dify公式の導入要件", url: docs }],
    },
    {
      id: "xserver-dify", name: "XServer VPS 4GB", maker: "エックスサーバー", kind: "Difyアプリイメージ対応",
      names: "^XServer VPS$", officialUrl: xapp,
      cells: {
        cost: { text: "1か月契約2,640円／月。初期費用0円。外部API・ドメインなどは別。" },
        fit: { text: "PCを閉じても、自分で管理するDifyを動かしたい。" },
        manage: { text: "初期構築はアプリイメージ。運用後の更新・保護・バックアップは要管理。" },
        limit: { text: "4GBは最小の対応プラン。大量の文書や同時利用の快適さは未検証。", tone: "bad" },
      },
      bestFor: "常時稼働が必要で、サーバーを管理する担当者を決められる人。",
      cautions: ["1か月契約は初回・更新とも月額2,640円、4 vCPU・NVMe SSD 150GBの公式表示を確認しました。実機の性能比較は行っていません。", "36か月契約の月額換算2,035円は、36か月分73,260円に相当します。月払い2,035円ではありません。最初から長期契約を選ぶ必要はありません。", "Difyアプリイメージは4GB以上が対象。SSLの同時設定に対応しますが、保守全般を代行するサービスとは区別してください。"],
      sources: [{ label: "公式料金・契約期間", url: xprice }, { label: "Dify対応条件", url: xapp }],
    },
  ],
  needs: [
    { title: "まだ用途が決まっていない", body: "まずクラウドの無料枠で、質問に答えるアプリを1つ作ってみます。目的を達成できるか分からない段階で、サーバー代を固定費にする必要はありません。" },
    { title: "自分のPCで仕組みを確かめたい", body: "Dockerを扱えるなら手元で検証できます。ネット上への公開を急がず、更新とバックアップの手順まで確認してから常時運用を考えます。" },
    { title: "自分の環境で常時動かしたい", body: "VPSが候補になります。ただしクラウド版でも目的を満たせるなら、サーバー保守の負担も含めて比べます。VPSが必ず安くなるとは限りません。" },
    { title: "社内データを安全に使いたい", body: "セルフホストだけでは、データが外部に出ない保証にはなりません。接続先のAIモデルやプラグインに送る内容、権限、保存先を確認します。要件が厳しい場合は管理担当者と設計してください。" },
  ],
  personas: [
    { who: "まず作れるか試したい人", why: "サーバー管理に時間を使わず、アプリの価値を先に確かめられます。無料枠の範囲で足りるなら、そのまま使う選択もあります。", picks: ["dify-cloud"] },
    { who: "自分で管理する理由と担当者が決まっている人", why: "手元で動作を確認してから、常時稼働が必要ならVPSへ。長期契約の安さより、更新・復旧を続けられるかを優先します。", picks: ["local-pc", "xserver-dify"] },
  ],
  points: [
    { title: "料金は「サーバー代＋モデル利用料＋保守」で考える", body: "VPS代にChatGPTなどのAPI利用料が含まれるわけではありません。たとえばサーバー代2,640円に、自分の利用量に応じたAPI料金、必要な保存先・ドメイン代、保守の時間を足します。使いたいモデルで小さく試し、1回の処理量と実際の請求額を確かめてから予算を決めてください。" },
    { title: "4GBという数字を、性能の保証にしない", body: "Dify公式の4 GiBは最低要件です。VPS各社のGB表記や実際に使えるメモリと、最低要件を満たすこと・目的の負荷に耐えることを分けて確認します。自分の文書と同時利用数で試し、必要なら上位プランを検討してください。" },
    { title: "設置した後の作業を決めておく", body: "誰が更新情報を確認し、バックアップを取り、復元を試すかを決めます。公開時のHTTPS、管理画面へのアクセス、APIキーの保護も必要です。設置が簡単でも、運用の責任はなくなりません。" },
    { title: "契約の直前に、受付状況と総額をもう一度見る", body: "料金・受付状況は変わります。今回確認したConoHa VPS公式料金ページには新規申し込みの受付停止表示があったため、申し込み先の候補には含めていません。再開を確認するまでは申し込みを勧めません。" },
  ],
  faq: [
    { q: "Difyを無料で使うならVPSはいらない？", a: "試すだけなら、Dify CloudのSandboxを選べます。無料枠には利用量の上限があります。上限や運用要件を確認してから、有料クラウドやセルフホストを比べてください。" },
    { q: "2GBの安いVPSで始めてもよい？", a: "Dify公式の最低要件は4 GiB RAMです。このページでは、価格だけを理由に2GBプランを勧めません。XServer VPSのDifyアプリイメージも4GB以上が対象です。" },
    { q: "月額2,035円で1か月だけ使える？", a: "確認したXServer VPSの料金では、2,035円は36か月契約の月額換算です。4GBの1か月契約は2,640円。期間と支払総額を分けて確認してください。" },
    { q: "セルフホストならAIモデルも無料になる？", a: "なりません。外部のモデルAPIを接続すれば、その提供元の利用料金が別に発生します。モデル自体を手元で動かす場合の機材・メモリなども、ここで比べたDifyの最低要件とは別です。" },
    { q: "仕事や他社への提供にも自由に使える？", a: "利用形態に応じてDifyのライセンスと接続先サービスの条件を確認してください。無料で入手できることと、あらゆる提供形態で無条件に使えることは同じではありません。" },
  ],
  extraSources: [{ label: "ConoHa VPSの受付状況", url: "https://vps.conoha.jp/pricing/" }, { label: "Difyのライセンス", url: "https://github.com/langgenius/dify/blob/main/LICENSE" }],
  articleMatch: "\\bDify\\b|ディファイ",
  articleGenres: ["ai"],
  articleLabel: "DifyにVPSは必要？無料で試す方法と費用を比べる",
  articleNote: "クラウド・自分のPC・常時運用のVPSを、管理の負担まで含めて選べます。",
};
