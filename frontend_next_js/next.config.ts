import type { NextConfig } from "next";

// In production (Vercel), NEXT_PUBLIC_API_URL is set to the live Render URL.
// In local dev, it falls back to localhost:8010.
const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/:path*`,
      },
    ];
  },
};

export default nextConfig;
