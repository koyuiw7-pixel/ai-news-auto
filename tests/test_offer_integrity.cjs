const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const test = require('node:test');
const ts = require('typescript');
const root = path.resolve(__dirname, '..');
const sourcePath = path.join(root, 'lib/offers.ts');
const compiled = ts.transpileModule(fs.readFileSync(sourcePath, 'utf8'), {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText;
const mod = new Module(sourcePath, module);mod.filename=sourcePath;mod.paths=Module._nodeModulePaths(path.dirname(sourcePath));const original=mod.require.bind(mod);mod.require=(name)=>name==='@/lib/content-fs'?fs:original(name);mod._compile(compiled,sourcePath);
const {offerForArticle,partnerItem}=mod.exports;
const offers=JSON.parse(fs.readFileSync(path.join(root,'content/offers.json'),'utf8'));
const links=JSON.parse(fs.readFileSync(path.join(root,'affiliate_links.json'),'utf8'));
const article={slug:'test-rtx',title:'RTX搭載のローカルAI用PC',seoTitle:'',tags:[],keywords:[],genreSlug:'ai',affiliateNames:[],verdict:null};
test('元の提携先URL・計測タグを保持し、期限をつける',()=>{
 const result=offerForArticle(article,12), item=result.items.find(i=>i.key==='oz-rtx5070ti');
 assert.ok(item);const p=offers.partners['oz-rtx5070ti'];const program=links[p.program];
 assert.equal(item.url,p.link??`${program.url}&a8ejpredirect=${encodeURIComponent(p.page)}`);
 assert.equal(item.image,p.image);assert.equal(item.activeUntil,'2026-11-01T00:00:00+09:00');
 const pixel=p.pixel??program.pixel;
 if(pixel) assert.ok(result.timedPixels.some(x=>x.url===pixel&&x.activeUntil===item.activeUntil)||result.pixels.includes(pixel));
});
test('販売停止中の候補をランキングと比較から外す',()=>{
 const result=offerForArticle(article,12);
 assert.equal(result.items.some(i=>i.key==='oz-rx9060xt'),false);
 assert.equal(partnerItem('oz-rx9060xt'),undefined);
 assert.ok(result.items.length>0);
});
test('クラウドゲームの記事にはローカルAI用のPCを勧めない',()=>{
 const cloud={...article,slug:'cloud',title:'NVIDIAのクラウドゲーム GeForce NOW に新作が登場'};
 assert.equal(offerForArticle(cloud,12),undefined);
 assert.ok(offerForArticle(article,12).items.some(i=>i.key==='oz-rtx5070ti'));
});
