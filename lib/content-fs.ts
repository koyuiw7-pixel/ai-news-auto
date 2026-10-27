import nodeFs from "node:fs";
import path from "node:path";

/**
 * コンテンツ（記事 JSON・設定ファイル・フォント）を読むための fs の薄い代役。
 *
 * Vercel / ビルド時は node:fs そのまま。
 * Cloudflare Workers ではファイルを同梱できないので、cloudflare/worker.ts が
 * 静的アセット（/_content/*）から先読みして globalThis.__SAISOKU_VFS__ に置いた中身を返す。
 */
export type VirtualFs = {
  /** cwd からの相対パス → 中身 */
  files: Map<string, string | Uint8Array>;
  /** cwd からの相対パス → ファイル名一覧 */
  dirs: Map<string, string[]>;
  /** この接頭辞の下は仮想側だけを見る（無ければ ENOENT） */
  roots: string[];
};

function vfs(): VirtualFs | undefined {
  return (globalThis as { __SAISOKU_VFS__?: VirtualFs }).__SAISOKU_VFS__;
}

/** Cloudflare で動いているか（仮想 fs が用意されているか） */
export function hasVirtualFs(): boolean {
  return vfs() !== undefined;
}

function rel(p: string): string | null {
  const r = path.relative(/*turbopackIgnore: true*/ process.cwd(), path.resolve(/*turbopackIgnore: true*/ process.cwd(), p)).split(path.sep).join("/");
  return r.startsWith("..") ? null : r;
}

function managed(v: VirtualFs, r: string): boolean {
  return v.roots.some((root) => r === root || r.startsWith(`${root}/`));
}

function enoent(p: string): Error {
  return Object.assign(new Error(`ENOENT: no such file or directory, open '${p}'`), { code: "ENOENT" });
}

function readVirtual(p: string): string | Uint8Array | undefined {
  const v = vfs();
  if (!v) return undefined;
  const r = rel(p);
  if (r === null || !managed(v, r)) return undefined;
  const data = v.files.get(r);
  if (data === undefined) throw enoent(p);
  return data;
}

function encode(data: string | Uint8Array, encoding?: unknown): string | Buffer {
  if (encoding) return typeof data === "string" ? data : Buffer.from(data).toString(encoding as BufferEncoding);
  return typeof data === "string" ? Buffer.from(data) : Buffer.from(data);
}

export function existsSync(p: string): boolean {
  const v = vfs();
  const r = v ? rel(p) : null;
  if (v && r !== null && managed(v, r)) return v.files.has(r) || v.dirs.has(r);
  return nodeFs.existsSync(p);
}

export function readdirSync(p: string): string[] {
  const v = vfs();
  const r = v ? rel(p) : null;
  if (v && r !== null && managed(v, r)) {
    const list = v.dirs.get(r);
    if (!list) throw enoent(p);
    return list;
  }
  return nodeFs.readdirSync(p);
}

export function readFileSync(p: string): Buffer;
export function readFileSync(p: string, encoding: BufferEncoding | { encoding: BufferEncoding }): string;
export function readFileSync(p: string, encoding?: unknown): string | Buffer {
  const enc = typeof encoding === "object" && encoding ? (encoding as { encoding: string }).encoding : encoding;
  const data = readVirtual(p);
  if (data !== undefined) return encode(data, enc);
  return nodeFs.readFileSync(p, enc as BufferEncoding);
}

export const promises = {
  async readFile(p: string): Promise<Buffer> {
    const data = readVirtual(p);
    if (data !== undefined) return Buffer.from(data);
    return nodeFs.promises.readFile(p);
  },
};

const fs = { existsSync, readdirSync, readFileSync, promises };
export default fs;
