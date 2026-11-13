/* Universal binary repair page (/binary).
 *
 * Two calls only:
 *   POST /api/binary/scan   multipart(binary, csrf)  -> read-only matrix/sink report
 *   POST /api/binary/repair multipart(binary, csrf, allow_static_only=1) -> candidate
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

  var els = {
    drop: document.getElementById("binary-drop"),
    file: document.getElementById("binary-file"),
    fileName: document.getElementById("binary-file-name"),
    scan: document.getElementById("binary-scan"),
    repair: document.getElementById("binary-repair"),
    allowStatic: document.getElementById("binary-allow-static"),
    status: document.getElementById("binary-scan-status"),
    error: document.getElementById("binary-error"),
    scanSection: document.getElementById("binary-scan-result"),
    scanVerdict: document.getElementById("binary-scan-verdict"),
    fmt: document.getElementById("binary-scan-format"),
    arch: document.getElementById("binary-scan-arch"),
    bits: document.getElementById("binary-scan-bits"),
    endian: document.getElementById("binary-scan-endian"),
    cell: document.getElementById("binary-scan-cell"),
    repairable: document.getElementById("binary-scan-repairable"),
    findingsCount: document.getElementById("binary-scan-findings-count"),
    findings: document.getElementById("binary-findings"),
    limitationsBlock: document.getElementById("binary-limitations-block"),
    limitations: document.getElementById("binary-limitations"),
    repairSection: document.getElementById("binary-repair-result"),
    disposition: document.getElementById("binary-disposition"),
    dispositionCode: document.getElementById("binary-disposition-code"),
    verified: document.getElementById("binary-verified"),
    tier: document.getElementById("binary-tier"),
    downloadAllowed: document.getElementById("binary-download-allowed"),
    repairDetail: document.getElementById("binary-repair-detail"),
    download: document.getElementById("binary-download"),
    candidateName: document.getElementById("binary-candidate-name"),
    downloadNote: document.getElementById("binary-download-note"),
    warningsBlock: document.getElementById("binary-warnings-block"),
    warnings: document.getElementById("binary-warnings"),
    report: document.getElementById("binary-report"),
    reportJson: document.getElementById("binary-report-json")
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
    if (!list) return;
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
    if (els.findings) {
      if (findingLines === 0) {
        var empty = document.createElement("li");
        empty.className = "binary-list-empty";
        empty.textContent = tx("没有发现可修补的 sink。");
        els.findings.appendChild(empty);
      }
    }

    var limitations = Array.isArray(scan.limitations) ? scan.limitations : [];
    var limitationLines = fillList(els.limitations, limitations, function (item) { return String(item); });
    setHidden(els.limitationsBlock, limitationLines === 0);
  }

  function renderDisposition(disposition) {
    if (!els.disposition) return;
    var meta = DISPOSITIONS[disposition];
    els.disposition.textContent = meta ? tx(meta.label) : (disposition || tx("未知"));
    els.disposition.className = "binary-badge " + (meta ? meta.cls : "is-unknown");
    els.disposition.hidden = false;
  }

  function renderRepair(payload) {
    state.repair = payload || null;
    if (!payload || !els.repairSection) {
      setHidden(els.repairSection, true);
      setHidden(els.download, true);
      return;
    }
    setHidden(els.repairSection, false);

    var report = payload.report && typeof payload.report === "object" ? payload.report : null;
    var delivery = (payload.delivery && typeof payload.delivery === "object")
      ? payload.delivery
      : (report && report.delivery && typeof report.delivery === "object" ? report.delivery : {});
    var disposition = payload.disposition || (report && report.disposition) || "";
    var verified = payload.verified === true ? true : (payload.verified === false ? false : null);

    renderDisposition(disposition);
    if (els.dispositionCode) els.dispositionCode.textContent = disposition || EMPTY;
    if (els.verified) els.verified.textContent = yesNo(verified == null ? undefined : verified);
    if (els.tier) els.tier.textContent = delivery.tier || EMPTY;
    if (els.downloadAllowed) {
      els.downloadAllowed.textContent = yesNo(
        delivery.download_allowed === true ? true : (delivery.download_allowed === false ? false : undefined)
      );
    }

    var detail = payload.detail || (report && report.error) || "";
    if (els.repairDetail) {
      els.repairDetail.textContent = detail ? String(detail) : "";
      els.repairDetail.hidden = !detail;
    }

    var allowed = delivery.download_allowed === true
      && typeof payload.patched_base64 === "string"
      && payload.patched_base64.length > 0;
    state.candidate = allowed
      ? { base64: payload.patched_base64, filename: safeFilename(payload.filename) }
      : null;

    if (els.download) {
      els.download.hidden = !allowed;
      els.download.disabled = !allowed;
      els.download.textContent = verified === true
        ? tx("下载已验证修复候选")
        : tx("下载未验证候选");
    }
    if (els.candidateName) {
      els.candidateName.textContent = allowed ? state.candidate.filename : "";
      els.candidateName.hidden = !allowed;
    }
    setHidden(els.downloadNote, allowed);

    var warnings = Array.isArray(payload.warnings)
      ? payload.warnings
      : (report && Array.isArray(report.warnings) ? report.warnings : []);
    var warningLines = fillList(els.warnings, warnings, function (item) { return String(item); });
    setHidden(els.warningsBlock, warningLines === 0);

    if (els.report && els.reportJson) {
      var shown = report || payload;
      els.reportJson.textContent = JSON.stringify(shown, null, 2);
      els.report.hidden = false;
    }
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

  function request(url, file) {
    var form = new FormData();
    form.append("binary", file, file.name);
    form.append("csrf", csrfToken());
    if (url.indexOf("/api/binary/repair") === 0 && els.allowStatic && els.allowStatic.checked) {
      form.append("allow_static_only", "1");
    }
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

  function downloadCandidate() {
    if (!state.candidate) return;
    var bytes = decodeBase64(state.candidate.base64);
    if (!bytes) {
      showError(tx("下载失败：候选数据无法解码。"));
      return;
    }
    var blob = new Blob([bytes], { type: "application/octet-stream" });
    var url = URL.createObjectURL(blob);
    var anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = state.candidate.filename;
    anchor.rel = "noopener";
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    window.setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  function refreshTexts() {
    renderFileName();
    if (state.statusKey !== "idle") setStatus(state.statusKey, state.statusData);
    if (state.scan) renderScan(state.scan);
    if (state.repair) renderRepair(state.repair);
  }

  if (els.file) {
    els.file.addEventListener("change", function () {
      var files = els.file.files;
      handleFile(files && files.length ? files[0] : null);
    });
  }

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

  if (els.drop) {
    ["dragenter", "dragover"].forEach(function (name) {
      els.drop.addEventListener(name, function (event) {
        event.preventDefault();
        event.stopPropagation();
        els.drop.classList.add("is-dragover");
      });
    });
    ["dragleave", "dragend"].forEach(function (name) {
      els.drop.addEventListener(name, function (event) {
        event.preventDefault();
        event.stopPropagation();
        if (event.relatedTarget && els.drop.contains(event.relatedTarget)) return;
        els.drop.classList.remove("is-dragover");
      });
    });
    els.drop.addEventListener("drop", function (event) {
      event.preventDefault();
      event.stopPropagation();
      els.drop.classList.remove("is-dragover");
      var transfer = event.dataTransfer;
      var files = transfer && transfer.files;
      if (files && files.length) handleFile(files[0]);
    });
  }

  document.addEventListener("brlang:change", refreshTexts);

  renderFileName();
  setHidden(els.download, true);
  setHidden(els.repairSection, true);
  setHidden(els.scanSection, true);
})();
