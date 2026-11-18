/**
 * Explicit same-origin API proxy. No database credentials belong in this config.
 * @param {Record<string, string | undefined>} values
 * @returns {import('next').NextConfig}
 */
export function deploymentConfig(values = process.env) {
  const origin = values.SPMS_BACKEND_ORIGIN;
  if (!origin) {
    if (values.VERCEL === "1") throw new Error("SPMS_BACKEND_ORIGIN is required on Vercel");
    return {};
  }
  const invalid = () => { throw new Error("SPMS_BACKEND_ORIGIN must be one backend HTTPS origin"); };
  let url;
  try { url = new URL(origin); } catch { return invalid(); }
  const local = values.SPMS_LOCAL_API_PROXY === "1" && values.VERCEL !== "1"
    && url.protocol === "http:" && ["localhost", "127.0.0.1"].includes(url.hostname);
  if ((!local && (url.protocol !== "https:" || (url.port && url.port !== "443")))
    || url.username || url.password || url.pathname !== "/" || url.search || url.hash
    || /\s|\\|\*/.test(origin) || !/^[\x20-\x7e]+$/.test(origin)
    || (!local && !/^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}$/.test(url.hostname))) return invalid();
  if (values.NEXT_PUBLIC_API_BASE_URL) {
    throw new Error("Remove NEXT_PUBLIC_API_BASE_URL when using the same-origin API proxy");
  }
  return {
    // Explicit build-time empty string keeps every existing API client on the
    // web origin instead of its localhost fallback. Backend URL stays server-side.
    env: { NEXT_PUBLIC_API_BASE_URL: "" },
    async rewrites() {
      return [{ source: "/api/v1/:path*", destination: `${url.origin}/api/v1/:path*` }];
    },
    async headers() {
      return [{ source: "/api/v1/:path*", headers: [
        { key: "Cache-Control", value: "no-store" },
        { key: "CDN-Cache-Control", value: "no-store" },
        { key: "Vercel-CDN-Cache-Control", value: "no-store" },
        { key: "x-vercel-enable-rewrite-caching", value: "0" },
      ] }];
    },
  };
}
