/**
 * Web Push crypto (Session 33) — VAPID (RFC 8292) request signing and
 * aes128gcm message encryption (RFC 8291/RFC 8188), hand-implemented on
 * top of the Workers runtime's native `crypto.subtle` (Web Crypto API).
 *
 * Deliberately zero external dependencies (no `web-push` npm package):
 * this repo has no build/bundle step of its own — Cloudflare's Git
 * integration runs `wrangler deploy` on Cloudflare's own infrastructure
 * (ADR-0029a), and this session has no way to verify that pipeline would
 * actually run `npm install` for a Workers-with-static-assets project
 * without introducing and testing a `package.json` this session can't
 * check end-to-end. `crypto.subtle` needs nothing installed at all — it's
 * part of the Workers runtime itself, same as any browser.
 *
 * Every function here is pure/stateless given its inputs — no KV, no
 * fetch, no env access — so the encryption logic itself is testable in
 * any JS engine with WebCrypto (this session verified it in a real
 * Chromium browser console, not just by reading the RFCs — see
 * PROGRESS.md's Session 33 addendum for exactly what was checked and
 * what wasn't).
 */

function base64UrlEncode(bytes) {
  let binary = "";
  const arr = new Uint8Array(bytes);
  for (let i = 0; i < arr.length; i++) binary += String.fromCharCode(arr[i]);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function base64UrlDecode(str) {
  const padded = str.replace(/-/g, "+").replace(/_/g, "/");
  const withPadding = padded + "===".slice((padded.length + 3) % 4);
  const binary = atob(withPadding);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function concatBytes(...parts) {
  const total = parts.reduce((sum, p) => sum + p.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const p of parts) {
    out.set(p, offset);
    offset += p.length;
  }
  return out;
}

/** Import this project's stored VAPID key pair (both base64url-encoded —
 * the public key as the 65-byte uncompressed EC point, the private key
 * as the 32-byte raw scalar, exactly what `generate_vapid_keys.py`
 * printed) as a Web Crypto `CryptoKey` usable for ECDSA signing.
 *
 * Web Crypto has no "raw" import format for EC *private* keys (only
 * public keys can be imported that way) — so the private scalar is
 * wrapped into a minimal JWK, reusing the public key's x/y coordinates
 * (already known, no extra derivation needed since both keys were
 * generated together and stored as a pair).
 */
async function importVapidPrivateKey(publicKeyB64Url, privateKeyB64Url) {
  const publicBytes = base64UrlDecode(publicKeyB64Url);
  const x = publicBytes.slice(1, 33);
  const y = publicBytes.slice(33, 65);
  const jwk = {
    kty: "EC",
    crv: "P-256",
    x: base64UrlEncode(x),
    y: base64UrlEncode(y),
    d: privateKeyB64Url,
    ext: true,
  };
  return crypto.subtle.importKey("jwk", jwk, { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
}

/** Build and sign a VAPID JWT (RFC 8292) for one push service `audience`
 * (the scheme+host of the subscription's own endpoint — VAPID JWTs are
 * scoped per push-service origin, not per subscription or per message).
 * `subject` is a mailto: or https: URL identifying the sender, per spec —
 * required by every push service so they have a way to contact the
 * sender about a misbehaving VAPID key, not used for anything else here.
 */
async function buildVapidJwt(audience, subject, publicKeyB64Url, privateKeyB64Url) {
  const header = { typ: "JWT", alg: "ES256" };
  const claims = {
    aud: audience,
    exp: Math.floor(Date.now() / 1000) + 12 * 60 * 60, // RFC 8292 recommends <= 24h; 12h is comfortably inside that
    sub: subject,
  };
  const encoder = new TextEncoder();
  const signingInput = `${base64UrlEncode(encoder.encode(JSON.stringify(header)))}.${base64UrlEncode(encoder.encode(JSON.stringify(claims)))}`;

  const privateKey = await importVapidPrivateKey(publicKeyB64Url, privateKeyB64Url);
  // Web Crypto's ECDSA signatures are already raw (r || s, 64 bytes) —
  // exactly JOSE/JWS's ES256 format, no ASN.1 DER re-encoding needed.
  const signature = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, privateKey, encoder.encode(signingInput));

  return `${signingInput}.${base64UrlEncode(signature)}`;
}

/** Encrypt `payloadBytes` for one push subscription per RFC 8291
 * ("Message Encryption for Web Push") + RFC 8188's aes128gcm content
 * encoding — the wire format every real push service (FCM, Mozilla's
 * autopush, etc.) expects, VAPID or not. Returns the exact bytes to POST
 * as the request body.
 *
 * `receiverPublicKeyB64Url`/`authSecretB64Url` come straight from the
 * browser's PushSubscription object (`keys.p256dh`/`keys.auth`) — never
 * generated here, since they're the receiver's half of the ECDH exchange.
 */
async function encryptPushPayload(payloadBytes, receiverPublicKeyB64Url, authSecretB64Url) {
  const receiverPublicBytes = base64UrlDecode(receiverPublicKeyB64Url);
  const authSecret = base64UrlDecode(authSecretB64Url);

  const receiverPublicKey = await crypto.subtle.importKey(
    "raw",
    receiverPublicBytes,
    { name: "ECDH", namedCurve: "P-256" },
    false,
    []
  );

  const ephemeralKeyPair = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]);
  const ephemeralPublicBytes = new Uint8Array(await crypto.subtle.exportKey("raw", ephemeralKeyPair.publicKey));

  const ecdhSecretBits = await crypto.subtle.deriveBits(
    { name: "ECDH", public: receiverPublicKey },
    ephemeralKeyPair.privateKey,
    256
  );
  const ecdhSecret = new Uint8Array(ecdhSecretBits);

  // Stage 1 (RFC 8291 §3.3): combine the ECDH secret with the
  // subscription's own auth secret into one "IKM" both endpoints can
  // derive identically — the browser has ecdhSecret via its own private
  // key + our ephemeral public key (sent in the message header below),
  // and already has authSecret from its own subscription.
  const encoder = new TextEncoder();
  const keyInfo = concatBytes(
    encoder.encode("WebPush: info\0"),
    receiverPublicBytes,
    ephemeralPublicBytes
  );
  const ikm = await hkdf(authSecret, ecdhSecret, keyInfo, 32);

  // Stage 2 (RFC 8188 §2.1): a fresh random 16-byte salt derives the
  // actual AES key + nonce from IKM — distinct from authSecret above
  // despite RFC 8188 also calling this a "salt"; different values, same
  // word, by unfortunate spec-naming coincidence.
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const cek = await hkdf(salt, ikm, encoder.encode("Content-Encoding: aes128gcm\0"), 16);
  const nonce = await hkdf(salt, ikm, encoder.encode("Content-Encoding: nonce\0"), 12);

  const cekKey = await crypto.subtle.importKey("raw", cek, { name: "AES-GCM" }, false, ["encrypt"]);
  // RFC 8188 §2: a single-record message's plaintext gets one trailing
  // 0x02 delimiter byte (no further padding needed for a short payload
  // like a scan summary) before AES-128-GCM sealing; the browser strips
  // this delimiter back off after decrypting.
  const paddedPlaintext = concatBytes(payloadBytes, new Uint8Array([2]));
  const ciphertext = new Uint8Array(
    await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce, tagLength: 128 }, cekKey, paddedPlaintext)
  );

  const recordSize = new Uint8Array(4);
  new DataView(recordSize.buffer).setUint32(0, 4096); // one record is enough for this payload size; 4096 is the RFC's own suggested default
  const header = concatBytes(salt, recordSize, new Uint8Array([ephemeralPublicBytes.length]), ephemeralPublicBytes);

  return concatBytes(header, ciphertext);
}

/** HKDF (RFC 5869) via Web Crypto's native HKDF support — used for both
 * RFC 8291's IKM derivation and RFC 8188's CEK/nonce derivation, just
 * with different (salt, ikm, info, length) each time.
 */
async function hkdf(salt, ikm, info, lengthBytes) {
  const key = await crypto.subtle.importKey("raw", ikm, { name: "HKDF" }, false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits(
    { name: "HKDF", hash: "SHA-256", salt, info },
    key,
    lengthBytes * 8
  );
  return new Uint8Array(bits);
}

export { base64UrlEncode, base64UrlDecode, buildVapidJwt, encryptPushPayload };
