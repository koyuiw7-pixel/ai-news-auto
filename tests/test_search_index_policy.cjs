const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const Module = require('node:module');

const filename = path.join(__dirname, '../lib/indexing.ts');
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS}}).outputText;
const loaded = new Module(filename, module);
loaded.filename = filename;
loaded.paths = module.paths;
loaded._compile(compiled, filename);
const { isIndexable, isDistributionEligible } = loaded.exports;

test('短い記事も検索対象だが、既存の配信基準は変えない', () => {
  for (const bodyLength of [1, 917, 1999]) {
    const article = { sourceType: 'web', channelSlug: 'official', bodyLength };
    assert.equal(isIndexable(article), true);
    assert.equal(isDistributionEligible(article), false);
  }
  const longArticle = { sourceType: 'web', channelSlug: 'official', bodyLength: 2000 };
  assert.equal(isIndexable(longArticle), true);
  assert.equal(isDistributionEligible(longArticle), true);
});

test('手動指定・配信元・まとめ記事・動画・空本文の扱いを保つ', () => {
  const short = { sourceType: 'web', channelSlug: 'official', bodyLength: 20 };
  assert.equal(isIndexable({ ...short, indexable: false }), false);
  assert.equal(isDistributionEligible({ ...short, indexable: false }), false);
  assert.equal(isIndexable({ ...short, channelSlug: 'prtimes' }), false);
  assert.equal(isDistributionEligible({ ...short, channelSlug: 'prtimes' }), false);
  assert.equal(isIndexable({ ...short, channelSlug: 'prtimes', indexable: true }), true);
  assert.equal(isDistributionEligible({ ...short, channelSlug: 'prtimes', indexable: true }), true);
  assert.equal(isIndexable({ ...short, bodyLength: 0 }), false);
  assert.equal(isIndexable({ ...short, type: 'roundup' }), true);
  assert.equal(isDistributionEligible({ ...short, type: 'roundup' }), true);
  assert.equal(isIndexable({ ...short, sourceType: 'video' }), true);
  assert.equal(isDistributionEligible({ ...short, sourceType: 'video' }), true);
});
