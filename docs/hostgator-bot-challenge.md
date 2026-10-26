# HostGator bot challenge (409 Conflict from api.php)

## Symptom
The agent reports `Client error '409 Conflict' for url 'https://davidaedwards.com/ausfdclist/api.php'`.

## Cause
`php/api.php` never returns 409. HostGator's bot protection (believed to be Imunify360 Webshield;
not confirmed) challenges non-browser clients such as the Render/OAP backend with:

    HTTP 409, text/html
    <script>document.cookie = "humans_21909=1"; document.location.reload(true)</script>

A browser runs the script and retries; `httpx` does not. With the cookie set, the same request
reaches PHP normally (verified with curl: returns the expected `400 db_user and db_pass are required`).

## Workaround (current)
`_php_post` in `backend/handlers.py` sends the cookie on every PHP API request.
Settings in `backend/config.py` (override via env vars if the host changes them):

| Env var | Default | Notes |
|---|---|---|
| `PHP_API_CHALLENGE_COOKIE_NAME` | `humans_21909` | Set to empty to disable. The number may change. |
| `PHP_API_CHALLENGE_COOKIE_VALUE` | `1` | |

This is a bypass of the host's protection and may stop working if HostGator changes the cookie.
If you see 409 again, re-run:

    curl -si -X POST https://davidaedwards.com/ausfdclist/api.php -H "Content-Type: application/json" -d '{"action":"statistics"}'

and update the cookie name/value from the returned script.

## Proper fix (not done)
Ask HostGator support (or check cPanel for Imunify360/security settings) to whitelist the hosting
platform's outbound IPs (Render: service Connect > Outbound; OAP: ask the platform team), then
remove the workaround.

## Images
Browser `<img>` requests to `https://davidaedwards.com/ausfdclist/images/...` hit the same 409 challenge
and show as broken images (an `<img>` can't run the challenge script). Images are therefore served through
the backend proxy `GET /img/{year}/{filename}` (`backend/main.py`), which fetches from HostGator with the
challenge cookie. `coverImgUrl` / `stampImgUrl` in `frontend/js/streaming.js` build `/img/...` URLs.
The route only accepts `[A-Za-z0-9_.-]` in both path parts, returns only `image/*` responses, and sends
`Cache-Control: public, max-age=86400`.
