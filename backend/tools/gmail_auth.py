"""One time helper: obtain a Gmail refresh token for sending mail.

Run this once on your own machine. It opens a browser, you approve, and it
prints the three values to put in the deployment's environment. Nothing here
runs in production, and no token is written to disk.

Why this exists at all: hosting providers commonly block outbound SMTP ports to
stop their address ranges being used for spam, which leaves an app unable to
send mail at all. Gmail's HTTP API goes out over 443 like any other request, so
no host blocks it, and because the mail genuinely originates from the Gmail
account it authenticates properly and lands in inboxes. A third party sending
on your behalf cannot do that: it fails SPF and DKIM alignment for an
@gmail.com sender and gets filtered.

Before running, in the Google Cloud Console:

  1. Create a project (any name).
  2. APIs and Services, Library, enable "Gmail API".
  3. APIs and Services, OAuth consent screen: External, fill the required
     fields, and add your own Gmail address under Test users.
  4. Credentials, Create credentials, OAuth client ID, type "Desktop app".
     Copy the client ID and client secret.

Then:

    python tools/gmail_auth.py

A note on expiry. While the consent screen is in "Testing" the refresh token
stops working after seven days. Publish the app (Audience, Publish) to keep it
indefinitely. Google will warn that the app is unverified, which is expected
and harmless when you are the only user.
"""

import base64
import hashlib
import http.server
import json
import secrets
import socketserver
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
# The narrowest scope that can send. Not gmail.compose, not full mail access:
# this token should be able to do exactly one thing.
SCOPE = "https://www.googleapis.com/auth/gmail.send"

_received: dict[str, str] = {}


class _Catcher(http.server.BaseHTTPRequestHandler):
    """Catches the single redirect Google makes back to localhost."""

    def do_GET(self):  # noqa: N802  (name fixed by the stdlib)
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        _received.update({k: v[0] for k, v in params.items()})
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        ok = "code" in _received
        self.wfile.write(
            (
                "<html><body style='font-family:sans-serif;background:#0b0f1e;"
                "color:#f5f7ff;padding:60px;text-align:center'>"
                f"<h2>{'Authorised.' if ok else 'Something went wrong.'}</h2>"
                "<p>You can close this tab and return to the terminal.</p>"
                "</body></html>"
            ).encode()
        )

    def log_message(self, *args):
        pass  # keep the terminal clean


def main() -> int:
    print("Gmail refresh token helper\n")
    client_id = input("  OAuth client ID     : ").strip()
    client_secret = input("  OAuth client secret : ").strip()
    if not client_id or not client_secret:
        print("\nBoth values are required. See the notes at the top of this file.")
        return 1

    # PKCE. Not strictly required for a desktop client with a secret, but the
    # authorisation code travels through a browser and a local socket, and
    # binding it to a verifier costs nothing.
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )

    with socketserver.TCPServer(("127.0.0.1", 0), _Catcher) as httpd:
        port = httpd.server_address[1]
        redirect_uri = f"http://127.0.0.1:{port}"
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            # offline plus consent is what actually returns a refresh token.
            # Without them Google issues an access token only, and a token that
            # dies in an hour is no use to a server.
            "access_type": "offline",
            "prompt": "consent",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

        print("\n  Opening your browser to approve access.")
        print("  If it does not open, paste this in yourself:\n")
        print(f"  {url}\n")
        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
        httpd.handle_request()

    if "code" not in _received:
        print(f"\nNo authorisation code came back: {_received}")
        return 1

    data = urllib.parse.urlencode(
        {
            "code": _received["code"],
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        }
    ).encode()
    req = urllib.request.Request(TOKEN_URL, data=data)
    with urllib.request.urlopen(req, timeout=30) as resp:
        token = json.load(resp)

    refresh = token.get("refresh_token")
    if not refresh:
        print("\nNo refresh token returned. This usually means the app has")
        print("already been authorised. Remove Argus at")
        print("https://myaccount.google.com/permissions and run this again.")
        return 1

    print("\n  Done. Put these three in the deployment's environment:\n")
    print(f"  GMAIL_CLIENT_ID={client_id}")
    print(f"  GMAIL_CLIENT_SECRET={client_secret}")
    print(f"  GMAIL_REFRESH_TOKEN={refresh}")
    print("\n  Leave BREVO_API_KEY unset so mail takes this path.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
