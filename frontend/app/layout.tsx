import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/state/auth-context";
import { Preloader } from "@/components/Preloader";
import { SpeedInsights } from "@vercel/speed-insights/next";

export const metadata: Metadata = {
  title: "LeadSynt — Control Center",
  description:
    "AI-powered global Lead Intelligence, Market Discovery, Opportunity, CRM and QA platform.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="shell-bg">
        {/* Preloader: SSR'd so it shows before JS loads (static fallback
            included — the gif only needs the file, no scripts). */}
        <div
          id="loader"
          aria-hidden
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 100,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "#0A1020",
          }}
        >
          <img
            src="/branding/leadsynt-loader.gif"
            alt="LeadSynt Loading"
            width={120}
            height={120}
            style={{ opacity: 0.9 }}
          />
        </div>
        <AuthProvider>
          {children}
          <Preloader />
        </AuthProvider>
        <SpeedInsights />
      </body>
    </html>
  );
}
