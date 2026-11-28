import Link from "next/link";
import type { ReactNode } from "react";
import "./flagship.css";
import Checklist from "@/components/flagship/Checklist";
import FamilyBuilder from "@/components/flagship/FamilyBuilder";
import { dateJa, flagshipHref, orderedSources, type FlagshipSource, type FlagshipStory } from "@/lib/flagship";
import { thirdChildMaxTotal } from "@/lib/child-allowance";
import { siteConfig } from "@/site.config";

/**
 * 特集のページの見た目（/stories/<slug>。lib/flagship.ts）。
 * 上から: 答え（決まったこと／決まっていないこと）→ うちの計算 → もし案が通ったら（未決定）→ やることリスト → よくある疑問 → 出典。
 * 色はサイトの紺と赤（app/globals.css のトークン）。ダークは右上のボタンで選んだとき（:root[data-theme="dark"]）。
 */

/** 1万円で割り切れる額は「657万円」、それ以外は「6,571,000円」 */
export function manYen(value: number): string {
  return value % 10000 === 0 ? `${(value / 10000).toLocaleString("ja-JP")}万円` : `${Math.round(value).toLocaleString("ja-JP")}円`;
}

function timeJa(iso: string): string {
  const d = new Date(iso);
  const jst = new Date(d.getTime() + 9 * 3600 * 1000);
  return `${jst.getUTCFullYear()}年${jst.getUTCMonth() + 1}月${jst.getUTCDate()}日 ${String(jst.getUTCHours()).padStart(2, "0")}:${String(jst.getUTCMinutes()).padStart(2, "0")}`;
}

/** 同じ発信元が2つ以上ある（こども家庭庁など）ときは、名前に資料の題名を足す（「出典：こども家庭庁、こども家庭庁」にしない） */
export function sourceLabel(source: FlagshipSource, all: FlagshipSource[]): string {
  if (all.filter((s) => s.org === source.org).length < 2) return source.org;
  const short = source.title.replace(/（[^）]*）/g, "").trim();
  return `${source.org}「${short}」`;
}

function SourceLink({ source, all }: { source: FlagshipSource; all: FlagshipSource[] }) {
  return (
    <a href={source.url} target="_blank" rel="noopener" className="fs-srclink">
      {sourceLabel(source, all)}
    </a>
  );
}

function Refs({ ids, map }: { ids: string[]; map: Map<string, FlagshipSource> }) {
  const all = [...map.values()];
  const list = ids.map((id) => map.get(id)).filter((s): s is FlagshipSource => Boolean(s));
  if (list.length === 0) return null;
  return (
    <span className="fs-src">
      出典：
      {list.map((s, i) => (
        <span key={s.id}>
          {i > 0 ? "、" : ""}
          <SourceLink source={s} all={all} />
        </span>
      ))}
    </span>
  );
}

export default function FlagshipStoryView({ story, adSlot }: { story: FlagshipStory; adSlot?: ReactNode }) {
  const sources = orderedSources(story);
  const map = new Map(sources.map((s) => [s.id, s]));
  const [y, m] = story.asOf.split("-").map(Number);
  const asOf = { year: y, month: m };
  const max = thirdChildMaxTotal(story.proposal.insightBirth);
  const insight = story.proposal.insight.replace("{max}", manYen(max.total));
  const sourceLinks = Object.fromEntries(sources.map((s) => [s.id, <SourceLink key={s.id} source={s} all={sources} />]));
  const url = `${siteConfig.url}${flagshipHref(story.slug)}`;
  const host = url.replace(/^https?:\/\//, "");
  const official = sources.filter((s) => s.kind === "official");
  const reports = sources.filter((s) => s.kind === "report");

  return (
    <article className="fs" data-flagship={story.slug}>
      <nav aria-label="パンくず" className="fs-crumbs">
        <Link href="/">ホーム</Link>
        <span aria-hidden="true">/</span>
        <Link href={story.genre.href}>{story.genre.label}</Link>
        <span aria-hidden="true">/</span>
        <span>特集</span>
      </nav>

      {/* 答え（最初の画面） */}
      <header className="fs-hero" id="answer">
        <div className="fs-hero-grid" aria-hidden="true" />
        <div className="fs-hero-in">
          <p className="fs-kick">
            <span className="fs-tag">特集</span>
            <span>{story.kicker}</span>
            <span className="fs-asof">
              <time dateTime={story.asOf}>{dateJa(story.asOf)}</time>時点
            </span>
          </p>
          <h1 className="fs-h1">{story.title}</h1>
          <p className="fs-answer">{story.answer.lead}</p>
          <p className="fs-answer-sub">{story.answer.sub}</p>
          <a href="#calc" className="fs-jump" data-fs-jump="">
            うちの額をいま計算する
          </a>

          <div className="fs-status" id="status">
            <section className="fs-col" data-kind="decided" aria-labelledby="fs-decided">
              <h2 id="fs-decided" className="fs-col-h">
                <span className="fs-dot" aria-hidden="true" />
                決まったこと
              </h2>
              <ul>
                {story.status.decided.map((item) => (
                  <li key={item.label}>
                    <b>{item.label}</b>
                    <span>{item.detail}</span>
                    <Refs ids={item.sources} map={map} />
                  </li>
                ))}
              </ul>
            </section>
            <section className="fs-col" data-kind="undecided" aria-labelledby="fs-undecided">
              <h2 id="fs-undecided" className="fs-col-h">
                <span className="fs-dot" aria-hidden="true" />
                決まっていないこと
              </h2>
              <ul>
                {story.status.undecided.map((item) => (
                  <li key={item.label}>
                    <b>{item.label}</b>
                    <span>{item.detail}</span>
                    <Refs ids={item.sources} map={map} />
                  </li>
                ))}
              </ul>
            </section>
          </div>

          <div className="fs-hero-foot">
            <a href="#calc" className="fs-btn fs-btn-hero">
              うちの場合を計算する
            </a>
            <p className="fs-byline">
              編集：<Link href="/about" rel="author">{siteConfig.author}</Link>
              <span>
                公開 <time dateTime={story.publishedAt}>{timeJa(story.publishedAt)}</time>
              </span>
              {story.updatedAt !== story.publishedAt ? (
                <span>
                  更新 <time dateTime={story.updatedAt}>{timeJa(story.updatedAt)}</time>
                </span>
              ) : null}
            </p>
          </div>
        </div>
      </header>

      <nav aria-label="この特集の中身" className="fs-toc">
        <a href="#calc">うちの計算</a>
        <a href="#proposal">もし案が通ったら</a>
        <a href="#checklist">やることリスト</a>
        <a href="#faq">よくある疑問</a>
        <a href="#sources">出典</a>
      </nav>

      {/* うちの計算 */}
      <section className="fs-sec" aria-labelledby="calc">
        <h2 id="calc" className="fs-h2">
          今の制度で、うちはいくら？
        </h2>
        <p className="fs-lead">
          子どもを上の子から足してください。こども家庭庁の案内どおりの数え方で、第何子になるか、1か月の合計、次の支給の月と額、1年分がその場で出ます。
        </p>
        <FamilyBuilder
          asOf={asOf}
          next={story.next}
          adSlot={adSlot}
          shareTitle="うちの児童手当（今の制度で計算）"
          shareNote={`第3子に1000万円は${dateJa(story.asOf)}時点で決まっていません（提言案）`}
          shareUrl={host}
        />
        <p className="fs-src fs-src-block">
          計算の出典：
          {["cfa-annai", "cfa-count", "cfa-gaiyou", "law"].map((id, i) => (map.get(id) ? <span key={id}>{i > 0 ? "、" : ""}<SourceLink source={map.get(id)!} all={sources} /></span> : null))}
          。もっとくわしい計算は<Link href={story.tool} className="fs-inlink">児童手当の計算ツール</Link>でもできます。
        </p>
      </section>

      {/* もし案が通ったら（未決定） */}
      <section className="fs-sec" aria-labelledby="proposal">
        <div className="fs-proposal" data-undecided="">
          <p className="fs-badge-undecided">{story.proposal.badge}</p>
          <h2 id="proposal" className="fs-h2">
            {story.proposal.title}
          </h2>
          <p className="fs-lead">{story.proposal.lead}</p>
          <div className="fs-known">
            <p className="fs-eyebrow">案に入っていると報じられたこと</p>
            <ul>
              {story.proposal.known.map((item) => (
                <li key={item.text}>
                  <span>{item.text}</span>
                  <Refs ids={item.sources} map={map} />
                </li>
              ))}
            </ul>
          </div>
          <div className="fs-watch">
            <p className="fs-eyebrow">次に見ること</p>
            <ol>
              {story.proposal.watch.map((item) => (
                <li key={item.what}>
                  <span className="fs-watch-when">{item.when}</span>
                  <span className="fs-watch-body">
                    <b>{item.what}</b>
                    <span>{item.detail}</span>
                    <Refs ids={item.sources} map={map} />
                  </span>
                </li>
              ))}
            </ol>
          </div>
          <div className="fs-insight">
            <p className="fs-eyebrow">サイソクの見方</p>
            <p>{insight}</p>
            <Refs ids={story.proposal.insightSources} map={map} />
          </div>
        </div>
      </section>

      {/* やることリスト */}
      <section className="fs-sec" aria-labelledby="checklist">
        <h2 id="checklist" className="fs-h2">
          うちのやることリスト
        </h2>
        <p className="fs-lead">児童手当は、出さないと受け取れない手続きがあります。期限の近いものから並べました。チェックはこの画面の中だけで、保存はしません。</p>
        <Checklist items={story.checklist} sourceLinks={sourceLinks} />
      </section>

      {/* よくある疑問（FAQPage の構造化データと同じ文） */}
      <section className="fs-sec" aria-labelledby="faq">
        <h2 id="faq" className="fs-h2">
          よくある疑問
        </h2>
        <div className="fs-faq">
          {story.faq.map((row, i) => (
            <details key={row.q} open={i === 0}>
              <summary>{row.q}</summary>
              <p>{row.a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* 出典（公式が先、報道が後） */}
      <section className="fs-sec" aria-labelledby="sources">
        <h2 id="sources" className="fs-h2">
          出典
        </h2>
        <p className="fs-lead">数字と手続きは公式の案内、提言案の中身は報道によります。開いて確かめた日を書いています。</p>
        {[
          { label: "公式の案内", list: official },
          { label: "報道", list: reports },
        ].map((group) => (
          <div key={group.label} className="fs-srcgroup">
            <p className="fs-eyebrow">{group.label}</p>
            <ul className="fs-cards">
              {group.list.map((s) => (
                <li key={s.id} id={`src-${s.id}`}>
                  <a href={s.url} target="_blank" rel="noopener" className="fs-card" data-kind={s.kind}>
                    <span className="fs-card-org">{s.org}</span>
                    <b>{s.title}</b>
                    <span className="fs-card-date">
                      <time dateTime={s.checked}>{dateJa(s.checked)}</time>に確認
                    </span>
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ))}
        <p className="fs-note">
          この特集はAIを使って作り、数字と事実は上の出典のページで確かめて載せています。制度や案の中身は変わることがあります。誤りに気づいたら
          <Link href="/corrections" className="fs-inlink">訂正の方針</Link>のとおりに直します。
        </p>
      </section>

      <nav aria-label="関連するページ" className="fs-related">
        <Link href={`/articles/${story.article}`} className="fs-next-link">
          <b>ニュースの記事を読む</b>
          <small>提言案の報道と、今の児童手当の申請期限をまとめた記事です。</small>
        </Link>
        <Link href={story.tool} className="fs-next-link">
          <b>児童手当の計算ツール</b>
          <small>よくある家族の例の表と、生まれた年月で計算するときのきまりがあります。</small>
        </Link>
      </nav>
    </article>
  );
}
