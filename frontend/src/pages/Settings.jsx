import { Link } from "react-router-dom";
import { Panel } from "../components/Panel.jsx";
import { Toggle } from "../components/Field.jsx";
import { Button } from "../components/Button.jsx";
import { GLYPH, SpecList, SpecRow } from "../components/SpecRow.jsx";
import { useSession } from "../state/session.jsx";
import { usePrefs } from "../state/prefs.jsx";
import { useStats } from "../hooks/useQueries.js";
import { useTitle } from "../hooks/useTitle.js";

// Set at build time. Left blank the link simply does not appear, which beats
// pointing people at github.com's front page.
const REPO_URL = import.meta.env.VITE_REPO_URL || "";

// A preference: description on the left, switch on the right.
function PrefRow({ title, body, checked, onChange, first }) {
  return (
    <div
      className={`flex items-start justify-between gap-5 ${
        first ? "" : "border-t border-line pt-4 mt-4"
      }`}
    >
      <div>
        <p className="text-[14.5px] font-medium text-text2">{title}</p>
        <p className="mt-0.5 text-[13px] leading-relaxed text-muted">{body}</p>
      </div>
      <div className="mt-0.5 shrink-0">
        <Toggle checked={checked} onChange={onChange} />
      </div>
    </div>
  );
}

export default function Settings() {
  useTitle("Settings");
  const { operator, isVerified, graceHoursLeft, signOut } = useSession();
  const { reducedMotion, texture, toggleReducedMotion, toggleTexture } = usePrefs();
  const stats = useStats();

  const channels = stats.data?.channels || { email: true, whatsapp: false };

  return (
    <main className="mx-auto max-w-[720px] px-4 py-8 sm:py-10">
      <h1 className="font-display text-[26px] font-bold text-text sm:text-[30px]">
        Settings
      </h1>
      <p className="mt-1 text-[15px] text-label">
        Who you are, how Argus reaches you, and how it looks.
      </p>

      <div className="mt-6 space-y-5">
        {/* The address is the account now, so it is shown rather than typed.
            Editing it here used to silently change where new alerts went while
            leaving every existing watcher pointing at the old address. */}
        <Panel title="Your account">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-[15px] font-semibold text-text">
                {operator}
              </p>
              <p className="mt-0.5 text-[13px] text-muted">
                Your sign in, and where alerts are sent.
              </p>
            </div>
            {isVerified ? (
              <span className="shrink-0 rounded-full border border-green/40 px-2.5 py-1 text-[12px] font-medium text-green">
                Confirmed
              </span>
            ) : (
              <Link
                to="/verify"
                className="shrink-0 rounded-full border border-amber/50 px-2.5 py-1 text-[12px] font-medium text-amber hover:bg-[var(--amber-fill)]"
              >
                {graceHoursLeft != null && graceHoursLeft < 24
                  ? `Confirm, ${Math.max(0, Math.floor(graceHoursLeft))}h left`
                  : "Confirm your email"}
              </Link>
            )}
          </div>
          <div className="mt-4 flex flex-wrap gap-2 border-t border-line pt-4">
            <Button variant="secondary" size="sm" to="/forgot">
              Change password
            </Button>
            <Button variant="ghost" size="sm" onClick={signOut}>
              Sign out
            </Button>
          </div>
        </Panel>

        <Panel title="How alerts reach you" bodyClass="p-5 pb-4">
          <SpecList>
            <SpecRow
              icon={GLYPH.mail}
              label="Email"
              value="Always on"
              tone="var(--color-green)"
              note={operator ? `Going to ${operator}` : null}
            />
            {/* "Not set up" read as something you could go and set up. You
                cannot: WhatsApp will not deliver to a number that has not
                opted in first, so this needs a setup step per person that
                does not exist yet. Say "coming soon" and mean it. */}
            <SpecRow
              icon={GLYPH.chat}
              label="WhatsApp"
              value={channels.whatsapp ? "On" : "Coming soon"}
              tone={channels.whatsapp ? "var(--color-green)" : undefined}
              note={
                channels.whatsapp
                  ? null
                  : "Alerts go by email for now. WhatsApp is on the way."
              }
            />
          </SpecList>
        </Panel>

        <Panel title="Appearance">
          <PrefRow
            first
            title="Calm mode"
            body="Stops the moving parts: orbiting watchers, the dial, and page transitions."
            checked={reducedMotion}
            onChange={toggleReducedMotion}
          />
          <PrefRow
            title="Night sky background"
            body="The faint stars and the warm glow behind everything. Turn it off for a plain background."
            checked={texture}
            onChange={toggleTexture}
          />
        </Panel>

        <Panel title="About Argus" bodyClass="p-5 pb-4">
          <SpecList>
            <SpecRow icon={GLYPH.tag} label="Version" value="0.1.0" />
            <SpecRow
              icon={GLYPH.orbit}
              label="Watchers running"
              value={stats.data?.total_watchers ?? "-"}
            />
            <SpecRow
              icon={GLYPH.pulse}
              label="Checks made so far"
              value={stats.data?.total_runs?.toLocaleString?.() ?? "-"}
            />
          </SpecList>
          {REPO_URL && (
            <a
              href={REPO_URL}
              target="_blank"
              rel="noreferrer"
              className="mt-4 inline-block text-[13px] text-label underline decoration-line underline-offset-4 hover:text-text"
            >
              Source code
            </a>
          )}
        </Panel>

        <p className="pt-1 text-center text-[12.5px] text-muted">
          Argus. Always watching, so you don't have to.
        </p>
      </div>
    </main>
  );
}
