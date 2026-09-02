/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async redirects() {
    return [
      {
        source: "/app/enrich",
        destination: "/osint",
        permanent: false,
      },
      {
        source: "/app/history",
        destination: "/osint/jobs",
        permanent: false,
      },
      {
        source: "/app/jobs",
        destination: "/osint/jobs",
        permanent: false,
      },
      {
        source: "/app/jobs/:id",
        destination: "/osint/jobs/:id",
        permanent: false,
      },
      {
        source: "/app/signals",
        destination: "/desk/signals",
        permanent: false,
      },
      {
        source: "/app/dashboard",
        destination: "/osint",
        permanent: false,
      },
      {
        source: "/app/health",
        destination: "/desk/system-health",
        permanent: false,
      },
      {
        source: "/app/admin",
        destination: "/desk",
        permanent: false,
      },
      {
        source: "/app/admin/:path*",
        destination: "/desk/:path*",
        permanent: false,
      },
    ];
  },
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
};

module.exports = nextConfig;
