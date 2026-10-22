/* 轮询脚本：每 2 秒取一次 /api/jobs/{id}，只更新状态文字与类名。
   规则（来自技术设计 §7）：
   - 不编造进度百分比，只显示阶段与状态；
   - 用 textContent 更新，不把服务端内容当 HTML 注入；
   - 任务结束（finished / cancelled）后停止轮询。

   语言规范：API 只返回英文 code（如 phase: "analyzing"、outcome: "rejected"），
   中文显示文案在前端映射（本文件），因此 API/导出数据保持全英文。
*/
(function () {
  "use strict";

  var body = document.body;
  var jobId = body.dataset.jobId;
  if (!jobId) return;

  var PHASE_LABELS = {
    draft: "草稿",
    queued: "排队中",
    running: "执行中",
    screening: "输入筛查",
    analyzing: "二进制分析",
    roundtrip: "C 往返校验",
    generating: "候选生成",
    applying: "写入副本",
    validating: "共享校验",
    finished: "已完成"
  };
  var OUTCOME_LABELS = {
    success_within_scope: "成功（声明范围内）",
    unsupported: "不支持",
    rejected: "被拒",
    inconclusive: "不确定",
    error: "错误",
    cancelled: "已取消"
  };
  var STATE_LABELS = {
    pending: "待执行",
    active: "进行中",
    done: "已完成",
    cancelled: "已取消"
  };
  var VALUE_LABELS = {
    not_run: "未运行（not_run）",
    passed: "通过",
    failed: "失败",
    inconclusive: "不确定",
    unavailable: "不可用"
  };

  function $(id) { return document.getElementById(id); }
  function setText(id, text) {
    var el = $(id);
    if (el) el.textContent = text;
  }

  function outcomeClass(outcome) {
    return outcome ? "outcome-" + outcome.replace(/_/g, "-") : "outcome-none";
  }

  function updateRoute(key, route) {
    setText("phase-" + key, PHASE_LABELS[route.phase] || route.phase);

    var badge = $("outcome-" + key);
    if (badge) {
      badge.textContent = OUTCOME_LABELS[route.outcome] || "尚无结论";
      badge.className = "badge " + outcomeClass(route.outcome);
    }

    var list = $("stages-" + key);
    if (list && route.stages) {
      route.stages.forEach(function (stage) {
        var li = list.querySelector('[data-stage="' + stage.name + '"]');
        if (!li) return;
        li.className = "stage stage-" + stage.state;
        var stateEl = li.querySelector(".stage-state");
        if (stateEl) stateEl.textContent = STATE_LABELS[stage.state] || stage.state;
      });
    }

    setText("tests-" + key, route.tests.passed + "/" + route.tests.total);
    setText("verification-" + key, VALUE_LABELS[route.verification] || route.verification);
    setText("compatibility-" + key, VALUE_LABELS[route.compatibility] || route.compatibility);
    setText("elapsed-" + key, route.elapsed_s + " s");
    setText("manual-" + key, route.manual_interventions + " 次");
    setText("ai-" + key, route.ai_usage);

    var reason = $("reason-" + key);
    if (reason) {
      reason.textContent = route.outcome_reason ? "结论原因：" + route.outcome_reason : "";
    }

    var tbody = $("regions-" + key);
    if (tbody && route.changed_regions && route.changed_regions.length) {
      tbody.textContent = "";
      route.changed_regions.forEach(function (region) {
        var tr = document.createElement("tr");
        [region.address, region.kind, region.before, region.after].forEach(function (value) {
          var td = document.createElement("td");
          if (value === region.address || value === region.before || value === region.after) {
            var code = document.createElement("code");
            code.textContent = value;
            td.appendChild(code);
          } else {
            td.textContent = value;
          }
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
    }
  }

  function overallResult(data) {
    if (data.cancelled) return { key: "cancelled", label: "已取消" };
    var finished = data.phase === "finished";
    if (!finished) return { key: "none", label: "—" };
    var outcomes = Object.keys(data.routes || {}).map(function (key) {
      return data.routes[key].outcome;
    });
    if (outcomes.indexOf("cancelled") !== -1) return { key: "cancelled", label: "已取消" };
    if (outcomes.indexOf("error") !== -1) return { key: "error", label: "失败（执行错误）" };
    if (outcomes.length && outcomes.every(function (value) { return value === "success_within_scope"; })) {
      return { key: "success-within-scope", label: "成功（声明范围内）" };
    }
    return { key: "rejected", label: "未达成（需两条路线各自成功）" };
  }

  function updateJob(data) {
    setText("job-phase", PHASE_LABELS[data.phase] || data.phase);

    var overall = overallResult(data);
    var overallBadge = $("job-outcome");
    if (overallBadge) {
      overallBadge.textContent = overall.label;
      overallBadge.className = "badge outcome-" + overall.key;
    }

    var finished = data.phase === "finished" || data.cancelled;
    Object.keys(data.routes).forEach(function (key) {
      updateRoute(key, data.routes[key]);
    });
    return finished;
  }

  var timer = null;

  function tick() {
    fetch("/api/jobs/" + encodeURIComponent(jobId), { headers: { "Accept": "application/json" } })
      .then(function (response) {
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.json();
      })
      .then(function (data) {
        var finished = updateJob(data);
        setText("poll-status", finished ? "已停止轮询（任务结束）" : "轮询中…");
        if (finished && timer) {
          clearInterval(timer);
          timer = null;
        }
      })
      .catch(function () {
        setText("poll-status", "网络错误，2 秒后重试");
      });
  }

  timer = setInterval(tick, 2000);
  tick();
})();
