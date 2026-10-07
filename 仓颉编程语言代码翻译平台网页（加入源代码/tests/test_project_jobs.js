const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../app.js"), "utf8");
const helpers = source.slice(source.indexOf("function showProjectJobProgress("), source.indexOf("async function runRealBackendTranslation("));
const snapshots = [
  { ok: true, status: "running", stage: "translating", completed_files: 0, total_files: 2, current_file: "Main.java" },
  { ok: true, status: "running", stage: "translating", completed_files: 1, total_files: 2, current_file: "Helper.java" },
  { ok: true, status: "completed", stage: "completed", completed_files: 2, total_files: 2, result: { ok: true, artifact: { download_url: "/download" } } }
];
const rendered = [];
const removed = [];
const targetCode = {};
const context = vm.createContext({
  API_BASE: "http://127.0.0.1:8765",
  PROJECT_JOB_STORAGE_KEY: "active-job",
  activeModule: "project",
  targetCode,
  setRunState: (message) => rendered.push(message),
  renderPipeline: () => {},
  delay: async () => {},
  localStorage: { removeItem: (key) => removed.push(key) },
  fetch: async () => ({ ok: true, json: async () => snapshots.shift() })
});
vm.runInContext(helpers, context);
context.showProjectJobProgress({ stage: "translating_project", completed_files: 0, total_files: 2 });
assert.match(targetCode.textContent, /正在整项目翻译并生成仓颉项目/);

context.waitForProjectJob("abc").then((result) => {
  assert.equal(result.artifact.download_url, "/download");
  assert.ok(rendered.some((message) => message.includes("1/2")));
  assert.deepEqual(removed, ["active-job"]);
  console.log("Project job polling, whole-project and per-file progress checks passed.");
}).catch((error) => { console.error(error); process.exitCode = 1; });
