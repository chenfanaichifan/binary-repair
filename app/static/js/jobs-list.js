/* ============================================================================
 * 侧栏任务列表（所有工作台页面共用）。
 *
 * 数据来源只有两处：
 *  1. 本机 localStorage：用户在本浏览器里创建/打开过的任务（顺序、可追溯）。
 *  2. 逐条 GET /api/jobs/{id}：核对任务是否仍存在、当前 phase。
 *
 * 边界：
 *  - 不伪造“全量任务列表”。没有 controller 的列表端点，这里就只显示本机记录，
 *    并在侧栏写明来源。
 *  - 不写任何后端状态；不删除记录（不可查时标灰，仍可追溯）。
 *  - 全部用 textContent 渲染，不拼接 HTML。
 * ========================================================================== */
(function () {
  "use strict";

  var KEY = "br.jobs.v1";
  var LIMIT = 50;

  var PHASE_LABELS = {
    draft: "草稿", queued: "排队中", running: "执行中", screening: "输入筛查",
    analyzing: "二进制分析", roundtrip: "C 往返校验", generating: "候选生成",
    applying: "写入副本", validating: "共享校验", finished: "已完成"
  };

  function read() {
    try {
      var raw = window.localStorage.getItem(KEY);
      if (!raw) return [];
      var list = JSON.parse(raw);
      if (!Array.isArray(list)) return [];
      return list.filter(function (item) {
        return item && typeof item.id === "string" && item.id;
      });
    } catch (error) {
      return [];
    }
  }

  function write(list) {
    try {
      window.localStorage.setItem(KEY, JSON.stringify(list.slice(0, LIMIT)));
    } catch (error) {
      /* 存储不可用时列表只在当前页面内存里；不阻断工作台。 */
    }
  }

  function currentId() {
    if (document.body && document.body.dataset.jobId) return document.body.dataset.jobId;
    var match = /^\/agent\/([^/?#]+)$/.exec(window.location.pathname);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function labelOf(entry) {
    return entry.label || "任务 " + entry.id.slice(0, 8);
  }

  function render() {
    var nav = document.getElementById("ds-job-list");
    if (!nav) return;
    var list = read();
    nav.textContent = "";

    if (!list.length) {
      var empty = document.createElement("p");
      empty.className = "ds-job-empty";
      empty.dataset.testid = "ds-job-empty";
      empty.textContent = "还没有本机任务记录。";
      nav.appendChild(empty);
      return;
    }

    var active = currentId();
    list.forEach(function (entry) {
      var link = document.createElement("a");
      link.className = "ds-job-item";
      link.href = "/agent/" + encodeURIComponent(entry.id);
      link.dataset.jobId = entry.id;
      link.dataset.testid = "ds-job-item";
      if (entry.id === active) link.classList.add("is-active");

      var dot = document.createElement("span");
      dot.className = "ds-job-dot";
      dot.setAttribute("aria-hidden", "true");

      var name = document.createElement("span");
      name.className = "ds-job-name";
      name.textContent = labelOf(entry);
      name.title = entry.id;

      var phase = document.createElement("span");
      phase.className = "ds-job-phase";
      phase.textContent = "";

      link.appendChild(dot);
      link.appendChild(name);
      link.appendChild(phase);
      nav.appendChild(link);
    });

    hydrate(nav);
  }

  var states = {};

  function mark(item, state, text) {
    item.dataset.state = state;
    var phase = item.querySelector(".ds-job-phase");
    if (phase) phase.textContent = text;
    states[item.dataset.jobId] = { state: state, text: text };
    document.dispatchEvent(new CustomEvent("brjobs:state", {
      detail: { id: item.dataset.jobId, state: state, text: text }
    }));
  }

  function hydrate(nav) {
    var items = nav.querySelectorAll(".ds-job-item");
    Array.prototype.forEach.call(items, function (item) {
      var id = item.dataset.jobId;
      fetch("/api/jobs/" + encodeURIComponent(id), {
        headers: { Accept: "application/json" }
      }).then(function (response) {
        if (response.status === 404) {
          mark(item, "missing", "后端已不可查");
          return null;
        }
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.json();
      }).then(function (data) {
        if (!data) return;
        if (data.cancelled) {
          mark(item, "cancelled", "已取消");
          return;
        }
        var phase = data.phase || "unknown";
        mark(item, phase, PHASE_LABELS[phase] || phase);
      }).catch(function () {
        mark(item, "unreachable", "状态未知");
      });
    });
  }

  function register(id, label) {
    if (!id || typeof id !== "string") return;
    var list = read();
    var existing = null;
    for (var i = 0; i < list.length; i += 1) {
      if (list[i].id === id) { existing = list[i]; break; }
    }
    var entry = {
      id: id,
      label: label || (existing && existing.label) || "",
      added_at: (existing && existing.added_at) || new Date().toISOString()
    };
    var rest = list.filter(function (item) { return item.id !== id; });
    write([entry].concat(rest));
    render();
  }

  window.BRJobs = {
    register: register,
    render: render,
    currentId: currentId,
    list: read,
    states: states
  };

  render();

  window.addEventListener("storage", function (event) {
    if (event.key === KEY) render();
  });
})();
