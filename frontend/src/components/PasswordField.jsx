import { useId, useState } from "react";

export const MIN_PASSWORD = 8;

// A password box you can read.
//
// The reveal toggle is not a nicety. Typing a long password blind on a phone
// keyboard is where most sign-up attempts die, and being able to check it
// removes the need for a second "confirm password" box that people paste the
// same typo into anyway.
export function PasswordField({
  label = "Password",
  value,
  onChange,
  autoComplete = "current-password",
  hint,
  error,
  autoFocus = false,
  showStrength = false,
}) {
  const [shown, setShown] = useState(false);
  const id = useId();
  const short = showStrength && value.length > 0 && value.length < MIN_PASSWORD;

  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-3">
        <label className="label" htmlFor={id}>
          {label}
        </label>
        <button
          type="button"
          onClick={() => setShown((s) => !s)}
          className="text-[12.5px] text-label hover:text-text"
          // Buttons inside a form submit it by default, and a reveal toggle
          // that submits a half-typed password is a genuinely confusing bug.
          tabIndex={-1}
        >
          {shown ? "Hide" : "Show"}
        </button>
      </div>
      <input
        id={id}
        type={shown ? "text" : "password"}
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        autoComplete={autoComplete}
        autoFocus={autoFocus}
        aria-invalid={Boolean(error) || short}
        // 16px on phones deliberately. Under 16, iOS Safari zooms the whole
        // page in the moment the field is focused and does not zoom back out,
        // which leaves someone stranded halfway through signing up.
        className="w-full rounded-xl border border-line bg-panel2 px-4 py-3 text-[16px] text-text placeholder:text-muted focus:border-amber sm:text-[15px]"
        style={error || short ? { borderColor: "var(--color-red)" } : undefined}
      />
      {error ? (
        <span className="mt-1.5 block text-[13px] text-red">{error}</span>
      ) : short ? (
        <span className="mt-1.5 block text-[13px] text-red">
          {MIN_PASSWORD - value.length} more character
          {MIN_PASSWORD - value.length === 1 ? "" : "s"} to go
        </span>
      ) : (
        hint && <span className="mt-1.5 block text-[13px] text-muted">{hint}</span>
      )}
    </div>
  );
}

// Same 16px rule, plus the keyboard and autofill hints that make an address
// bearable to type on a phone.
export function EmailField({
  label = "Email",
  value,
  onChange,
  error,
  hint,
  autoFocus = false,
  autoComplete = "email",
}) {
  const id = useId();
  return (
    <div>
      <label className="label mb-1.5 block" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        type="email"
        inputMode="email"
        autoCapitalize="none"
        autoCorrect="off"
        spellCheck="false"
        autoComplete={autoComplete}
        autoFocus={autoFocus}
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        placeholder="you@example.com"
        aria-invalid={Boolean(error)}
        className="w-full rounded-xl border border-line bg-panel2 px-4 py-3 text-[16px] text-text placeholder:text-muted focus:border-amber sm:text-[15px]"
        style={error ? { borderColor: "var(--color-red)" } : undefined}
      />
      {error ? (
        <span className="mt-1.5 block text-[13px] text-red">{error}</span>
      ) : (
        hint && <span className="mt-1.5 block text-[13px] text-muted">{hint}</span>
      )}
    </div>
  );
}

export function looksLikeEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test((value || "").trim());
}
