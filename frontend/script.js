(function () {
  "use strict";
  var config = window.DATAGUARD_CONFIG || {};
  var state = { file: null, report: null, filter: "ALL", objectUrl: null };
  var $ = function (id) { return document.getElementById(id); };
  var formatSize = function (bytes) { return bytes < 1024 ? bytes + " B" : (bytes / 1024).toFixed(1) + " KB"; };
  var setMessage = function (text, error) { $("upload-message").textContent = text || ""; $("upload-message").style.color = error ? "#e84c5c" : "#16ad70"; };
  function chooseFile(file) {
    setMessage("");
    if (!file) return;
    if (!/\.csv$/i.test(file.name)) return setMessage("Please choose a CSV file.", true);
    if (file.size === 0) return setMessage("The selected file is empty.", true);
    if (file.size > (config.maxFileSizeBytes || 10485760)) return setMessage("File exceeds the 10 MB limit.", true);
    state.file = file;
    $("selected-file").hidden = false;
    $("selected-file").textContent = file.name + " · " + formatSize(file.size);
    $("upload-actions").hidden = false;
    $("file-name").textContent = file.name;
    $("file-size").textContent = formatSize(file.size);
    $("view-file").disabled = false;
  }
  function reset() {
    state.file = null; state.report = null; $("file-input").value = ""; $("selected-file").hidden = true; $("upload-actions").hidden = true; $("view-file").disabled = true; $("download-report").disabled = true; $("upload-progress").hidden = true; setMessage("");
  }
  function setTimeline(step, failed) {
    var items = document.querySelectorAll(".timeline li");
    items.forEach(function (item, index) { item.classList.toggle("complete", index < step); item.classList.toggle("active", index === step); });
    if (failed) items[step].querySelector("strong").textContent = "Processing failed";
  }
  function renderReport(report) {
    state.report = report;
    $("total-records").textContent = report.total_rows == null ? "—" : report.total_rows;
    $("missing-values").textContent = report.missing_values || 0;
    $("duplicate-rows").textContent = report.duplicate_rows || 0;
    $("invalid-values").textContent = report.invalid_values || 0;
    $("quality-score").textContent = report.quality_score == null ? "—" : report.quality_score + "%";
    var score = Number(report.quality_score) || 0;
    $("score-ring").style.background = "conic-gradient(#32c98b " + (score * 3.6) + "deg, #ebf1f5 0deg)";
    $("valid-percent").textContent = score + "%"; $("issue-percent").textContent = (100 - score) + "%";
    var issues = report.issues || [];
    var counts = { MISSING_VALUE: 0, DUPLICATE_ROW: 0, INVALID_VALUE: 0 };
    issues.forEach(function (issue) { if (counts[issue.issue_type] !== undefined) counts[issue.issue_type]++; });
    $("all-count").textContent = "(" + issues.length + ")"; $("missing-count").textContent = "(" + counts.MISSING_VALUE + ")"; $("duplicate-count").textContent = "(" + counts.DUPLICATE_ROW + ")"; $("invalid-count").textContent = "(" + counts.INVALID_VALUE + ")";
    $("issue-total").textContent = "(" + issues.length + ")";
    var visible = state.filter === "ALL" ? issues : issues.filter(function (issue) { return issue.issue_type === state.filter; });
    $("issues-body").innerHTML = visible.length ? visible.map(function (issue) { var type = issue.issue_type || ""; var label = type.replace(/_/g, " "); var cls = type === "MISSING_VALUE" ? "missing" : type === "DUPLICATE_ROW" ? "duplicate" : "invalid"; return "<tr><td>" + (issue.row || "—") + "</td><td>" + (issue.column || "—") + '</td><td><span class="tag ' + cls + '">' + label + "</span></td><td>" + (issue.value == null ? "—" : issue.value) + "</td><td>" + (issue.description || "") + "</td></tr>"; }).join("") : '<tr><td colspan="5" class="empty">No issues in this category.</td></tr>';
    $("download-report").disabled = false; $("file-status").textContent = report.status || "Completed"; $("processed-at").textContent = new Date().toLocaleString(); setTimeline(4);
  }
  async function upload() {
    if (!state.file) return;
    if (!config.apiBaseUrl) return setMessage("Configure apiBaseUrl in frontend/config.js to upload through AWS.", true);
    $("upload-progress").hidden = false; $("upload-progress").firstElementChild.style.width = "20%"; setTimeline(1);
    try {
      var response = await fetch(config.apiBaseUrl + "/upload-url", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ filename: state.file.name, content_type: state.file.type || "text/csv", file_size: state.file.size }) });
      if (!response.ok) throw new Error("Could not create an upload URL.");
      var uploadInfo = await response.json(); $("upload-progress").firstElementChild.style.width = "60%";
      var uploadResponse = await fetch(uploadInfo.upload_url, { method: uploadInfo.upload_method || "PUT", headers: uploadInfo.upload_headers || { "Content-Type": "text/csv" }, body: state.file });
      if (!uploadResponse.ok) throw new Error("The file upload failed.");
      $("upload-progress").firstElementChild.style.width = "100%"; setTimeline(2); poll(uploadInfo.job_id);
    } catch (error) { setMessage(error.message, true); setTimeline(0, true); }
  }
  async function poll(jobId) {
    try {
      var response = await fetch(config.apiBaseUrl + "/jobs/" + encodeURIComponent(jobId));
      if (!response.ok) throw new Error("Could not retrieve processing status.");
      var job = await response.json();
      if (job.status === "COMPLETED" || job.status === "ISSUES_FOUND") {
        var reportResponse = await fetch(config.apiBaseUrl + "/jobs/" + encodeURIComponent(jobId) + "/report");
        if (!reportResponse.ok) throw new Error("The report is not ready.");
        renderReport(await reportResponse.json()); return;
      }
      if (job.status === "FAILED") { setMessage(job.message || "Processing failed.", true); setTimeline(2, true); return; }
      setTimeline(job.status === "PROCESSING" ? 2 : 1); window.setTimeout(function () { poll(jobId); }, config.pollIntervalMs || 3000);
    } catch (error) { setMessage(error.message, true); }
  }
  $("choose-file").addEventListener("click", function () { $("file-input").click(); }); $("file-input").addEventListener("change", function (event) { chooseFile(event.target.files[0]); }); $("remove-file").addEventListener("click", reset); $("upload-file").addEventListener("click", upload);
  $("drop-zone").addEventListener("dragover", function (event) { event.preventDefault(); $("drop-zone").classList.add("dragging"); }); $("drop-zone").addEventListener("dragleave", function () { $("drop-zone").classList.remove("dragging"); }); $("drop-zone").addEventListener("drop", function (event) { event.preventDefault(); $("drop-zone").classList.remove("dragging"); chooseFile(event.dataTransfer.files[0]); }); $("drop-zone").addEventListener("keydown", function (event) { if (event.key === "Enter" || event.key === " ") $("file-input").click(); });
  document.querySelectorAll(".tabs button").forEach(function (button) { button.addEventListener("click", function () { document.querySelector(".tabs .active").classList.remove("active"); button.classList.add("active"); state.filter = button.dataset.filter; if (state.report) renderReport(state.report); }); });
  $("download-report").addEventListener("click", function () { if (!state.report) return; var blob = new Blob([JSON.stringify(state.report, null, 2)], { type: "application/json" }); var link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = (state.file ? state.file.name.replace(/\.csv$/i, "") : "dataguard-report") + "-report.json"; link.click(); URL.revokeObjectURL(link.href); });
  $("view-file").addEventListener("click", function () { if (!state.file) return; if (state.objectUrl) URL.revokeObjectURL(state.objectUrl); state.objectUrl = URL.createObjectURL(state.file); window.open(state.objectUrl, "_blank", "noopener"); }); document.querySelector(".theme-button").addEventListener("click", function () { document.documentElement.classList.toggle("theme-dark"); });
}());
