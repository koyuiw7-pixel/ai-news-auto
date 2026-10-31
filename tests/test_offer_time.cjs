const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const test = require('node:test');
const ts = require('typescript');
const sourcePath = path.resolve(__dirname, '../lib/offer-time.ts');
const compiled = ts.transpileModule(fs.readFileSync(sourcePath, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const mod = new Module(sourcePath, module); mod.filename = sourcePath; mod._compile(compiled, sourcePath);
const { offerIsActive, nextOfferExpiry } = mod.exports;
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
