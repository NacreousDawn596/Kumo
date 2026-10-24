/**
 * SchoolApp identity worker.
 *
 * Verifies a student's SchoolApp credentials (via schoolapp.js), retrieves the
 * stable subject identifier, and returns a short-lived, audience-restricted,
 * HMAC-signed assertion that the Kumo backend can verify.
 *
 * The student's SchoolApp password is used once to authenticate and is never
 * logged, stored, or returned. It only ever travels over TLS between this
 * worker and the SchoolApp server.
 */

import { SchoolAppClient } from "schoolapp";

const TTL_SECONDS = 120; // assertion lifetime
const ISSUER = "schoolapp-worker";
const AUDIENCE = "kumo";
const MAX_BODY_BYTES = 8 * 1024;

// Simple in-memory rate limiter (per-IP sliding window).
const RATE_WINDOW_MS = 60_000;
const RATE_MAX = 10;
const rateBuckets = new Map();

function rateLimited(ip) {
  const now = Date.now();
  const bucket = rateBuckets.get(ip);
  if (!bucket || now - bucket.start >= RATE_WINDOW_MS) {
    rateBuckets.set(ip, { start: now, count: 1 });
    return false;
  }
  bucket.count += 1;
  if (bucket.count > RATE_MAX) return true;
  return false;
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function b64urlFromString(str) {
  return btoa(str).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function b64urlFromBytes(bytes) {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function hmacSign(secret, message) {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(message));
  return new Uint8Array(sig);
}

async function signAssertion(secret, claims) {
  const body = {
    exp: Math.floor(Date.now() / 1000) + TTL_SECONDS,
    iss: ISSUER,
    aud: AUDIENCE,
    ...claims,
  };
  const payloadB64 = b64urlFromString(JSON.stringify(body));
  const sig = await hmacSign(secret, payloadB64);
  return `${payloadB64}.${b64urlFromBytes(sig)}`;
}

// Extract the stable student identifier from a parsed SchoolApp profile.
function extractSubject(profile) {
  const p = profile || {};
  const personal = p.personal_info || {};
  const admin = p.administrative_info || {};
  const candidates = [
    personal.Code,
    personal["Code Etudiant"],
    personal["Code Étudiant"],
    personal["CNE/Masar"],
    admin.Code,
    admin["Code Etudiant"],
    personal.Numero,
    personal["Numéro"],
  ];
  for (const c of candidates) {
    if (c && String(c).trim()) return String(c).trim();
  }
  return null;
}

function extractName(profile) {
  const p = profile || {};
  const basic = p.basic_info || {};
  const personal = p.personal_info || {};
  if (basic.full_name) return basic.full_name;
  if (personal.Nom || personal["Prénom"]) {
    return `${personal["Prénom"] || ""} ${personal.Nom || ""}`.trim();
  }
  return null;
}

async function verifyCredentials(env, email, password) {
  const client = new SchoolAppClient(env.SCHOOLAPP_BASE_URL || undefined);
  const ok = await client.login(email, password);
  if (!ok) return null;

  const profile = await client.getProfile();
  const subject = extractSubject(profile);
  if (!subject) return null;

  return {
    sub: subject,
    email: email,
    name: extractName(profile),
  };
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // CORS for the Kumo frontend.
    const corsHeaders = {
      "access-control-allow-origin": env.ALLOWED_ORIGIN || "*",
      "access-control-allow-methods": "POST, GET, OPTIONS",
      "access-control-allow-headers": "content-type",
    };
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    if (url.pathname === "/health") {
      return json({ ok: true }, 200);
    }

    if (url.pathname === "/verify" && request.method === "POST") {
      const ip = request.headers.get("cf-connecting-ip") || "unknown";
      if (rateLimited(ip)) {
        return json({ error: "Too many attempts. Try again shortly." }, 429);
      }

      let email;
      let password;
      try {
        const body = await request.text();
        if (body.length > MAX_BODY_BYTES) return json({ error: "Request too large." }, 413);
        const parsed = JSON.parse(body);
        email = (parsed.email || "").trim();
        password = parsed.password || "";
      } catch {
        return json({ error: "Invalid JSON." }, 400);
      }

      if (!email || !password || !email.includes("@") || password.length < 1) {
        return json({ error: "Email and password are required." }, 400);
      }

      if (!env.SCHOOLAPP_WORKER_SECRET) {
        return json({ error: "Worker is not configured (missing secret)." }, 500);
      }

      let claims;
      try {
        claims = await verifyCredentials(env, email, password);
      } catch (err) {
        // Never leak internals or credentials; log a sanitized message.
        console.error("schoolapp verify error:", err && err.message ? err.message : String(err));
        return json({ error: "Unable to verify with SchoolApp." }, 502);
      }

      if (!claims) {
        return json({ error: "Invalid SchoolApp credentials." }, 401);
      }

      const assertion = await signAssertion(env.SCHOOLAPP_WORKER_SECRET, claims);
      return json(
        { assertion, sub: claims.sub, name: claims.name },
        200
      );
    }

    return json({ error: "Not found." }, 404);
  },
};
