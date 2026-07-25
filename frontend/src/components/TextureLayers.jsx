import { useEffect } from "react";

// The night sky behind everything: a static starfield, a soft warm glow, a few
// stars that twinkle, and the occasional shooting star. Non-interactive, and
// switched off wholesale by the texture preference.
//
// [left, top, delay, colour?, size?] — mostly white, with a few coloured
// (gold, ice blue, teal, warm peach) so the sky reads like real starlight,
// where stars burn at different temperatures. The last six are marked extra
// and drop away on phones.
const TWINKLES = [
  ["8%", "22%", "0s"],
  ["21%", "68%", "1.4s"],
  ["37%", "12%", "2.6s", "#ffd9a0", "2.5px"],
  ["55%", "80%", "0.7s"],
  ["66%", "30%", "3.3s", "#8fb8ff", "2px"],
  ["81%", "58%", "1.9s"],
  ["90%", "14%", "2.2s", "#ffb000", "2px"],
  ["12%", "88%", "3.8s", "#7fe7c4", "1.5px"],
  ["30%", "40%", "5.1s", "#8fb8ff", "1.5px"],
  ["73%", "84%", "4.4s", "#ffd9a0", "2px"],
  ["47%", "6%", "6.2s"],
  ["95%", "76%", "2.9s", "#ffb000", "1.5px"],
];
const PHONE_STARS = 6;

export function TextureLayers() {
  // Park the whole layer while the tab is in the background. CSS animation
  // keeps running there otherwise, spending battery on a sky nobody can see.
  useEffect(() => {
    const sync = () =>
      document.documentElement.setAttribute(
        "data-idle",
        document.hidden ? "true" : "false",
      );
    sync();
    document.addEventListener("visibilitychange", sync);
    return () => {
      document.removeEventListener("visibilitychange", sync);
      document.documentElement.removeAttribute("data-idle");
    };
  }, []);

  return (
    <div aria-hidden="true">
      <div className="tex tex-stars" />
      <div className="tex tex-glow" />
      <div className="tex tex-drift">
        {TWINKLES.map(([left, top, delay, color, size], i) => (
          <span
            key={`${left}-${top}`}
            className={`twinkle${i >= PHONE_STARS ? " twinkle-extra" : ""}`}
            style={{
              left,
              top,
              animationDelay: delay,
              ...(color ? { background: color } : {}),
              ...(size ? { width: size, height: size } : {}),
            }}
          />
        ))}
        <span
          className="shoot"
          style={{ left: "12%", top: "8%", animationDelay: "3s" }}
        />
        <span
          className="shoot twinkle-extra"
          style={{
            left: "58%",
            top: "16%",
            animationDelay: "11s",
            animationDuration: "23s",
          }}
        />
      </div>
    </div>
  );
}
