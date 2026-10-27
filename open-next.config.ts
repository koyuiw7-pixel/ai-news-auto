import { defineCloudflareConfig } from "@opennextjs/cloudflare";
import kvIncrementalCache from "@opennextjs/cloudflare/overrides/incremental-cache/kv-incremental-cache";
import doQueue from "@opennextjs/cloudflare/overrides/queue/do-queue";

// ISR のキャッシュは KV（R2 はダッシュボードで有効化が必要なため。有効化したら r2-incremental-cache に替える）。
// revalidateTag は使っていないのでタグキャッシュは不要
export default defineCloudflareConfig({
  incrementalCache: kvIncrementalCache,
  queue: doQueue,
});
