// 広告・提携の開示（2026-11-09。もしもアフィリエイト・Amazon・楽天の審査の準備）
// 1. 「Amazonのアソシエイトとして…」は lib/disclosure.ts のフラグが true のときだけ出す（承認前に書くと事実と違う）
// 2. フッター・/privacy・/disclaimer は文面を直接書かず、lib/disclosure.ts から読む
// 3. フッターには運営者情報・プライバシーポリシー・免責事項・お問い合わせへのリンクがある（全ページの足元）
// 4. /privacy にはアフィリエイトの Cookie と止め方、/disclaimer にはアフィリエイトに参加している旨がある
const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');const test=require('node:test');
const root=path.resolve(__dirname,'..');
const read=(rel)=>fs.readFileSync(path.join(root,rel),'utf8');

test('Amazon の決まった文はフラグの後ろにだけある',()=>{
 const lib=read('lib/disclosure.ts');
 assert.match(lib,/export const AMAZON_ASSOCIATE_APPROVED = (true|false);/);
 assert.match(lib,/Amazonのアソシエイトとして、\$\{siteConfig\.siteName\}は適格販売により収入を得ています。/);
 // 2026-11-11 オーナー決定（台帳 W40「広告の表示は『PR』だけ」）: フッターの広告の説明文は外した。Amazon の決まった文は /privacy・/disclaimer に出す
 assert.doesNotMatch(read('components/Footer.tsx'),/Amazonのアソシエイトとして|アフィリエイトプログラムに参加しており/);
 for(const rel of ['app/privacy/page.tsx','app/disclaimer/page.tsx']){
  const src=read(rel);
  assert.doesNotMatch(src,/Amazonのアソシエイトとして/,rel);
  assert.match(src,/amazonAssociateStatement\(\)/,rel);
 }
});

test('フッターに運営者情報・プライバシー・免責事項・お問い合わせへのリンク',()=>{
 const src=read('components/Footer.tsx');
 for(const href of ['/about','/privacy','/disclaimer','/contact']) assert.match(src,new RegExp(`href: "${href}"`),href);
 assert.match(read('app/layout.tsx'),/<Footer \/>/);
});

test('/privacy はアフィリエイトの Cookie と止め方、/disclaimer は参加していることを書く',()=>{
 const p=read('app/privacy/page.tsx');
 assert.match(p,/提携リンクで使われるCookie/);
 assert.match(p,/提携リンクのCookieを止めるには/);
 assert.match(p,/AFFILIATE_PROGRAMS/);
 const d=read('app/disclaimer/page.tsx');
 assert.match(d,/アフィリエイトプログラムに参加しています/);
 assert.match(d,/ステルスマーケティング規制/);
});

test('/privacy-policy と /terms は正しいページへ転送',()=>{
 const c=read('next.config.ts');
 assert.match(c,/source: "\/privacy-policy", destination: "\/privacy"/);
 assert.match(c,/source: "\/terms", destination: "\/disclaimer"/);
});

test('自己紹介に「ざっくり」と「｜」を使わない',()=>{
 for(const rel of ['app/about/page.tsx','app/privacy/page.tsx','app/disclaimer/page.tsx','app/editorial-policy/page.tsx','lib/disclosure.ts']){
  const src=read(rel);
  assert.doesNotMatch(src,/ざっくり|｜/,rel);
 }
});
