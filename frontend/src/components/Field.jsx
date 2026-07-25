// Friendly form fields: rounded, roomy, plain labels.

export function Field({
  label,
  hint,
  value,
  onChange,
  type = "text",
  placeholder,
  ...rest
}) {
  return (
    <label className="block">
      {label && <span className="label mb-1.5 block">{label}</span>}
      <input
        type={type}
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-xl border border-line bg-panel2 px-4 py-3 text-[15px] text-text placeholder:text-muted focus:border-amber"
        {...rest}
      />
      {hint && <span className="mt-1.5 block text-[13px] text-muted">{hint}</span>}
    </label>
  );
}

export function Textarea({ label, hint, value, onChange, placeholder, rows = 4, ...rest }) {
  return (
    <label className="block">
      {label && <span className="label mb-1.5 block">{label}</span>}
      <textarea
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        placeholder={placeholder}
        rows={rows}
        className="w-full resize-y rounded-xl border border-line bg-panel2 px-4 py-3 text-[15px] leading-relaxed text-text placeholder:text-muted focus:border-amber"
        {...rest}
      />
      {hint && <span className="mt-1.5 block text-[13px] text-muted">{hint}</span>}
    </label>
  );
}

export function Toggle({ checked, onChange, label, id, disabled = false }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-busy={disabled}
      id={id}
      disabled={disabled}
      onClick={() => !disabled && onChange?.(!checked)}
      className="inline-flex items-center gap-3 disabled:cursor-wait disabled:opacity-50"
    >
      <span
        className="relative inline-flex h-6 w-11 items-center rounded-full border transition-colors duration-150"
        style={{
          borderColor: checked ? "var(--color-amber)" : "var(--color-lineb)",
          background: checked ? "var(--amber-fill)" : "transparent",
        }}
      >
        <span
          className="mx-0.5 inline-block h-4 w-4 rounded-full transition-transform duration-150"
          style={{
            background: checked ? "var(--color-amber)" : "var(--color-steel)",
            transform: checked ? "translateX(20px)" : "translateX(0)",
          }}
        />
      </span>
      {label && <span className="text-[14px] text-text2">{label}</span>}
    </button>
  );
}
