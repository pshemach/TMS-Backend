/**
 * TMS UI API helper.
 *
 * __TMS_API_BASE__ comes from /runtime-config.js (server .env).
 * Leave empty for same-origin requests (/fleet, /order, …).
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
