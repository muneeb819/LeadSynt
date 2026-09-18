"use client";

import { useEffect } from "react";

/**
 * Fades out the SSR'd #loader overlay (leadsynt-loader.gif on #0A1020)
 * once the app has hydrated. The overlay is plain HTML in app/layout.tsx,
 * so it renders BEFORE any JavaScript executes — it is also the fallback
 * for slow-JS environments (never disappears, always shows the loader).
 */
export function Preloader() {
  useEffect(() => {
    const el = document.getElementById("loader");
    if (!el) return;
    // minimum display time, then fade
    const t = setTimeout(() => {
      el.style.transition = "opacity 450ms ease";
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 500);
    }, 450);
    return () => clearTimeout(t);
  }, []);
  return null;
}
