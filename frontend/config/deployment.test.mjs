import test from "node:test";
import assert from "node:assert/strict";
import { deploymentConfig } from "./deployment.mjs";

test("local direct API configuration stays unchanged", () => {
  assert.deepEqual(deploymentConfig({ NEXT_PUBLIC_API_BASE_URL: "http://localhost:8001" }), {});
});
test("Vercel requires a configured backend instead of silently using localhost", () => {
  assert.throws(() => deploymentConfig({ VERCEL: "1" }), /SPMS_BACKEND_ORIGIN/);
});
test("deployed API remains same-origin and is explicitly not cached", async () => {
  const c = deploymentConfig({ VERCEL: "1", SPMS_BACKEND_ORIGIN: "https://spms-api.example.test" });
  assert.equal(c.env.NEXT_PUBLIC_API_BASE_URL, "");
  assert.deepEqual(await c.rewrites(), [{ source: "/api/v1/:path*", destination: "https://spms-api.example.test/api/v1/:path*" }]);
  const headers = (await c.headers())[0].headers;
  assert.ok(headers.some(h => h.key === "Cache-Control" && h.value === "no-store"));
  assert.ok(headers.some(h => h.key === "x-vercel-enable-rewrite-caching" && h.value === "0"));
});
test("URL credentials, paths, wildcard hosts and insecure cloud origins fail closed", () => {
  for (const origin of ["http://spms.example.test", "https://*.vercel.app", "https://user:PrivateFixture@spms.example.test", "https://spms.example.test/api", "https://spms.example.test?key=PrivateFixture", "https://spms.example.test#fragment", "https://spms.example.test:8443", " https://spms.example.test", "https://127.0.0.1", "https://spms.example.test\\evil"]) {
    assert.throws(() => deploymentConfig({ VERCEL: "1", SPMS_BACKEND_ORIGIN: origin }), e => !e.message.includes("PrivateFixture"));
  }
});
test("localhost proxy is opt-in and is never allowed on Vercel", () => {
  const values = { SPMS_BACKEND_ORIGIN: "http://localhost:8012", SPMS_LOCAL_API_PROXY: "1" };
  assert.doesNotThrow(() => deploymentConfig(values));
  assert.throws(() => deploymentConfig({ ...values, VERCEL: "1" }));
  assert.throws(() => deploymentConfig({ SPMS_BACKEND_ORIGIN: values.SPMS_BACKEND_ORIGIN }));
});
test("direct browser API override cannot bypass the same-origin cookie design", () => {
  assert.throws(() => deploymentConfig({ SPMS_BACKEND_ORIGIN: "https://spms-api.example.test", NEXT_PUBLIC_API_BASE_URL: "https://another.example.test" }));
});
