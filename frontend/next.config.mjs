/** @type {import('next').NextConfig} */
const nextConfig = {
  // Avoid standalone symlinks on Windows; Linux deployment keeps this output.
  output: process.platform === "win32" ? undefined : "standalone",
};

export default nextConfig;
