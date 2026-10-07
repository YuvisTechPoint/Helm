/** @type {import('next').NextConfig} */
const apiTarget = process.env.API_PROXY_TARGET || "http://127.0.0.1:8000";

const nextConfig = {
  reactStrictMode: true,
  devIndicators: { position: "bottom-right" },
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  experimental: { optimizePackageImports: ["lucide-react"] },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiTarget}/:path*` }];
  },
};

module.exports = nextConfig;
