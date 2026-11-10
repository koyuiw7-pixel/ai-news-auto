const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

// 比較ページの「あなたに合うのは」と絞り込み一覧のデータ（content/buying-guides/*.json の planFinder。2026-11-11 COMPARE-2）。
// 数字は公式ページの記載だけ・出典と確認日つき・提携先で順番を変えない、を確かめる。
const root = path.resolve(__dirname, "..");
const read = (rel) => fs.readFileSync(path.join(root, rel), "utf8");
const dir = path.join(root, "content/buying-guides");
const guides = fs.readdirSync(dir).filter((f) => f.endsWith(".json")).map((f) => JSON.parse(fs.readFileSync(path.join(dir, f), "utf8"))).filter((g) => g.planFinder);

function strings(value, out = []) {
  if (typeof value === "string") out.push(value);
  else if (Array.isArray(value)) value.forEach((v) => strings(v, out));
  else if (value && typeof value === "object") Object.values(value).forEach((v) => strings(v, out));
  return out;
}

test("絞り込みのあるガイドがある（格安SIMは15社以上）", () => {
  const sim = guides.find((g) => g.slug === "kakuyasu-sim");
  assert.ok(sim, "格安SIM");
  assert.ok(sim.planFinder.items.length >= 15, `格安SIMは${sim.planFinder.items.length}社`);
});

for (const g of guides) {
  const f = g.planFinder;
  test(`${g.slug}: どの行にも商品と公式の出典があり、表の値は段と条件のすべてにある`, () => {
    const ids = new Set(g.products.map((p) => p.id ?? p.partner));
    assert.equal(new Set(f.items.map((i) => i.id)).size, f.items.length, "id の重複");
    for (const item of f.items) {
      assert.ok(ids.has(item.id), `${item.id} に products がない`);
      const product = g.products.find((p) => (p.id ?? p.partner) === item.id);
      assert.ok(product.sources?.length >= 1, `${item.id}: 出典`);
      for (const s of product.sources) {
        assert.match(s.url, /^https:\/\//, item.id);
        assert.doesNotMatch(s.url, /a8\.net|afl\.rakuten|valuecommerce|accesstrade|moshimo/, `${item.id}: 出典に広告のリンク`);
      }
      assert.equal(product.priceSource.type, "official");
      assert.ok(Date.parse(product.priceSource.checkedAt) <= Date.now());
      for (const tier of f.tiers) {
        const row = item.matrix[tier.key];
        assert.ok(row, `${item.id}: 段 ${tier.key}`);
        for (const opt of f.options ?? [{ key: "any" }]) {
          assert.ok(opt.key in row, `${item.id}: ${tier.key}/${opt.key}`);
          const cell = row[opt.key];
          if (cell) {
            assert.ok(Number.isInteger(cell.yen) && cell.yen > 0, `${item.id}: 金額`);
            assert.ok(cell.label.length > 0);
          }
        }
      }
      for (const t of item.tags) assert.ok(f.tags.includes(t), `${item.id}: 札 ${t}`);
    }
  });

  test(`${g.slug}: 条件を厳しくすると金額は下がらない（データ量・通話）`, () => {
    for (const item of f.items) {
      const opts = (f.options ?? [{ key: "any" }]).map((o) => o.key);
      for (const tier of f.tiers) {
        let prev = 0;
        for (const o of opts) {
          const cell = item.matrix[tier.key][o];
          if (!cell) { prev = Infinity; continue; }
          assert.ok(cell.yen >= prev || prev === Infinity, `${item.id} ${tier.key} ${o}`);
          prev = cell.yen;
        }
      }
      for (const o of opts) {
        let prev = 0;
        for (const tier of f.tiers) {
          const cell = item.matrix[tier.key][o];
          if (!cell) { prev = Infinity; continue; }
          assert.ok(cell.yen >= prev || prev === Infinity, `${item.id} ${tier.key} ${o}`);
          prev = cell.yen;
        }
      }
    }
  });

  test(`${g.slug}: 並び順の決まりを書き、提携先で順番を変えないと明記。最安・No.1・おすすめ順位の言葉を使わない`, () => {
    assert.match(f.sortRule, /安い順/);
    assert.match(f.sortRule, /提携先（PR）かどうかで順番は変えていません/);
    const text = strings(g).join("\n");
    assert.doesNotMatch(text, /最安|No\.1|ナンバーワン|日本一|業界一|ランキング1位/);
    assert.doesNotMatch(text, /｜|ざっくり/);
  });

  test(`${g.slug}: 結論の名前と金額は表の値と同じ`, () => {
    for (const persona of g.personas ?? []) {
      for (const pick of persona.picks) assert.ok(f.items.some((i) => i.id === pick), `${pick} が一覧にない`);
      const amounts = [...persona.why.matchAll(/([\d,]{3,})円/g)].map((m) => Number(m[1].replace(/,/g, "")));
      const all = new Set(f.items.flatMap((i) => Object.values(i.matrix).flatMap((row) => Object.values(row).flatMap((c) => (c ? [c.yen] : [])))).concat(f.items.map((i) => i.initialYen)));
      for (const yen of amounts) assert.ok(all.has(yen), `${g.slug}: 結論の ${yen}円 が表にない（${persona.who}）`);
    }
  });
}

test("一覧の部品: 3つの質問・並べ替え・PR の札・sponsored のリンクは提携先だけ", () => {
  const src = read("components/compare/PlanFinder.tsx");
  assert.match(src, /あなたに合うのは/);
  assert.match(src, /月額の安い順/);
  assert.match(src, /初めの費用の安い順/);
  assert.match(src, /データ量の多い順/);
  assert.match(src, /rel=\{product\.sponsored \? "sponsored nofollow noopener noreferrer" : "nofollow noopener"\}/);
  assert.match(src, /data-aff-pos="compare"/);
  // 上位3件は金額だけで決める（sponsored を並び替えに使わない）
  const sortBody = src.slice(src.indexOf("const byPrice"), src.indexOf("const missing"));
  assert.doesNotMatch(sortBody, /sponsored/);
});
