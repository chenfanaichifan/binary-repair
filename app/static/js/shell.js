/* Collapsible application sidebar. The state is persisted and applied before
 * paint by the inline boot script in base.html; this file only handles the
 * two buttons and the accessibility state. */
(function () {
  "use strict";
  var root = document.documentElement;
  var toggle = document.getElementById("ds-sidebar-toggle");
  var expand = document.getElementById("ds-sidebar-expand");
  var sidebar = document.getElementById("ds-sidebar");
  if (!toggle || !expand || !sidebar) return;

  function persist(collapsed) {
    try { window.localStorage.setItem("br.sidebar", collapsed ? "collapsed" : "open"); } catch (e) {}
  }

  function setCollapsed(collapsed, save) {
    root.classList.toggle("side-collapsed", collapsed);
    toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
    expand.setAttribute("aria-expanded", collapsed ? "true" : "false");
    toggle.setAttribute("aria-label", collapsed ? "展开侧栏" : "收起侧栏");
    expand.setAttribute("aria-label", collapsed ? "展开侧栏" : "收起侧栏");
    if (save) { persist(collapsed); }
    if (save) {
      if (collapsed) {
        expand.focus({ preventScroll: true });
      } else {
        var first = sidebar.querySelector("a, button");
        if (first) { first.focus({ preventScroll: true }); }
      }
    }
  }

  setCollapsed(root.classList.contains("side-collapsed"), false);
  toggle.addEventListener("click", function () { setCollapsed(true, true); });
  expand.addEventListener("click", function () { setCollapsed(false, true); });
  document.addEventListener("keydown", function (event) {
    if ((event.metaKey || event.ctrlKey) && event.key === "\\") {
      event.preventDefault();
      setCollapsed(!root.classList.contains("side-collapsed"), true);
    }
  });
})();
