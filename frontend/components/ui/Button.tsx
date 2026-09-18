"use client";

import { cn } from "@/utils/cn";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
}

export function Button({
  variant = "primary",
  size = "md",
  className,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 disabled:opacity-50 disabled:pointer-events-none",
        size === "sm" ? "h-8 px-3 text-xs" : "h-9 px-4 text-sm",
        variant === "primary" && "bg-indigo-600 text-white hover:bg-indigo-500",
        variant === "secondary" &&
          "bg-white/5 text-zinc-200 hover:bg-white/10 border border-white/10 dark:bg-white/5 dark:text-zinc-200",
        variant === "ghost" && "text-zinc-400 hover:text-zinc-100 hover:bg-white/5",
        variant === "danger" && "bg-rose-600/90 text-white hover:bg-rose-500",
        className,
      )}
      {...props}
    />
  );
}
