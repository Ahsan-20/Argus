/**
 * Argus mail relay, to be pasted into script.google.com.
 *
 * Why this exists. Hosting providers commonly block outbound SMTP ports to stop
 * their address ranges being used for spam, which leaves the backend unable to
 * send anything. Routing mail through a third party fixes the port problem but
 * creates a worse one: mail claiming to be from a @gmail.com address that Gmail
 * did not send fails SPF and DKIM alignment, so it lands in spam. That is no use
 * for a verification link somebody is waiting on.
 *
 * Apps Script avoids both. It runs inside the Google account that owns the
 * mailbox, so MailApp really does send as that account and authenticates
 * properly, and the backend reaches it over ordinary HTTPS, which no host
 * blocks. It also needs no Cloud project, no billing, and no card.
 *
 * ---------------------------------------------------------------------------
 * SETUP
 *
 *  1. Go to script.google.com and create a new project.
 *  2. Delete whatever is in Code.gs and paste this file in.
 *  3. Change SHARED_SECRET below to a long random string. Keep it: the backend
 *     needs the same value.
 *  4. Deploy, New deployment, type "Web app".
 *       Execute as        : Me
 *       Who has access    : Anyone
 *     "Anyone" is required because the backend calls it without a Google
 *     login. The shared secret is what actually protects it, which is why it
 *     must not be guessable.
 *  5. Approve the permission prompt. Google will warn the app is unverified;
 *     that is expected for a script you wrote for yourself. Advanced, then
 *     "Go to (project name)".
 *  6. Copy the deployment URL, ending in /exec, into the backend as
 *     APPS_SCRIPT_MAIL_URL, and the secret as APPS_SCRIPT_MAIL_SECRET.
 *
 * Quota: a consumer Gmail account may send to roughly 100 recipients a day
 * through Apps Script, which is far more than this needs.
 * ---------------------------------------------------------------------------
 */

// CHANGE THIS. It is the only thing standing between a public URL and anyone
// being able to send mail as you.
var SHARED_SECRET = "replace-me-with-a-long-random-string";

function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);

    // Constant time is overkill here, but refusing early and saying nothing
    // useful is not: a caller without the secret learns only that it failed.
    if (!body.secret || body.secret !== SHARED_SECRET) {
      return json({ ok: false, error: "unauthorised" });
    }
    if (!body.to || !body.subject) {
      return json({ ok: false, error: "missing to or subject" });
    }

    var options = {
      to: body.to,
      subject: body.subject,
      body: body.text || "",
      name: body.fromName || "Argus",
    };

    if (body.html) {
      options.htmlBody = body.html;
    }

    // The logo travels as an inline attachment referenced by cid, exactly as
    // it does over SMTP, because Gmail strips data: image URLs and would
    // otherwise show a broken image where the mark should be.
    if (body.logoBase64 && body.logoCid) {
      var blob = Utilities.newBlob(
        Utilities.base64Decode(body.logoBase64),
        "image/png",
        "argus.png"
      );
      var inline = {};
      inline[body.logoCid] = blob;
      options.inlineImages = inline;
    }

    MailApp.sendEmail(options);
    return json({ ok: true });
  } catch (err) {
    return json({ ok: false, error: String(err) });
  }
}

function doGet() {
  // A plain visit should say what this is without revealing anything, and
  // gives an easy way to confirm the deployment is live.
  return json({ ok: true, service: "argus-mail-relay" });
}

function json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(
    ContentService.MimeType.JSON
  );
}
