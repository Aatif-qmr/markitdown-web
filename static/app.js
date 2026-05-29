// MarkItDown GUI front end: input handling, async polling, copy/download.

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const browseBtn = document.getElementById("browse-btn");
const urlInput = document.getElementById("url-input");
const urlBtn = document.getElementById("url-btn");
const errorBox = document.getElementById("error");
const spinner = document.getElementById("spinner");
const outputSection = document.getElementById("output-section");
const output = document.getElementById("output");
const copyBtn = document.getElementById("copy-btn");
const downloadBtn = document.getElementById("download-btn");

let pollTimer = null;
let downloadName = "converted.md"; // updated per source

// ---- UI state helpers --------------------------------------------------

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}

function clearError() {
  errorBox.hidden = true;
  errorBox.textContent = "";
}

function setBusy(busy) {
  spinner.hidden = !busy;
  browseBtn.disabled = busy;
  urlBtn.disabled = busy;
  urlInput.disabled = busy;
}

function showOutput(markdown) {
  output.value = markdown;
  outputSection.hidden = false;
}

// ---- Conversion flow ---------------------------------------------------

function baseName(filename) {
  const dot = filename.lastIndexOf(".");
  return dot > 0 ? filename.slice(0, dot) : filename;
}

async function startConversion(formDataOrJson, isJson) {
  clearError();
  outputSection.hidden = true;
  setBusy(true);
  try {
    const res = await fetch("/convert", {
      method: "POST",
      ...(isJson
        ? {
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(formDataOrJson),
          }
        : { body: formDataOrJson }),
    });
    const data = await res.json();
    if (!res.ok) {
      setBusy(false);
      showError(data.error || "Conversion request failed.");
      return;
    }
    pollStatus(data.job_id);
  } catch (err) {
    setBusy(false);
    showError("Connection error — is the server running?");
  }
}

function pollStatus(jobId) {
  pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`/status/${jobId}`);
      const data = await res.json();
      if (data.status === "running") return;

      clearInterval(pollTimer);
      setBusy(false);
      if (data.status === "done") {
        showOutput(data.markdown || "");
      } else {
        showError(data.error || "Conversion failed.");
      }
    } catch (err) {
      clearInterval(pollTimer);
      setBusy(false);
      showError("Connection error — is the server running?");
    }
  }, 1000);
}

function convertFile(file) {
  downloadName = baseName(file.name) + ".md";
  const fd = new FormData();
  fd.append("file", file);
  startConversion(fd, false);
}

function convertUrl() {
  const url = urlInput.value.trim();
  if (!url) {
    showError("Please enter a URL.");
    return;
  }
  downloadName = "converted.md";
  startConversion({ url }, true);
}

// ---- Input wiring ------------------------------------------------------

browseBtn.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("click", (e) => {
  if (e.target === browseBtn) return; // button handles its own click
  fileInput.click();
});
dropzone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    fileInput.click();
  }
});

fileInput.addEventListener("change", () => {
  if (fileInput.files.length) convertFile(fileInput.files[0]);
  fileInput.value = ""; // allow re-selecting the same file
});

["dragenter", "dragover"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  })
);
["dragleave", "drop"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
  })
);
dropzone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files[0];
  if (file) convertFile(file);
});

urlBtn.addEventListener("click", convertUrl);
urlInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") convertUrl();
});

// ---- Output actions ----------------------------------------------------

copyBtn.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(output.value);
    copyBtn.textContent = "Copied!";
    setTimeout(() => (copyBtn.textContent = "Copy"), 1500);
  } catch (err) {
    output.select();
    document.execCommand("copy");
  }
});

downloadBtn.addEventListener("click", () => {
  const blob = new Blob([output.value], { type: "text/markdown" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = downloadName;
  a.click();
  URL.revokeObjectURL(a.href);
});
