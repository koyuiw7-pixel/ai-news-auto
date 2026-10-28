/**
 * Web Push の暗号化と送信（外部ライブラリなし。WebCrypto だけ）。
 *
 * - 本文の暗号化: RFC 8291（aes128gcm, RFC 8188）
 * - 送信者の証明: RFC 8292（VAPID。ES256 の JWT）
 *
 * 正しさは cloudflare/webpush.test.ts が RFC 8291 付録 A の公式の例と突き合わせて確かめる
 * （node cloudflare/webpush.test.ts）。
 */

export type PushKeys = { p256dh: string; auth: string };
export type PushTarget = { endpoint: string; keys: PushKeys };
export type Vapid = { publicKey: string; privateKey: string; subject: string };

const te = new TextEncoder();
type Bytes = Uint8Array<ArrayBuffer>;

export function b64urlEncode(bytes: Uint8Array | ArrayBuffer): string {
  const view = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let bin = "";
  for (const b of view) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function b64urlDecode(text: string): Bytes {
  const b64 = text.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((text.length + 3) % 4);
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function concat(...parts: Uint8Array[]): Bytes {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let offset = 0;
  for (const p of parts) {
    out.set(p, offset);
    offset += p.length;
  }
  return out;
}

async function hmac(key: Bytes, data: Bytes): Promise<Bytes> {
  const k = await crypto.subtle.importKey("raw", key, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return new Uint8Array(await crypto.subtle.sign("HMAC", k, data));
}

/** 公開鍵（非圧縮 65 バイト）と秘密鍵（32 バイト）から JWK を作る */
function jwk(publicRaw: Uint8Array, privateRaw?: Uint8Array): JsonWebKey {
  return {
    kty: "EC",
    crv: "P-256",
    x: b64urlEncode(publicRaw.slice(1, 33)),
    y: b64urlEncode(publicRaw.slice(33, 65)),
    ...(privateRaw ? { d: b64urlEncode(privateRaw) } : {}),
    ext: true,
  };
}

/** 送信者側の使い捨て鍵（テストでは固定値を渡す） */
export type EncryptOptions = { senderPrivate?: Bytes; senderPublic?: Bytes; salt?: Bytes };

/** RFC 8291: 購読者の鍵で本文を暗号化し、aes128gcm の本文（ヘッダー付き）を返す */
export async function encryptPayload(keys: PushKeys, plaintext: Uint8Array, opts: EncryptOptions = {}): Promise<Bytes> {
  const uaPublic = b64urlDecode(keys.p256dh);
  const authSecret = b64urlDecode(keys.auth);
  if (uaPublic.length !== 65 || uaPublic[0] !== 4) throw new Error("bad p256dh");
  if (authSecret.length !== 16) throw new Error("bad auth");

  let asPrivate: CryptoKey;
  let asPublic: Bytes;
  if (opts.senderPrivate && opts.senderPublic) {
    asPrivate = await crypto.subtle.importKey("jwk", jwk(opts.senderPublic, opts.senderPrivate), { name: "ECDH", namedCurve: "P-256" }, false, ["deriveBits"]);
    asPublic = opts.senderPublic;
  } else {
    const pair = (await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"])) as CryptoKeyPair;
    asPrivate = pair.privateKey;
    asPublic = new Uint8Array((await crypto.subtle.exportKey("raw", pair.publicKey)) as ArrayBuffer);
  }

  const uaKey = await crypto.subtle.importKey("raw", uaPublic, { name: "ECDH", namedCurve: "P-256" }, false, []);
  const ecdhSecret = new Uint8Array(
    await crypto.subtle.deriveBits({ name: "ECDH", public: uaKey } as EcdhKeyDeriveParams, asPrivate, 256),
  );

  // IKM = HKDF(auth_secret, ecdh_secret, "WebPush: info" || 0x00 || ua_public || as_public, 32)
  const prkKey = await hmac(authSecret, ecdhSecret);
  const keyInfo = concat(te.encode("WebPush: info\0"), uaPublic, asPublic);
  const ikm = await hmac(prkKey, concat(keyInfo, new Uint8Array([1])));

  const salt = opts.salt ?? crypto.getRandomValues(new Uint8Array(16));
  const prk = await hmac(salt, ikm);
  const cek = (await hmac(prk, concat(te.encode("Content-Encoding: aes128gcm\0"), new Uint8Array([1])))).slice(0, 16);
  const nonce = (await hmac(prk, concat(te.encode("Content-Encoding: nonce\0"), new Uint8Array([1])))).slice(0, 12);

  // 1レコードだけ。末尾に区切り 0x02（最後のレコード）を付ける
  const aesKey = await crypto.subtle.importKey("raw", cek, "AES-GCM", false, ["encrypt"]);
  const cipher = new Uint8Array(
    await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce }, aesKey, concat(plaintext, new Uint8Array([2]))),
  );

  // ヘッダー: salt(16) || rs(4) || idlen(1) || keyid(送信者の公開鍵 65)
  const rs = 4096;
  const header = concat(salt, new Uint8Array([(rs >>> 24) & 255, (rs >>> 16) & 255, (rs >>> 8) & 255, rs & 255, asPublic.length]), asPublic);
  return concat(header, cipher);
}

const jwtCache = new Map<string, { token: string; exp: number }>();

/** RFC 8292: 送り先（プッシュサービスのオリジン）ごとの VAPID の JWT。12時間有効、同じ isolate では使い回す */
export async function vapidAuthorization(endpoint: string, vapid: Vapid): Promise<string> {
  const aud = new URL(endpoint).origin;
  const now = Math.floor(Date.now() / 1000);
  const cached = jwtCache.get(aud);
  let token = cached && cached.exp - now > 3600 ? cached.token : "";
  if (!token) {
    const exp = now + 12 * 3600;
    const header = b64urlEncode(te.encode(JSON.stringify({ typ: "JWT", alg: "ES256" })));
    const claims = b64urlEncode(te.encode(JSON.stringify({ aud, exp, sub: vapid.subject })));
    const pub = b64urlDecode(vapid.publicKey);
    const key = await crypto.subtle.importKey("jwk", jwk(pub, b64urlDecode(vapid.privateKey)), { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
    // WebCrypto の ECDSA 署名は r||s（64 バイト）で、JWS の ES256 と同じ形
    const sig = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, key, te.encode(`${header}.${claims}`));
    token = `${header}.${claims}.${b64urlEncode(sig)}`;
    jwtCache.set(aud, { token, exp });
  }
  return `vapid t=${token}, k=${vapid.publicKey}`;
}

export type SendResult = { ok: boolean; status: number; gone: boolean };

/** 1件送る。gone=true は購読が消えている（404/410）ので保存先から消してよい */
export async function sendPush(
  target: PushTarget,
  payload: unknown,
  vapid: Vapid,
  opts: { ttl?: number; urgency?: "very-low" | "low" | "normal" | "high"; topic?: string } = {},
): Promise<SendResult> {
  const body = await encryptPayload(target.keys, te.encode(JSON.stringify(payload)));
  const headers: Record<string, string> = {
    Authorization: await vapidAuthorization(target.endpoint, vapid),
    "Content-Encoding": "aes128gcm",
    "Content-Type": "application/octet-stream",
    TTL: String(opts.ttl ?? 6 * 3600),
    Urgency: opts.urgency ?? "high",
  };
  // 同じ topic の未配達の通知は新しいものに置き換わる（32文字以内の英数字と - _）
  if (opts.topic) headers.Topic = opts.topic.replace(/[^A-Za-z0-9_-]/g, "").slice(0, 32);
  const res = await fetch(target.endpoint, { method: "POST", headers, body });
  // 本文は読まずに捨てる（接続を早く返すため）
  res.body?.cancel().catch(() => {});
  return { ok: res.status >= 200 && res.status < 300, status: res.status, gone: res.status === 404 || res.status === 410 };
}
