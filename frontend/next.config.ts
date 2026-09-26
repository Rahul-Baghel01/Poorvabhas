import type { NextConfig } from "next";
// Vercel Services routes /api to FastAPI. Local standalone Next.js development
// retains the existing proxy to a backend on port 8000.

const nextConfig: NextConfig = {
  output: process.env.VERCEL ? undefined : "standalone",
  poweredByHeader: false,
  agentRules: false,
  async rewrites() {
    return process.env.VERCEL
      ? []
      : [{ source: "/api/:path*", destination: `${process.env.API_URL || "http://localhost:8000"}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};

export default function config(): NextConfig {
  return nextConfig;
}
