/* Theme controller: light/dark switching + sidebar collapse.
   Runs early (loaded from <head>) so data-theme is applied before first paint. */
(function () {
  "use strict";

  var THEME_KEY = "sms-theme";
  var SIDEBAR_KEY = "sms-sidebar-collapsed";
  var TRANSITION_MS = 340;
  var root = document.documentElement;
  var transitionTimer = null;

  function readStored(key) {
    try { return window.localStorage.getItem(key); } catch (error) { return null; }
  }

  function writeStored(key, value) {
    try { window.localStorage.setItem(key, value); } catch (error) { /* private mode: keep session-only */ }
  }

  function prefersDark() {
    return Boolean(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
  }

  function applyTheme(theme) {
    root.setAttribute("data-theme", theme === "dark" ? "dark" : "light");
  }

  applyTheme(readStored(THEME_KEY) || (prefersDark() ? "dark" : "light"));

  // Follow OS-level changes only while the user has not made an explicit choice.
  if (window.matchMedia) {
    var colorScheme = window.matchMedia("(prefers-color-scheme: dark)");
    var onSchemeChange = function (event) {
      if (!readStored(THEME_KEY)) applyTheme(event.matches ? "dark" : "light");
    };
    if (colorScheme.addEventListener) colorScheme.addEventListener("change", onSchemeChange);
    else if (colorScheme.addListener) colorScheme.addListener(onSchemeChange);
  }

  function withSmoothTransition(action) {
    root.classList.add("theme-transition");
    window.clearTimeout(transitionTimer);
    transitionTimer = window.setTimeout(function () {
      root.classList.remove("theme-transition");
    }, TRANSITION_MS);
    action();
  }

  function toggleTheme() {
    withSmoothTransition(function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      applyTheme(next);
      writeStored(THEME_KEY, next);
    });
  }

  function bind() {
    var themeButton = document.getElementById("theme-toggle");
    if (themeButton) themeButton.addEventListener("click", toggleTheme);

    var sidebarButton = document.getElementById("sidebar-toggle");
    var shell = document.querySelector(".app-shell");
    if (sidebarButton && shell) {
      if (readStored(SIDEBAR_KEY) === "1") shell.classList.add("sidebar-collapsed");
      sidebarButton.addEventListener("click", function () {
        shell.classList.toggle("sidebar-collapsed");
        writeStored(SIDEBAR_KEY, shell.classList.contains("sidebar-collapsed") ? "1" : "0");
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }
})();
