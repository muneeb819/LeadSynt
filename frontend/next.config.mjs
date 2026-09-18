const BACKEND = process.env.BACKEND_URL || "http://127.0.0.1:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Single deployable: the production build ships as Next's "standalone"
  // output (self-contained node server.js), which the root Docker image
  // runs alongside the FastAPI backend in ONE container, ONE port (3000).
  output: "standalone",
  async rewrites() {
    // Browser never talks to the backend directly — same-origin /api/* is
    // proxied by the Next server (keeps secrets server-side, works in any
    // embedding context).
    return [
      { source: "/api/:path*", destination: `${BACKEND}/api/:path*` },
    ];
  },
};

export default nextConfig;
