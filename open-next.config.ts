import { defineCloudflareConfig } from "@opennextjs/cloudflare";
import kvIncrementalCache from "@opennextjs/cloudflare/overrides/incremental-cache/kv-incremental-cache";
import staticAssetsIncrementalCache from "@opennextjs/cloudflare/overrides/incremental-cache/static-assets-incremental-cache";

import type { IncrementalCache, Queue } from "@opennextjs/aws/types/overrides.js";

/**
 * ISR のキャッシュ。実行時に作ったもの（再生成・初回アクセスの古い記事）は KV、
 * ビルド時に作ったものは静的アセット（scripts/cf_content.mjs が cdn-cgi/_next_cache へ写す）から読む。
 * KV にビルド結果を毎回書き込むと 200MB・20分以上かかるため、アップロードの速い静的アセットに置く。
 * キーにビルド ID が入るので、デプロイをまたいで古いものが混ざることはない。
 * （R2 はダッシュボードで有効化が必要。有効化したら KV の代わりに r2-incremental-cache でもよい）
 *
 * 読む順は静的アセット → KV。デプロイ直後はビルド ID が新しいので KV は必ず空振りし、
 * その空振り（各地のエッジで初回は中央まで問い合わせる）が初回表示を数百ms遅らせていた。
 * 再生成をしない（下の noRevalidation）ので、ビルド時に作ったページが KV に書かれることはなく、順番を変えても中身は同じ
 */
const kvOverAssets: IncrementalCache = {
  name: "saisoku-kv-over-assets",
  async get(key, cacheType) {
    if (cacheType !== "composable") {
      const fromAssets = await staticAssetsIncrementalCache.get(key, cacheType);
      if (fromAssets) return fromAssets;
    }
    return kvIncrementalCache.get(key, cacheType);
  },
  set: (key, value, cacheType) => kvIncrementalCache.set(key, value, cacheType),
  delete: (key) => kvIncrementalCache.delete(key),
};

/**
 * 時間経過による再生成はしない（古くなっても作り直さず、そのまま返す）。
 * 記事が増えるたびにデプロイしてキャッシュ（ビルド ID ごと）が丸ごと新しくなるので、再生成の必要がない。
 * Workers では再生成の判定が isolate ごとにずれて毎回「古い」扱いになり、CPU を無駄に使うため止めている
 */
const noRevalidation: Queue = {
  name: "saisoku-no-revalidation",
  send: async () => {},
};

// revalidateTag は使っていないのでタグキャッシュは不要
export default defineCloudflareConfig({
  incrementalCache: kvOverAssets,
  queue: noRevalidation,
});
