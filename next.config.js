/** @type {import('next').NextConfig} */
const nextConfig = {
  turbopack: {
    root: __dirname,
  },
  experimental: {
    proxyClientMaxBodySize: process.env.NEXT_CLIENT_MAX_BODY_SIZE || "2000mb",
  },
  // Dev: proxies /api/python/* to the local FastAPI server.
  // Prod: Vercel routes via vercel.json (rewrites are ignored in production)
  async rewrites() {
    return [
      {
        source: "/api/python/:path*",
        destination: `${process.env.API_BACKEND_URL || "http://127.0.0.1:8001"}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
