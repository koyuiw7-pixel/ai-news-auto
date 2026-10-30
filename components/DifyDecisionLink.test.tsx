/** Nextのpathnameだけを差し替え、Footer用Linkの実際のpropsを検証する。 */
import assert from "node:assert/strict";
import DifyDecisionLink from "./DifyDecisionLink";

const pathMock = globalThis as typeof globalThis & { __testDifyPathname: string | null };
const guide = "/choose/dify-hosting";
const label = "Difyの無料利用・VPSの選び方";
let passed = 0;
for (const [pathname, expected] of [
  ["/guides/dify-free-api-cost", `${guide}?sa_from=difyfree`],
  ["/guides/dify-1-18-startup-check", `${guide}?sa_from=difystartup`],
  ["/articles/unrelated", guide],
  [guide, guide],
  [null, guide],
] as const) {
  pathMock.__testDifyPathname = pathname;
  const element = DifyDecisionLink({ children: label, className: "existing-style" });
  assert.equal(element.props.href, expected);
  assert.equal(element.props.children, label);
  assert.equal(element.props.className, "existing-style");
  passed++;
}
console.log(`${passed} footer-link checks passed; Next props only, no navigation or ASP requests.`);
