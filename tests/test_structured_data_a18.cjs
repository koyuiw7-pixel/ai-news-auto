// SEO A18: 構造化データはページに見えているものと一致させる。
// - VideoObject は、ページで再生できる解説動画（ArticleVideo）がある記事だけ。YouTube をもとにした記事は isBasedOn で元動画を示す
// - FAQPage の問いは、ページに表示している問いだけ（イベントページで見えない問いが2つあった）
// - 編集責任者の Person と、ガイドの著者は、記事と同じ @id を指す
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const Module = require('node:module');

const root = path.join(__dirname, '..');
const read = (rel) => fs.readFileSync(path.join(root, rel), 'utf8');

// "@/..." を repo の中に、.ts/.tsx を TypeScript のまま読む（イベントページを実際に描いて確かめるため）
const compile = (m, filename) => {
  const out = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, jsx: ts.JsxEmit.ReactJSX },
    fileName: filename,
  }).outputText;
  m._compile(out, filename);
};
require.extensions['.ts'] = compile;
require.extensions['.tsx'] = compile;
require.extensions['.css'] = () => {};
const origResolve = Module._resolveFilename;
Module._resolveFilename = function (request, parent, ...rest) {
  if (request.startsWith('@/')) request = path.join(root, request.slice(2));
  return origResolve.call(this, request, parent, ...rest);
};

const sd = require(path.join(root, 'lib/structured-data.ts'));
const SITE = 'https://ai-tech-express.jp';
const opts = { rendered: true, siteUrl: SITE, name: '題名', description: '説明', publisherId: `${SITE}/#publisher` };

test('[A18] 再生できる動画が無い記事（YouTube をもとにした記事）は VideoObject を出さない', () => {
  // 本番で確かめる記事（YouTube の元動画をもとにした記事。ページには YouTube へのリンクだけで、再生部品は無い）
  const article = JSON.parse(read('content/articles/microsoft-foundry-agent-service-copilot-harness.json'));
  assert.ok(article.videoId && article.sourceType !== 'web', 'YouTube をもとにした記事のはず');
  assert.equal(sd.playableVideoJsonLd(article.video, opts), null);
  assert.equal(sd.playableVideoJsonLd(null, opts), null);
  // 元動画は出典（isBasedOn・citation）として示し、VideoObject の形にはしない
  const src = sd.sourceJsonLd({ url: article.videoUrl, name: article.videoTitle, publisher: 'YouTube' });
  assert.equal(src.isBasedOn, article.videoUrl);
  assert.equal(src.citation['@type'], 'CreativeWork');
  assert.doesNotMatch(JSON.stringify(src), /VideoObject/);
  assert.deepEqual(sd.sourceJsonLd(null), {});
});

test('[A18] ページで再生できる解説動画があれば VideoObject（再生部品を出さない形のページでは出さない）', () => {
  const video = { src: '/video/x.mp4', poster: 'https://ai-tech-express.jp/video/x.jpg', seconds: 56.4, title: '解説', uploadedAt: '2026-11-02T20:51:03Z' };
  const ld = sd.playableVideoJsonLd(video, opts);
  assert.equal(ld['@type'], 'VideoObject');
  assert.equal(ld.contentUrl, `${SITE}/video/x.mp4`);
  assert.equal(ld.uploadDate, '2026-11-02T20:51:03Z');
  assert.equal(ld.duration, 'PT56S');
  assert.deepEqual(ld.thumbnailUrl, [video.poster]);
  assert.equal(ld.embedUrl, undefined);
  assert.equal(sd.playableVideoJsonLd(video, { ...opts, rendered: false }), null);
  // 足した日時が分からない動画に日付を作らない
  assert.equal(sd.playableVideoJsonLd({ src: '/video/y.mp4' }, opts).uploadDate, undefined);
  assert.equal(sd.isoDuration(90), 'PT1M30S');
  assert.equal(sd.isoDuration(120), 'PT2M');
  assert.equal(sd.isoDuration(0), undefined);
});

test('[A18] 解説動画のある記事はすべて、足した日時（uploadedAt）を持つ', () => {
  const dir = path.join(root, 'content/articles');
  for (const name of fs.readdirSync(dir).filter((n) => n.endsWith('.json'))) {
    const a = JSON.parse(fs.readFileSync(path.join(dir, name), 'utf8'));
    if (!a.video?.src) continue;
    assert.match(a.video.uploadedAt || '', /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/, name);
  }
  assert.match(read('scripts/sns_video_followup.py'), /"uploadedAt"/);
});

test('[A18] 記事ページ: VideoObject を直接書かない・判定カードから見えない問いを作らない・FAQPage は表示している問いから', () => {
  const page = read('app/articles/[slug]/page.tsx');
  assert.doesNotMatch(page, /"@type": "VideoObject"/);
  assert.doesNotMatch(page, /youtube\.com\/embed/);
  // 再生部品（ArticleVideo）を出す今までの見た目の分かれ道の後ろでだけ VideoObject を足す
  const classic = page.slice(page.indexOf("return noirArticlePage("));
  assert.match(classic, /playableVideoJsonLd\(article\.video,/);
  assert.match(classic, /JSON.stringify\(pageJsonLd\)/);
  assert.match(classic, /<ArticleVideo video=\{article.video\} \/>/);
  assert.doesNotMatch(page.slice(0, page.indexOf("return noirArticlePage(")), /playableVideoJsonLd\(/);
  assert.match(page, /const faq = articleFaq\.map\(/);
  assert.doesNotMatch(page, /\$\{name\}は今すぐ使える？/);
  // 表示側も同じ articleFaq を出す（今までの見た目とノワール）
  assert.match(page, /<ArticleFaq items=\{articleFaq\} \/>/);
  assert.match(read('components/noir/noirArticlePage.tsx'), /<ArticleFaq items=\{articleFaq\} \/>/);
  // ノワールの見た目は解説動画の再生部品を出さない（だから VideoObject も出さない）
  assert.doesNotMatch(read('components/noir/noirArticlePage.tsx'), /ArticleVideo/);
});

test('[A18] FAQPage は空なら出さない', () => {
  assert.equal(sd.faqPageJsonLd([]), null);
  assert.equal(sd.faqPageJsonLd([{ q: '問い', a: '' }]), null);
  assert.equal(sd.faqPageJsonLd([{ q: '問い？', a: '答え。' }]).mainEntity[0].name, '問い？');
});

test('[A18] 編集責任者の Person に @id、/about に同じ @id の Person と AboutPage、ガイドの著者は編集部の @id', () => {
  const pub = read('lib/publisher.ts');
  assert.match(pub, /export const editorPersonId = `\$\{siteConfig\.url\}\/about#editor`/);
  assert.match(pub, /"@type": "Person", "@id": editorPersonId/);
  const about = read('app/about/page.tsx');
  assert.match(about, /"@type": "AboutPage"/);
  assert.match(about, /"@type": "Person",\s*"@id": editorPersonId/);
  assert.match(about, /\.\.\.publisherJsonLd/);
  assert.match(about, /application\/ld\+json/);
  const guide = read('components/HowtoGuideView.tsx');
  assert.match(guide, /author: authorJsonLd,/);
});

test('[A18] イベントページ: FAQPage の問いはすべてページの文字に出ている（実際に描いて確かめる）', async () => {
  const React = require('react');
  const { renderToStaticMarkup } = require('react-dom/server');
  const { getAllEvents } = require(path.join(root, 'lib/events.ts'));
  const Page = require(path.join(root, 'app/events/[slug]/page.tsx')).default;
  const events = getAllEvents();
  assert.ok(events.length > 0);
  const unescape = (s) => s.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#x27;/g, "'");
  for (const event of events) {
    const el = await Page({ params: Promise.resolve({ slug: event.slug }) });
    const html = renderToStaticMarkup(el);
    const ldRaw = [...html.matchAll(/<script type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/g)].map((m) => JSON.parse(m[1]));
    const faqs = ldRaw.flat().filter((x) => x['@type'] === 'FAQPage');
    assert.equal(faqs.length, 1, event.slug);
    const text = unescape(html.replace(/<script[\s\S]*?<\/script>/g, '').replace(/<[^>]+>/g, ''));
    for (const q of faqs[0].mainEntity) {
      assert.ok(text.includes(q.name), `${event.slug}: 見えない問い「${q.name}」`);
      assert.ok(text.includes(q.acceptedAnswer.text.split('。')[0].replace(/^日本時間/, '').split('：')[0]), `${event.slug}: 答えが見えていない「${q.acceptedAnswer.text}」`);
    }
  }
});

const ldOf = (html) => [...html.matchAll(/<script type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/g)].map((m) => JSON.parse(m[1])).flat();
const textOf = (html) => html.replace(/<script[\s\S]*?<\/script>/g, '').replace(/<[^>]+>/g, '').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#x27;/g, "'");

test('[A18] 記事ページを実際に描く: YouTube をもとにした記事は VideoObject なし・isBasedOn に元動画、解説動画のある記事だけ VideoObject、FAQPage の問いは本文に見えている', async () => {
  const { renderToStaticMarkup } = require('react-dom/server');
  const Page = require(path.join(root, 'app/articles/[slug]/page.tsx')).default;
  const render = async (slug) => renderToStaticMarkup(await Page({ params: Promise.resolve({ slug }) }));
  const yt = JSON.parse(read('content/articles/microsoft-foundry-agent-service-copilot-harness.json'));
  const html = await render(yt.slug);
  const ld = ldOf(html);
  assert.equal(ld.filter((x) => x['@type'] === 'VideoObject').length, 0);
  assert.doesNotMatch(JSON.stringify(ld), /VideoObject|youtube\.com\/embed/);
  assert.equal(ld.find((x) => x['@type'] === 'NewsArticle').isBasedOn, yt.videoUrl);
  // 解説動画（ArticleVideo）を出す記事
  const own = await render('openai-grid-protectors-program');
  const ownLd = ldOf(own);
  const vo = ownLd.filter((x) => x['@type'] === 'VideoObject');
  assert.equal(vo.length, 1);
  assert.match(vo[0].contentUrl, /^https:\/\/ai-tech-express\.jp\/video\/.+\.mp4$/);
  assert.ok(vo[0].uploadDate);
  for (const page of [html, own]) {
    const faq = ldOf(page).find((x) => x['@type'] === 'FAQPage');
    if (!faq) continue;
    const text = textOf(page);
    for (const q of faq.mainEntity) assert.ok(text.includes(q.name), `見えない問い「${q.name}」`);
  }
});

test('[A18] /about を実際に描く: AboutPage・発行元・編集責任者の Person（記事の editor と同じ @id）、/about へのリンクは今のまま', () => {
  const { renderToStaticMarkup } = require('react-dom/server');
  const About = require(path.join(root, 'app/about/page.tsx')).default;
  const html = renderToStaticMarkup(About());
  const ld = ldOf(html);
  const { editorPersonId, editorInCharge } = require(path.join(root, 'lib/publisher.ts'));
  assert.ok(ld.some((x) => x['@type'] === 'AboutPage'));
  assert.ok(ld.some((x) => x['@type'] === 'NewsMediaOrganization' && x['@id'].endsWith('/#publisher')));
  const person = ld.find((x) => x['@type'] === 'Person');
  assert.equal(person['@id'], editorPersonId);
  assert.ok(textOf(html).includes(person.name), '名前は表に見えているものだけ');
  assert.ok(textOf(html).includes(person.jobTitle));
  assert.equal(editorInCharge('public').jsonLd['@id'], editorPersonId);
});
