/* ============================================================================
 * 修复控制台（/agent）—— M2（GUI owner）专属。
 *
 * 边界（Lead 87 号分配）：
 *  - 不实现 assistant planner，不定义 plan 内容；plan 来自 M5（开发期用 fixture）。
 *  - 不调用任何模型，不读写 API key。
 *  - 创建任务必须用户显式点击；助手不发起运行、不写 verdict。
 *  - 前端不计算 outcome；义务结果逐字渲染后端取值。
 *  - 未回传（receipt pending）时显示占位，不渲染 not_run。
 *  - 不引入框架 / 构建 / SSE / WebSocket；2 秒轮询，页面隐藏时降频。
 *
 * 语言：界面文案中文；进入提交 payload 的值必须是英文 ASCII（行内校验拦截）。
 * ========================================================================== */
(function () {
  "use strict";

  var root = document.getElementById("agent-root");
  if (!root) return;

  /* The deliverable upload posts to a same-origin API, so it only makes sense
   * when the page is served over HTTP(S). Opened from file:// the endpoint does
   * not exist, and offering the control would only produce a network error. */
  var UPLOAD_AVAILABLE =
    window.location.protocol === "http:" || window.location.protocol === "https:";

  /* Mirrors DELIVERABLE_MAX_BYTES in app/controller_api.py so the browser can
   * reject oversized files without a round trip. Keep the two in sync. */
  var DELIVERABLE_MAX_BYTES = 64 * 1024 * 1024;

  /* ---------- 状态面板：可折叠，让对话流占满整行 ---------- */

  var sideBody = document.querySelector(".agent-body");
  var sideToggle = document.getElementById("agent-side-toggle");
  var SIDE_KEY = "br.agent.side.collapsed";

  function readSidePref() {
    try { return window.localStorage.getItem(SIDE_KEY); } catch (e) { return null; }
  }

  function setSideCollapsed(collapsed, persist) {
    if (!sideBody || !sideToggle) return;
    sideBody.classList.toggle("is-side-collapsed", collapsed);
    sideToggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
    sideToggle.textContent = collapsed ? "展开状态面板" : "收起状态面板";
    if (persist) {
      try { window.localStorage.setItem(SIDE_KEY, collapsed ? "1" : "0"); } catch (e) {}
    }
  }

  if (sideToggle && sideBody) {
    var storedSide = readSidePref();
    var narrowSide = window.matchMedia("(max-width: 1100px)").matches;
    /* 窄屏默认收起；用户显式选择过就尊重它。 */
    setSideCollapsed(storedSide === null ? narrowSide : storedSide === "1", false);
    sideToggle.addEventListener("click", function () {
      setSideCollapsed(!sideBody.classList.contains("is-side-collapsed"), true);
    });
  }

  var FIXTURE_MODE = root.dataset.fixture === "1";
  var CSRF = root.dataset.csrf || "";
  var FIXTURES = window.AGENT_FIXTURES || null;
  var QUERY = new URLSearchParams(window.location.search);
  /* ?plan=fixture：引导计划用占位 plan（M5 T8.1 未接入），但创建任务仍走真实
     POST /jobs、之后真实轮询。与 ?fixture=1（全演示、不创建）区分开。 */
  var PLAN_FIXTURE = !FIXTURE_MODE && QUERY.get("plan") === "fixture" && !!FIXTURES;

  var ASSISTANT_MODE = root.dataset.assistantMode || "deterministic";
  var ASSISTANT_AVAILABLE = root.dataset.assistantAvailable === "1";

  var state = {
    jobId: root.dataset.jobId || "",
    plan: null,
    stepIndex: 0,
    answers: {},
    file: null,
    snapshot: null,
    artifacts: [],
    view: "chat",
    scenario: "fresh",
    submitting: false,
    replaying: false,
    planPending: null,
    entries: []
  };

  /* ---------- 单任务历史（本机） ----------
   * 每个任务 id 一个键，只存对话与工具摘要，不存文件内容。
   * 服务端历史要等 M5 的 T8.1 持久化；这里明确标注来源，不冒充跨设备记录。 */

  var HISTORY_LIMIT = 120;

  function historyKey() {
    return "br.msg.v1." + (state.jobId || "draft");
  }

  function readHistory() {
    try {
      var raw = window.localStorage.getItem(historyKey());
      var list = raw ? JSON.parse(raw) : [];
      return Array.isArray(list) ? list : [];
    } catch (error) {
      return [];
    }
  }

  function writeHistoryFor(jobId, list) {
    if (!jobId) return;
    try {
      window.localStorage.setItem(
        "br.msg.v1." + jobId,
        JSON.stringify(list.slice(-HISTORY_LIMIT))
      );
    } catch (error) {
      /* 存储满或被禁用时不阻断对话；当前页仍然可用。 */
    }
  }

  function record(entry) {
    if (state.replaying || FIXTURE_MODE) return;
    state.entries.push(entry);
    if (state.entries.length > HISTORY_LIMIT) {
      state.entries = state.entries.slice(-HISTORY_LIMIT);
    }
    if (state.jobId) writeHistoryFor(state.jobId, state.entries);
  }

  function registerJob(label) {
    if (!state.jobId || !window.BRJobs) return;
    window.BRJobs.register(state.jobId, label);
  }

  /* ---------- 中文展示标签：仅翻译，不判定 ---------- */

  var PHASE_LABELS = {
    draft: "草稿", queued: "排队中", running: "执行中", screening: "输入筛查",
    analyzing: "二进制分析", roundtrip: "C 往返校验", generating: "候选生成",
    applying: "写入副本", validating: "共享校验", finished: "已完成"
  };
  var OUTCOME_LABELS = {
    success_within_scope: "成功（声明范围内）", unsupported: "不支持", rejected: "被拒",
    inconclusive: "不确定", error: "错误", cancelled: "已取消"
  };
  var STATE_LABELS = { pending: "待执行", active: "进行中", done: "已完成", cancelled: "已取消" };
  // 时间线语义来自后端 timeline_status；route/status 的旧语义保持不变。
  var TIMELINE_LABELS = {
    ok: "成功", failed: "失败", timeout: "超时", cancelled: "已取消", unknown: "未知"
  };
  // T8.4：badge 用人话显示计划来源，同时保留原始 mode 值便于核对。
  var PLAN_MODE_LABELS = { deterministic: "脚本 v1", llm: "LLM" };
  var KIND_ORDER = { identity: 0, structure: 1, interface: 2, behaviour: 3, symbolic: 4, reproducibility: 5 };

  /* 失败原因展示字典：只负责把后端给出的 reason_code 翻译成人话并附建议。
     它永远不产生 reason_code，也不参与任何判定。未登记的 code 原样显示。 */
  var REASON_INFO = {
    worker_env_missing: {
      title: "测试机缺少必需的环境变量",
      advice: [
        { text: "在测试机补齐 BINARYREPAIR_ORIGINAL 与 BINARYREPAIR_CONTRACT 后重跑该 attempt", owner: "M1/M3", retry: "可重试" }
      ]
    },
    original_missing: {
      title: "原始样本未随任务下发到测试机",
      advice: [{ text: "检查 controller 是否把 original.elf 拷入 job_dir", owner: "M1", retry: "可重试" }]
    },
    contract_missing_or_stale: {
      title: "契约文件缺失或哈希与审批记录不符",
      advice: [{ text: "重新审批契约（新 revision）并重新下发到测试机", owner: "M1/M2", retry: "可重试" }]
    },
    candidate_hash_mismatch: {
      title: "候选文件哈希与 edit-manifest 记录不一致",
      advice: [{ text: "重新生成候选，不要手工替换候选文件", owner: "M3", retry: "可重试" }]
    },
    layout_conflict: {
      title: "补丁破坏了 ELF 段布局约束",
      advice: [{ text: "改为扩展已有 PT_LOAD 的 p_filesz/p_memsz，不新增段", owner: "M3/M5", retry: "可重试" }]
    },
    toolchain_missing: {
      title: "测试机缺少执行工具链",
      advice: [{ text: "挂载 patcherex2 / LIEF / Ghidra，并在 status.json.tool_versions 留证", owner: "M3", retry: "可重试" }]
    },
    execution_timeout: {
      title: "执行超时",
      advice: [{ text: "提高超时阈值或拆分用例；检查候选是否引入死循环", owner: "M3", retry: "可重试" }]
    },
    crash_on_invalid_input: {
      title: "越界输入仍导致崩溃",
      advice: [{ text: "补长度检查后重新生成候选", owner: "M3/M5", retry: "可重试" }]
    },
    regression_on_valid_input: {
      title: "合法输入的行为发生回退",
      advice: [{ text: "与基线用例逐条对比，缩小补丁改动面", owner: "M3", retry: "可重试" }]
    },
    unsupported_arch: {
      title: "样本架构或格式不在支持范围",
      advice: [{ text: "仅支持 x86-64 ELF；更换样本或在契约中声明 unsupported", owner: "M3", retry: "不可重试" }]
    },
    evidence_incomplete: {
      title: "证据不全，部分义务未执行",
      advice: [{ text: "补齐对应 obligation 的证据后再判定", owner: "M4", retry: "可重试" }]
    },
    bundle_unverified: {
      title: "回传包校验失败（哈希或清单不符）",
      advice: [{ text: "按 SHA256SUMS 重新打包回传", owner: "M3", retry: "可重试" }]
    },
    bundle_rejected_path: {
      title: "回传包含有越界路径",
      advice: [{ text: "只允许 bundle-root 下的相对路径，禁止 .. / 绝对路径 / 软链", owner: "M1", retry: "不可重试" }]
    }
  };

  /* ---------- DOM 工具 ---------- */

  function $(id) { return document.getElementById(id); }
  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }
  function clear(node) { if (node) node.textContent = ""; }
  function setText(id, text) { var node = $(id); if (node) node.textContent = text; }
  function show(id, visible) { var node = $(id); if (node) node.hidden = !visible; }
  function shortHash(value) { return value ? String(value).slice(0, 16) + "…" : "—"; }
  function stream() { return $("agent-stream"); }
  function scrollStream() {
    var node = stream();
    if (node) node.scrollTop = node.scrollHeight;
  }

  /* ---------- 数据源与归一化 ----------
   * 渲染层只消费 normalize() 的返回结构。execution-bridge-v1 与 M5 plan schema
   * 到位后，只需调整这里与取数函数，不动渲染层。 */

  function routeUsage(routes) {
    // M1: routes.<A|B>.ai_usage is {input_tokens, output_tokens, partial} or null.
    // Only surface numbers the backend actually sent; never fill them in.
    if (!routes || typeof routes !== "object") return null;
    var keys = Object.keys(routes);
    for (var i = 0; i < keys.length; i += 1) {
      var usage = routes[keys[i]] && routes[keys[i]].ai_usage;
      if (usage && typeof usage === "object") {
        return {
          input: typeof usage.input_tokens === "number" ? usage.input_tokens : undefined,
          output: typeof usage.output_tokens === "number" ? usage.output_tokens : undefined,
          partial: usage.partial === true,
          model: typeof usage.model === "string" ? usage.model : null
        };
      }
    }
    return null;
  }

  function normalize(data) {
    data = data || {};
    var agent = data.agent || null;
    if (!agent) {
      var usage = routeUsage(data.routes);
      if (usage) {
        agent = {
          model: usage.model,
          tokens: { input: usage.input, output: usage.output, partial: usage.partial }
        };
      }
    }
    var execution = data.execution || null;
    var routes = data.routes || {};
    var routeKeys = Object.keys(routes);

    // 占位推导：协议到位后改为直读 execution.status。
    var receiptPending = false;
    if (execution && typeof execution.receipt_pending === "boolean") {
      receiptPending = execution.receipt_pending;
    }

    var obligations = [];
    routeKeys.forEach(function (key) {
      var list = routes[key].obligations || [];
      list.forEach(function (item) {
        obligations.push({
          route: key,
          id: item.id || item.kind || "?",
          kind: item.kind || "",
          result: item.result, // 逐字保留，不映射、不美化
          reason: item.reason || item.detail || ""
        });
      });
    });
    if (!obligations.length && Array.isArray(data.obligations)) {
      // 兼容顶层形状：routes 未携带义务时按顶层列表渲染，route 缺失记为 "?"。
      data.obligations.forEach(function (item) {
        if (!item || typeof item !== "object") return;
        obligations.push({
          route: item.route || "?",
          id: item.id || item.kind || "?",
          kind: item.kind || "",
          result: item.result,
          reason: item.reason || item.detail || ""
        });
      });
    }
    obligations.sort(function (a, b) {
      return (KIND_ORDER[a.kind] === undefined ? 99 : KIND_ORDER[a.kind]) -
             (KIND_ORDER[b.kind] === undefined ? 99 : KIND_ORDER[b.kind]);
    });

    return {
      jobId: data.job_id || data.id || state.jobId || "",
      phase: data.phase || "",
      cancelled: !!data.cancelled,
      originalSha256: data.original_sha256 || "",
      contract: data.contract || null,
      verdict: data.verdict || null,
      routes: routes,
      routeKeys: routeKeys,
      obligations: obligations,
      artifacts: data.artifacts || [],
      candidate: data.candidate || null,
      agent: agent,
      execution: execution,
      receiptPending: receiptPending,
      scope: data.scope || null,
      bounded: data.bounded || null
    };
  }

  var evidenceCache = {};
  var attemptsCache = { jobId: "", available: null, items: [] };
  var comparisonCache = null; // { status, detail, artifacts }

  // 179 契约：GET /api/jobs/{id}/comparison
  // not_provided / 端点不可用一律按不可用显示，绝不显示通过，也不猜字段名。
  function fetchComparison(jobId) {
    if (!jobId) { comparisonCache = null; return Promise.resolve(null); }
    return fetch("/api/jobs/" + encodeURIComponent(jobId) + "/comparison", {
      headers: { Accept: "application/json" }
    }).then(function (response) {
      if (!response.ok) {
        comparisonCache = { status: "unavailable", detail: "HTTP " + response.status, artifacts: [] };
        return comparisonCache;
      }
      return response.json();
    }).then(function (payload) {
      if (!payload || typeof payload.status !== "string") {
        comparisonCache = { status: "unavailable", detail: "payload 不可解析", artifacts: [] };
        return comparisonCache;
      }
      comparisonCache = {
        status: payload.status,
        detail: payload.detail || "",
        artifacts: Array.isArray(payload.artifacts) ? payload.artifacts : []
      };
      return comparisonCache;
    }).catch(function () {
      comparisonCache = { status: "unavailable", detail: "请求失败", artifacts: [] };
      return comparisonCache;
    });
  }

  function fetchAttemptEvidence(attemptId) {
    if (evidenceCache[attemptId]) return Promise.resolve(evidenceCache[attemptId]);
    return fetch("/api/attempts/" + encodeURIComponent(attemptId) + "/evidence", {
      headers: { Accept: "application/json" }
    }).then(function (response) {
      if (!response.ok) return null;
      return response.json();
    }).then(function (payload) {
      if (!payload || payload.available === false) return null;
      evidenceCache[attemptId] = payload;
      return payload;
    }).catch(function () { return null; });
  }

  function attachAttemptEvidence(data) {
    var routes = data && data.routes ? data.routes : {};
    var wanted = [];
    Object.keys(routes).forEach(function (key) {
      var id = routes[key] && routes[key].attempt_id;
      if (typeof id === "string" && id) wanted.push({ key: key, id: id });
    });
    if (!wanted.length) return Promise.resolve(data);
    return Promise.all(wanted.map(function (item) {
      return fetchAttemptEvidence(item.id);
    })).then(function (items) {
      wanted.forEach(function (item, index) {
        if (items[index]) routes[item.key].__evidence = items[index];
      });
      return data;
    });
  }

  function fetchAttempts(jobId) {
    if (!jobId || FIXTURE_MODE) return Promise.resolve();
    return fetch("/api/jobs/" + encodeURIComponent(jobId) + "/attempts", {
      headers: { Accept: "application/json" }
    }).then(function (response) {
      // 404 表示端点/任务不可用，必须与“零次尝试”分开。
      if (response.status === 404) return { available: false, attempts: [] };
      if (!response.ok) return { available: false, attempts: [] };
      return response.json();
    }).then(function (data) {
      if (state.jobId !== jobId) return;
      attemptsCache = {
        jobId: jobId,
        available: !!(data && data.available !== false),
        items: data && Array.isArray(data.attempts) ? data.attempts : []
      };
    }).catch(function () {
      if (state.jobId === jobId) {
        attemptsCache = { jobId: jobId, available: false, items: [] };
      }
    });
  }

  function fetchLiveSnapshot() {
    return fetch("/api/jobs/" + encodeURIComponent(state.jobId), {
      headers: { Accept: "application/json" }
    }).then(function (response) {
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    }).then(attachAttemptEvidence);
  }

  function fetchArtifacts() {
    if (!state.jobId) return Promise.resolve([]);
    var jobId = state.jobId;
    return fetch("/api/jobs/" + encodeURIComponent(jobId) + "/artifacts", {
      headers: { Accept: "application/json" }
    }).then(function (response) {
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    }).then(function (payload) {
      var out = [];
      ["A", "B"].forEach(function (key) {
        var rows = payload && Array.isArray(payload[key]) ? payload[key] : [];
        rows.forEach(function (row) {
          if (row && typeof row === "object") out.push(row);
        });
      });
      if (state.jobId === jobId) state.artifacts = out;
      return out;
    }).catch(function () {
      if (state.jobId === jobId) state.artifacts = [];
      return [];
    });
  }

  /* ---------- 终端流渲染 ---------- */

  function pushMessage(role, text, options) {
    var item = el("li", "agent-msg agent-msg-" + role);
    var head = el("div", "agent-msg-head");
    head.appendChild(el("span", "agent-msg-role", role === "user" ? "你" : "助手"));
    var body = el("div", "agent-msg-body", text);
    item.appendChild(head);
    item.appendChild(body);
    stream().appendChild(item);
    scrollStream();
    if (!(options && options.replay)) {
      record({ kind: "message", role: role, text: text, at: new Date().toISOString() });
    }
    return body;
  }

  function pushTool(name, summary, fields, raw, options) {
    var item = el("li", "agent-msg");
    var tool = el("div", "agent-tool");
    var button = el("button", "agent-tool-summary");
    button.type = "button";
    button.setAttribute("aria-expanded", "false");
    button.appendChild(el("span", "agent-tool-name", name));
    button.appendChild(el("span", null, summary));
    var toggle = el("span", "agent-tool-toggle", "展开 ▾");
    button.appendChild(toggle);

    var detail = el("div", "agent-tool-detail");
    detail.hidden = true;
    if (fields) {
      var dl = el("dl", "agent-tool-fields");
      Object.keys(fields).forEach(function (key) {
        dl.appendChild(el("dt", null, key));
        dl.appendChild(el("dd", null, fields[key]));
      });
      detail.appendChild(dl);
    }
    if (raw) detail.appendChild(el("pre", null, raw));

    button.addEventListener("click", function () {
      detail.hidden = !detail.hidden;
      toggle.textContent = detail.hidden ? "展开 ▾" : "收起 ▴";
      button.setAttribute("aria-expanded", detail.hidden ? "false" : "true");
    });

    tool.appendChild(button);
    tool.appendChild(detail);
    item.appendChild(tool);
    stream().appendChild(item);
    scrollStream();
    if (!(options && options.replay)) {
      record({
        kind: "tool",
        name: name,
        summary: summary,
        fields: fields || {},
        at: new Date().toISOString()
      });
    }
  }

  function replayHistory() {
    var entries = state.entries;
    if (!entries.length) return;
    state.replaying = true;
    entries.forEach(function (entry) {
      if (!entry || typeof entry !== "object") return;
      if (entry.kind === "message" && typeof entry.text === "string") {
        pushMessage(entry.role === "user" ? "user" : "assistant", entry.text, { replay: true });
      } else if (entry.kind === "tool" && typeof entry.name === "string") {
        pushTool(entry.name, entry.summary || "", entry.fields || {}, null, { replay: true });
      }
    });
    state.replaying = false;
  }

  function pushCard(cardElement) {
    var item = el("li", "agent-msg");
    item.appendChild(cardElement);
    stream().appendChild(item);
    scrollStream();
  }

  /* ---------- 引导流程（plan 驱动；plan 内容由 M5 提供） ---------- */

  /* 计划只来自后端。后端没开通就直说“未接通”，绝不退回 fixture 冒充真实计划。 */
  function planUnavailableText(data) {
    if (!data) { return "计划服务未接通（网络错误）"; }
    if (data.error === "assistant_unavailable") {
      return "计划服务未接通（" + (data.fallback_reason || data.detail || "endpoint_missing") + "）";
    }
    if (data.error === "invalid_request") {
      return "计划请求无效（" + (data.detail || "缺少描述") + "）";
    }
    return "计划服务返回了无法使用的结果";
  }

  function requestPlan(description) {
    if (state.planPending) return state.planPending;
    state.planPending = fetch("/api/assistant/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": CSRF },
      body: JSON.stringify({ description: description, context: {} })
    }).then(function (response) {
      return response.json().then(function (data) {
        return { ok: response.ok, status: response.status, data: data };
      }, function () {
        return { ok: false, status: response.status, data: null };
      });
    }, function () {
      return { ok: false, status: 0, data: null };
    }).then(function (result) {
      state.planPending = null;
      return result;
    });
    return state.planPending;
  }

  function currentStep() {
    return state.plan && state.plan.steps ? state.plan.steps[state.stepIndex] : null;
  }

  function startGuidedFlow() {
    state.stepIndex = 0;
    state.answers = {};
    state.file = null;
    clear(stream());
    var titles = state.plan.steps.map(function (step) {
      return step.title || step.id;
    }).join(" → ");
    pushMessage("assistant",
      "你好，我是这个工作台的引导助手。这次按「" + titles + "」带你填完任务单。\n" +
      "两件事先说清楚：我只做引导和解释，不会替你创建任务或开始执行；修复结论由验收引擎给出，不由我判断。");
    renderCurrentStep();
    renderSide();
  }

  function renderCurrentStep() {
    var step = currentStep();
    if (!step) return;
    setText("agent-side-step", step.title || step.id);
    pushMessage("assistant", step.prompt);
    if (step.kind === "upload") pushUploadCard(step);
    else if (step.kind === "question") pushQuestionCard(step);
    else if (step.kind === "review") pushReviewCard();
  }

  function validateQuestion(question, value) {
    var trimmed = (value || "").trim();
    if (question.required && !trimmed) return "这一项必填。";
    if (question.ascii && /[^\x00-\x7F]/.test(trimmed)) {
      return "提交数据必须是英文 ASCII，请去掉中文等非 ASCII 字符。";
    }
    return "";
  }

  function pushQuestionCard(step) {
    var card = el("div", "agent-card");
    card.dataset.testid = "agent-question-card";
    card.appendChild(el("p", "agent-card-title", step.title));
    var inputs = {};

    step.questions.forEach(function (question) {
      var wrap = el("div", "agent-question");
      var id = "agent-q-" + question.key;
      var label = el("label", null, question.label);
      label.setAttribute("for", id);
      var input = el(question.input === "textarea" ? "textarea" : "input");
      input.id = id;
      input.dataset.key = question.key;
      input.dataset.testid = "agent-field-" + question.key;
      if (question.input !== "textarea") input.type = "text";
      else input.rows = 3;
      input.value = state.answers[question.key] || "";
      var error = el("p", "agent-field-error");
      error.dataset.testid = "agent-error-" + question.key;

      input.addEventListener("input", function () {
        state.answers[question.key] = input.value;
        error.textContent = validateQuestion(question, input.value);
      });

      wrap.appendChild(label);
      wrap.appendChild(input);
      wrap.appendChild(error);
      card.appendChild(wrap);
      inputs[question.key] = { input: input, error: error, question: question };
    });

    var actions = el("div", "agent-card-actions");
    var nextStep = state.plan.steps[state.stepIndex + 1];
    var next = el("button", "agent-btn", nextStep && nextStep.kind === "review" ? "进入复核" : "保存并继续");
    next.type = "button";
    next.dataset.testid = "agent-question-next";
    next.addEventListener("click", function () {
      var valid = true;
      Object.keys(inputs).forEach(function (key) {
        var entry = inputs[key];
        var message = validateQuestion(entry.question, entry.input.value);
        entry.error.textContent = message;
        if (message) valid = false;
      });
      if (!valid) return;
      Object.keys(inputs).forEach(function (key) {
        state.answers[key] = inputs[key].input.value;
      });
      pushMessage("user", summarizeAnswers(step));
      state.stepIndex += 1;
      renderCurrentStep();
    });

    var defaults = el("button", "agent-btn ghost", "使用默认答案");
    defaults.type = "button";
    defaults.dataset.testid = "agent-question-default";
    defaults.addEventListener("click", function () {
      Object.keys(inputs).forEach(function (key) {
        var entry = inputs[key];
        entry.input.value = entry.question.default || "";
        entry.error.textContent = "";
        state.answers[key] = entry.input.value;
      });
    });

    actions.appendChild(next);
    actions.appendChild(defaults);
    card.appendChild(actions);
    pushCard(card);
  }

  function summarizeAnswers(step) {
    return step.questions.map(function (question) {
      var value = (state.answers[question.key] || "").trim();
      return question.label + "：" + (value || "（未填）");
    }).join("\n");
  }

  function pushUploadCard() {
    var card = el("div", "agent-card");
    card.dataset.testid = "agent-upload-card";
    card.appendChild(el("p", "agent-card-title", "上传样本"));

    var zone = el("div", "agent-dropzone", "把文件拖到这里，或点击选择（≤ 20 MiB）");
    zone.dataset.testid = "agent-dropzone";
    zone.tabIndex = 0;
    var input = el("input");
    input.type = "file";
    input.hidden = true;
    input.dataset.testid = "agent-file-input";

    var progress = el("div", "agent-progress");
    progress.hidden = true;
    var bar = el("div", "agent-progress-bar");
    progress.appendChild(bar);
    var progressText = el("p", "agent-progress-text", "");
    var warning = el("p", "agent-warning", "");

    zone.addEventListener("click", function () { input.click(); });
    zone.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); input.click(); }
    });
    zone.addEventListener("dragover", function (event) {
      event.preventDefault();
      zone.classList.add("is-over");
    });
    zone.addEventListener("dragleave", function () { zone.classList.remove("is-over"); });
    zone.addEventListener("drop", function (event) {
      event.preventDefault();
      zone.classList.remove("is-over");
      if (event.dataTransfer.files && event.dataTransfer.files[0]) {
        readFile(event.dataTransfer.files[0]);
      }
    });
    input.addEventListener("change", function () {
      if (input.files && input.files[0]) readFile(input.files[0]);
    });

    function readFile(file) {
      warning.textContent = "";
      if (!file.size) { warning.textContent = "文件为空，请重新选择。"; return; }
      if (file.size > 20 * 1024 * 1024) { warning.textContent = "文件超过 20 MiB，无法提交。"; return; }

      progress.hidden = false;
      bar.style.width = "0%";
      progressText.textContent = "本机读取中 0%";
      var reader = new FileReader();
      reader.onprogress = function (event) {
        if (event.lengthComputable) {
          var percent = Math.round((event.loaded / event.total) * 100);
          bar.style.width = percent + "%";
          progressText.textContent = "本机读取中 " + percent + "%";
        }
      };
      reader.onerror = function () { warning.textContent = "读取文件失败，请重试。"; };
      reader.onload = function () {
        var buffer = reader.result;
        var bytes = new Uint8Array(buffer);
        var isElf = bytes.length > 4 && bytes[0] === 0x7f && bytes[1] === 0x45 &&
                    bytes[2] === 0x4c && bytes[3] === 0x46;
        var finish = function (hex) {
          state.file = { file: file, name: file.name, size: file.size, sha256: hex, isElf: isElf };
          bar.style.width = "100%";
          progressText.textContent = "读取完成 100%";
          if (!isElf) warning.textContent = "未检测到 ELF 文件头；仍可作为演示样本提交，实际执行可能被判为 unsupported。";
          pushTool("读取样本", file.name, {
            "size_bytes": file.size,
            "sha256": hex,
            "elf_magic": isElf ? "present" : "absent"
          });
          state.stepIndex += 1;
          renderCurrentStep();
        };
        if (window.crypto && crypto.subtle && crypto.subtle.digest) {
          crypto.subtle.digest("SHA-256", buffer).then(function (digest) {
            var hex = Array.prototype.map.call(new Uint8Array(digest), function (b) {
              return ("0" + b.toString(16)).slice(-2);
            }).join("");
            finish(hex);
          }).catch(function () { finish("unavailable"); });
        } else {
          finish("unavailable");
        }
      };
      reader.readAsArrayBuffer(file);
    }

    card.appendChild(zone);
    card.appendChild(input);
    card.appendChild(progress);
    card.appendChild(progressText);
    card.appendChild(warning);
    pushCard(card);
  }

  function pushReviewCard() {
    var card = el("div", "agent-card");
    card.dataset.testid = "agent-review-card";
    card.appendChild(el("p", "agent-card-title", "任务单复核"));

    var table = el("table", "agent-table");
    var tbody = el("tbody");
    var rows = [["样本", state.file ? state.file.name + "（" + state.file.size + " B）" : "（未选择）", 0]];
    var labels = {
      defect: "缺陷描述", valid_tests: "用例", environment: "环境",
      valid_domain: "合法输入域", forbidden: "禁止行为",
      invalid_outcome: "非法输入期望", assumptions: "假设条件"
    };
    state.plan.steps.forEach(function (step, index) {
      (step.questions || []).forEach(function (question) {
        // The plan owns the wording; the legacy map is only a fallback.
        rows.push([question.label || labels[question.key] || question.key, state.answers[question.key] || "（未填）", index]);
      });
    });

    rows.forEach(function (row) {
      var tr = el("tr");
      tr.appendChild(el("td", null, row[0]));
      var value = el("td");
      value.appendChild(el("code", null, row[1]));
      tr.appendChild(value);
      var action = el("td");
      var edit = el("button", "agent-btn ghost", "修改");
      edit.type = "button";
      edit.addEventListener("click", function () {
        state.stepIndex = row[2];
        pushMessage("assistant", "回到「" + (state.plan.steps[row[2]].title || "该步骤") + "」，已填内容保留，改完继续即可。");
        renderCurrentStep();
      });
      action.appendChild(edit);
      tr.appendChild(action);
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    card.appendChild(table);

    var progress = el("div", "agent-progress");
    progress.hidden = true;
    var bar = el("div", "agent-progress-bar");
    progress.appendChild(bar);
    var progressText = el("p", "agent-progress-text", "");

    var actions = el("div", "agent-card-actions");
    var create = el("button", "agent-btn", "创建任务（由你确认）");
    create.type = "button";
    create.dataset.testid = "agent-create-job";
    create.addEventListener("click", function () { createJob(create, progress, bar, progressText); });
    actions.appendChild(create);
    card.appendChild(actions);
    card.appendChild(progress);
    card.appendChild(progressText);
    pushCard(card);
  }

  /* ---------- 创建任务：用户显式动作 + 真实上传进度 ---------- */

  function createJob(button, progress, bar, progressText) {
    if (state.submitting) return;
    if (!state.file) { pushMessage("assistant", "还没有样本文件，请回到第 1 步上传。"); return; }
    if (FIXTURE_MODE) {
      pushMessage("assistant", "当前是演示模式，不会真的创建任务。去掉地址栏的 ?fixture=1 后再试。");
      return;
    }

    var form = new FormData();
    form.append("binary", state.file.file, state.file.name);
    ["defect", "valid_tests", "environment", "valid_domain", "forbidden",
     "invalid_outcome", "assumptions"].forEach(function (key) {
      form.append(key, state.answers[key] || "");
    });
    form.append("csrf", CSRF);

    state.submitting = true;
    button.disabled = true;
    progress.hidden = false;
    progressText.textContent = "上传中 0%";

    var xhr = new XMLHttpRequest();
    xhr.open("POST", "/jobs");
    xhr.upload.onprogress = function (event) {
      if (event.lengthComputable) {
        var percent = Math.round((event.loaded / event.total) * 100);
        bar.style.width = percent + "%";
        progressText.textContent = "上传中 " + percent + "%";
      }
    };
    xhr.onload = function () {
      state.submitting = false;
      button.disabled = false;
      // mock 与 controller 的 id 形式不同（job-… / hex），统一取 /jobs/ 后一段。
      var match = /\/jobs\/([^/?#]+)/.exec(xhr.responseURL || "");
      if (match) {
        progressText.textContent = "上传完成，已创建任务";
        pushTool("创建任务", match[1], { "job_id": match[1], "http_status": xhr.status });
        state.jobId = match[1];
        // 把本次会话（创建前的问答）一并归档到新任务，避免历史断在创建那一步。
        writeHistoryFor(match[1], state.entries);
        registerJob((state.answers.defect || "").slice(0, 40));
        window.location.href = "/agent/" + encodeURIComponent(match[1]);
      } else {
        progressText.textContent = "创建失败";
        pushMessage("assistant", "创建任务没有成功（HTTP " + xhr.status + "）。请检查必填项与英文 ASCII 要求，或切到表单页查看详细报错。");
      }
    };
    xhr.onerror = function () {
      state.submitting = false;
      button.disabled = false;
      progressText.textContent = "网络错误";
      pushMessage("assistant", "网络错误，任务未创建。可以重试，或切到表单页。");
    };
    xhr.send(form);
  }

  /* ---------- 状态面板与结果屏 ---------- */

  function renderSide() {
    var view = state.snapshot ? normalize(state.snapshot) : null;
    setText("agent-job-chip", state.jobId ? "任务 " + state.jobId.slice(0, 8) : "未选择任务");

    var agent = view && view.agent ? view.agent : (state.plan || null);
    var notWired = ASSISTANT_MODE === "llm" && !ASSISTANT_AVAILABLE;

    var activeMode = agent && agent.mode ? agent.mode : ASSISTANT_MODE;
    var badge = $("agent-mode-badge");
    if (badge) badge.setAttribute("data-plan-mode", activeMode);
    if (agent && agent.mode) {
      setText("agent-mode-badge",
        "助手模式：" + (PLAN_MODE_LABELS[agent.mode] || agent.mode) + "（" + agent.mode + "）");
    } else if (notWired) {
      setText("agent-mode-badge", "助手模式：LLM（未接线）");
    } else {
      setText("agent-mode-badge",
        "助手模式：" + (PLAN_MODE_LABELS[ASSISTANT_MODE] || ASSISTANT_MODE) + "（" + ASSISTANT_MODE + "）");
    }

    var fallback = (agent && agent.fallback) || (!agent && notWired);
    show("agent-fallback", !!fallback);
    if (fallback) {
      var reason = agent && agent.fallback_reason
        ? agent.fallback_reason
        : "llm_client_not_configured";
      setText("agent-fallback-text",
        "模型通道未建立（" + reason + "），当前回退到确定性引导；页面内容不代表模型输出。");
    }

    if (notWired && !(agent && (agent.model || agent.tokens))) {
      setText("agent-model-meta", "未调用（llm 通道未接线）");
    } else if (agent && (agent.model || agent.tokens)) {
      var parts = [];
      if (agent.model) parts.push("model：" + agent.model);
      if (agent.tokens) {
        var input = agent.tokens.input !== undefined ? agent.tokens.input : agent.tokens.prompt;
        var output = agent.tokens.output !== undefined ? agent.tokens.output : agent.tokens.completion;
        // null/absent usage is "未提供", never 0 and never an estimate.
        // partial=true means some rows had no usable counts; the sum is real
        // but incomplete, so it must say so.
        if (input === undefined && output === undefined) {
          parts.push("tokens：未提供");
        } else {
          parts.push("tokens：input " + (input === undefined ? "未提供" : input) +
            " / output " + (output === undefined ? "未提供" : output) +
            (agent.tokens.partial ? "（部分真实用量）" : ""));
        }
      }
      setText("agent-model-meta", parts.join("；"));
    } else {
      setText("agent-model-meta", "未提供");
    }

    if (!view) {
      setText("agent-side-execution", "—");
      setText("agent-side-phase", "—");
      setText("agent-side-contract", "—");
      return;
    }

    if (view.agent && view.agent.current_step) {
      setText("agent-side-step", view.agent.current_step);
    }
    if (view.execution) {
      // 状态码原样显示；后端给了中文标签才用标签，不为未知枚举编造文案。
      setText("agent-side-execution",
        (view.execution.status_label ? view.execution.status_label + "（" : "") +
        (view.execution.status || "unknown") + (view.execution.status_label ? "）" : ""));
    } else {
      setText("agent-side-execution", "后端未提供");
    }
    setText("agent-side-phase", PHASE_LABELS[view.phase] || view.phase || "—");
    if (view.contract) {
      setText("agent-side-contract",
        shortHash(view.contract.sha256) + (view.contract.approved ? " · 已审批" : " · 未审批"));
    }

    var artifacts = $("agent-side-artifacts");
    clear(artifacts);
    if (!view.artifacts.length) {
      artifacts.appendChild(el("li", "agent-muted", "尚无产物"));
    } else {
      view.artifacts.forEach(function (artifact) {
        var li = el("li");
        if (FIXTURE_MODE) {
          li.textContent = (artifact.label || artifact.id) + "（演示数据，不可下载）";
        } else {
          var link = el("a", null, artifact.label || artifact.id);
          link.href = "/api/artifacts/" + encodeURIComponent(artifact.id) + "/download";
          li.appendChild(link);
        }
        artifacts.appendChild(li);
      });
    }
  }

  function renderTimeline(view) {
    var list = $("agent-timeline");
    clear(list);

    // 优先用 /attempts 的时间线语义；旧 route/status 字段保持原样，不覆盖。
    if (attemptsCache.jobId === view.jobId) {
      if (attemptsCache.available === false) {
        list.appendChild(el("li", "agent-muted", "尝试记录不可用"));
        return;
      }
      if (attemptsCache.items.length) {
        attemptsCache.items.forEach(function (attempt) {
          var status = attempt.timeline_status;
          var item = el("li", "agent-timeline-item" +
            (status === "ok" ? " is-done" :
              (status === "failed" || status === "timeout") ? " is-failed" : " is-active"));
          item.appendChild(el("span", "agent-timeline-name",
            "尝试 #" + (attempt.attempt_no || "?") + " · " +
            (attempt.route_label || attempt.route || "?")));
          item.appendChild(el("span", "agent-timeline-meta", TIMELINE_LABELS[status] || "未知"));
          if (attempt.duration_ms !== null && attempt.duration_ms !== undefined) {
            item.appendChild(el("span", "agent-timeline-meta", attempt.duration_ms + " ms"));
          }
          // 数据库没有可靠退出码时后端给 null；这里显示“未知”，不补 0。
          item.appendChild(el("span", "agent-timeline-meta",
            (attempt.exit_code === null || attempt.exit_code === undefined)
              ? "未知退出码" : "退出码 " + attempt.exit_code));
          if (attempt.started_at) {
            item.appendChild(el("span", "agent-timeline-meta", attempt.started_at));
          }
          list.appendChild(item);
        });
        return;
      }
      if (attemptsCache.available === true) {
        list.appendChild(el("li", "agent-muted", "尚无尝试记录"));
        return;
      }
    }

    if (view.execution && view.execution.status) {
      var item = el("li", "agent-timeline-item is-active");
      item.appendChild(el("span", "agent-timeline-name", "回传状态"));
      item.appendChild(el("span", "agent-timeline-meta", view.execution.status));
      if (view.execution.last_heartbeat) {
        item.appendChild(el("span", "agent-timeline-meta", "心跳 " + view.execution.last_heartbeat));
      }
      list.appendChild(item);
    }
    var any = !!(view.execution && view.execution.status);
    view.routeKeys.forEach(function (key) {
      var route = view.routes[key];
      (route.stages || []).forEach(function (stage) {
        any = true;
        var item = el("li", "agent-timeline-item" +
          (stage.state === "done" ? " is-done" : stage.state === "failed" ? " is-failed" : " is-active"));
        item.appendChild(el("span", "agent-timeline-name", "Route " + key + " · " + (PHASE_LABELS[stage.name] || stage.name)));
        item.appendChild(el("span", "agent-timeline-meta", STATE_LABELS[stage.state] || stage.state));
        if (stage.at) item.appendChild(el("span", "agent-timeline-meta", stage.at));
        list.appendChild(item);
      });
    });
    if (!any) list.appendChild(el("li", "agent-muted", "尚无执行记录"));
  }

  function renderBeforeAfter(view) {
    setText("agent-original-sha", "original_sha256：" + (view.originalSha256 || "—"));
    setText("agent-candidate-sha",
      "candidate_sha256：" + (view.candidate && view.candidate.sha256 ? view.candidate.sha256 : "—"));

    var box = $("agent-before-after");
    clear(box);
    if (view.candidate && view.candidate.diff) {
      box.appendChild(el("pre", "agent-diff", view.candidate.diff));
      return;
    }
    var regions = [];
    view.routeKeys.forEach(function (key) {
      (view.routes[key].changed_regions || []).forEach(function (region) {
        regions.push({ route: key, region: region });
      });
    });
    if (!regions.length) {
      box.appendChild(el("p", "agent-muted", "未产出候选改动；没有可展示的代码差异。"));
      return;
    }
    var table = el("table", "agent-table");
    var head = el("thead");
    var hr = el("tr");
    ["路线", "地址", "类型", "原始字节", "新字节"].forEach(function (title) {
      hr.appendChild(el("th", null, title));
    });
    head.appendChild(hr);
    table.appendChild(head);
    var tbody = el("tbody");
    regions.forEach(function (entry) {
      var tr = el("tr");
      tr.appendChild(el("td", null, "Route " + entry.route));
      ["address", "kind", "before", "after"].forEach(function (field) {
        var td = el("td");
        // 缺失字段显示 —，不留空白单元格（空白会被读成“无改动”）。
        var value = entry.region[field];
        td.appendChild(el("code", null,
          value === undefined || value === null || value === "" ? "—" : value));
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    box.appendChild(table);
  }

  function appendScopeBox(box, view) {
    // Review 12：scope/bounded 缺失必须显示 unknown，不能隐藏；exceeded 只认布尔值。
    if (!view.jobId && !view.phase) return;
    var wrap = el("div", "agent-card");
    wrap.dataset.testid = "agent-scope-bounded";
    wrap.appendChild(el("p", "agent-card-title", "范围与边界"));

    var scopeText = "unknown";
    if (view.scope && view.scope.kind && view.scope.value !== undefined &&
        view.scope.value !== null && view.scope.value !== "") {
      scopeText = view.scope.kind + "：" + view.scope.value +
        (view.scope.note ? "（" + view.scope.note + "）" : "");
    }
    wrap.appendChild(el("p", null, "scope：" + scopeText));

    var boundedText = "unknown";
    if (view.bounded) {
      if (view.bounded.exceeded === true) {
        boundedText = "超出边界";
      } else if (view.bounded.exceeded === false) {
        boundedText = "未超出边界" +
          (view.bounded.limit ? "（上限 " + view.bounded.limit + "，实测 " +
            (view.bounded.observed || "unknown") + "）" : "");
      }
    }
    wrap.appendChild(el("p", null, "bounded：" + boundedText));
    box.appendChild(wrap);
  }

  function appendComparisonBox(box) {
    // 只看 status；comparison 的内容不做字段级解析，未提供就是未提供。
    if (!comparisonCache) return;
    var wrap = el("div", "agent-card");
    wrap.dataset.testid = "agent-comparison";
    wrap.appendChild(el("p", "agent-card-title", "行为对比"));
    var text;
    if (comparisonCache.status === "available") {
      text = "已提供（" + comparisonCache.artifacts.length + " 个 artifact）";
    } else if (comparisonCache.status === "not_provided") {
      text = "未提供（not_provided）";
    } else {
      text = "不可用（" + (comparisonCache.detail || "unknown") + "）";
    }
    wrap.appendChild(el("p", null, "comparison：" + text));
    box.appendChild(wrap);
  }

  function renderDiagnostics(view) {
    // 结论只读 verdict，绝不由前端推断。
    var verdictText = "结论：—";
    if (view.verdict && view.verdict.outcome) {
      verdictText = "结论：" + (OUTCOME_LABELS[view.verdict.outcome] || view.verdict.outcome) +
        "（" + view.verdict.outcome + "）";
      if (view.verdict.reason) verdictText += " · reason_code：" + view.verdict.reason;
      if (view.verdict.failing_obligation) verdictText += " · 失败义务 " + view.verdict.failing_obligation;
      if (view.verdict.detail) verdictText += " · " + view.verdict.detail;
    } else if (view.phase === "finished" && !view.cancelled) {
      verdictText = "结论：尚无 verdict（等待验收引擎）";
    }
    setText("agent-verdict", verdictText);

    show("agent-receipt-placeholder", view.receiptPending);

    var reasonCard = $("agent-reason-card");
    var adviceCard = $("agent-advice-card");
    clear(reasonCard);
    clear(adviceCard);
    reasonCard.hidden = true;
    adviceCard.hidden = true;

    var code = view.verdict && view.verdict.reason ? view.verdict.reason : "";
    var failed = view.verdict && view.verdict.outcome &&
      view.verdict.outcome !== "success_within_scope" && code;
    if (failed && !view.receiptPending) {
      var info = REASON_INFO[code];
      reasonCard.hidden = false;
      reasonCard.appendChild(el("p", "agent-card-title", info ? info.title : "未知原因"));
      reasonCard.appendChild(el("p", null, "reason_code：" + code +
        (info ? "" : "（未登记，请把 status.json 发给 M1/M4，不在此猜测原因）")));
      adviceCard.hidden = false;
      adviceCard.appendChild(el("p", "agent-card-title", "建议动作"));
      var list = el("ol");
      var advice = info ? info.advice : [{ text: "下载 status.json 与 decision.json，交给 M1/M4 定位", owner: "M1/M4", retry: "待定" }];
      advice.slice(0, 3).forEach(function (entry) {
        list.appendChild(el("li", null, entry.text + "（负责：" + entry.owner + " · " + entry.retry + "）"));
      });
      adviceCard.appendChild(list);
    }

    var box = $("agent-diagnostics");
    clear(box);
    if (view.receiptPending) return; // 未回传：只显示占位，不渲染 not_run
    appendScopeBox(box, view);
    appendComparisonBox(box);

    view.routeKeys.forEach(function (key) {
      var route = view.routes[key];
      var evidence = route.__evidence || null;
      var v3 = evidence && evidence.v3 ? evidence.v3 : null;
      var title = "Route " + key;
      if (v3 && v3.valid && typeof v3.valid.total === "number" &&
          typeof v3.valid.passed === "number") {
        title += " · valid " + v3.valid.passed + "/" + v3.valid.total;
      } else {
        var tests = route.tests || {};
        var total = typeof tests.total === "number" ? tests.total : null;
        var passed = typeof tests.passed === "number" ? tests.passed : null;
        // No cases is not "0/0 passed": show N/A so an empty suite is never
        // read as a result, and never fold it into another suite's ratio.
        title += " · 用例 " + ((total === null || total === 0 || passed === null) ? "N/A" : (passed + "/" + total));
      }
      if (v3) {
        // Lead 定稿：input_mode="none" 时 invalid 是 {0,0}，显示 N/A；
        // 任何 total=0 也不显示 0/0，避免被读成“没有失败”。
        var invalidText = "N/A";
        var noInput = v3.input_mode === "none" || v3.invalid_applicable === false;
        if (!noInput && v3.invalid &&
            typeof v3.invalid.total === "number" && typeof v3.invalid.passed === "number" &&
            v3.invalid.total > 0) {
          invalidText = v3.invalid.passed + "/" + v3.invalid.total;
        }
        title += " · invalid " + invalidText;
      }
      box.appendChild(el("h3", "agent-side-subtitle", title));

      if (!evidence) {
        // 拉不到证据时明说不可用，不静默省略整块（省略会被读成“没有 gate”）。
        box.appendChild(el("p", "agent-muted",
          route.attempt_id
            ? "证据不可用（attempt 未回传或端点未开通）"
            : "证据不可用（该路线未回传 attempt）"));
      }

      if (evidence && Array.isArray(evidence.gates) && evidence.gates.length) {
        // Gates render in the order the endpoint returns them; the front end
        // does not sort, reorder, or fill in a missing gate.
        var gateList = el("ul", "agent-gates");
        gateList.dataset.testid = "agent-gates-" + key;
        evidence.gates.forEach(function (gate) {
          var li = el("li");
          var value = el("span", "agent-result-value",
            gate.result === null || gate.result === undefined ? "—" : String(gate.result));
          value.dataset.testid = "agent-gate-" + key + "-" + gate.gate;
          li.appendChild(value);
          li.appendChild(document.createTextNode(" "));
          li.appendChild(el("code", null, gate.gate + (gate.kind ? " " + gate.kind : "")));
          if (gate.detail) li.appendChild(document.createTextNode(" · " + gate.detail));
          gateList.appendChild(li);
        });
        box.appendChild(gateList);
      }
    });

    if (!view.obligations.length) {
      box.appendChild(el("p", "agent-muted", "后端未提供义务结果"));
      return;
    }
    var list = el("ul", "agent-obligations");
    list.dataset.testid = "agent-obligations";
    view.obligations.forEach(function (item) {
      var li = el("li");
      li.dataset.route = item.route;
      var value = el("span", "agent-result-value", item.result); // 逐字：not_run 就是 not_run
      value.dataset.testid = "agent-obligation-" + item.id;
      li.appendChild(value);
      li.appendChild(document.createTextNode(" "));
      li.appendChild(el("code", null, item.id + (item.kind ? " " + item.kind : "")));
      li.appendChild(document.createTextNode(" · Route " + item.route));
      if (item.reason) li.appendChild(document.createTextNode(" · " + item.reason));
      list.appendChild(li);
    });
    box.appendChild(list);
  }

  function renderDownloads(view) {
    var list = $("agent-downloads");
    clear(list);
    if (FIXTURE_MODE) {
      list.appendChild(el("li", "agent-muted", "演示模式不产出真实文件，下载入口在接入真实任务后可用。"));
      return;
    }
    if (!state.jobId) {
      list.appendChild(el("li", "agent-muted", "尚未创建任务"));
      return;
    }
    var id = encodeURIComponent(state.jobId);
    var items = [
      { label: "证据包 JSON（/api/jobs/{id}/export）", href: "/api/jobs/" + id + "/export" },
      { label: "HTML 报告（查看）", href: "/jobs/" + id + "/report" },
      { label: "HTML 报告（下载）", href: "/jobs/" + id + "/report?download=1" }
    ];
    items.forEach(function (entry) {
      var li = el("li");
      var link = el("a", null, entry.label);
      link.href = entry.href;
      li.appendChild(link);
      list.appendChild(li);
    });
    var seen = {};
    (view.artifacts || []).concat(state.artifacts || []).forEach(function (artifact) {
      // 缺 id 不生成死链（/api/artifacts/undefined/download）。
      if (!artifact || typeof artifact.id !== "string" || !artifact.id || seen[artifact.id]) return;
      seen[artifact.id] = true;
      var li = el("li");
      var label = artifact.name || artifact.label || artifact.id;
      if (artifact.role) label += "（" + artifact.role + "）";
      var link = el("a", null, "产物：" + label);
      link.href = "/api/jobs/" + encodeURIComponent(state.jobId) + "/artifacts/" +
        encodeURIComponent(artifact.id) + "/download";
      li.appendChild(link);
      list.appendChild(li);
    });
  }

  function renderResult() {
    var view = state.snapshot ? normalize(state.snapshot) : null;
    if (!view) {
      setText("agent-verdict", "结论：—");
      clear($("agent-timeline"));
      $("agent-timeline").appendChild(el("li", "agent-muted", "尚无执行记录"));
      clear($("agent-diagnostics"));
      $("agent-diagnostics").appendChild(el("p", "agent-muted", "尚未选择任务"));
      clear($("agent-downloads"));
      $("agent-downloads").appendChild(el("li", "agent-muted", "尚未创建任务"));
      show("agent-receipt-placeholder", false);
      return;
    }
    renderTimeline(view);
    renderBeforeAfter(view);
    renderDiagnostics(view);
    renderDownloads(view);
  }

  /* ---------- 轮询 ---------- */

  var timer = null;

  function tick() {
    if (!state.jobId) return;
    if (FIXTURE_MODE) return;
    Promise.all([fetchLiveSnapshot(), fetchAttempts(state.jobId), fetchComparison(state.jobId), fetchArtifacts()]).then(function (results) {
      var data = results[0];
      state.snapshot = data;
      setText("agent-poll", "轮询中 · " + new Date().toLocaleTimeString());
      renderSide();
      renderResult();
      if ((data.phase === "finished" || data.cancelled) && timer) {
        clearInterval(timer);
        timer = null;
        setText("agent-poll", "任务结束，停止轮询");
      }
    }).catch(function () {
      setText("agent-poll", "网络错误，稍后重试");
    });
  }

  function startPolling() {
    if (FIXTURE_MODE || !state.jobId) {
      setText("agent-poll", FIXTURE_MODE ? "演示数据，不轮询" : "未选择任务");
      return;
    }
    stopPolling();
    timer = setInterval(tick, document.hidden ? 8000 : 2000);
    tick();
  }

  function stopPolling() { if (timer) { clearInterval(timer); timer = null; } }

  document.addEventListener("visibilitychange", function () {
    if (!FIXTURE_MODE && state.jobId) startPolling();
  });

  /* ---------- 视图切换 ---------- */

  function setView(name) {
    state.view = name;
    show("agent-view-chat", name === "chat");
    show("agent-view-result", name === "result");
    var tabs = document.querySelectorAll(".agent-tab[data-view]");
    Array.prototype.forEach.call(tabs, function (tab) {
      var active = tab.dataset.view === name;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });
    if (name === "result") renderResult();
  }

  Array.prototype.forEach.call(document.querySelectorAll(".agent-tab[data-view]"), function (tab) {
    tab.addEventListener("click", function () { setView(tab.dataset.view); });
  });

  /* ---------- composer ---------- */

  function handleCommand(text) {
    var parts = text.split(/\s+/);
    var command = parts[0];
    if (command === "/restart") { startGuidedFlow(); return true; }
    if (command === "/status") {
      var view = state.snapshot ? normalize(state.snapshot) : null;
      pushMessage("assistant", view
        ? "当前阶段：" + (PHASE_LABELS[view.phase] || view.phase) +
          "\n执行状态：" + (view.execution ? view.execution.status : "后端未提供") +
          "\n义务条数：" + view.obligations.length +
          "\n结论：" + (view.verdict && view.verdict.outcome ? view.verdict.outcome : "尚无 verdict")
        : "还没有任务。先完成引导，或打开 /agent?job=<任务ID>。");
      return true;
    }
    if (command === "/skip") {
      var step = currentStep();
      if (step && step.questions) {
        step.questions.forEach(function (question) {
          state.answers[question.key] = question.default || "";
        });
        pushMessage("user", "使用默认答案\n" + summarizeAnswers(step));
        state.stepIndex += 1;
        renderCurrentStep();
      } else {
        pushMessage("assistant", "当前这一步没有可填的默认答案。");
      }
      return true;
    }
    if (command === "/fixture" && FIXTURE_MODE) {
      loadScenario(parts[1] || "fresh");
      return true;
    }
    return false;
  }

  $("agent-composer").addEventListener("submit", function (event) {
    event.preventDefault();
    var input = $("agent-input");
    var text = input.value.trim();
    if (!text) return;
    input.value = "";
    if (text.charAt(0) === "/") {
      if (handleCommand(text)) return;
    }
    pushMessage("user", text);
    var step = currentStep();
    if (step && step.questions && step.questions.length === 1) {
      var question = step.questions[0];
      var message = validateQuestion(question, text);
      if (message) { pushMessage("assistant", message); return; }
      state.answers[question.key] = text;
      state.stepIndex += 1;
      renderCurrentStep();
    } else if (!state.plan) {
      if (state.planPending) return;
      setText("agent-side-step", "正在生成引导计划…");
      setText("agent-poll", "请求计划中");
      requestPlan(text).then(function (result) {
        var plan = result.ok && result.data ? result.data.plan : null;
        if (!plan || !plan.steps || !plan.steps.length) {
          setText("agent-side-step", "后端未提供");
          setText("agent-poll", "未选择任务");
          pushMessage("assistant", planUnavailableText(result.data) +
            "。你可以点上方「改用表单建单」，或打开 /agent/new?fixture=1 预览控制台。");
          return;
        }
        state.plan = plan;
        startGuidedFlow();
        if (plan.fallback) {
          pushMessage("assistant",
            "注意：这是后端给出的回退计划（" + (plan.fallback_reason || "未说明原因") +
            "），没有发生真实模型调用。步骤仍按契约渲染。");
        } else if (plan.mode === "deterministic") {
          pushMessage("assistant",
            "说明：这是确定性计划（未调用模型），步骤来自固定模板，不是模型输出。");
        }
      });
    } else {
      pushMessage("assistant", "这一步请直接在上方卡片里填写，或点「使用默认答案」。");
    }
  });

  $("agent-input").addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      $("agent-composer").dispatchEvent(new Event("submit", { cancelable: true }));
    }
  });

  // 起始页大输入卡片带来的描述，预填进 composer，由用户决定是否发送。
  var preset = QUERY.get("q");
  if (preset) { $("agent-input").value = preset; }

  // composer 左侧 ＋：优先触发引导里的上传控件，否则回退到表单页。
  $("agent-attach").addEventListener("click", function () {
    var fileInput = document.querySelector('[data-testid="agent-file-input"]');
    if (fileInput) { fileInput.click(); return; }
    var zone = document.querySelector('[data-testid="agent-dropzone"]');
    if (zone) { zone.click(); return; }
    window.location.href = "/jobs/new";
  });

  /* ---------- 场景与初始化 ---------- */

  function loadScenario(name) {
    if (!FIXTURES) return;
    state.scenario = FIXTURES.snapshots[name] !== undefined ? name : "fresh";
    state.snapshot = FIXTURES.snapshots[state.scenario];
    state.jobId = state.snapshot ? state.snapshot.job_id : "";
    if (state.scenario === "fresh") {
      state.plan = FIXTURES.plan;
      startGuidedFlow();
    } else {
      state.plan = null;
      clear(stream());
      pushMessage("assistant", "已载入演示场景「" + state.scenario + "」。点上方「结果与证据」查看该场景下的报告呈现。");
      pushTool("载入演示快照", state.scenario, {
        "job_id": state.jobId,
        "execution": state.snapshot.execution ? state.snapshot.execution.status : "unknown",
        "verdict": state.snapshot.verdict ? state.snapshot.verdict.outcome : "none"
      }, JSON.stringify(state.snapshot, null, 2));
      setText("agent-side-step", state.snapshot.agent ? state.snapshot.agent.current_step : "—");
    }
    renderSide();
    renderResult();
    setText("agent-poll", "演示数据，不轮询");
  }

  function uploadDeliverable() {
    var input = $("agent-deliverable-input");
    var status = $("agent-deliverable-status");
    if (!state.jobId) { setText("agent-deliverable-status", "尚未创建任务"); return; }
    if (!input || !input.files || !input.files.length) {
      setText("agent-deliverable-status", "请选择修复后的 ELF 文件");
      return;
    }
    var file = input.files[0];
    if (file.size > DELIVERABLE_MAX_BYTES) {
      setText("agent-deliverable-status", "文件超过 64 MiB 上限，已取消上传");
      return;
    }
    var form = new FormData();
    form.append("file", file);
    setText("agent-deliverable-status", "上传中…");
    fetch("/api/jobs/" + encodeURIComponent(state.jobId) + "/deliverables", {
      method: "POST",
      headers: { "x-csrf-token": CSRF },
      body: form
    }).then(function (response) {
      return response.json().then(function (payload) {
        if (!response.ok) throw new Error(payload && payload.detail ? payload.detail : "HTTP " + response.status);
        return payload;
      });
    }).then(function (payload) {
      var a = payload && payload.artifact ? payload.artifact : null;
      setText("agent-deliverable-status",
        a ? "已保存：" + a.name + "（可下载，不参与验收）" : "已保存（不参与验收）");
      input.value = "";
      return fetchArtifacts().then(function () { renderResult(); });
    }).catch(function (exc) {
      setText("agent-deliverable-status", "上传失败：" + exc.message);
    });
  }

  var uploadButton = $("agent-deliverable-upload");
  var uploadInput = $("agent-deliverable-input");
  if (!UPLOAD_AVAILABLE) {
    if (uploadButton) uploadButton.hidden = true;
    if (uploadInput) uploadInput.hidden = true;
  }
  if (uploadButton) uploadButton.addEventListener("click", uploadDeliverable);

  function init() {
    show("agent-fixture-hint", FIXTURE_MODE);
    var scenario = QUERY.get("scenario");

    if (FIXTURE_MODE) {
      loadScenario(scenario || (state.jobId ? "pending" : "fresh"));
      return;
    }

    if (state.jobId) {
      clear(stream());
      state.entries = readHistory();
      registerJob();
      replayHistory();
      pushMessage(
        "assistant",
        "已打开任务 " + state.jobId + "。上面的对话来自本机保存的该任务记录；我会每 2 秒刷新状态。" +
        "引导计划需要 M1 的 assistant 端点与 M5 的 planner 接入后才会出现在这里。",
        { replay: true }
      );
      setText("agent-side-step", "后端未提供");
      startPolling();
    } else if (PLAN_FIXTURE) {
      state.plan = FIXTURES.plan;
      startGuidedFlow();
      pushMessage("assistant", "说明：本页的引导计划来自占位 fixture（真实计划需要 M1 的端点与 M5 的 planner），但你点击「创建任务」后会真实提交到本机后端。");
    } else {
      clear(stream());
      pushMessage("assistant",
        "描述你想修的这个二进制问题，我会向后端请求一份引导计划。\n" +
        "计划由后端生成；如果计划服务还没接通，我会直接说「未接通」，不会用占位内容代替。\n" +
        "也可以点上方「改用表单建单」直接提交材料，或打开 /agent/new?fixture=1 预览控制台。");
      setText("agent-side-step", "等待描述");
      setText("agent-poll", "未选择任务");
    }
    renderSide();
  }

  init();
})();
