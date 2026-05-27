/** @type {import('next').NextConfig} */
const nextConfig = {
  turbopack: {
    root: __dirname,
  },
  // Dev: proxies /api/python/* → Flask on :5328
  // Prod: Vercel routes via vercel.json (rewrites are ignored in production)
  async rewrites() {
    return [
      {
        source: "/api/python/:path*",
        destination: "http://127.0.0.1:5328/:path*",
      },
    ];
  },
};

module.exports = nextConfig;
