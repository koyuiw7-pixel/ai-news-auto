// 「あなたは対象？」と「次にやること」（content/next_steps.json・components/noir/NextSteps.tsx。2026-11-10 オーナー承認）の決まり。node --test tests/test_next_steps.cjs
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.join(__dirname, '..');
const read = (rel) => fs.readFileSync(path.join(root, rel), 'utf8');
const data = JSON.parse(read('content/next_steps.json'));
const exists = (slug) => fs.existsSync(path.join(root, 'content/articles', `${slug}.json`));
const ARROW = /[→›»⇒➡]/;

test('記事・リンク先の記事が今あり、記事の中の場所は「手順と公式の窓口」の欄だけ', () => {
  for (const [slug, entry] of Object.entries(data.articles)) {
    assert.ok(exists(slug), slug);
    for (const item of entry.check?.items ?? []) {
      if (item.slug) assert.ok(exists(item.slug), `${slug}: ${item.slug}`);
      if (item.href) assert.equal(item.href, '#steps-fold', `${slug}: ${item.href}`);
      if (item.slug || item.href) assert.ok(item.link, `${slug}: リンクの文字が無い`);
    }
    const branch = entry.check?.branch;
    if (branch?.slug) assert.ok(exists(branch.slug), `${slug}: ${branch.slug}`);
    if (branch?.href) assert.equal(branch.href, '#steps-fold');
    assert.ok((entry.next ?? []).length <= 3, `${slug}: 次にやることは3つまで`);
    for (const step of entry.next ?? []) {
      assert.ok(exists(step.slug), `${slug}: ${step.slug}`);
      assert.notEqual(step.slug, slug, `${slug}: 自分を案内しない`);
    }
  }
});

test('矢印の印・縦棒を使わない（オーナー「→みたいな印はいらない」「｜」を使わない）', () => {
  const text = JSON.stringify(data);
  assert.doesNotMatch(text, ARROW);
  assert.doesNotMatch(text, /｜/);
  for (const rel of ['components/noir/NextSteps.tsx', 'components/noir/StoryLinks.tsx']) {
    const code = read(rel).split('\n').filter((line) => !/^\s*(\/\/|\*|\/\*|\{\/\*)/.test(line)).join('\n');
    assert.doesNotMatch(code, ARROW, rel);
  }
});

test('「手順と公式の窓口」の欄に飛べる（id と、閉じた欄を開く部品）', () => {
  const page = read('components/noir/noirArticlePage.tsx');
  assert.match(page, /<Fold\s+id="steps-fold"/);
  assert.match(page, /<FoldOpener \/>/);
});
