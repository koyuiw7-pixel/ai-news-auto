import { build } from "esbuild";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const dir = await mkdtemp(join(tmpdir(), "saisoku-aff-test-"));
try {
  const outfile = join(dir, "test.mjs");
  await build({ entryPoints: ["cloudflare/aff.test.ts"], outfile, bundle: true, platform: "node", format: "esm", logLevel: "warning" });
  await import(pathToFileURL(outfile).href);
  const clientOutfile = join(dir, "client-test.mjs");
  await build({ entryPoints: ["components/RevenueFunnelTracker.test.ts"], outfile: clientOutfile, bundle: true, platform: "node", format: "esm", logLevel: "warning", plugins: [{
    name: "unused-react-hooks-for-client-event-unit-test",
    setup(build) {
      build.onResolve({ filter: /^(react|next\/navigation)$/ }, args => ({ path: args.path, namespace: "test-hooks" }));
      build.onLoad({ filter: /.*/, namespace: "test-hooks" }, () => ({ contents: "export const useEffect=()=>{}; export const useRef=()=>({current:null}); export const usePathname=()=>null;", loader: "js" }));
    },
  }] });
  await import(pathToFileURL(clientOutfile).href);
} finally {
  await rm(dir, { recursive: true, force: true });
}
