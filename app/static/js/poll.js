/* 轮询脚本：每 2 秒取一次 /api/jobs/{id}，只更新状态文字与类名。
   规则（来自技术设计 §7）：
   - 不编造进度百分比，只显示阶段与状态；
   - 用 textContent 更新，不把服务端内容当 HTML 注入；
   - 任务结束（finished / cancelled）后停止轮询。
*/
(function () {
  "use strict";

  var body = document.body;
  var jobId = body.dataset.jobId;
  if (!jobId) return;

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

  function updateRoute(key, route) {
    setText("phase-" + key, route.phase_label);

    var badge = $("outcome-" + key);
    if (badge) {
      badge.textContent = route.outcome_label || "尚无结论";
      badge.className = "badge " + (route.outcome_class || "outcome-none");
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

  function updateJob(data) {
    setText("job-phase", data.phase_label);

    var finished = data.phase === "finished" || data.cancelled;
    var outcomes = Object.keys(data.routes).map(function (key) {
      return data.routes[key].outcome;
    });
    var overall = "—";
    if (finished) {
      if (outcomes.length === 2 && outcomes.every(function (v) { return v === "success_within_scope"; })) {
        overall = "成功（声明范围内）";
      } else if (outcomes.indexOf("cancelled") !== -1) {
        overall = "已取消";
      } else {
        overall = "未达成（需两条路线各自成功）";
      }
    }
    setText("job-outcome", overall);

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
