/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "**",
      },
      {
        protocol: "http",
        hostname: "localhost",
      },
    ],
  },
  async redirects() {
    return [
      { source: "/app/admin", destination: "/desk", permanent: false },
      { source: "/app/admin/:path*", destination: "/desk/:path*", permanent: false },
    ];
  },
};

module.exports = nextConfig;
