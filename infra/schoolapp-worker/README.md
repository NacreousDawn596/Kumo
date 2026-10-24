# SchoolApp integration — Cloudflare Worker boundary

This directory is an **honest scaffold** for the SchoolApp authentication
integration. Kumo's preferred identity provider is SchoolApp, but the concrete
OAuth/OIDC contract (authorize/token endpoints, JWKS URL, subject claim, and
scopes) is provider-specific and was not available during development.

## What this boundary should do

1. Receive the user's "Continue with SchoolApp" request.
2. Generate an anti-forgery `state` and a `nonce`, then redirect to the
   provider's authorize endpoint.
3. On the callback, validate `state` and exchange the authorization code for
   tokens via the provider's token endpoint (server-to-server, secret never
   leaves the Worker).
4. Verify the ID token/assertion: signature against the provider JWKS,
   `iss`, `aud`, `exp`, and replay protections (`jti`/`nonce`).
5. Mint a **short-lived, audience-restricted assertion** (or forward the
   verified claims through the protected callback) that the Kumo backend can
   trust without holding provider credentials.

## What is implemented

Nothing beyond this scaffold. The backend exposes `POST /api/auth/schoolapp/start`
and `POST /api/auth/schoolapp/assert`, both of which return `501 Not Implemented`
until the provider endpoints are supplied. The backend adapter
(`backend/app/auth/provider.py`) documents exactly which settings are required.

## Config required (see `.env.example`)

- `SCHOOLAPP_ISSUER`
- `SCHOOLAPP_CLIENT_ID` / `SCHOOLAPP_CLIENT_SECRET`
- `SCHOOLAPP_AUTHORIZE_URL` / `SCHOOLAPP_TOKEN_URL` / `SCHOOLAPP_JWKS_URL`
- `SCHOOLAPP_AUDIENCE`

## Placeholder Worker (reference shape only)

```js
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/auth/start") {
      const state = crypto.randomUUID();
      const redirect = new URL(env.SCHOOLAPP_AUTHORIZE_URL);
      redirect.searchParams.set("client_id", env.SCHOOLAPP_CLIENT_ID);
      redirect.searchParams.set("response_type", "code");
      redirect.searchParams.set("scope", "openid email profile");
      redirect.searchParams.set("state", state);
      redirect.searchParams.set("redirect_uri", env.REDIRECT_URI);
      return Response.redirect(redirect.toString(), 302);
    }
    if (url.pathname === "/auth/callback") {
      // Validate state, exchange code, verify ID token (JWKS + iss/aud/exp),
      // then deliver a short-lived assertion to the Kumo backend callback.
      return new Response("not implemented", { status: 501 });
    }
    return new Response("not found", { status: 404 });
  },
};
```

Until the provider contract is documented, use the `local` auth provider for
development and tests. Do not invent endpoints or scrape credentials.
