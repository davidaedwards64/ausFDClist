# Sign-in with private_key_jwt (OIDC app linked to an AI Agent)

## Why this change was made

When an OIDC app is linked to an Okta AI Agent (O4AA), both share a single client ID, and the
app's **Client authentication** is **Public key / Private key**. Okta stores one
`token_endpoint_auth_method` per client, so the original sign-in code — which sent
`client_secret` in the `/v1/token` POST body (`client_secret_post`) — was rejected:

```
{"error":"invalid_client", ...}
System log: OIDC token request FAILURE: invalid_token_endpoint_auth_method
            (legacy event type app.oauth2.token.grant_failure)
```

The sign-in token request now authenticates the same way the STS token exchange does:
a signed `client_assertion` JWT (`private_key_jwt`), using `OKTA_AGENT_PRIVATE_JWK`.

## Code changes

| File | Change |
|---|---|
| `backend/main.py` (`/auth/callback`) | Builds the token request body. If `OKTA_CLIENT_SECRET` is set, sends `client_secret` as before. Otherwise, if `OKTA_AGENT_PRIVATE_JWK` is set, sends `client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer` and a `client_assertion` JWT. Imports `create_client_assertion_jwt` from `backend/auth/okta_sts.py`. |
| `backend/config.py` | Comment only: `okta_client_secret` is now optional. |
| `render.yaml` | Comment on `OKTA_CLIENT_SECRET`: leave blank for private key auth. |
| `README.md`, `docs/okta-authentication-flow.md` | `OKTA_CLIENT_SECRET` documented as optional; token step describes both methods. |

Assertion claims (reusing `create_client_assertion_jwt`): `iss` = `sub` = `OKTA_CLIENT_ID`,
`aud` = `{OKTA_ISSUER}/v1/token` (the exact URL being called), `exp` = now + 60s, unique `jti`,
RS256, `kid` taken from the JWK.

Behaviour matrix:

| `OKTA_CLIENT_SECRET` | `OKTA_AGENT_PRIVATE_JWK` | Sign-in authenticates with |
|---|---|---|
| set | any | client secret (`client_secret_post`) |
| empty | set | private key JWT (`private_key_jwt`) |
| empty | empty | nothing — Okta will reject the request |

**Important:** for private key auth, `OKTA_CLIENT_SECRET` must be **unset or empty** in Render/OAP,
otherwise the secret path wins and Okta rejects it.

## Okta configuration

On the OIDC app (shared client ID, `0oa...` or `wlp...`):

1. **General → Client Credentials → Client authentication**: *Public key / Private key*.
2. The public key registered on the app must be the pair of the private key in
   `OKTA_AGENT_PRIVATE_JWK` (matching `kid`). If you rotated keys, update both.
3. **Grant types**: *Authorization Code* enabled (alongside the token-exchange grant used by the agent).
4. **Sign-in redirect URIs**: add every deployment URL, e.g.
   - `https://<service>.onrender.com/auth/callback`
   - `https://ausfdclist.deadwoods-apps.platform.atko.ai/auth/callback`
5. **Sign-out redirect URIs**: add `https://<host>/auth/signin` for each deployment.
6. **Assignments**: users who sign in must be assigned to the app.
7. If `OKTA_ISSUER` is a custom authorization server, its access policy must allow this client.

## Deployment variables

- Leave `OKTA_CLIENT_SECRET` **blank / delete it**.
- `OKTA_CLIENT_ID` and `OKTA_AGENT_CLIENT_ID` can be the same value.
- `OKTA_AGENT_PRIVATE_JWK` must be raw JSON starting with `{`.
- After changing env vars, redeploy (OAP: env changes apply on next deploy/restart).

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `invalid_token_endpoint_auth_method` | Okta app set to Client secret but `OKTA_CLIENT_SECRET` empty, or secret set but app is Public key / Private key. |
| `invalid_client` with a `client_assertion` | Public key on the app doesn't match `OKTA_AGENT_PRIVATE_JWK`, or `aud` mismatch (`OKTA_ISSUER` must be the exact issuer used in `/authorize`). |
| `redirect_uri` error | Redirect URI not added to the app. |
| `JSONDecodeError` on sign-in | `OKTA_AGENT_PRIVATE_JWK` not raw JSON. |

Not tested against a live Okta org at the time of writing.
