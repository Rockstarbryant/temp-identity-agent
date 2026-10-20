/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  async rewrites() {
    return [
      // Shortcut links: https://<this-site>/@direct/https://example.com
      // Next.js reserves folder names starting with "@", so the "@direct" URL is rewritten to /direct.
      { source: "/@direct", destination: "/direct" },
      { source: "/@direct/:path*", destination: "/direct/:path*" },
    ];
  },

  async headers() {
    return [
      {
        // The service worker must always be re-checked so updates reach users.
        source: "/sw.js",
        headers: [
          { key: "Content-Type", value: "application/javascript; charset=utf-8" },
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
        ],
      },
    ];
  },
};

export default nextConfig;
