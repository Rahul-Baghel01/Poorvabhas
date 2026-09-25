import type { NextConfig } from "next";
import { PHASE_PRODUCTION_BUILD } from "next/constants";

// Read at BUILD time: the rewrite destination is baked into the build output.
const API_URL = process.env.API_URL || "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  agentRules: false,
  async rewrites() {
    // Browser talks same-origin to /api/*; Next proxies to FastAPI (httpOnly cookie stays first-party).
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
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

export default function config(phase: string): NextConfig {
  if (phase === PHASE_PRODUCTION_BUILD && !process.env.API_URL) {
    console.warn("[poorvabhas] API_URL is not set: this build will proxy /api to http://localhost:8000. Set API_URL to the backend URL before building for deployment.");
  }
  return nextConfig;
}
