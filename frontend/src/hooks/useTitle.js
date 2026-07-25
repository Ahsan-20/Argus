import { useEffect } from "react";

export const BASE_TITLE = "Argus: we watch the page for you";

// The browser tab should say where you are. One title across every page wastes
// the tab and makes back-button history entries indistinguishable. Pass null
// on the landing page to keep the full brand line.
export function useTitle(title) {
  useEffect(() => {
    document.title = title ? `${title} · Argus` : BASE_TITLE;
  }, [title]);
}
