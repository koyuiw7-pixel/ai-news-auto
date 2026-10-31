const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const test = require('node:test');
const ts = require('typescript');
const sourcePath = path.resolve(__dirname, '../lib/offer-time.ts');
const compiled = ts.transpileModule(fs.readFileSync(sourcePath, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const mod = new Module(sourcePath, module); mod.filename = sourcePath; mod._compile(compiled, sourcePath);
const { offerIsActive, nextOfferExpiry, priceIsFresh } = mod.exports;
const end = '2026-11-01T00:00:00+09:00';
const deadline = Date.parse(end);
test('販売終了時刻の前だけ掲載し、時刻が不明なら表示しない', () => {
  assert.equal(offerIsActive(end, null), false);
  assert.equal(offerIsActive(end, deadline - 1), true);
  assert.equal(offerIsActive(end, deadline), false);
  assert.equal(offerIsActive(end, deadline + 1), false);
});
test('不正な期限は安全側に倒し、期限なし広告は従来通り', () => {
  assert.equal(offerIsActive('invalid', deadline), false);
  assert.equal(offerIsActive(end, NaN), false);
  assert.equal(offerIsActive(undefined, null), true);
});
test('残りの期限を早い順で選ぶ', () => {
  assert.equal(nextOfferExpiry(['invalid', end, undefined], deadline - 1), deadline);
  assert.equal(nextOfferExpiry([end], deadline), undefined);
});

test('金額は確認後48時間だけ表示し、未知・未来・境界は安全側', () => {
 const expires=Date.parse(end), start=expires-48*60*60*1000;
 assert.equal(priceIsFresh(end,null),false);
 assert.equal(priceIsFresh(undefined,expires-1),false);
 assert.equal(priceIsFresh('invalid',expires-1),false);
 assert.equal(priceIsFresh(end,start-1),false);
 assert.equal(priceIsFresh(end,start),true);
 assert.equal(priceIsFresh(end,expires-1),true);
 assert.equal(priceIsFresh(end,expires),false);
});
