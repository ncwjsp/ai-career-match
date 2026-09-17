import type { NextConfig } from "next";

const config: NextConfig = {
  poweredByHeader: false,
  experimental: { proxyClientMaxBodySize: "11mb" },
  async rewrites() {
    const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
    return [{ source: "/backend/:path*", destination: backend + "/:path*" }];
  },
};

export default config;
