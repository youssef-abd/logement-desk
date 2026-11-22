// Runs before the page paints so a chosen theme does not flash. Automatic = no attribute: the stylesheet follows the system.
(function () {
  try { var t = localStorage.getItem("ld-theme"); if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t); } catch (e) { /* private mode */ }
})();
