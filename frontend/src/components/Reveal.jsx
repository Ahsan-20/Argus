import { motion } from "framer-motion";
import { usePrefs } from "../state/prefs.jsx";

// Sections rise into place as they come into view. Skipped entirely in calm
// mode, where the content simply appears.
//
// `delay` staggers siblings so a row of cards arrives as a sequence rather
// than a single block. Keep it small: past about 0.2s between items the page
// starts feeling slow instead of alive.
// `as` lets a section reveal itself rather than sit inside a wrapper div, so
// the id and scroll-margin that the jump links rely on stay on the element
// that is actually being scrolled to.
export function Reveal({
  children,
  className = "",
  delay = 0,
  as = "div",
  ...rest
}) {
  const { reducedMotion } = usePrefs();
  const Plain = as;
  if (reducedMotion)
    return (
      <Plain className={className} {...rest}>
        {children}
      </Plain>
    );
  const Motion = motion[as] || motion.div;
  return (
    <Motion
      className={className}
      {...rest}
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.5, delay, ease: [0.2, 0, 0, 1] }}
    >
      {children}
    </Motion>
  );
}
