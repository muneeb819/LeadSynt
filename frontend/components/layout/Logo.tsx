"use client";

import { useState } from "react";
import { cn } from "@/utils/cn";
import { useTheme } from "@/hooks/useTheme";

/**
 * Brand logo with hover state.
 *
 * Assets (frontend/public/branding/):
 *   website-black   → light header (black art, transparent bg)
 *   website-white   → dark mode / footer (white art, transparent bg)
 *   hover-master    → :hover / active state (neon, "feels alive")
 *   monogram-*      → favicon / compact spots
 *
 * Usage: <Logo variant="master" className="h-9 w-auto" />
 */
export function Logo({
  variant = "master",
  className,
  hover = true,
}: {
  variant?: "master" | "monogram";
  className?: string;
  hover?: boolean;
}) {
  const { theme } = useTheme();
  const [hovering, setHovering] = useState(false);

  const active = hover && hovering;
  const src =
    variant === "master"
      ? active
        ? "/branding/leadsynt-hover-master.png"
        : theme === "dark"
          ? "/branding/leadsynt-website-white.png"
          : "/branding/leadsynt-website-black.png"
      : active
        ? "/branding/leadsynt-hover-monogram.png"
        : theme === "dark"
          ? "/branding/leadsynt-monogram-white.png"
          : "/branding/leadsynt-monogram-black.png";

  return (
    <img
      src={src}
      alt="LeadSynt"
      draggable={false}
      className={cn("select-none transition-opacity duration-150", className)}
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
    />
  );
}
