/**
 * Shared API base for the TMS UI.
 *
 * window.__TMS_API_BASE__ is injected by /runtime-config.js from server config.
 * Empty string = same origin (correct when UI is served by FastAPI).
 */
(function (global) {
  const raw = global.__TMS_API_BASE__;
  const base =
    typeof raw === "string" ? raw.replace(/\/$/, "") : "";

  function url(path) {
    const p = path.startsWith("/") ? path : `/${path}`;
    return `${base}${p}`;
  }

  global.TMS_API = { base, url };
})(window);
