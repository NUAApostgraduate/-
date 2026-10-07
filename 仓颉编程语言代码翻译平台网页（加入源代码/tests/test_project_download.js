const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../app.js"), "utf8");
const pathHelpers = source.slice(source.indexOf("function projectFilePath("), source.indexOf("function projectFileExtension("));
const pathContext = vm.createContext({});
vm.runInContext(pathHelpers, pathContext);
assert.equal(pathContext.uploadedProjectRelativePath({ webkitRelativePath: "demo/src/main/java/Main.java", name: "Main.java" }), "src/main/java/Main.java");
assert.equal(pathContext.uploadedProjectRelativePath({ name: "Main.java" }), "Main.java");
const helpers = source.slice(source.indexOf("function resetProjectResult()"), source.indexOf("function loadHistoryIntoWorkbench("));
const artifact = {
  download_url: "/artifacts/project_migration_20261006_120000_a1b2c3d4/download",
  download_name: "project.zip",
  files: ["src/main.cj", "cjpm.toml"],
  validation: { build: { build_verified: false, status: "failed" } }
};

function makeContext() {
  const calls = [];
  const context = vm.createContext({
    projectResult: {}, targetCode: {}, copyBtn: {}, projectDownloadStatus: {},
    projectResultSummary: {}, downloadProjectBtn: {}, API_BASE: "http://127.0.0.1:8765",
    window: { setTimeout: (callback) => callback() },
    URL: { createObjectURL: () => "blob:project", revokeObjectURL: () => calls.push("revoke") },
    document: {
      body: { appendChild: () => calls.push("append") },
      createElement: () => ({ click: () => calls.push("click"), remove: () => calls.push("remove") })
    },
    fetch: async (url) => {
      calls.push(url);
      return { ok: true, blob: async () => new Blob(["PK test ZIP"]) };
    }
  });
  vm.runInContext(`let downloadableProject = null;\n${helpers}`, context);
  return { context, calls };
}

async function main() {
  const { context, calls } = makeContext();
  context.renderTranslationOutput("translated code", "project", artifact);
  assert.equal(context.projectResult.hidden, false);
  assert.equal(context.targetCode.hidden, true);
  assert.equal(context.copyBtn.hidden, true);
  assert.equal(context.targetCode.textContent, "translated code");
  assert.match(context.projectResultSummary.textContent, /2.*ZIP/);
  assert.match(context.projectResultSummary.textContent, /构建未通过/);

  context.window.showSaveFilePicker = async (options) => {
    calls.push("picker");
    assert.equal(options.suggestedName, "project.zip");
    return { createWritable: async () => ({
      write: async (blob) => { assert.ok(blob.size > 0); calls.push("write"); },
      close: async () => calls.push("close")
    }) };
  };
  await context.downloadTranslatedProject();
  assert.equal(calls[0], "picker");
  assert.equal(calls[1], `${context.API_BASE}${artifact.download_url}`);
  assert.deepEqual(calls.slice(2), ["write", "close"]);
  assert.match(context.projectDownloadStatus.textContent, /已保存/);
  assert.equal(context.downloadProjectBtn.disabled, false);

  calls.length = 0;
  context.window.showSaveFilePicker = async () => { throw { name: "AbortError" }; };
  await context.downloadTranslatedProject();
  assert.equal(calls.length, 0);
  assert.match(context.projectDownloadStatus.textContent, /取消/);

  delete context.window.showSaveFilePicker;
  await context.downloadTranslatedProject();
  assert.ok(calls.includes("click"));
  assert.match(context.projectDownloadStatus.textContent, /下载记录/);

  context.fetch = async () => ({ ok: false });
  await context.downloadTranslatedProject();
  assert.match(context.projectDownloadStatus.textContent, /保存失败/);
  assert.equal(context.downloadProjectBtn.disabled, false);

  context.renderTranslationOutput("snippet", "snippet", null);
  assert.equal(context.projectResult.hidden, true);
  assert.equal(context.targetCode.hidden, false);
  assert.equal(context.copyBtn.hidden, false);
  assert.equal(context.targetCode.textContent, "snippet");
  console.log("Project output, save picker, cancellation, fallback, failure and reset checks passed.");
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
