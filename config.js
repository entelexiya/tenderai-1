// Use the same origin for the combined app, or the existing Space on GitHub Pages.
window.TENDERAI_CONFIG = Object.freeze({
  apiBase: location.hostname.endsWith("github.io")
    ? "https://entelexiya-tenderai-api.hf.space"
    : "",
  timeoutMs: 90000,
});
