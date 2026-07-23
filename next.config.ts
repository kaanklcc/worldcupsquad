import type { NextConfig } from "next";

const production = process.env.NODE_ENV === "production";
const publicApiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const publicApiIsAbsolute = /^https?:\/\//i.test(publicApiBase);
if (!publicApiIsAbsolute && !publicApiBase.startsWith("/")) {
  throw new Error("NEXT_PUBLIC_API_URL must be an absolute http(s) URL or a root-relative proxy path");
}

let backendApiOrigin = process.env.BACKEND_API_ORIGIN
  || (publicApiIsAbsolute ? publicApiBase : "http://localhost:8000");
try {
  backendApiOrigin = new URL(backendApiOrigin).origin;
} catch {
  throw new Error("BACKEND_API_ORIGIN must be an absolute http(s) URL");
}

const browserApiOrigin = publicApiIsAbsolute ? new URL(publicApiBase).origin : "'self'";
const secureDeployment = production && backendApiOrigin.startsWith("https://");

const contentSecurityPolicy = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${production ? "" : " 'unsafe-eval'"}`,
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' https://fonts.gstatic.com data:",
  "img-src 'self' data: blob:",
  `connect-src 'self' ${browserApiOrigin} https://k8s.testnet.json-rpc.injective.network https://ethereum-sepolia-rpc.publicnode.com`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  secureDeployment ? "upgrade-insecure-requests" : "",
].filter(Boolean).join("; ");

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async rewrites() {
    if (publicApiIsAbsolute) return [];
    const proxyPrefix = publicApiBase.replace(/\/+$/, "");
    return [
      {
        source: `${proxyPrefix}/:path*`,
        destination: `${backendApiOrigin}/:path*`,
      },
    ];
  },
  async headers() {
    const headers = [
      { key: "Content-Security-Policy", value: contentSecurityPolicy },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
      { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
    ];
    if (secureDeployment) {
      headers.push({ key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" });
    }
    return [{ source: "/:path*", headers }];
  },
};

export default nextConfig;
