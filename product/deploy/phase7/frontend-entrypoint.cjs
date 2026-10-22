// Production-only entrypoint. No identity harness or token minting is shipped.
function origin(value) {
  try {
    const u = new URL(value);
    return u.protocol === "https:" && !u.username && !u.password &&
      u.pathname === "/" && !u.search && !u.hash &&
      !["localhost", "127.0.0.1", "[::1]"].includes(u.hostname);
  } catch { return false; }
}
function endpoint(value, secure = false) {
  try {
    const u = new URL(value);
    return (secure ? u.protocol === "https:" : ["http:", "https:"].includes(u.protocol)) &&
      !!u.hostname && !u.username && !u.password && !u.search && !u.hash;
  } catch { return false; }
}
function valid(e) {
  return e.NODE_ENV === "production" && /^[a-f0-9]{40}$/.test(e.FLA_RELEASE_SHA || "") &&
    origin(e.NEXTAUTH_URL) && endpoint(e.OIDC_ISSUER_URL, true) &&
    (e.NEXTAUTH_SECRET || "").length >= 32 && !!e.OIDC_CLIENT_ID &&
    !!e.OIDC_CLIENT_SECRET && endpoint(e.BACKEND_URL);
}
if (require.main === module) {
  if (!valid(process.env)) {
    console.error("frontend_production_configuration_invalid");
    process.exit(1);
  }
  require("./server.js");
}
module.exports = { valid };
