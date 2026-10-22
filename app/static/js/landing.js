/* Landing hero slides + about sheet. */
(function () {
  "use strict";

  var slides = [
    {
      eyebrow: "AI-DRIVEN BINARY VULNERABILITY REPAIR",
      body: "上传 ELF 样本、冻结安全契约；两条路线分别做直接指令修复与恢复 C 回填。漏洞位置高亮、AI 候选交互展示，结果由 V0–V5 确定性义务与可复核证据决定，而不是\u201c看起来更安全\u201d。"
    },
    {
      eyebrow: "DISASSEMBLY · VULNERABILITY HIGHLIGHT",
      body: "反汇编与恢复 C 双视图：漏洞指令/行红色高亮，修复后新增行与差异行可切换，点击任意高亮行查看地址、改动原因与对应契约。"
    },
    {
      eyebrow: "CONTRACT · REVISION · V0\u2013V5 EVIDENCE",
      body: "契约修改会生成新 revision 并清除批准，陈旧 revision 或哈希返回 409；导出包含义务结论、范围假设与产物哈希，证据可被独立复核。"
    }
  ];

  var root = document.querySelector(".hero-info");
  var eyebrow = document.querySelector('[data-slide="eyebrow"]');
  var line = document.querySelector('[data-slide="body"]');
  var dots = Array.prototype.slice.call(document.querySelectorAll("[data-slide-dot]"));
  var index = 0;
  var timer = null;

  function render(next) {
    index = (next + slides.length) % slides.length;
    root.classList.add("is-changing");
    eyebrow.style.opacity = "0";
    window.setTimeout(function () {
      eyebrow.textContent = slides[index].eyebrow;
      line.textContent = slides[index].body;
      dots.forEach(function (dot, i) {
        var active = i === index;
        dot.classList.toggle("is-active", active);
        dot.setAttribute("aria-selected", active ? "true" : "false");
      });
      root.classList.remove("is-changing");
      eyebrow.style.opacity = "";
    }, 200);
  }

  function start() {
    stop();
    timer = window.setInterval(function () { render(index + 1); }, 8000);
  }
  function stop() {
    if (timer) { window.clearInterval(timer); timer = null; }
  }

  document.querySelectorAll("[data-slide-prev]").forEach(function (button) {
    button.addEventListener("click", function () { render(index - 1); start(); });
  });
  document.querySelectorAll("[data-slide-next]").forEach(function (button) {
    button.addEventListener("click", function () { render(index + 1); start(); });
  });
  dots.forEach(function (dot) {
    dot.addEventListener("click", function () {
      render(Number(dot.getAttribute("data-slide-dot")));
      start();
    });
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "ArrowLeft") { render(index - 1); }
    if (event.key === "ArrowRight") { render(index + 1); }
  });

  if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    start();
    document.querySelector(".hero").addEventListener("mouseenter", stop);
    document.querySelector(".hero").addEventListener("mouseleave", start);
  }

  /* About sheet */
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
