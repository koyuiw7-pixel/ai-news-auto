/**
 * ノワールの記事の見出しの書体（Zen Kaku Gothic New の 700・900）と数字の書体（Inter）。2026-11-07 オーナー承認（台帳 W8・W36）。
 * 書体はノワールの記事だけで使う（今までのページには読み込まない）。
 * Google Fonts の text= で、このページの表紙・要点・見出しに出る文字だけのファイルにする（数 KB。@font-face は書体ごとに1つ）。
 * スタイルシートはスクリプトから足すので描画を止めない。届くまではヒラギノ・Noto で出し、届いたら差し替わる
 * （題名は高さの決まった表紙の中、見出しは画面の下なので、差し替わっても上の物は動かない）
 */
export function noirFontHref(glyphs: string): string {
  return `https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@700;900&family=Inter:wght@500;600;800&display=swap&text=${encodeURIComponent(glyphs)}`;
}

/** 最初に開いたとき用（描画の前に読み始める）。サイト内の移動で開いたときは components/noir/NoirChrome.tsx が足す */
export default function NoirFonts({ href }: { href: string }) {
  const script = `try{var d=document,h=d.head;if(!d.getElementById("nr-fonts")){var c=d.createElement("link");c.rel="preconnect";c.href="https://fonts.gstatic.com";c.crossOrigin="";h.appendChild(c);var l=d.createElement("link");l.id="nr-fonts";l.rel="stylesheet";l.href=${JSON.stringify(href)};h.appendChild(l)}}catch(e){}`;
  return <script dangerouslySetInnerHTML={{ __html: script }} />;
}
