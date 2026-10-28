/**
 * Web Push の暗号化を RFC 8291 付録 A の公式の例と突き合わせる（node cloudflare/webpush.test.ts）。
 * VAPID の署名も、作った JWT を公開鍵で検証できるかで確かめる。
 */
import { b64urlDecode, b64urlEncode, encryptPayload, vapidAuthorization } from "./webpush.ts";

let failed = 0;
function check(name: string, ok: boolean, detail = "") {
  console.log(`${ok ? "ok  " : "FAIL"} ${name}${ok ? "" : ` ${detail}`}`);
  if (!ok) failed++;
}

// RFC 8291 付録 A
const body = await encryptPayload(
  { p256dh: "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4", auth: "BTBZMqHH6r4Tts7J_aSIgg" },
  new TextEncoder().encode("When I grow up, I want to be a watermelon"),
  {
    senderPrivate: b64urlDecode("yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"),
    senderPublic: b64urlDecode("BP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A8"),
    salt: b64urlDecode("DGv6ra1nlYgDCS1FRnbzlw"),
  },
);
const expected =
  "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_yl95bQpu6cVPTpK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN";
check("RFC 8291 appendix A", b64urlEncode(body) === expected, b64urlEncode(body));

// VAPID: 使い捨ての鍵で JWT を作り、公開鍵で検証する
const pair = (await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign", "verify"])) as CryptoKeyPair;
const pub = new Uint8Array((await crypto.subtle.exportKey("raw", pair.publicKey)) as ArrayBuffer);
const priv = (await crypto.subtle.exportKey("jwk", pair.privateKey)).d!;
const auth = await vapidAuthorization("https://fcm.googleapis.com/fcm/send/abc", {
  publicKey: b64urlEncode(pub),
  privateKey: priv,
  subject: "https://ai-tech-express.jp",
});
const m = /^vapid t=([^.]+)\.([^.]+)\.([^,]+), k=(.+)$/.exec(auth);
check("VAPID header shape", !!m);
if (m) {
  const valid = await crypto.subtle.verify(
    { name: "ECDSA", hash: "SHA-256" },
    pair.publicKey,
    b64urlDecode(m[3]),
    new TextEncoder().encode(`${m[1]}.${m[2]}`),
  );
  check("VAPID signature verifies", valid);
  const claims = JSON.parse(new TextDecoder().decode(b64urlDecode(m[2])));
  check("VAPID aud", claims.aud === "https://fcm.googleapis.com", JSON.stringify(claims));
  check("VAPID k", m[4] === b64urlEncode(pub));
}

if (failed) process.exit(1);
