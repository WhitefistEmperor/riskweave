import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.RINGSENTINEL_API_PROXY_TARGET ?? 'http://127.0.0.1:8000'}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
