/* Universal binary repair page (/binary).
 *
 * Deterministic single path:
 *   POST /api/binary/scan   multipart(binary, csrf)  -> read-only matrix/sink report
 *   POST /api/binary/repair multipart(binary, csrf, allow_static_only=1) -> candidate
 *
 * Two direct-AI paths (independent file picker, shared best-effort opt-in):
 *   POST /api/binary/ai-repair multipart(binary, csrf, path=ai_plan|ai_bytes,
 *                                        allow_static_only=1) -> candidate
 *
 * The page never derives a verdict on its own: the disposition badge, the
 * verified flag and the download permission all come from the server report.
 * Unverified candidates are only offered when the operator explicitly opts in.
 */
(function () {
  "use strict";

  var page = document.querySelector('[data-testid="binary-page"]');
  if (!page) return;

  var MAX_BYTES = 20 * 1024 * 1024;
  var REQUEST_TIMEOUT_MS = 120000;
  var EMPTY = "\u2014";

  var DISPOSITIONS = {
    verified_patch: { label: "已验证", cls: "is-verified" },
    static_only_patch: { label: "未验证，仅静态证据", cls: "is-static" },
    not_verified: { label: "未验证", cls: "is-not-verified" },
    analysis_only: { label: "仅分析", cls: "is-analysis" },
    unsupported: { label: "不支持", cls: "is-unsupported" },
    rejected: { label: "已拒绝", cls: "is-rejected" },
    invalid: { label: "无效输入", cls: "is-invalid" }
  };

  function byId(id) { return document.getElementById(id); }

  var els = {
    drop: byId("binary-drop"),
    file: byId("binary-file"),
    fileName: byId("binary-file-name"),
    scan: byId("binary-scan"),
    repair: byId("binary-repair"),
    allowStatic: byId("binary-allow-static"),
    status: byId("binary-scan-status"),
    error: byId("binary-error"),
    scanSection: byId("binary-scan-result"),
    scanVerdict: byId("binary-scan-verdict"),
    fmt: byId("binary-scan-format"),
    arch: byId("binary-scan-arch"),
    bits: byId("binary-scan-bits"),
    endian: byId("binary-scan-endian"),
    cell: byId("binary-scan-cell"),
    repairable: byId("binary-scan-repairable"),
    findingsCount: byId("binary-scan-findings-count"),
    findings: byId("binary-findings"),
    limitationsBlock: byId("binary-limitations-block"),
    limitations: byId("binary-limitations"),
    repairSection: byId("binary-repair-result"),
    disposition: byId("binary-disposition"),
    dispositionCode: byId("binary-disposition-code"),
    verified: byId("binary-verified"),
    tier: byId("binary-tier"),
    downloadAllowed: byId("binary-download-allowed"),
    repairDetail: byId("binary-repair-detail"),
    download: byId("binary-download"),
    candidateName: byId("binary-candidate-name"),
    downloadNote: byId("binary-download-note"),
    warningsBlock: byId("binary-warnings-block"),
    warnings: byId("binary-warnings"),
    report: byId("binary-report"),
    reportJson: byId("binary-report-json")
  };

  var state = {
    file: null,
    scan: null,
    repair: null,
    candidate: null,
    statusKey: "idle",
    statusData: "",
    busy: false
  };

  function tx(text) {
    try {
      if (window.I18N && typeof window.I18N.translate === "function") {
        return window.I18N.translate(text);
      }
    } catch (error) { /* keep the source string */ }
    return text;
  }

  function csrfToken() {
    var fromPage = page.getAttribute("data-csrf");
    if (fromPage) return fromPage;
    var meta = document.querySelector('meta[name="csrf"]');
    return meta ? (meta.getAttribute("content") || "") : "";
  }

  function setHidden(element, hidden) {
    if (element) element.hidden = !!hidden;
  }

  function safeFilename(name) {
    var base = String(name == null ? "" : name).split(/[\\/]/).pop() || "candidate.bin";
    base = base.replace(/[\u0000-\u001f\u007f]/g, "").trim();
    return base || "candidate.bin";
  }

  function formatBytes(size) {
    var n = Number(size);
    if (!isFinite(n) || n < 0) return "";
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
    return (n / (1024 * 1024)).toFixed(2) + " MB";
  }

  function yesNo(value) {
    if (value === true) return tx("是");
    if (value === false) return tx("否");
    return EMPTY;
  }

  function clearError() {
    if (els.error) {
      els.error.textContent = "";
      els.error.hidden = true;
    }
  }

  function showError(message) {
    if (!els.error) return;
    els.error.textContent = message ? tx(message) : "";
    els.error.hidden = !message;
  }

  function statusText() {
    switch (state.statusKey) {
      case "scanning": return tx("扫描中…");
      case "scanned": return tx("扫描完成") + (state.statusData ? " · " + state.statusData : "");
      case "repairing": return tx("修复中…");
      case "repaired": return tx("修复完成") + (state.statusData ? " · " + state.statusData : "");
      case "scan-failed": return tx("扫描失败");
      case "repair-failed": return tx("修复失败");
      case "empty": return state.statusData || "";
      default: return "";
    }
  }

  function setStatus(key, data) {
    state.statusKey = key;
    state.statusData = data || "";
    if (els.status) els.status.textContent = statusText();
  }

  function setBusy(busy) {
    state.busy = !!busy;
    if (els.scan) els.scan.disabled = state.busy;
    if (els.repair) els.repair.disabled = state.busy;
    page.setAttribute("aria-busy", state.busy ? "true" : "false");
  }

  function renderFileName() {
    if (!els.fileName) return;
    if (!state.file) {
      els.fileName.textContent = "";
      els.fileName.hidden = true;
      return;
    }
    els.fileName.textContent = state.file.name + " · " + formatBytes(state.file.size);
    els.fileName.hidden = false;
  }

  function fillList(list, items, line) {
    if (!list) return 0;
    while (list.firstChild) list.removeChild(list.firstChild);
    var values = Array.isArray(items) ? items.slice(0, 200) : [];
    values.forEach(function (item) {
      var li = document.createElement("li");
      li.textContent = line(item);
      list.appendChild(li);
    });
    return values.length;
  }

  function renderScan(scan) {
    state.scan = scan || null;
    if (!scan || !els.scanSection) {
      setHidden(els.scanSection, true);
      return;
    }
    setHidden(els.scanSection, false);

    if (els.fmt) els.fmt.textContent = scan.format || EMPTY;
    if (els.arch) els.arch.textContent = scan.arch || EMPTY;
    if (els.bits) els.bits.textContent = scan.bits == null ? EMPTY : String(scan.bits);
    if (els.endian) els.endian.textContent = scan.endian || EMPTY;

    var matrix = scan.matrix || {};
    if (els.cell) els.cell.textContent = matrix.cell || tx("矩阵外");
    if (els.repairable) els.repairable.textContent = yesNo(matrix.repairable);

    if (els.scanVerdict) {
      var supported = scan.supported === true;
      var repairable = matrix.repairable === true;
      els.scanVerdict.textContent = supported
        ? (repairable ? tx("矩阵内") : tx("仅分析"))
        : tx("不支持");
      els.scanVerdict.className = "binary-pill " +
        (supported && repairable ? "is-verified" : supported ? "is-analysis" : "is-unsupported");
    }

    var findings = Array.isArray(scan.findings) ? scan.findings : [];
    if (els.findingsCount) els.findingsCount.textContent = String(findings.length);
    var findingLines = fillList(els.findings, findings, function (finding) {
      var parts = [
        finding.kind || "sink",
        finding.address || "",
        finding.callee || "",
        "capacity=" + (finding.capacity == null ? "?" : finding.capacity),
        "before=" + (finding.before == null ? "?" : finding.before),
        "after=" + (finding.after == null ? "?" : finding.after),
        finding.patchable === false ? "not patchable" : ""
      ];
      return parts.filter(Boolean).join(" · ");
    });
    if (els.findings && findingLines === 0) {
      var empty = document.createElement("li");
      empty.className = "binary-list-empty";
      empty.textContent = tx("没有发现可修补的 sink。");
      els.findings.appendChild(empty);
    }

    var limitations = Array.isArray(scan.limitations) ? scan.limitations : [];
    var limitationLines = fillList(els.limitations, limitations, function (item) { return String(item); });
    setHidden(els.limitationsBlock, limitationLines === 0);
  }

  function dispositionMeta(disposition) {
    return DISPOSITIONS[disposition] || null;
  }

  function paintBadge(element, disposition) {
    if (!element) return;
    var meta = dispositionMeta(disposition);
    element.textContent = meta ? tx(meta.label) : (disposition || tx("未知"));
    element.className = "binary-badge " + (meta ? meta.cls : "is-unknown");
    element.hidden = false;
  }

  /* Shared report renderer for the deterministic path and the two AI cards. */
  function applyResult(target, payload) {
    var report = payload.report && typeof payload.report === "object" ? payload.report : null;
    var delivery = (payload.delivery && typeof payload.delivery === "object")
      ? payload.delivery
      : (report && report.delivery && typeof report.delivery === "object" ? report.delivery : {});
    var disposition = payload.disposition || (report && report.disposition) || "";
    var verified = payload.verified === true ? true : (payload.verified === false ? false : null);
    var allowed = delivery.download_allowed === true
      && typeof payload.patched_base64 === "string"
      && payload.patched_base64.length > 0;

    target.disposition = disposition;
    target.verified = verified;
    target.delivery = delivery;
    target.allowed = allowed;
    target.candidate = allowed
      ? { base64: payload.patched_base64, filename: safeFilename(payload.filename) }
      : null;

    paintBadge(target.badge, disposition);
    if (target.dispositionCode) target.dispositionCode.textContent = disposition || EMPTY;
    if (target.verifiedEl) target.verifiedEl.textContent = yesNo(verified);
    if (target.tier) target.tier.textContent = delivery.tier || EMPTY;
    if (target.downloadAllowed) {
      target.downloadAllowed.textContent = yesNo(
        delivery.download_allowed === true ? true : (delivery.download_allowed === false ? false : undefined)
      );
    }

    var detail = payload.detail || (report && report.error) || "";
    if (target.detail) {
      target.detail.textContent = detail ? String(detail) : "";
      target.detail.hidden = !detail;
    }

    if (target.download) {
      target.download.hidden = !allowed;
      target.download.disabled = !allowed;
      target.download.textContent = verified === true
        ? tx(target.verifiedDownloadLabel || "下载已验证修复候选")
        : tx(target.downloadLabel || "下载未验证候选");
    }
    if (target.filename) {
      target.filename.textContent = allowed ? target.candidate.filename : "";
      target.filename.hidden = !allowed;
    }

    var warnings = Array.isArray(payload.warnings)
      ? payload.warnings
      : (report && Array.isArray(report.warnings) ? report.warnings : []);
    var warningLines = fillList(target.warnings, warnings, function (item) { return String(item); });
    setHidden(target.warningsBlock, warningLines === 0);

    if (target.report && target.reportJson) {
      target.reportJson.textContent = JSON.stringify(report || payload, null, 2);
      target.report.hidden = false;
    }
  }

  function renderRepair(payload) {
    state.repair = payload || null;
    if (!payload || !els.repairSection) {
      state.candidate = null;
      setHidden(els.repairSection, true);
      setHidden(els.download, true);
      return;
    }
    setHidden(els.repairSection, false);
    var target = {
      badge: els.disposition,
      dispositionCode: els.dispositionCode,
      verifiedEl: els.verified,
      tier: els.tier,
      downloadAllowed: els.downloadAllowed,
      detail: els.repairDetail,
      download: els.download,
      filename: els.candidateName,
      warningsBlock: els.warningsBlock,
      warnings: els.warnings,
      report: els.report,
      reportJson: els.reportJson,
      downloadLabel: "下载修复候选"
    };
    applyResult(target, payload);
    state.candidate = target.candidate;
    if (els.downloadNote) setHidden(els.downloadNote, !!target.allowed);
  }

  function renderRepairError(payload, httpStatus) {
    renderRepair(payload);
    var detail = (payload && payload.detail) || (payload && payload.report && payload.report.error) || "";
    var code = "HTTP " + httpStatus;
    showError(detail ? detail + " (" + code + ")" : tx("修复请求失败") + " (" + code + ")");
    setStatus("repair-failed", payload && payload.disposition ? payload.disposition : "");
  }

  function parseJson(response) {
    return response.text().then(function (body) {
      if (!body) return {};
      try {
        return JSON.parse(body);
      } catch (error) {
        return { detail: body.slice(0, 500) };
      }
    });
  }

  function postForm(url, form) {
    var controller = typeof AbortController === "function" ? new AbortController() : null;
    var timer = null;
    if (controller) {
      timer = window.setTimeout(function () { controller.abort(); }, REQUEST_TIMEOUT_MS);
    }
    var options = {
      method: "POST",
      body: form,
      credentials: "same-origin",
      headers: { "Accept": "application/json" }
    };
    if (controller) options.signal = controller.signal;
    return fetch(url, options).then(function (response) {
      if (timer) window.clearTimeout(timer);
      return parseJson(response).then(function (payload) {
        return { status: response.status, ok: response.ok, payload: payload };
      });
    }).catch(function (error) {
      if (timer) window.clearTimeout(timer);
      throw error;
    });
  }

  function newForm(file) {
    var form = new FormData();
    form.append("binary", file, file.name);
    form.append("csrf", csrfToken());
    return form;
  }

  function request(url, file) {
    var form = newForm(file);
    if (url.indexOf("/api/binary/repair") === 0 && els.allowStatic && els.allowStatic.checked) {
      form.append("allow_static_only", "1");
    }
    return postForm(url, form);
  }

  function requestFailure(error) {
    if (error && error.name === "AbortError") return tx("请求超时，请重试。");
    return tx("网络请求失败，请确认本机服务仍在运行。");
  }

  function scanFile(file) {
    if (state.busy) return Promise.resolve();
    clearError();
    setBusy(true);
    setStatus("scanning");
    return request("/api/binary/scan", file).then(function (result) {
      var payload = result.payload || {};
      if (result.status === 200 && payload.ok === true && payload.scan) {
        renderScan(payload.scan);
        if (payload.scan.matrix && payload.scan.matrix.cell) {
          setStatus("scanned", payload.scan.matrix.cell);
        } else {
          setStatus("scanned");
        }
        return;
      }
      if (payload.scan && typeof payload.scan === "object") renderScan(payload.scan);
      else setHidden(els.scanSection, true);
      var detail = payload.detail;
      if (Array.isArray(detail)) detail = detail.join("；");
      showError(detail || tx("扫描失败：该输入无法识别或不在支持范围内。"));
      setStatus("scan-failed");
    }).catch(function (error) {
      showError(requestFailure(error));
      setStatus("scan-failed");
    }).finally(function () {
      setBusy(false);
    });
  }

  function repairFile(file) {
    if (state.busy) return Promise.resolve();
    clearError();
    setBusy(true);
    setStatus("repairing");
    return request("/api/binary/repair", file).then(function (result) {
      var payload = result.payload || {};
      if (result.status === 200 && payload.ok === true) {
        renderRepair(payload);
        var delivery = payload.delivery || {};
        setStatus("repaired", (payload.disposition || "") +
          (delivery.tier ? " · " + delivery.tier : ""));
        return;
      }
      renderRepairError(payload, result.status);
    }).catch(function (error) {
      showError(requestFailure(error));
      setStatus("repair-failed");
    }).finally(function () {
      setBusy(false);
    });
  }

  function handleFile(file) {
    if (!file) return;
    state.file = file;
    state.scan = null;
    state.repair = null;
    state.candidate = null;
    renderFileName();
    setHidden(els.repairSection, true);
    setHidden(els.download, true);
    if (els.report) els.report.hidden = true;
    if (file.size > MAX_BYTES) {
      showError(tx("文件超过 20 MiB 上限，请换一个更小的样本。"));
      setStatus("empty", "");
      return;
    }
    if (file.size === 0) {
      showError(tx("文件为空，请重新选择。"));
      setStatus("empty", "");
      return;
    }
    scanFile(file);
  }

  function decodeBase64(value) {
    try {
      var binary = window.atob(value);
      var bytes = new Uint8Array(binary.length);
      for (var index = 0; index < binary.length; index += 1) {
        bytes[index] = binary.charCodeAt(index);
      }
      return bytes;
    } catch (error) {
      return null;
    }
  }

  function triggerDownload(candidate) {
    var bytes = decodeBase64(candidate.base64);
    if (!bytes) {
      showError(tx("下载失败：候选数据无法解码。"));
      return false;
    }
    var blob = new Blob([bytes], { type: "application/octet-stream" });
    var url = URL.createObjectURL(blob);
    var anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = candidate.filename;
    anchor.rel = "noopener";
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    window.setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    return true;
  }

  function downloadCandidate() {
    if (state.candidate) triggerDownload(state.candidate);
  }

  /* ==================== 两条 AI 直接二进制修复路径 ==================== */

  function cardElements(prefix) {
    return {
      result: byId(prefix + "-result"),
      badge: byId(prefix + "-badge"),
      path: byId(prefix + "-path"),
      called: byId(prefix + "-called"),
      aiStatus: byId(prefix + "-ai-status"),
      mode: byId(prefix + "-mode"),
      provider: byId(prefix + "-provider"),
      model: byId(prefix + "-model"),
      sha: byId(prefix + "-sha"),
      latency: byId(prefix + "-latency"),
      dispositionCode: byId(prefix + "-disposition"),
      verifiedEl: byId(prefix + "-verified"),
      tier: byId(prefix + "-tier"),
      downloadAllowed: byId(prefix + "-download-allowed"),
      detail: byId(prefix + "-detail"),
      error: byId(prefix + "-error"),
      download: byId(prefix + "-download"),
      filename: byId(prefix + "-filename"),
      warningsBlock: byId(prefix + "-warnings-block"),
      warnings: byId(prefix + "-warnings"),
      report: byId(prefix + "-report"),
      reportJson: byId(prefix + "-report-json")
    };
  }

  var aiEls = {
    section: document.querySelector('[data-testid="binary-ai-section"]'),
    drop: byId("binary-ai-drop"),
    file: byId("binary-ai-file"),
    fileName: byId("binary-ai-file-name"),
    allowStatic: byId("binary-ai-allow-static"),
    runPlan: byId("binary-ai-run-plan"),
    runBytes: byId("binary-ai-run-bytes"),
    status: byId("binary-ai-status"),
    error: byId("binary-ai-error"),
    plan: cardElements("binary-ai-plan"),
    bytes: cardElements("binary-ai-bytes")
  };

  function aiCard(pathName) {
    return pathName === "ai_bytes" ? aiEls.bytes : aiEls.plan;
  }

  var aiState = {
    file: null,
    busy: false,
    statusKey: "idle",
    statusData: "",
    results: { ai_plan: null, ai_bytes: null },
    candidates: { ai_plan: null, ai_bytes: null }
  };

  function aiPathLabel(pathName) {
    return pathName === "ai_bytes" ? tx("路径二（AI 字节）") : tx("路径一（AI 规划）");
  }

  function aiStatusText() {
    switch (aiState.statusKey) {
      case "ai-ready": return tx("已选择文件，选择一条 AI 路径运行。") +
        (aiState.statusData ? " · " + aiState.statusData : "");
      case "ai-running": return tx(aiState.statusData === "ai_bytes" ? "路径二运行中…" : "路径一运行中…");
      case "ai-done": return tx(aiState.statusData.indexOf("ai_bytes") === 0 ? "路径二完成" : "路径一完成") +
        (aiState.statusData.indexOf(" · ") >= 0 ? " · " + aiState.statusData.split(" · ").slice(1).join(" · ") : "");
      case "ai-failed": return tx(aiState.statusData === "ai_bytes" ? "路径二运行失败" : "路径一运行失败");
      case "empty": return aiState.statusData || "";
      default: return "";
    }
  }

  function setAiStatus(key, data) {
    aiState.statusKey = key;
    aiState.statusData = data || "";
    if (aiEls.status) aiEls.status.textContent = aiStatusText();
  }

  function setAiBusy(busy) {
    aiState.busy = !!busy;
    if (aiEls.runPlan) aiEls.runPlan.disabled = aiState.busy;
    if (aiEls.runBytes) aiEls.runBytes.disabled = aiState.busy;
    if (aiEls.section) aiEls.section.setAttribute("aria-busy", aiState.busy ? "true" : "false");
  }

  function clearAiError() {
    if (!aiEls.error) return;
    aiEls.error.textContent = "";
    aiEls.error.hidden = true;
  }

  function showAiError(message) {
    if (!aiEls.error) return;
    aiEls.error.textContent = message ? tx(message) : "";
    aiEls.error.hidden = !message;
  }

  function renderAiFileName() {
    if (!aiEls.fileName) return;
    if (!aiState.file) {
      aiEls.fileName.textContent = "";
      aiEls.fileName.hidden = true;
      return;
    }
    aiEls.fileName.textContent = aiState.file.name + " · " + formatBytes(aiState.file.size);
    aiEls.fileName.hidden = false;
  }

  function renderAi(pathName, payload, httpStatus) {
    aiState.results[pathName] = payload
      ? { payload: payload, status: httpStatus || 0 }
      : null;
    var card = aiCard(pathName);
    if (!payload || !card || !card.result) {
      if (card) setHidden(card.result, true);
      return;
    }
    setHidden(card.result, false);
    var ok = httpStatus === 200 && payload.ok === true;

    var ai = payload.ai && typeof payload.ai === "object" ? payload.ai : {};
    var called = ai.called === true ? true : (ai.called === false ? false : undefined);
    if (card.path) card.path.textContent = payload.path || pathName;
    if (card.called) card.called.textContent = yesNo(called);
    if (card.aiStatus) card.aiStatus.textContent = ai.status ? String(ai.status) : EMPTY;
    if (card.mode) card.mode.textContent = ai.mode ? String(ai.mode) : EMPTY;
    if (card.provider) card.provider.textContent = ai.provider ? String(ai.provider) : EMPTY;
    if (card.model) card.model.textContent = ai.model ? String(ai.model) : EMPTY;
    if (card.sha) card.sha.textContent = ai.plan_sha256 ? String(ai.plan_sha256) : EMPTY;
    if (card.latency) {
      card.latency.textContent = ai.latency_ms == null ? EMPTY : String(ai.latency_ms) + " ms";
    }

    applyResult(card, payload);
    aiState.candidates[pathName] = card.candidate;

    var disposition = payload.disposition || "";
    var verified = payload.verified === true ? true : (payload.verified === false ? false : null);
    card.result.dataset.state = ok ? "ok" : "error";
    card.result.dataset.disposition = disposition || "unset";
    card.result.dataset.verified =
      verified === true ? "true" : (verified === false ? "false" : "unknown");
    card.result.dataset.report = card.report && card.report.hidden ? "hidden" : "shown";
    card.result.dataset.download = card.allowed ? "allowed" : "blocked";
    if (card.download) card.download.dataset.state = card.allowed ? "allowed" : "blocked";

    if (card.error) {
      var aiError = ai.error ? String(ai.error) : "";
      card.error.textContent = aiError;
      card.error.hidden = !aiError;
    }
  }

  function aiErrorText(status, payload) {
    var detail = payload && payload.detail;
    if (Array.isArray(detail)) detail = detail.join("；");
    var suffix = detail ? " · " + String(detail) : "";
    if (status === 503) return tx("AI 服务未配置（未设置 provider）") + suffix;
    if (status === 422) return tx("AI 修复未通过校验") + suffix;
    return (detail ? String(detail) : tx("AI 修复请求失败")) + " · HTTP " + status;
  }

  function runAiPath(pathName) {
    if (aiState.busy) return Promise.resolve();
    if (!aiState.file) {
      showAiError(tx("请先选择或拖入一个二进制文件（AI 路径）。"));
      return Promise.resolve();
    }
    clearAiError();
    setAiBusy(true);
    setAiStatus("ai-running", pathName);
    var form = newForm(aiState.file);
    form.append("path", pathName);
    form.append(
      "allow_static_only",
      aiEls.allowStatic && aiEls.allowStatic.checked ? "1" : "0"
    );
    return postForm("/api/binary/ai-repair", form).then(function (result) {
      var payload = result.payload || {};
      renderAi(pathName, payload, result.status);
      if (result.status === 200 && payload.ok === true) {
        var delivery = payload.delivery || {};
        setAiStatus("ai-done", pathName + " · " +
          (payload.disposition || "") + (delivery.tier ? " · " + delivery.tier : ""));
        return;
      }
      showAiError(aiErrorText(result.status, payload));
      setAiStatus("ai-failed", pathName);
    }).catch(function (error) {
      showAiError(requestFailure(error));
      setAiStatus("ai-failed", pathName);
    }).finally(function () {
      setAiBusy(false);
    });
  }

  function downloadAi(pathName) {
    var candidate = aiState.candidates[pathName];
    if (candidate) triggerDownload(candidate);
  }

  function handleAiFile(file) {
    if (!file) return;
    aiState.file = file;
    aiState.results = { ai_plan: null, ai_bytes: null };
    aiState.candidates = { ai_plan: null, ai_bytes: null };
    renderAiFileName();
    clearAiError();
    [aiEls.plan, aiEls.bytes].forEach(function (card) {
      setHidden(card.result, true);
      if (card.result) {
        card.result.dataset.state = "idle";
        card.result.dataset.disposition = "unset";
        card.result.dataset.verified = "unknown";
        card.result.dataset.report = "hidden";
        card.result.dataset.download = "blocked";
      }
      if (card.download) card.download.dataset.state = "blocked";
    });
    if (file.size > MAX_BYTES) {
      showAiError(tx("文件超过 20 MiB 上限，请换一个更小的样本。"));
      setAiStatus("empty", "");
      return;
    }
    if (file.size === 0) {
      showAiError(tx("文件为空，请重新选择。"));
      setAiStatus("empty", "");
      return;
    }
    setAiStatus("ai-ready", file.name);
  }

  /* ==================== 共享交互 ==================== */

  function wireDrop(drop, input, onFile) {
    if (input) {
      input.addEventListener("change", function () {
        var files = input.files;
        onFile(files && files.length ? files[0] : null);
      });
    }
    if (!drop) return;
    ["dragenter", "dragover"].forEach(function (name) {
      drop.addEventListener(name, function (event) {
        event.preventDefault();
        event.stopPropagation();
        drop.classList.add("is-dragover");
      });
    });
    ["dragleave", "dragend"].forEach(function (name) {
      drop.addEventListener(name, function (event) {
        event.preventDefault();
        event.stopPropagation();
        if (event.relatedTarget && drop.contains(event.relatedTarget)) return;
        drop.classList.remove("is-dragover");
      });
    });
    drop.addEventListener("drop", function (event) {
      event.preventDefault();
      event.stopPropagation();
      drop.classList.remove("is-dragover");
      var transfer = event.dataTransfer;
      var files = transfer && transfer.files;
      if (files && files.length) onFile(files[0]);
    });
  }

  function refreshTexts() {
    renderFileName();
    if (state.statusKey !== "idle") setStatus(state.statusKey, state.statusData);
    if (state.scan) renderScan(state.scan);
    if (state.repair) renderRepair(state.repair);
    if (aiEls.section) {
      renderAiFileName();
      if (aiState.statusKey !== "idle") setAiStatus(aiState.statusKey, aiState.statusData);
      var planEntry = aiState.results.ai_plan;
      var bytesEntry = aiState.results.ai_bytes;
      if (planEntry) renderAi("ai_plan", planEntry.payload, planEntry.status);
      if (bytesEntry) renderAi("ai_bytes", bytesEntry.payload, bytesEntry.status);
    }
  }

  wireDrop(els.drop, els.file, handleFile);

  if (els.scan) {
    els.scan.addEventListener("click", function () {
      if (!state.file) {
        showError(tx("请先选择或拖入一个二进制文件。"));
        return;
      }
      scanFile(state.file);
    });
  }

  if (els.repair) {
    els.repair.addEventListener("click", function () {
      if (!state.file) {
        showError(tx("请先选择或拖入一个二进制文件。"));
        return;
      }
      repairFile(state.file);
    });
  }

  if (els.download) {
    els.download.addEventListener("click", downloadCandidate);
  }

  if (aiEls.section) {
    wireDrop(aiEls.drop, aiEls.file, handleAiFile);
    if (aiEls.runPlan) {
      aiEls.runPlan.addEventListener("click", function () { runAiPath("ai_plan"); });
    }
    if (aiEls.runBytes) {
      aiEls.runBytes.addEventListener("click", function () { runAiPath("ai_bytes"); });
    }
    if (aiEls.plan.download) {
      aiEls.plan.download.addEventListener("click", function () { downloadAi("ai_plan"); });
    }
    if (aiEls.bytes.download) {
      aiEls.bytes.download.addEventListener("click", function () { downloadAi("ai_bytes"); });
    }
    setHidden(aiEls.plan.result, true);
    setHidden(aiEls.bytes.result, true);
  }

  document.addEventListener("brlang:change", refreshTexts);

  renderFileName();
  setHidden(els.download, true);
  setHidden(els.repairSection, true);
  setHidden(els.scanSection, true);
})();
