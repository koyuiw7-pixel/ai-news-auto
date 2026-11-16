const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

// サイソクの運営者が自分のサービス（マイソクメーカー）を扱う比較ガイド（2026-11-16 オーナー決定・台帳 W46）。
// 自分の商品を第三者のように紹介しない: 題名より前に運営が同じことの1行（文章で書く。提携の広告ではないので「PR」の札は付けない）・提携の枠なし・リンクは maisoku-maker.jp。
const root = path.resolve(__dirname, "..");
const read = (rel) => fs.readFileSync(path.join(root, rel), "utf8");
const dir = path.join(root, "content", "buying-guides");
const guides = fs
  .readdirSync(dir)
  .filter((f) => f.endsWith(".json"))
  .map((f) => JSON.parse(fs.readFileSync(path.join(dir, f), "utf8")));
const ownGuides = guides.filter((g) => g.ownerNote || (g.products ?? []).some((p) => p.own));

function strings(value, out = []) {
  if (typeof value === "string") out.push(value);
  else if (Array.isArray(value)) value.forEach((v) => strings(v, out));
  else if (value && typeof value === "object") Object.values(value).forEach((v) => strings(v, out));
  return out;
}

test("[W46] マイソク作成ソフトの比較ガイドがあり、自社サービスの表示が付いている", () => {
  const guide = ownGuides.find((g) => g.slug === "maisoku-software");
  assert.ok(guide, "content/buying-guides/maisoku-software.json が無い");
  assert.equal(guide.schemaVersion, 2);
  assert.equal(guide.editorial, "manual", "自動の作り直しの対象にしない");
});

test("[W46] 自社サービスを扱うページは、冒頭の1行・自社の印・提携なしがそろっている", () => {
  for (const guide of ownGuides) {
    const own = (guide.products ?? []).filter((p) => p.own);
    assert.ok(own.length >= 1, `${guide.slug}: ownerNote があるのに own の商品が無い`);
    assert.match(guide.ownerNote ?? "", /サイソクの運営者が開発・運営しているサービスです。/, `${guide.slug}: 運営が同じことの1行`);
    for (const p of own) assert.ok((guide.ownerNote ?? "").includes(p.name), `${guide.slug}: 1行に ${p.name} の名前`);
    // 自社の商品の記事にアフィリエイトの枠は入れない
    for (const p of guide.products) assert.equal(p.partner, undefined, `${guide.slug}: 提携先（${p.partner}）を並べない`);
    assert.deepEqual(guide.quickPick ?? [], [], `${guide.slug}: 「迷ったらこれ」の提携の枠を置かない`);
    assert.deepEqual(guide.topics ?? [], [], `${guide.slug}: 記事の商品枠の話題に結ばない`);
    for (const text of strings(guide)) assert.doesNotMatch(text, /a8\.net|px\.a8|rakuten\.co\.jp\/.*scid|amazon\.co\.jp.*tag=/, `${guide.slug}: 提携のリンク`);
  }
});

test("[W46] マイソクメーカーのリンクは maisoku-maker.jp（同じ名前の別のツールと取り違えない）", () => {
  for (const guide of ownGuides) {
    for (const p of guide.products.filter((x) => x.own && x.name === "マイソクメーカー")) {
      assert.equal(p.officialUrl, "https://maisoku-maker.jp");
      for (const s of p.sources ?? []) assert.equal(new URL(s.url).hostname, "maisoku-maker.jp");
    }
    for (const note of guide.notes ?? []) if (note.link) assert.equal(note.link.url, "https://maisoku-maker.jp", `${guide.slug}: 段のボタンの行き先`);
    for (const text of strings(guide)) assert.doesNotMatch(text, /h-suga/, `${guide.slug}: 別のツールのドメイン`);
  }
});

test("[W46] マイソクメーカーの数字は決めたまま（勝手に変えない）", () => {
  const guide = ownGuides.find((g) => g.slug === "maisoku-software");
  const all = strings(guide.products.find((p) => p.id === "maisoku-maker")).join("\n");
  for (const fact of ["月額980円", "2026年12月31日までの申込み", "2027年1月1日以降の新しい申込みは月額1,980円", "月3物件まで", "100種", "318種"]) {
    assert.ok(all.includes(fact), `「${fact}」が無い`);
  }
});

test("[W46] 文章の決まり: 要約すると・サイソクの見方・選び方の表・縦棒なし・根拠のない言い切りなし・順位なし", () => {
  for (const guide of ownGuides) {
    assert.match(guide.intro, /^要約すると、/, `${guide.slug}: 「要約すると」で始める`);
    assert.ok((guide.notes ?? []).some((n) => n.label === "サイソクの見方"), `${guide.slug}: サイソクの見方`);
    assert.ok((guide.fitTable ?? []).length >= 4, `${guide.slug}: 選び方の表`);
    for (const text of strings(guide)) {
      assert.doesNotMatch(text, /[｜|]/, `${guide.slug}: 縦棒「${text.slice(0, 30)}」`);
      assert.doesNotMatch(text, /ざっくり/, `${guide.slug}: ざっくり`);
      assert.doesNotMatch(text, /最安|必ず|一番|No\.?\s*1|ナンバーワン|おすすめ1位|より優れ/, `${guide.slug}: 根拠のない言い方「${text.slice(0, 30)}」`);
    }
    assert.ok(strings(guide).some((t) => /おすすめの順ではありません/.test(t)), `${guide.slug}: 並びが順位でないことを書く`);
  }
});

test("[W46] 題名: 「事務作業の救世主」は道具の種類に付ける（自社のサービスだけを指して書かない）", () => {
  const guide = ownGuides.find((g) => g.slug === "maisoku-software");
  // 探される言葉は題名に残す
  assert.match(guide.title, /マイソク作成ソフト5つを比べる/);
  assert.match(guide.title, /不動産会社の事務作業の救世主/);
  // 題名の約束（事務作業が軽くなる）に本文が答えている
  assert.ok(strings(guide.notes).some((t) => /事務作業が軽くなる/.test(t)), "本文に事務作業の話");
  // 「救世主」とマイソクメーカーを同じ文に書かない（順位を付けない）
  for (const text of strings(guide)) for (const sentence of text.split("。")) {
    if (/救世主/.test(sentence)) assert.doesNotMatch(sentence, /マイソクメーカー/, `自社だけを救世主と書かない「${sentence.slice(0, 30)}」`);
  }
});

test("[W46] マイソクメーカーの良さ: できること・AI・約5分を、条件つきで書く", () => {
  const guide = ownGuides.find((g) => g.slug === "maisoku-software");
  const can = (guide.notes ?? []).find((n) => n.id === "maisoku-can");
  assert.ok(can, "「できること」の段");
  assert.equal(can.place, "top", "比較表より上に置く");
  assert.ok((can.points ?? []).length >= 6, "できることを並べる");
  const canText = strings(can).join("\n");
  assert.match(canText, /AI/);
  // AI は候補を出すだけ（そのまま図面に入るように書かない）
  assert.match(canText, /AIが出すのは候補だけ/);
  // 「5分」は当社計測の目安。段の外（導入・表・動画の説明など）でも、同じ文に「目安」を添える
  assert.match(canText, /当社が文字の入ったPDF1枚で計測した目安/);
  const rest = { ...guide, notes: (guide.notes ?? []).filter((n) => n.id !== "maisoku-can") };
  for (const text of strings(rest)) if (/5分/.test(text)) assert.match(text, /目安/, `「5分」に目安の断りが無い「${text.slice(0, 30)}」`);
  // プロプランだけの機能は、そう書く
  for (const point of can.points) if (/AI|帯|住所/.test(point.title)) assert.match(point.body, /プロプランの機能/, `${point.title}: プランの断り`);
  // 動画はこの段の中（上のほう）に置く
  assert.equal(guide.video.inNote, "maisoku-can");
});

test("[W46] 動画は音を消して始め、何が本物で何が作り物かを書く", () => {
  const guide = ownGuides.find((g) => g.slug === "maisoku-software");
  assert.ok(guide.video, "動画");
  assert.equal(guide.video.muted, true);
  assert.match(guide.video.src, /^\/video\/[A-Za-z0-9][A-Za-z0-9_-]{0,160}\.mp4$/);
  assert.match(guide.video.poster, /^\/video\/[A-Za-z0-9][A-Za-z0-9_-]{0,160}\.jpg$/);
  assert.match(guide.video.caption, /画面と図面は実際の製品で、物件は架空、写真と背景は生成したものです。/);
  const player = read("components/ArticleVideo.tsx");
  assert.match(player, /muted=\{muted\}/, "音を消す指定が動画に渡っている");
  // 押す前は <video> を置かない（自動再生しない）
  assert.match(player, /playing \? \(/);
});

test("[W46] 画面: 題名より前に運営が同じことの1行を出す。「PR」の札は提携先だけ（自社のサービスには付けない）", () => {
  const parts = read("components/compare/parts.tsx");
  const ownerNote = parts.slice(parts.indexOf("export function OwnerNote"));
  assert.match(ownerNote, /data-owner-note[\s\S]*?\{note\}/, "1行を出す");
  assert.doesNotMatch(ownerNote.slice(0, ownerNote.indexOf("\n}\n")), /<PrMark/, "1行に「PR」の札は付けない");
  const variant = read("components/compare/VariantA.tsx");
  const head = variant.indexOf("guide.ownerNote && <OwnerNote");
  assert.ok(head > 0 && head < variant.indexOf('<h1 className="t-h1'), "題名より前に出す");
  // 「PR」の札は提携先（sponsored）だけ。own で札を出す分岐を作らない
  for (const src of [parts, variant, read("app/compare/page.tsx"), read("lib/buying-guides.ts")]) assert.doesNotMatch(src, /showsPr|\.own\b[^\n]*PrMark/);
  // 自社のサービスは提携リンクとして数えない（rel は sponsored にしない）
  assert.match(parts, /rel=\{product\.sponsored \? "sponsored nofollow noopener noreferrer" : "nofollow noopener"\}/);
  assert.match(read("docs/owner_rules.md"), /^\| W46 \| \*\*2026-11-16 オーナー決定/m);
  // SNS の投稿には断り書きの行を付けない。運営が同じことは、ページの冒頭の1行で伝える（だから1行は消さない）
  assert.match(read("docs/owner_rules.md"), /^\| W46 \|.*断り書きの行は付けない.*ページの冒頭の1行（①）で伝える/m);
});
