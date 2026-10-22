/* Landing page: about sheet only (no slides). */
(function () {
  "use strict";

  var sheet = document.querySelector("[data-about-sheet]");

  function openAbout() {
    if (!sheet) return;
    sheet.classList.remove("is-hidden");
    var close = sheet.querySelector("[data-about-close]");
    if (close) close.focus();
  }

  function closeAbout() {
    if (!sheet) return;
    sheet.classList.add("is-hidden");
  }

  document.querySelectorAll("[data-about]").forEach(function (link) {
    link.addEventListener("click", function (event) {
      event.preventDefault();
      openAbout();
    });
  });
  document.querySelectorAll("[data-about-close]").forEach(function (button) {
    button.addEventListener("click", closeAbout);
  });
  if (sheet) {
    sheet.addEventListener("click", function (event) {
      if (event.target === sheet) closeAbout();
    });
  }
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeAbout();
  });
})();
