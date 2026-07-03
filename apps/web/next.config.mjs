/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  webpack: (config) => {
    // vega-canvas optionally requires the native `canvas` module for server-side
    // rendering; the browser build doesn't need it. Alias it to false so webpack
    // stops trying (and failing) to resolve it. Fixes:
    //   Module not found: Can't resolve 'canvas' in vega-canvas
    config.resolve.alias = { ...config.resolve.alias, canvas: false };
    return config;
  },
};

export default nextConfig;
