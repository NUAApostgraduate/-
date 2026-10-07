const datasetExamples = Array.isArray(window.CANGJIE_DATASET_EXAMPLES)
  ? window.CANGJIE_DATASET_EXAMPLES
  : [];

const moduleData = {
  snippet: {
    note: "片段级请选择 1 个本地代码文件，也可直接粘贴代码；建议不超过 240 行或 12000 字符。",
    strategy: "translator-api",
    title: "源代码片段",
    samples: {
      java: `public class Demo {
  public static int sumEven(int[] nums) {
    int total = 0;
    for (int n : nums) {
      if (n % 2 == 0) {
        total += n;
      }
    }
    return total;
  }
}`,
      cpp: `#include <vector>
using namespace std;

int sumEven(vector<int> nums) {
  int total = 0;
  for (int n : nums) {
    if (n % 2 == 0) {
      total += n;
    }
  }
  return total;
}`,
      python: `def sum_even(nums):
    total = 0
    for n in nums:
        if n % 2 == 0:
            total += n
    return total`
    },
    projectFiles: [
      { path: "pom.xml", language: "XML", content: `<?xml version="1.0" encoding="UTF-8"?>
<project>
  <modelVersion>4.0.0</modelVersion>
  <groupId>demo.cangjie</groupId>
  <artifactId>inventory-report</artifactId>
  <version>1.0.0</version>
  <properties>
    <maven.compiler.source>8</maven.compiler.source>
    <maven.compiler.target>8</maven.compiler.target>
  </properties>
</project>`, lines: 11 },
      { path: "README.md", language: "Markdown", content: `# Inventory Report Sample

Small multi-file Java project for project-level migration testing.
The application connects an entry point, service, repository, model, report,
test and resource through real cross-file references.

Exactly one deliberate source error is present:
InventoryService.java is missing its final class-closing brace.`, lines: 8 },
      { path: "src/main/resources/application.properties", language: "Properties", content: `inventory.currency=unit
inventory.report.title=Current Stock`, lines: 2 },
      { path: "src/main/java/app/Main.java", language: "Java", content: `package app;

import app.model.Item;
import app.repository.InMemoryInventoryRepository;
import app.service.InventoryReport;
import java.util.stream.Collectors;

public class Main {
  public static void main(String[] args) {
    InMemoryInventoryRepository repository = new InMemoryInventoryRepository();
    InventoryService service = new InventoryService(repository);
    service.add("keyboard", 3);
    service.add("keyboard", 2);
    service.add("monitor", 2);
    InventoryReport report = new InventoryReport(repository);
    System.out.println(report.render());
    System.out.println("keyboard=" + service.count("keyboard"));
    System.out.println("items=" + repository.findAll().stream().map(Item::getName).collect(Collectors.toList()));
  }
}`, lines: 20 },
      { path: "src/main/java/app/InventoryService.java", language: "Java", content: `package app;

import app.model.Item;
import app.repository.InventoryRepository;

public class InventoryService {
  private final InventoryRepository repository;

  public InventoryService(InventoryRepository repository) {
    this.repository = repository;
  }

  public void add(String name, int quantity) {
    Item item = repository.findByName(name);
    if (item == null) {
      repository.save(new Item(name, quantity));
      return;
    }
    item.increment(quantity);
  }

  public int count(String name) {
    Item item = repository.findByName(name);
    return item == null ? 0 : item.getQuantity();
  }
`, lines: 25 },
      { path: "src/main/java/app/service/InventoryReport.java", language: "Java", content: `package app.service;

import app.model.Item;
import app.repository.InventoryRepository;

public class InventoryReport {
  private final InventoryRepository repository;

  public InventoryReport(InventoryRepository repository) {
    this.repository = repository;
  }

  public String render() {
    StringBuilder result = new StringBuilder("Current Stock\\n");
    for (Item item : repository.findAll()) {
      result.append(item.getName()).append("=").append(item.getQuantity()).append("\\n");
    }
    return result.toString().trim();
  }
}`, lines: 18 },
      { path: "src/main/java/app/model/Item.java", language: "Java", content: `package app.model;

public class Item {
  private final String name;
  private int quantity;

  public Item(String name, int quantity) {
    if (name == null || name.trim().isEmpty()) {
      throw new IllegalArgumentException("Item name is required");
    }
    if (quantity < 0) {
      throw new IllegalArgumentException("Quantity cannot be negative");
    }
    this.name = name;
    this.quantity = quantity;
  }

  public String getName() { return name; }
  public int getQuantity() { return quantity; }

  public void increment(int amount) {
    if (amount < 0) {
      throw new IllegalArgumentException("Increment cannot be negative");
    }
    quantity += amount;
  }
}`, lines: 25 },
      { path: "src/main/java/app/repository/InventoryRepository.java", language: "Java", content: `package app.repository;

import app.model.Item;
import java.util.Collection;

public interface InventoryRepository {
  void save(Item item);
  Item findByName(String name);
  Collection<Item> findAll();
}`, lines: 10 },
      { path: "src/main/java/app/repository/InMemoryInventoryRepository.java", language: "Java", content: `package app.repository;

import app.model.Item;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.Map;

public class InMemoryInventoryRepository implements InventoryRepository {
  private final Map<String, Item> items = new LinkedHashMap<>();
  public void save(Item item) { items.put(item.getName(), item); }
  public Item findByName(String name) { return items.get(name); }
  public Collection<Item> findAll() { return items.values(); }
}`, lines: 13 },
      { path: "src/test/java/app/InventoryServiceTest.java", language: "Java", content: `package app;

import app.repository.InMemoryInventoryRepository;

public class InventoryServiceTest {
  public static void main(String[] args) {
    InMemoryInventoryRepository repository = new InMemoryInventoryRepository();
    InventoryService service = new InventoryService(repository);
    service.add("keyboard", 3);
    service.add("keyboard", 2);
    if (service.count("keyboard") != 5) {
      throw new AssertionError("Expected keyboard count to be 5");
    }
    System.out.println("InventoryServiceTest passed");
  }
}`, lines: 15 }
    ],
    output: `public func sumEven(nums: Array<Int64>): Int64 {
  var total: Int64 = 0
  for (n in nums) {
    if (n % 2 == 0) {
      total += n
    }
  }
  return total
}`
  },
  project: {
    note: "项目级请选择 1 个本地项目文件夹；翻译完成后下载一个 ZIP 文件，保留生成项目的目录结构。",
    strategy: "whole-project",
    title: "项目文件内容",
    samples: {
      java: `project: inventory-report

pom.xml
README.md
src/main/resources/application.properties
src/main/java/app/Main.java
src/main/java/app/InventoryService.java
src/main/java/app/service/InventoryReport.java
src/main/java/app/model/Item.java
src/main/java/app/repository/InventoryRepository.java
src/main/java/app/repository/InMemoryInventoryRepository.java
src/test/java/app/InventoryServiceTest.java

// src/main/java/app/Main.java
package app;

import app.repository.InMemoryInventoryRepository;
import app.service.InventoryReport;

public class Main {
  public static void main(String[] args) {
    InMemoryInventoryRepository repository = new InMemoryInventoryRepository();
    InventoryService service = new InventoryService(repository);
    service.add("keyboard", 3);
    service.add("keyboard", 2);
    service.add("monitor", 2);
    System.out.println(new InventoryReport(repository).render());
  }
}

// src/main/java/app/InventoryService.java
package app;

import app.model.Item;
import app.repository.InventoryRepository;

public class InventoryService {
  private final InventoryRepository repository;

  public InventoryService(InventoryRepository repository) {
    this.repository = repository;
  }

  public int count(String name) {
    Item item = repository.findByName(name);
    return item == null ? 0 : item.getQuantity();
  }
// Deliberate single error: the final class-closing brace is missing.
// Other files provide the repository, model, report, test, resource and Maven build graph.`,
      cpp: `project: inventory-cli

src/main.cpp
src/inventory.cpp
include/inventory.hpp
CMakeLists.txt

int main() {
  Inventory inventory;
  inventory.add("keyboard", 3);
  cout << inventory.count("keyboard") << endl;
}`,
      python: `project: inventory_tool

main.py
inventory/service.py
inventory/model.py
requirements.txt

from inventory.service import InventoryService
service = InventoryService()
service.add("keyboard", 3)
print(service.count("keyboard"))`
    },
    output: `inventory-cj/
  cjpm.toml
  src/
    main.cj
    inventory_service.cj
    model/
      item.cj

// src/main.cj
import inventory_service.InventoryService

main(): Int64 {
  let service = InventoryService()
  service.add("keyboard", 3)
  println(service.count("keyboard"))
  return 0
}`
  },
  ui: {
    note: "UI 网页级请选择 HTML、CSS、JavaScript 等网页文件，可一次选择多个文件，不选择文件夹。",
    strategy: "vision",
    title: "网页 UI 代码",
    samples: {
      web: `<!-- file: index.html -->
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Task Board</title>
  <style>
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: #f4f7fb;
      font-family: Arial, "Microsoft YaHei", sans-serif;
    }
    .board {
      width: min(420px, calc(100vw - 32px));
      padding: 22px;
      border: 1px solid #d8e1ec;
      border-radius: 12px;
      background: #fff;
      box-shadow: 0 18px 50px rgba(20, 35, 60, 0.12);
    }
    h1 { margin: 0 0 14px; font-size: 22px; }
    .row { display: flex; gap: 8px; }
    input {
      flex: 1;
      min-height: 38px;
      padding: 0 10px;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
    }
    button {
      min-height: 38px;
      padding: 0 14px;
      border: 0;
      border-radius: 8px;
      color: #fff;
      background: #0f766e;
      font-weight: 700;
      cursor: pointer;
    }
    ul { display: grid; gap: 8px; margin: 16px 0 0; padding: 0; list-style: none; }
    li { padding: 10px 12px; border-radius: 8px; background: #ecfdf5; color: #134e4a; }
  </style>
</head>
<body>
  <main class="board">
    <h1>Task Board</h1>
    <div class="row">
      <input id="taskInput" placeholder="输入任务" />
      <button id="addBtn">添加</button>
    </div>
    <ul id="taskList"></ul>
  </main>
  <script>
    const input = document.querySelector("#taskInput");
    const list = document.querySelector("#taskList");
    document.querySelector("#addBtn").addEventListener("click", () => {
      const text = input.value.trim();
      if (!text) return;
      const item = document.createElement("li");
      item.textContent = text;
      list.appendChild(item);
      input.value = "";
    });
  </script>
</body>
</html>`,
      java: `// Swing UI
JFrame frame = new JFrame("Login");
JTextField userInput = new JTextField();
JPasswordField passwordInput = new JPasswordField();
JButton submit = new JButton("Sign in");
submit.addActionListener(e -> login(userInput.getText()));
frame.add(userInput);
frame.add(passwordInput);
frame.add(submit);`,
      cpp: `// Qt UI
QWidget window;
QLineEdit* userInput = new QLineEdit();
QLineEdit* passwordInput = new QLineEdit();
QPushButton* submit = new QPushButton("Sign in");
QObject::connect(submit, &QPushButton::clicked, [&]() {
  login(userInput->text());
});`,
      python: `# Tkinter UI
root = Tk()
user_input = Entry(root)
password_input = Entry(root, show="*")
submit = Button(root, text="Sign in", command=lambda: login(user_input.get()))
user_input.pack()
password_input.pack()
submit.pack()`
    },
    output: `// migration_plan
// Use Cangjie as the application runtime and serve the original web UI as static assets.

// file: cjpm.toml
[package]
  name = "migrated_web_ui"
  version = "1.0.0"

// file: src/main.cj
// Start a Cangjie HTTP service, serve static/index.html, static/styles.css, and static/app.js.
// Browser-side DOM interactions are preserved so the page design and behavior remain unchanged.

// file: static/index.html
// Original HTML structure is preserved.

// verifier_report
// Run: cjpm run
// Open: http://127.0.0.1:8080`
  }
};

const uiMigrationExamples = [
  {
    id: "task-board",
    title: "任务看板",
    summary: "输入任务并追加到列表，测试 DOM 创建和按钮点击事件。",
    source: moduleData.ui.samples.web
  },
  {
    id: "login-form",
    title: "登录表单",
    summary: "校验账号密码并显示状态，测试表单输入、错误提示和状态切换。",
    source: `<!-- file: index.html -->
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Login Panel</title>
  <style>
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: #eef4f8;
      font-family: Arial, "Microsoft YaHei", sans-serif;
    }
    .login {
      width: min(360px, calc(100vw - 32px));
      padding: 24px;
      border: 1px solid #d7e0ea;
      border-radius: 12px;
      background: #ffffff;
      box-shadow: 0 18px 50px rgba(15, 35, 55, 0.12);
    }
    h1 { margin: 0 0 16px; font-size: 22px; color: #17212f; }
    label { display: grid; gap: 6px; margin-bottom: 12px; color: #475569; font-weight: 700; }
    input {
      min-height: 40px;
      padding: 0 12px;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      font: inherit;
    }
    button {
      width: 100%;
      min-height: 42px;
      border: 0;
      border-radius: 8px;
      color: #ffffff;
      background: #2563eb;
      font-weight: 800;
      cursor: pointer;
    }
    #status { min-height: 22px; margin: 12px 0 0; color: #b45309; font-weight: 700; }
    #status.ok { color: #15803d; }
  </style>
</head>
<body>
  <main class="login">
    <h1>Account Login</h1>
    <label>Username <input id="username" placeholder="admin" /></label>
    <label>Password <input id="password" type="password" placeholder="123456" /></label>
    <button id="loginBtn">Sign in</button>
    <p id="status"></p>
  </main>
  <script>
    const statusText = document.querySelector("#status");
    document.querySelector("#loginBtn").addEventListener("click", () => {
      const username = document.querySelector("#username").value.trim();
      const password = document.querySelector("#password").value.trim();
      if (!username || !password) {
        statusText.className = "";
        statusText.textContent = "Please enter username and password.";
        return;
      }
      statusText.className = "ok";
      statusText.textContent = "Welcome, " + username + "!";
    });
  </script>
</body>
</html>`
  },
  {
    id: "filter-list",
    title: "筛选列表",
    summary: "输入关键词过滤卡片，测试实时 input 事件和列表显示隐藏。",
    source: `<!-- file: index.html -->
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Course Filter</title>
  <style>
    body {
      margin: 0;
      min-height: 100vh;
      background: #f5f7fb;
      color: #17212f;
      font-family: Arial, "Microsoft YaHei", sans-serif;
    }
    .wrap {
      width: min(720px, calc(100vw - 32px));
      margin: 48px auto;
    }
    .top {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 16px;
    }
    h1 { margin: 0; font-size: 24px; }
    input {
      width: min(280px, 100%);
      min-height: 40px;
      padding: 0 12px;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      font: inherit;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    .course {
      padding: 16px;
      border: 1px solid #d8e1ec;
      border-radius: 10px;
      background: #ffffff;
    }
    .course strong { display: block; margin-bottom: 6px; }
    .course span { color: #657282; font-size: 13px; }
    .hidden { display: none; }
    @media (max-width: 620px) {
      .top { align-items: stretch; flex-direction: column; }
      input { width: 100%; }
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main class="wrap">
    <div class="top">
      <h1>Course Filter</h1>
      <input id="keyword" placeholder="Search course..." />
    </div>
    <section class="grid" id="courseGrid">
      <article class="course" data-name="Java Migration"><strong>Java Migration</strong><span>Code translation</span></article>
      <article class="course" data-name="UI Migration"><strong>UI Migration</strong><span>HTML CSS JS</span></article>
      <article class="course" data-name="Agent Workflow"><strong>Agent Workflow</strong><span>Project migration</span></article>
    </section>
  </main>
  <script>
    const keyword = document.querySelector("#keyword");
    const courses = Array.from(document.querySelectorAll(".course"));
    keyword.addEventListener("input", () => {
      const value = keyword.value.trim().toLowerCase();
      courses.forEach((item) => {
        const name = item.dataset.name.toLowerCase();
        item.classList.toggle("hidden", value && !name.includes(value));
      });
    });
  </script>
</body>
</html>`
  }
];

moduleData.project.projectFiles = moduleData.snippet.projectFiles;

const flowData = {
  snippet: [
    ["语法解析", "抽取函数、类和控制流上下文。"],
    ["模型翻译", "调用片段级 Java 到仓颉翻译模型。"],
    ["仓颉校验", "执行格式修复、类型检查和语法回传。"],
    ["结果输出", "生成可复制的仓颉代码片段。"]
  ],
  project: [
    ["读取项目", "识别源码、配置文件和目录结构。"],
    ["依赖分析", "在本地分析导入和跨文件符号。"],
    ["整项目翻译", "一次输入完整的小型项目，统一生成仓颉项目。"],
    ["构建打包", "检查生成工程并制作下载 ZIP。"]
  ],
  ui: [
    ["网页解析", "解析 HTML、CSS、JavaScript 与资源引用。"],
    ["保真迁移", "保留 DOM 结构、样式规则和浏览器端交互。"],
    ["仓颉运行时", "生成仓颉 Web 托管项目和静态资源映射。"],
    ["运行检查", "输出启动命令、访问地址和功能验证清单。"]
  ]
};

const navItems = document.querySelectorAll(".nav-item");
const views = document.querySelectorAll(".view");
const homeActions = document.querySelectorAll("[data-home-target]");
const segments = document.querySelectorAll(".segment");
const sourceLang = document.getElementById("sourceLang");
const languageDetection = document.getElementById("languageDetection");
const languageDetectionTitle = document.getElementById("languageDetectionTitle");
const languageDetectionCopy = document.getElementById("languageDetectionCopy");
const switchDetectedLanguageBtn = document.getElementById("switchDetectedLanguageBtn");
const strategy = document.getElementById("strategy");
const sourceTitle = document.getElementById("sourceTitle");
const sourceCode = document.getElementById("sourceCode");
const targetCode = document.getElementById("targetCode");
const projectResult = document.getElementById("projectResult");
const projectResultSummary = document.getElementById("projectResultSummary");
const downloadProjectBtn = document.getElementById("downloadProjectBtn");
const projectDownloadStatus = document.getElementById("projectDownloadStatus");
const moduleNote = document.getElementById("moduleNote");
const pipelineList = document.getElementById("pipelineList");
const runState = document.getElementById("runState");
const translateBtn = document.getElementById("translateBtn");
const evaluateBtn = document.getElementById("evaluateBtn");
const modelEvaluateBtn = null;
const sampleBtn = document.getElementById("sampleBtn");
const clearBtn = document.getElementById("clearBtn");
const copyBtn = document.getElementById("copyBtn");
const uploadBtn = document.getElementById("uploadBtn");
const uploadBtnText = document.getElementById("uploadBtnText");
const importHint = document.getElementById("importHint");
const importDialog = document.getElementById("importDialog");
const importDialogTitle = document.getElementById("importDialogTitle");
const importDialogBody = document.getElementById("importDialogBody");
const importConfirmBtn = document.getElementById("importConfirmBtn");
const importCancelBtn = document.getElementById("importCancelBtn");
const fileInput = document.getElementById("fileInput");
const healthBtn = document.getElementById("healthBtn");
const backendStatus = document.getElementById("backendStatus");
const backendDot = document.getElementById("backendDot");
const backendWidgetStatus = document.getElementById("backendWidgetStatus");
const pageTitle = document.getElementById("pageTitle");
const pageCrumb = document.getElementById("pageCrumb");
const workbenchTabs = document.querySelectorAll(".w-tab-input");
const exampleStrip = document.getElementById("exampleStrip");
const exampleSelect = document.getElementById("exampleSelect");
const exampleMeta = document.getElementById("exampleMeta");
const prevExampleBtn = document.getElementById("prevExampleBtn");
const nextExampleBtn = document.getElementById("nextExampleBtn");
const randomExampleBtn = document.getElementById("randomExampleBtn");
const referenceExampleBtn = document.getElementById("referenceExampleBtn");
const chatMessages = document.getElementById("chatMessages");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const chatSendBtn = document.getElementById("chatSendBtn");
const chatStopBtn = document.getElementById("chatStopBtn");
const clearChatBtn = document.getElementById("clearChatBtn");
const chatInputCount = document.getElementById("chatInputCount");
const chatSessionMeta = document.getElementById("chatSessionMeta");
const chatConnectionStatus = document.getElementById("chatConnectionStatus");
const chatWelcome = document.getElementById("chatWelcome");
const quickPromptBtns = document.querySelectorAll(".quick-prompts [data-prompt]");
const chatContextModule = document.getElementById("chatContextModule");
const chatContextStrategy = document.getElementById("chatContextStrategy");
const chatContextLang = document.getElementById("chatContextLang");
const chatContextSize = document.getElementById("chatContextSize");
const chatContextOutput = document.getElementById("chatContextOutput");
const historyCountBadge = document.getElementById("historyCountBadge");
const refreshHistoryBtn = document.getElementById("refreshHistoryBtn");
const historySearch = document.getElementById("historySearch");
const historyModuleFilter = document.getElementById("historyModuleFilter");
const historyStatusFilter = document.getElementById("historyStatusFilter");
const historyList = document.getElementById("historyList");
const historyDetail = document.getElementById("historyDetail");
const historyResultCount = document.getElementById("historyResultCount");
const historyStatTotal = document.getElementById("historyStatTotal");
const historyStatSuccess = document.getElementById("historyStatSuccess");
const historyStatProjects = document.getElementById("historyStatProjects");
const historyStatDuration = document.getElementById("historyStatDuration");
const historySuccessRate = document.getElementById("historySuccessRate");
const historyStatChars = document.getElementById("historyStatChars");
const repairToggle = document.getElementById("repairToggle");
const repairPanel = document.getElementById("repairPanel");
const repairSummary = document.getElementById("repairSummary");
const repairBadge = document.getElementById("repairBadge");
const repairList = document.getElementById("repairList");
const repairAnnotatedSource = document.getElementById("repairAnnotatedSource");
const repairDetails = document.getElementById("repairDetails");
const repairedCode = document.getElementById("repairedCode");
const applyRepairBtn = document.getElementById("applyRepairBtn");
const projectUploadPanel = document.getElementById("projectUploadPanel");
const projectFolderBtn = document.getElementById("projectFolderBtn");
const clearProjectFilesBtn = document.getElementById("clearProjectFilesBtn");
const projectFolderInput = document.getElementById("projectFolderInput");
const projectFileList = document.getElementById("projectFileList");
const projectFileSummary = document.getElementById("projectFileSummary");
const uiExamplePanel = document.getElementById("uiExamplePanel");
const uiExampleSummary = document.getElementById("uiExampleSummary");
const uiExampleBtns = document.querySelectorAll("[data-ui-example]");
const uiUploadPanel = document.getElementById("uiUploadPanel");
const uiFilesBtn = document.getElementById("uiFilesBtn");
const clearUiFilesBtn = document.getElementById("clearUiFilesBtn");
const uiFilesInput = document.getElementById("uiFilesInput");
const uiFileSummary = document.getElementById("uiFileSummary");
const uiFileList = document.getElementById("uiFileList");
const runtimeReport = document.getElementById("runtimeReport");
const runtimeReportStatus = document.getElementById("runtimeReportStatus");
const runtimeReportBody = document.getElementById("runtimeReportBody");

let activeModule = "snippet";
let downloadableProject = null;
let pipelineTimers = [];
let pipelineLitSteps = new Set();
let activeExampleIndex = 0;
let chatHistory = [];
let chatAbortController = null;
let lastChatQuestion = "";
let historyRecords = [];
let activeHistoryId = "";
let historySearchTimer = 0;
let latestRepairedSource = "";
let uploadedProjectFiles = [];
let uploadedUiFiles = [];
let uploadedUiImages = [];
let activeUiExampleId = "task-board";
let detectedSourceLanguage = null;
let languageDetectionTimer = 0;
let pendingImportInput = null;
const API_BASE = window.location.protocol === "file:" ? "http://127.0.0.1:8765" : window.location.origin;
const CHAT_STORAGE_KEY = "cangjie-translator-chat-v2";
const PROJECT_JOB_STORAGE_KEY = "cangjie-active-project-job-v1";
const PROJECT_MAX_FILES = Number.MAX_SAFE_INTEGER;
const PROJECT_MAX_FILE_CHARS = Number.MAX_SAFE_INTEGER;
const PROJECT_MAX_TOTAL_CHARS = Number.MAX_SAFE_INTEGER;
const PROJECT_TEXT_EXTENSIONS = new Set([
  "java", "kt", "kts", "cpp", "cc", "cxx", "c", "h", "hpp", "hh",
  "py", "html", "htm", "css", "js", "ts", "jsx", "tsx", "xml", "json", "yaml", "yml", "toml", "gradle", "properties",
  "md", "txt", "cmake"
]);
const PROJECT_ALWAYS_INCLUDE = new Set([
  "pom.xml", "build.gradle", "settings.gradle", "gradlew", "gradlew.bat",
  "cmakelists.txt", "requirements.txt", "pyproject.toml", "package.json"
]);
const PROJECT_IGNORED_PARTS = new Set([
  ".git", ".idea", ".vscode", "node_modules", "target", "build", "dist",
  "out", ".gradle", "__pycache__", ".pytest_cache", ".mvn", "venv", ".venv"
]);
const moduleLabels = {
  snippet: "片段级",
  project: "项目级",
  ui: "UI 迁移"
};
const SNIPPET_MAX_LINES = 240;
const SNIPPET_MAX_CHARS = 12000;
const SNIPPET_REQUEST_TIMEOUT_MS = 255000;
const UI_REQUEST_TIMEOUT_MS = 15 * 60 * 1000;
const WEB_UI_TEXT_EXTENSIONS = new Set(["html", "htm", "css", "js", "ts", "jsx", "tsx", "json", "xml", "txt"]);
const SNIPPET_ACCEPT = ".java,.cpp,.c,.cc,.cxx,.h,.hpp,.hh,.py,.kt,.kts,.txt,.xml,.json,.toml,.md";
const WEB_UI_MARKER_PATTERN = /<!doctype\s+html|<html\b|<\/html>|<head\b|<body\b|<script\b|<style\b/i;
const SOURCE_LANGUAGE_LABELS = {
  java: "Java",
  cpp: "C / C++",
  python: "Python",
  web: "HTML / CSS / JS"
};

function getActiveData() {
  return moduleData[activeModule];
}

function setView(viewId) {
  if (!document.getElementById(viewId)) return;
  const viewLabels = {
    home: ["首页", "平台总览"],
    workbench: ["翻译工作台", "代码迁移"],
    history: ["翻译记录", "历史任务"],
    assistant: ["迁移助手", "智能问答"]
  };
  const [title, crumb] = viewLabels[viewId] || ["仓颉迁移台", ""];
  pageTitle.textContent = title;
  pageCrumb.textContent = crumb;
  navItems.forEach((item) => {
    const isActive = item.dataset.view === viewId;
    item.classList.toggle("active", isActive);
    if (isActive) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  });
  views.forEach((view) => view.classList.toggle("active", view.id === viewId));
  updateChatContext();
  if (viewId === "history") {
    loadHistoryRecords();
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function renderPipeline(activeIndex = -1, allDone = false) {
  pipelineList.innerHTML = flowData[activeModule]
    .map(([title, desc], index) => {
      const state = allDone ? "done" : index < activeIndex ? "done" : index === activeIndex ? "active" : "pending";
      const marker = state === "done"
        ? '<svg class="pipeline-check" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>'
        : index + 1;
      return `<li class="pipeline-node stage-${state}">
        <span class="pipeline-marker">${marker}</span>
        <div class="pipeline-node-body"><strong>${title}</strong><span>${desc}</span></div>
      </li>`;
    })
    .join("");
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function lightPipelineStep(index, statusText) {
  if (pipelineLitSteps.has(index)) {
    return;
  }
  pipelineLitSteps.add(index);
  renderPipeline(index);
  runState.textContent = statusText || flowData[activeModule][index][0];
}

function clearPipelineProgress() {
  pipelineTimers.forEach((id) => clearTimeout(id));
  pipelineTimers = [];
}

function startPipelineProgress() {
  clearPipelineProgress();
  pipelineLitSteps = new Set();
  lightPipelineStep(0);
  if (activeModule === "project") return;

  const stepCount = flowData[activeModule].length;
  const lastIndex = stepCount - 1;
  const delays = [0, 1200, 3200];

  for (let index = 1; index < lastIndex; index += 1) {
    const delayMs = delays[index] || index * 1200;
    pipelineTimers.push(setTimeout(() => lightPipelineStep(index), delayMs));
  }
}

async function finishPipelineProgress(statusText, allDone = true) {
  clearPipelineProgress();
  const lastIndex = Math.max(flowData[activeModule].length - 1, 0);
  const currentIndex = pipelineLitSteps.size ? Math.max(...pipelineLitSteps) : 0;
  const targetIndex = allDone ? lastIndex : currentIndex;
  for (let index = currentIndex + 1; index <= targetIndex; index += 1) {
    lightPipelineStep(index, index === targetIndex ? statusText : undefined);
    if (index < targetIndex) {
      await delay(220);
    }
  }
  renderPipeline(targetIndex, allDone);
  runState.textContent = statusText;
}

function setBackendStatus(state, text) {
  backendStatus.className = `backend-status ${state}`;
  backendStatus.textContent = text;
  backendDot.className = `status-dot ${state}`;
  backendWidgetStatus.textContent = `后端${text}`;
}

function setTabDot(tabId, visible) {
  const dot = document.querySelector(`#${tabId} + .w-tab-head .tab-dot`);
  if (dot) dot.hidden = !visible;
}

function setRunState(text, state = "") {
  runState.className = `run-state${state ? ` ${state}` : ""}`;
  runState.textContent = text;
}

async function fetchHealthWithRetry() {
  let lastError = new Error("后端未响应");
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 5000);
    try {
      return await fetch(`${API_BASE}/health`, {
        cache: "no-store",
        signal: controller.signal
      });
    } catch (error) {
      lastError = error.name === "AbortError" ? new Error("后端健康检查超时") : error;
      if (attempt < 2) await delay(700 * (attempt + 1));
    } finally {
      window.clearTimeout(timer);
    }
  }
  throw lastError;
}

function resetRuntimeReport() {
  runtimeReport.hidden = true;
  runtimeReportStatus.textContent = "等待运行";
  runtimeReportBody.textContent = "";
  setTabDot("wbtab-report", false);
}

function showRuntimeReport(status, text) {
  runtimeReport.hidden = false;
  runtimeReportStatus.textContent = status;
  runtimeReportBody.textContent = text;
  setTabDot("wbtab-report", true);
}

function evaluationModeLabel(mode) {
  if (mode === "model_translation") return "模型真实翻译评测";
  if (mode === "dataset_lookup") return "本地数据集检索验证";
  return "未知评测模式";
}

function reportValue(value, fallback = "未知") {
  return value === undefined || value === null || value === "" ? fallback : value;
}

function formatEvaluationReport(data) {
  const metrics = data.metrics || {};
  const compiler = data.compiler || {};
  const rows = Array.isArray(data.rows) ? data.rows : [];
  const rowLines = rows.slice(0, 12).map((row, index) => {
    const status = row.success ? "成功" : "失败";
    const exact = row.exact_match ? "完全匹配" : "未完全匹配";
    const error = row.error ? `，错误：${row.error}` : "";
    return `${index + 1}. ${row.case || row.java_file || "未命名样例"}：${status}，${exact}，BLEU ${row.bleu}${error}`;
  });

  return [
    "【数据集评估】",
    `模式：${evaluationModeLabel(data.evaluation_mode)}`,
    `说明：${data.evaluation_mode === "model_translation" ? "逐条调用当前模型翻译后与参考答案比较。" : "不调用模型，只验证本地 Java/Cangjie 参考数据集可读取并计算指标；不能代表模型翻译效果。"}`,
    `数据集：${data.dataset || "未返回"}`,
    `可用样例：${data.total_cases_available || 0}`,
    `本次评估：${data.cases_evaluated || 0}`,
    `翻译成功率：${reportValue(metrics.translation_success_rate)}%`,
    `完全匹配率：${reportValue(metrics.exact_match_rate)}%`,
    `简化 BLEU：${reportValue(metrics.simple_bleu)}`,
    `语法状态：${metrics.syntax_status || compiler.status || "unknown"}`,
    `仓颉编译器：${compiler.compiler_path || compiler.compiler || "未找到"}`,
    "",
    "【样例明细】",
    rowLines.length ? rowLines.join("\n") : "无明细",
    "",
    data.note || ""
  ].filter(Boolean).join("\n");
}

function formatArtifactReport(artifact) {
  if (!artifact) {
    return "";
  }

  const validation = artifact.validation || {};
  const uiChecks = validation.ui_static_checks || {};
  const files = Array.isArray(artifact.files) ? artifact.files : [];
  return [
    "【生成产物】",
    `输出目录：${artifact.output_dir || "未返回"}`,
    artifact.html_preview_url ? `HTML 预览：${artifact.html_preview_url}` : "",
    `写入文件：${files.length}`,
    ...files.slice(0, 20).map((file) => `- ${file}`),
    files.length > 20 ? `- ...其余 ${files.length - 20} 个文件` : "",
    "",
    "【验证状态】",
    `编译器状态：${validation.compiler_status || "unknown"}`,
    `是否完成构建验证：${validation.build_verified ? "是" : "否"}`,
    `原因：${validation.reason || "未返回"}`,
    uiChecks.html_entry_exists !== undefined ? "" : "",
    uiChecks.html_entry_exists !== undefined ? "【UI 静态检查】" : "",
    uiChecks.html_entry_exists !== undefined ? `HTML 入口文件：${uiChecks.html_entry_exists ? "存在" : "缺失"}` : "",
    uiChecks.html_structure_detected !== undefined ? `HTML 结构识别：${uiChecks.html_structure_detected ? "通过" : "未通过"}` : "",
    uiChecks.interactive_markers_detected !== undefined ? `交互标记识别：${uiChecks.interactive_markers_detected ? "发现" : "未发现"}` : "",
    uiChecks.browser_runtime_tested !== undefined ? `浏览器交互自动测试：${uiChecks.browser_runtime_tested ? "已执行" : "未执行"}` : "",
    uiChecks.browser_runtime_reason ? `说明：${uiChecks.browser_runtime_reason}` : ""
  ].filter(Boolean).join("\n");
}

function formatAgentStageReport(stages) {
  if (!Array.isArray(stages) || !stages.length) {
    return "";
  }

  return [
    "【Agent 阶段日志】",
    ...stages.map((stage, index) => [
      `${index + 1}. ${stage.title || stage.name || "未命名阶段"}：${stage.status || "unknown"}`,
      String(stage.content || "").trim()
    ].join("\n"))
  ].join("\n\n");
}

function renderRuntimeReport(data) {
  const parts = [
    formatArtifactReport(data.artifact),
    formatAgentStageReport(data.agent_stages),
    data.compiler ? `【本地仓颉工具链】\n状态：${data.compiler.status}\n编译器：${data.compiler.compiler_path || data.compiler.compiler || "未找到"}\n项目构建：${data.compiler.project_build_path || data.compiler.project_build || "未找到"}` : ""
  ].filter(Boolean);

  if (!parts.length) {
    resetRuntimeReport();
    return;
  }

  showRuntimeReport("翻译报告已生成", parts.join("\n\n"));
}

async function runDatasetEvaluation(useModel = false) {
  evaluateBtn.disabled = true;
  if (modelEvaluateBtn) modelEvaluateBtn.disabled = true;
  showRuntimeReport("评估中", useModel ? "正在调用模型评估数据集样例..." : "正在执行本地参考基线自检...");
  setBackendStatus("idle", "评估中");

  try {
    const response = await fetch(`${API_BASE}/evaluate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        limit: useModel ? 5 : 20,
        use_model: useModel
      })
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }

    showRuntimeReport("评估完成", formatEvaluationReport(data));
    setBackendStatus("ok", "评估完成");
  } catch (error) {
    showRuntimeReport("评估失败", `数据集评估未完成：${error.message}\n\n请确认后端已重启并运行在 ${API_BASE}。`);
    setBackendStatus("fail", "评估失败");
  } finally {
    evaluateBtn.disabled = false;
    if (modelEvaluateBtn) modelEvaluateBtn.disabled = false;
  }
}

function countNonEmptyLines(text) {
  return String(text || "")
    .split(/\r?\n/)
    .filter((line) => line.trim()).length;
}

function detectSnippetLanguageFromFiles(files) {
  const extToLang = {
    java: "java",
    py: "python",
    cpp: "cpp",
    cc: "cpp",
    cxx: "cpp",
    c: "cpp",
    h: "cpp",
    hpp: "cpp",
    hh: "cpp",
    kt: "java",
    kts: "java"
  };

  const counts = {};
  files.forEach((file) => {
    const path = projectFilePath(file).toLowerCase();
    const ext = projectFileExtension(path);
    const lang = extToLang[ext];
    if (lang) {
      counts[lang] = (counts[lang] || 0) + 1;
    }
  });

  if ((counts.python || 0) > (counts.cpp || 0) && (counts.python || 0) > (counts.java || 0)) {
    return "python";
  }
  if ((counts.cpp || 0) > (counts.java || 0)) {
    return "cpp";
  }
  return "java";
}

function validateSnippetSource(text) {
  const lineCount = countNonEmptyLines(text);
  const charCount = String(text || "").length;
  if (lineCount > SNIPPET_MAX_LINES || charCount > SNIPPET_MAX_CHARS) {
    return {
      ok: false,
      message: `片段级翻译要求更短一些，请控制在 ${SNIPPET_MAX_LINES} 行或 ${SNIPPET_MAX_CHARS} 个字符以内。当前为 ${lineCount} 行、${charCount} 个字符。`
    };
  }
  return { ok: true, message: "" };
}

function detectSourceLanguage(code) {
  const text = String(code || "").trim();
  if (text.length < 8) {
    return null;
  }

  const scores = { java: 0, cpp: 0, python: 0, web: 0 };
  const add = (language, pattern, score) => {
    if (pattern.test(text)) scores[language] += score;
  };

  add("python", /^\s*(?:async\s+)?def\s+\w+\s*\([^)]*\)\s*:/m, 7);
  add("python", /^\s*class\s+\w+(?:\([^)]*\))?\s*:/m, 6);
  add("python", /^\s*(?:from\s+[\w.]+\s+import|import\s+[\w.]+)/m, 4);
  add("python", /^\s*(?:if|elif|else|for|while|try|except|with)\b.*:\s*$/m, 3);
  add("python", /^\s*print\s*\(/m, 4);
  add("python", /\b(?:None|True|False|self)\b/, 2);
  add("python", /(?:^|[^\w])f["'][^"']*\{[^}]+\}/m, 2);

  add("java", /\bpublic\s+static\s+void\s+main\s*\(/, 7);
  add("java", /\b(?:public|private|protected)\s+(?:static\s+)?(?:class|interface|enum|void|boolean|byte|short|int|long|float|double|char|String)\b/, 6);
  add("java", /\bclass\s+[A-Z]\w*[^\n{]*\{/, 5);
  add("java", /\b(?:System\.out\.|package\s+[\w.]+\s*;|import\s+java\.)/, 5);
  add("java", /@(?:Override|Deprecated|SuppressWarnings)\b/, 3);
  add("java", /\bnew\s+[A-Z]\w*\s*\(/, 2);

  add("cpp", /^\s*#\s*include\s*[<"]/m, 7);
  add("cpp", /\b(?:std::|using\s+namespace\s+std|cout\s*<<|cin\s*>>)/, 6);
  add("cpp", /\b(?:int|void|char|float|double)\s+main\s*\(/, 5);
  add("cpp", /\b(?:printf|scanf|malloc|calloc|realloc|free)\s*\(/, 4);
  add("cpp", /\b(?:vector|string|map|unordered_map|unique_ptr|shared_ptr)\s*</, 3);
  add("cpp", /(?:->|\bnullptr\b|\bsize_t\b)/, 2);

  add("web", /<!doctype\s+html|<html\b|<head\b|<body\b|<script\b|<style\b/i, 8);
  add("web", /<(?:div|main|section|header|footer|nav|button|input|form)\b[^>]*>/i, 6);
  add("web", /<\/[a-z][^>]*>/i, 3);
  add("web", /\b(?:document\.|window\.|querySelector\s*\(|addEventListener\s*\()/, 5);
  add("web", /\b(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=.*;/, 2);
  add("web", /\bconsole\.log\s*\(/, 3);
  add("web", /(?:^|\})\s*[.#][\w-]+\s*\{[^}]*:[^}]*\}/m, 6);

  const ranked = Object.entries(scores).sort((left, right) => right[1] - left[1]);
  const [bestLanguage, bestScore] = ranked[0];
  const secondScore = ranked[1][1];
  if (bestScore < 4 || bestScore - secondScore < 2) {
    return null;
  }

  return {
    value: bestLanguage,
    label: SOURCE_LANGUAGE_LABELS[bestLanguage],
    score: bestScore
  };
}

function hideLanguageDetection() {
  languageDetection.hidden = true;
}

function updateLanguageDetection() {
  window.clearTimeout(languageDetectionTimer);
  if (activeModule !== "snippet") {
    detectedSourceLanguage = null;
    hideLanguageDetection();
    return null;
  }

  detectedSourceLanguage = detectSourceLanguage(sourceCode.value);
  if (!detectedSourceLanguage || detectedSourceLanguage.value === sourceLang.value) {
    hideLanguageDetection();
    return null;
  }

  const selectedLabel = SOURCE_LANGUAGE_LABELS[sourceLang.value]
    || sourceLang.options[sourceLang.selectedIndex]?.text
    || sourceLang.value;
  languageDetectionTitle.textContent = `检测到可能是 ${detectedSourceLanguage.label} 代码`;
  languageDetectionCopy.textContent = `当前选择为 ${selectedLabel}，继续翻译可能产生错误，请重新选择源语言。`;
  switchDetectedLanguageBtn.textContent = `切换为 ${detectedSourceLanguage.label}`;
  languageDetection.hidden = false;
  return detectedSourceLanguage;
}

function scheduleLanguageDetection() {
  window.clearTimeout(languageDetectionTimer);
  languageDetectionTimer = window.setTimeout(updateLanguageDetection, 280);
}

function applyDetectedSourceLanguage() {
  if (!detectedSourceLanguage) {
    return;
  }
  const language = detectedSourceLanguage;
  sourceLang.value = language.value;
  updateLocalImportControls();
  resetRepairReport();
  resetRuntimeReport();
  updateChatContext();
  updateLanguageDetection();
  setRunState(`已切换为 ${language.label}`, "busy");
  sourceCode.focus();
}

function validateWebUiSource(text, sourceLangValue, projectFiles = []) {
  const source = String(text || "");
  if (String(sourceLangValue || "").toLowerCase() !== "web") {
    return {
      ok: false,
      message: "UI 迁移请先把源语言切换为 HTML/CSS/JS。"
    };
  }
  const hasHtmlMarker = WEB_UI_MARKER_PATTERN.test(source);
  const hasHtmlFile = Array.isArray(projectFiles) && projectFiles.some((file) => {
    const path = String((file && (file.path || file.name)) || "").toLowerCase();
    return path.endsWith(".html") || path.endsWith(".htm");
  });

  if (!hasHtmlMarker && !hasHtmlFile && !uploadedUiImages.length) {
    return {
      ok: false,
      message: "UI 迁移只接受网页代码，请导入 HTML/CSS/JS 文件，或确保内容包含 HTML 结构。"
    };
  }

  return { ok: true, message: "" };
}

function updateLocalImportControls() {
  if (activeModule === "snippet") {
    uploadBtn.title = "导入 1 个代码文件";
    uploadBtn.setAttribute("aria-label", "导入 1 个代码文件");
    uploadBtnText.textContent = "导入文件";
    importHint.textContent = `片段级：请选择 1 个源代码文件，建议不超过 ${SNIPPET_MAX_LINES} 行或 ${SNIPPET_MAX_CHARS} 字符。`;
    fileInput.accept = SNIPPET_ACCEPT;
    return;
  }

  if (activeModule === "ui") {
    uploadBtn.title = "导入网页文件";
    uploadBtn.setAttribute("aria-label", "导入网页文件");
    uploadBtnText.textContent = "导入网页文件";
    importHint.textContent = "UI 网页级：请选择 HTML、CSS、JavaScript 等网页文件，可一次选择多个文件；不要选择文件夹。";
    return;
  }

  uploadBtn.title = "导入项目文件夹";
  uploadBtn.setAttribute("aria-label", "导入项目文件夹");
  uploadBtnText.textContent = "导入文件夹";
  importHint.textContent = "项目级：请选择 1 个项目文件夹，翻译完成后点击下载 ZIP 并保存到本地。";
}

function requestImport(input) {
  updateLocalImportControls();
  const guidance = activeModule === "snippet"
    ? ["导入片段级代码文件", `下一步请选择 1 个 Java、Python 或 C/C++ 等源代码文件。建议不超过 ${SNIPPET_MAX_LINES} 行或 ${SNIPPET_MAX_CHARS} 字符。`]
    : activeModule === "project"
    ? ["导入项目文件夹", "下一步请选择 1 个完整的项目文件夹，不要只选择其中某个源码文件。系统会读取其中支持的源码和配置文件；翻译完成后，输出区显示下载按钮，将生成项目保存为一个 ZIP 文件。"]
    : ["导入 UI 网页文件", "下一步请选择 HTML、CSS、JavaScript 等网页文件，可一次选择多个文件。此模式不选择文件夹，建议包含 HTML 入口文件。"];
  importDialogTitle.textContent = guidance[0];
  importDialogBody.textContent = guidance[1];
  importConfirmBtn.textContent = activeModule === "project" ? "选择文件夹" : "选择文件";
  pendingImportInput = input;
  if (typeof importDialog.showModal === "function") {
    importDialog.showModal();
  } else if (window.confirm(`${guidance[0]}\n\n${guidance[1]}`)) {
    pendingImportInput = null;
    input.click();
  } else {
    pendingImportInput = null;
  }
}

function resetRepairReport() {
  latestRepairedSource = "";
  repairPanel.hidden = true;
  repairSummary.textContent = "等待运行翻译";
  repairBadge.className = "repair-badge idle";
  repairBadge.textContent = "未检测";
  repairList.innerHTML = "";
  repairAnnotatedSource.innerHTML = "";
  repairedCode.textContent = "";
  repairDetails.open = false;
  applyRepairBtn.disabled = true;
  setTabDot("wbtab-repair", false);
}

function setRepairBadge(state, text) {
  repairBadge.className = `repair-badge ${state}`;
  repairBadge.textContent = text;
  setTabDot("wbtab-repair", state !== "idle");
}

function projectFilePath(file) {
  return (file.webkitRelativePath || file.name || "unknown").replace(/\\/g, "/");
}

function uploadedProjectRelativePath(file) {
  const path = projectFilePath(file);
  // Folder selection includes the selected folder's name; the project root must not.
  return file.webkitRelativePath ? path.split("/").slice(1).join("/") || file.name : path;
}

function projectFileExtension(path) {
  const fileName = path.split("/").pop() || "";
  const dotIndex = fileName.lastIndexOf(".");
  return dotIndex >= 0 ? fileName.slice(dotIndex + 1).toLowerCase() : fileName.toLowerCase();
}

function projectFileLanguage(path) {
  const ext = projectFileExtension(path);
  const map = {
    java: "Java",
    kt: "Kotlin",
    kts: "Kotlin",
    cpp: "C++",
    cc: "C++",
    cxx: "C++",
    c: "C",
    h: "C/C++ Header",
    hpp: "C++ Header",
    hh: "C++ Header",
    py: "Python",
    html: "HTML",
    htm: "HTML",
    css: "CSS",
    js: "JavaScript",
    ts: "TypeScript",
    jsx: "React JSX",
    tsx: "React TSX",
    xml: "XML",
    json: "JSON",
    yaml: "YAML",
    yml: "YAML",
    toml: "TOML",
    gradle: "Gradle",
    properties: "Properties",
    cmake: "CMake",
    md: "Markdown",
    txt: "Text"
  };
  return map[ext] || "Text";
}

function shouldIncludeProjectFile(file) {
  const path = projectFilePath(file);
  const parts = path.split("/").map((part) => part.toLowerCase());
  if (parts.some((part) => PROJECT_IGNORED_PARTS.has(part))) {
    return false;
  }

  const fileName = parts[parts.length - 1] || "";
  const ext = projectFileExtension(path);
  if (PROJECT_ALWAYS_INCLUDE.has(fileName)) {
    return true;
  }
  if (!PROJECT_TEXT_EXTENSIONS.has(ext)) {
    return false;
  }
  return file.size <= 512 * 1024;
}

function shouldIncludeUiFile(file) {
  const path = projectFilePath(file);
  const parts = path.split("/").map((part) => part.toLowerCase());
  if (parts.some((part) => PROJECT_IGNORED_PARTS.has(part))) {
    return false;
  }
  return file.type.startsWith("image/") || (WEB_UI_TEXT_EXTENSIONS.has(projectFileExtension(path)) && file.size <= 512 * 1024);
}

function formatProjectSource(files, skippedCount = 0) {
  const totalLines = files.reduce((sum, file) => sum + file.lines, 0);
  const header = [
    "project: uploaded-local-project",
    `// uploaded_files: ${files.length}`,
    `// skipped_files: ${skippedCount}`,
    `// total_source_lines: ${totalLines}`,
    "// source format: each file is separated by a file boundary for project-level multi-agent migration"
  ].join("\n");

  const body = files.map((file) => {
    const truncated = file.truncated ? "\n// note: file content truncated before sending to model" : "";
    return [
      `// file: ${file.path}`,
      `// language: ${file.language}`,
      "```",
      file.content,
      `\`\`\`${truncated}`
    ].join("\n");
  }).join("\n\n");

  return `${header}\n\n${body}`;
}

function renderProjectFiles() {
  projectFileList.innerHTML = "";
  if (!uploadedProjectFiles.length) {
    projectFileSummary.textContent = "请选择 1 个项目文件夹，系统会读取其中支持的源码和配置文件";
    return;
  }

  const totalLines = uploadedProjectFiles.reduce((sum, file) => sum + file.lines, 0);
  projectFileSummary.textContent = `已载入 ${uploadedProjectFiles.length} 个项目文件，合计 ${totalLines} 行；默认整项目翻译，也可选择逐文件策略`;

  uploadedProjectFiles.slice(0, 30).forEach((file) => {
    const item = document.createElement("div");
    item.className = "project-file-item";

    const main = document.createElement("div");
    const path = document.createElement("strong");
    path.textContent = file.path;
    const meta = document.createElement("span");
    meta.textContent = `${file.language} · ${file.lines} 行${file.truncated ? " · 已截断" : ""}`;
    main.append(path, meta);

    const size = document.createElement("span");
    size.className = "project-file-meta";
    size.textContent = `${Math.ceil(file.originalSize / 1024)} KB`;

    item.append(main, size);
    projectFileList.appendChild(item);
  });

  if (uploadedProjectFiles.length > 30) {
    const item = document.createElement("div");
    item.className = "project-file-item";
    item.textContent = `还有 ${uploadedProjectFiles.length - 30} 个文件已载入，未在清单中展开显示。`;
    projectFileList.appendChild(item);
  }
}

function clearProjectUpload() {
  resetProjectResult();
  localStorage.removeItem(PROJECT_JOB_STORAGE_KEY);
  uploadedProjectFiles = [];
  renderProjectFiles();
}

function renderUiFiles() {
  uiFileList.innerHTML = "";
  if (!uploadedUiFiles.length && !uploadedUiImages.length) {
    uiFileSummary.textContent = "请选择 HTML、CSS、JavaScript 等网页文件，可一次选择多个文件";
    return;
  }

  const allFiles = [...uploadedUiFiles, ...uploadedUiImages.map((image) => ({
    path: image.name,
    language: "图片",
    lines: 0,
    originalSize: Math.ceil(image.data_url.length * 0.75)
  }))];
  const totalLines = uploadedUiFiles.reduce((sum, file) => sum + file.lines, 0);
  uiFileSummary.textContent = `已载入 ${allFiles.length} 个网页文件，合计 ${totalLines} 行；所选文件名将发送给 UI 迁移模块`;

  allFiles.slice(0, 30).forEach((file) => {
    const item = document.createElement("div");
    item.className = "project-file-item";
    const main = document.createElement("div");
    const path = document.createElement("strong");
    path.textContent = file.path;
    const meta = document.createElement("span");
    meta.textContent = `${file.language} · ${file.lines || 0} 行`;
    main.append(path, meta);
    const size = document.createElement("span");
    size.className = "project-file-meta";
    size.textContent = `${Math.ceil((file.originalSize || 0) / 1024)} KB`;
    item.append(main, size);
    uiFileList.appendChild(item);
  });
}

function clearUiUpload() {
  uploadedUiFiles = [];
  uploadedUiImages = [];
  renderUiFiles();
}

function repairIssueLineRange(issue) {
  const start = Number(issue.line_start || issue.line || 0);
  const end = Number(issue.line_end || issue.line_start || issue.line || start);
  if (!Number.isFinite(start) || start <= 0) {
    return "位置待确认";
  }
  if (Number.isFinite(end) && end > start) {
    return `第 ${start}-${end} 行`;
  }
  return `第 ${start} 行`;
}

function repairIssueLineSet(issues) {
  const lineSet = new Set();
  issues.forEach((issue) => {
    const start = Number(issue.line_start || issue.line || 0);
    const end = Number(issue.line_end || issue.line_start || issue.line || start);
    if (!Number.isFinite(start) || start <= 0) {
      return;
    }
    const safeEnd = Number.isFinite(end) && end >= start ? Math.min(end, start + 30) : start;
    for (let line = start; line <= safeEnd; line += 1) {
      lineSet.add(line);
    }
  });
  return lineSet;
}

function renderAnnotatedSource(sourceText, issues) {
  repairAnnotatedSource.innerHTML = "";
  const lines = sourceText.split(/\r?\n/);
  const issueLines = repairIssueLineSet(issues);

  lines.forEach((line, index) => {
    const row = document.createElement("div");
    const lineNumber = index + 1;
    row.className = `annotated-line${issueLines.has(lineNumber) ? " issue" : ""}`;

    const number = document.createElement("span");
    number.className = "annotated-number";
    number.textContent = String(lineNumber);

    const text = document.createElement("span");
    text.className = "annotated-text";
    text.textContent = line || " ";

    row.append(number, text);
    repairAnnotatedSource.appendChild(row);
  });
}

function appendRepairIssue(issue) {
  const item = document.createElement("li");

  const location = document.createElement("span");
  location.className = "repair-location";
  location.textContent = `${issue.source_file ? `${issue.source_file} · ` : ""}${repairIssueLineRange(issue)}`;

  const detail = document.createElement("div");

  const title = document.createElement("strong");
  const type = issue.type || "代码问题";
  const severity = issue.severity ? ` / ${issue.severity}` : "";
  title.textContent = `${type}${severity}`;

  const explanation = document.createElement("span");
  explanation.textContent = issue.explanation || issue.reason || "模型识别到这里可能存在语法错误或上下文不完整。";

  detail.append(title, explanation);

  if (issue.original) {
    const original = document.createElement("code");
    original.textContent = `原片段：${issue.original}`;
    detail.appendChild(original);
  }

  if (issue.repair || issue.fix) {
    const repair = document.createElement("code");
    repair.textContent = `修复建议：${issue.repair || issue.fix}`;
    detail.appendChild(repair);
  }

  item.append(location, detail);
  repairList.appendChild(item);
}

function renderRepairReport(repair, originalSource) {
  if (!repair || !repair.enabled) {
    resetRepairReport();
    return;
  }

  repairPanel.hidden = false;
  repairList.innerHTML = "";
  const issues = Array.isArray(repair.issues) ? repair.issues : [];
  const usedForTranslation = Boolean(repair.used_for_translation);
  latestRepairedSource = repair.repaired_code || "";
  repairedCode.textContent = latestRepairedSource || originalSource;
  applyRepairBtn.disabled = !latestRepairedSource || latestRepairedSource === originalSource;
  renderAnnotatedSource(originalSource, issues);

  if (repair.error) {
    setRepairBadge("fail", "诊断异常");
    repairSummary.textContent = `诊断或翻译流程未正常完成：${repair.error}`;
    appendRepairIssue({
      type: "流程异常",
      severity: "warning",
      explanation: repair.error
    });
    return;
  }

  if (repair.needs_repair || issues.length) {
    setRepairBadge("warn", usedForTranslation ? "已修复" : "需检查");
    repairSummary.textContent = repair.repair_mode === "report_only"
      ? `逐文件本地检查发现 ${issues.length || 1} 处问题；未调用模型重写项目文件。`
      : usedForTranslation
      ? `发现 ${issues.length || 1} 处错误或不完整位置，已使用修复后的代码继续翻译。`
      : `发现 ${issues.length || 1} 处疑似问题，请检查标注位置。`;
    if (issues.length) {
      issues.forEach(appendRepairIssue);
    } else {
      appendRepairIssue({
        type: "代码不完整或语法错误",
        severity: "warning",
        explanation: "模型返回了修复后的代码，但没有给出精确行号，请对照修复前后版本检查。"
      });
    }
    return;
  }

  setRepairBadge("ok", "通过");
  repairSummary.textContent = "未发现明显语法错误或不完整片段，已按原始代码翻译。";
}

function selectedOptionText(selectElement) {
  if (!selectElement || selectElement.selectedIndex < 0) {
    return "";
  }
  return selectElement.options[selectElement.selectedIndex].textContent.trim();
}

function getActiveDatasetExample() {
  if (activeModule !== "snippet" || !datasetExamples.length) {
    return null;
  }
  return datasetExamples[activeExampleIndex] || null;
}

function updateChatContext() {
  if (!chatContextModule) {
    return;
  }

  const nonEmptyLines = sourceCode.value
    .split(/\r?\n/)
    .filter((line) => line.trim()).length;
  const outputLines = targetCode.textContent
    .split(/\r?\n/)
    .filter((line) => line.trim() && !line.trim().startsWith("// 点击")).length;

  chatContextModule.textContent = moduleLabels[activeModule] || activeModule;
  chatContextStrategy.textContent = selectedOptionText(strategy) || strategy.value;
  chatContextLang.textContent = selectedOptionText(sourceLang) || sourceLang.value;
  chatContextSize.textContent = activeModule === "project" && uploadedProjectFiles.length
    ? `${uploadedProjectFiles.length} 个文件 · ${nonEmptyLines} 行预览`
    : `${nonEmptyLines} 行源代码`;
  chatContextOutput.textContent = outputLines > 0 ? `${outputLines} 行可供分析` : "尚未生成";
}

function appendInlineChatText(container, text) {
  const value = String(text || "");
  const tokenPattern = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let cursor = 0;
  let match;
  while ((match = tokenPattern.exec(value)) !== null) {
    if (match.index > cursor) {
      container.appendChild(document.createTextNode(value.slice(cursor, match.index)));
    }
    if (match[0].startsWith("**")) {
      const strong = document.createElement("strong");
      strong.textContent = match[0].slice(2, -2);
      container.appendChild(strong);
    } else {
      const code = document.createElement("code");
      code.textContent = match[0].slice(1, -1);
      container.appendChild(code);
    }
    cursor = tokenPattern.lastIndex;
  }
  if (cursor < value.length) {
    container.appendChild(document.createTextNode(value.slice(cursor)));
  }
}

function markdownTableCells(line) {
  const source = line.trim().replace(/^\||\|$/g, "");
  const cells = [];
  let current = "";
  let inCode = false;
  for (let index = 0; index < source.length; index += 1) {
    const char = source[index];
    if (char === "\\" && source[index + 1] === "|") {
      current += "|";
      index += 1;
    } else if (char === "`") {
      inCode = !inCode;
      current += char;
    } else if (char === "|" && !inCode) {
      cells.push(current.trim());
      current = "";
    } else {
      current += char;
    }
  }
  cells.push(current.trim());
  return cells;
}

function appendPlainChatText(container, text) {
  const lines = String(text || "").split("\n");
  let list = null;
  let listType = "";

  const closeList = () => {
    list = null;
    listType = "";
  };

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const bullet = line.match(/^\s*[-*]\s+(.+)/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.+)/);
    const heading = line.match(/^\s*(#{1,6})\s+(.+)/);
    const isTable = /^\s*\|.+\|\s*$/.test(line)
      && index + 1 < lines.length
      && /^\s*\|(?:\s*:?-{3,}:?\s*\|)+\s*$/.test(lines[index + 1]);
    if (isTable) {
      closeList();
      const tableWrap = document.createElement("div");
      tableWrap.className = "chat-table-wrap";
      const table = document.createElement("table");
      const head = document.createElement("thead");
      const headRow = document.createElement("tr");
      markdownTableCells(line).forEach((cell) => {
        const th = document.createElement("th");
        appendInlineChatText(th, cell);
        headRow.appendChild(th);
      });
      head.appendChild(headRow);
      table.appendChild(head);
      index += 2;
      const body = document.createElement("tbody");
      while (index < lines.length && /^\s*\|.+\|\s*$/.test(lines[index])) {
        const row = document.createElement("tr");
        markdownTableCells(lines[index]).forEach((cell) => {
          const td = document.createElement("td");
          appendInlineChatText(td, cell);
          row.appendChild(td);
        });
        body.appendChild(row);
        index += 1;
      }
      index -= 1;
      table.appendChild(body);
      tableWrap.appendChild(table);
      container.appendChild(tableWrap);
      continue;
    }
    if (bullet || numbered) {
      const nextType = bullet ? "ul" : "ol";
      if (!list || listType !== nextType) {
        list = document.createElement(nextType);
        listType = nextType;
        container.appendChild(list);
      }
      const item = document.createElement("li");
      appendInlineChatText(item, (bullet || numbered)[1]);
      list.appendChild(item);
      continue;
    }

    closeList();
    if (heading) {
      const title = document.createElement(heading[1].length >= 3 ? "h4" : "h3");
      appendInlineChatText(title, heading[2]);
      container.appendChild(title);
      continue;
    }
    if (!line.trim()) {
      const spacer = document.createElement("span");
      spacer.className = "chat-line-break";
      container.appendChild(spacer);
      continue;
    }
    const paragraph = document.createElement("p");
    appendInlineChatText(paragraph, line);
    container.appendChild(paragraph);
  }
}

function renderChatText(container, text) {
  container.replaceChildren();
  const value = String(text || "");
  const fencePattern = /```([^\n`]*)\n?([\s\S]*?)```/g;
  let cursor = 0;
  let match;
  while ((match = fencePattern.exec(value)) !== null) {
    appendPlainChatText(container, value.slice(cursor, match.index));
    const codeWrap = document.createElement("div");
    codeWrap.className = "chat-code-block";
    const codeHead = document.createElement("div");
    codeHead.textContent = match[1].trim() || "code";
    const copyButton = document.createElement("button");
    copyButton.type = "button";
    copyButton.textContent = "复制";
    copyButton.addEventListener("click", async () => {
      await navigator.clipboard.writeText(match[2].trim());
      copyButton.textContent = "已复制";
      window.setTimeout(() => { copyButton.textContent = "复制"; }, 1200);
    });
    codeHead.appendChild(copyButton);
    const pre = document.createElement("pre");
    const code = document.createElement("code");
    code.textContent = match[2].trim();
    pre.appendChild(code);
    codeWrap.append(codeHead, pre);
    container.appendChild(codeWrap);
    cursor = fencePattern.lastIndex;
  }
  appendPlainChatText(container, value.slice(cursor));
}

function addChatMessageActions(message, text, question = "") {
  if (!message || message.querySelector(".chat-message-actions")) {
    return;
  }
  const content = message.querySelector(".chat-message-content");
  if (!content) {
    return;
  }
  const actions = document.createElement("div");
  actions.className = "chat-message-actions";
  const copyButton = document.createElement("button");
  copyButton.type = "button";
  copyButton.textContent = "复制回答";
  copyButton.addEventListener("click", async () => {
    await navigator.clipboard.writeText(text);
    copyButton.textContent = "已复制";
    window.setTimeout(() => { copyButton.textContent = "复制回答"; }, 1200);
  });
  actions.appendChild(copyButton);
  if (question) {
    const retryButton = document.createElement("button");
    retryButton.type = "button";
    retryButton.textContent = "重新生成";
    retryButton.addEventListener("click", () => sendChatMessage(question));
    actions.appendChild(retryButton);
  }
  content.appendChild(actions);
}

function appendChatMessage(role, text, extraClass = "", metadata = "") {
  const message = document.createElement("div");
  message.className = `chat-message ${role}${extraClass ? ` ${extraClass}` : ""}`;

  const label = document.createElement("span");
  label.textContent = role === "user" ? "我" : "CJ";

  const content = document.createElement("div");
  content.className = "chat-message-content";
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble";
  renderChatText(bubble, text);
  content.appendChild(bubble);
  if (metadata) {
    const meta = document.createElement("small");
    meta.className = "chat-message-meta";
    meta.textContent = metadata;
    content.appendChild(meta);
  }

  message.append(label, content);
  chatMessages.appendChild(message);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return message;
}

function setChatMessageText(message, text, rich = true) {
  const bubble = message.querySelector(".chat-bubble");
  if (bubble) {
    if (rich) {
      renderChatText(bubble, text);
    } else {
      bubble.textContent = text;
    }
  }
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function saveChatSession() {
  try {
    localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(chatHistory.slice(-20)));
  } catch (_error) {
    // Storage can be disabled by the browser; the current session still works.
  }
}

function restoreChatSession() {
  try {
    const saved = JSON.parse(localStorage.getItem(CHAT_STORAGE_KEY) || "[]");
    if (!Array.isArray(saved) || !saved.length) {
      return;
    }
    chatHistory = saved
      .filter((item) => item && ["user", "assistant"].includes(item.role) && typeof item.content === "string")
      .slice(-20);
    if (!chatHistory.length) {
      return;
    }
    chatWelcome.hidden = true;
    chatHistory.forEach((item) => {
      const message = appendChatMessage(item.role, item.content);
      if (item.role === "assistant") addChatMessageActions(message, item.content);
    });
    chatSessionMeta.textContent = `已恢复 ${Math.ceil(chatHistory.length / 2)} 轮对话 · 自动关联当前工作台`;
  } catch (_error) {
    localStorage.removeItem(CHAT_STORAGE_KEY);
  }
}

function clearChatSession() {
  if (chatAbortController) {
    chatAbortController.abort();
  }
  chatHistory = [];
  lastChatQuestion = "";
  localStorage.removeItem(CHAT_STORAGE_KEY);
  chatMessages.replaceChildren(chatWelcome);
  chatWelcome.hidden = false;
  chatSessionMeta.textContent = "新会话 · 自动关联当前工作台";
  chatInput.focus();
}

function buildChatContext() {
  const activeExample = getActiveDatasetExample();
  return {
    module: activeModule,
    module_label: moduleLabels[activeModule] || activeModule,
    strategy: strategy.value,
    strategy_label: selectedOptionText(strategy),
    source_lang: sourceLang.value,
    source_lang_label: selectedOptionText(sourceLang),
    source_code: sourceCode.value,
    target_code: targetCode.textContent,
    project_files: activeModule === "project" ? uploadedProjectFiles.map((file) => ({
      path: file.path,
      language: file.language,
      lines: file.lines
    })) : [],
    dataset_case: activeExample ? activeExample.id : "",
    example_title: activeExample ? activeExample.title : ""
  };
}

function setChatBusy(isBusy) {
  chatSendBtn.disabled = isBusy || !chatInput.value.trim();
  chatStopBtn.hidden = !isBusy;
  quickPromptBtns.forEach((button) => {
    button.disabled = isBusy;
  });
  chatConnectionStatus.classList.toggle("working", isBusy);
  chatConnectionStatus.lastChild.textContent = isBusy ? " 正在生成" : " 上下文已同步";
}

async function sendChatMessage(question) {
  const trimmedQuestion = question.trim();
  if (!trimmedQuestion || chatAbortController) {
    return;
  }

  updateChatContext();
  chatWelcome.hidden = true;
  appendChatMessage("user", trimmedQuestion);
  lastChatQuestion = trimmedQuestion;
  chatInput.value = "";
  updateChatInputState();
  setChatBusy(true);

  const pendingMessage = appendChatMessage(
    "assistant",
    "正在读取当前工作台上下文…",
    "pending"
  );
  const startedAt = performance.now();
  let answer = "";
  let providerLabel = "";
  let paintFrame = 0;
  chatAbortController = new AbortController();

  try {
    const response = await fetch(`${API_BASE}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: trimmedQuestion,
        history: chatHistory.slice(-8),
        context: buildChatContext()
      }),
      signal: chatAbortController.signal
    });

    if (!response.ok || !response.body) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || `HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finished = false;
    while (!finished) {
      const { value, done } = await reader.read();
      finished = done;
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.trim()) continue;
        const event = JSON.parse(line);
        if (event.type === "meta") {
          providerLabel = event.model || event.provider || "在线模型";
        } else if (event.type === "delta") {
          answer += event.content || "";
          if (!paintFrame) {
            paintFrame = requestAnimationFrame(() => {
              pendingMessage.classList.remove("pending");
              pendingMessage.classList.add("streaming");
              setChatMessageText(pendingMessage, answer, false);
              paintFrame = 0;
            });
          }
        } else if (event.type === "error") {
          throw new Error(event.error || "模型生成失败");
        }
      }
    }

    if (!answer.trim()) {
      throw new Error("模型没有返回有效内容。");
    }
    if (paintFrame) {
      cancelAnimationFrame(paintFrame);
      paintFrame = 0;
    }
    pendingMessage.classList.remove("pending", "streaming");
    setChatMessageText(pendingMessage, answer, true);
    const elapsed = ((performance.now() - startedAt) / 1000).toFixed(1);
    const meta = document.createElement("small");
    meta.className = "chat-message-meta";
    meta.textContent = `${providerLabel || "在线模型"} · ${elapsed}s`;
    pendingMessage.querySelector(".chat-message-content").appendChild(meta);
    addChatMessageActions(pendingMessage, answer, trimmedQuestion);
    chatHistory.push(
      { role: "user", content: trimmedQuestion },
      { role: "assistant", content: answer }
    );
    chatHistory = chatHistory.slice(-20);
    saveChatSession();
    chatSessionMeta.textContent = `${Math.ceil(chatHistory.length / 2)} 轮对话 · 自动关联当前工作台`;
    setBackendStatus("ok", "问答可用");
  } catch (error) {
    pendingMessage.classList.remove("pending", "streaming");
    if (error.name === "AbortError") {
      const stoppedText = answer.trim() || "已停止生成。";
      setChatMessageText(pendingMessage, stoppedText, true);
      pendingMessage.classList.add("stopped");
      if (answer.trim()) addChatMessageActions(pendingMessage, answer, trimmedQuestion);
    } else {
      setChatMessageText(pendingMessage, `生成失败：${error.message}\n请检查后端连接后重试。`, true);
      pendingMessage.classList.add("error");
      addChatMessageActions(pendingMessage, `生成失败：${error.message}`, trimmedQuestion);
      setBackendStatus("fail", "问答失败");
    }
  } finally {
    chatAbortController = null;
    setChatBusy(false);
    chatInput.focus();
  }
}

function updateChatInputState() {
  chatInput.style.height = "auto";
  chatInput.style.height = `${Math.min(Math.max(chatInput.scrollHeight, 48), 180)}px`;
  chatInputCount.textContent = `${chatInput.value.length} / 4000`;
  chatSendBtn.disabled = Boolean(chatAbortController) || !chatInput.value.trim();
}

function formatHistoryDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value || "未知时间";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

function formatHistoryDuration(milliseconds) {
  const value = Number(milliseconds) || 0;
  if (value < 1000) return `${value}ms`;
  if (value < 60000) return `${(value / 1000).toFixed(value < 10000 ? 1 : 0)}s`;
  return `${Math.floor(value / 60000)}m ${Math.round((value % 60000) / 1000)}s`;
}

function formatHistoryNumber(value) {
  return new Intl.NumberFormat("zh-CN", { notation: Number(value) >= 10000 ? "compact" : "standard" }).format(Number(value) || 0);
}

function historyTaskLabel(taskType) {
  return moduleLabels[taskType] || taskType || "未知模块";
}

function historyStrategyLabel(value) {
  return {
    model: "大模型直译 + 语法校验",
    "translator-api": "真实片段算法 API",
    agent: "逐文件模型翻译",
    "whole-project": "整项目模型翻译",
    vision: "多模态控件识别"
  }[value] || value || "—";
}

function historyProviderLabel(value) {
  return {
    openai_compatible: "在线大模型",
    spark_http: "星火 HTTP",
    spark: "星火 WebSocket",
    local_dataset: "本地数据集"
  }[value] || value || "—";
}

function historyStatusLabel(status) {
  return status === "success" ? "翻译成功" : "翻译失败";
}

function historyElement(tag, className = "", text = "") {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== "") element.textContent = text;
  return element;
}

function renderHistoryStats(stats = {}) {
  const total = Number(stats.total) || 0;
  const success = Number(stats.success) || 0;
  historyStatTotal.textContent = formatHistoryNumber(total);
  historyStatSuccess.textContent = formatHistoryNumber(success);
  historyStatProjects.textContent = formatHistoryNumber(stats.projects);
  historyStatDuration.textContent = formatHistoryDuration(stats.average_duration_ms);
  historySuccessRate.textContent = `成功率 ${total ? Math.round(success / total * 100) : 0}%`;
  historyStatChars.textContent = `累计 ${formatHistoryNumber(stats.source_chars)} 字符`;
  historyCountBadge.textContent = String(total > 99 ? "99+" : total);
  historyCountBadge.hidden = total === 0;
}

function renderHistoryList() {
  historyList.replaceChildren();
  historyResultCount.textContent = `${historyRecords.length} 条`;
  if (!historyRecords.length) {
    const empty = historyElement("div", "history-empty");
    const icon = historyElement("div", "history-empty-icon", "↺");
    const title = historyElement("strong", "", "还没有符合条件的记录");
    const copy = historyElement("p", "", "运行一次代码翻译后，记录会自动出现在这里。");
    empty.append(icon, title, copy);
    historyList.appendChild(empty);
    return;
  }

  historyRecords.forEach((record) => {
    const item = historyElement("button", `history-item ${record.status}${record.id === activeHistoryId ? " active" : ""}`);
    item.type = "button";
    item.dataset.historyId = record.id;
    const top = historyElement("div", "history-item-top");
    const task = historyElement("span", "history-task-badge", historyTaskLabel(record.task_type));
    const status = historyElement("span", `history-status ${record.status}`, historyStatusLabel(record.status));
    const date = historyElement("time", "", formatHistoryDate(record.created_at));
    top.append(task, status, date);
    const title = historyElement("strong", "history-item-title", record.title || "未命名翻译");
    const previewText = record.status === "success"
      ? (record.target_preview || record.source_preview || "翻译已完成")
      : (record.error || record.source_preview || "翻译失败");
    const preview = historyElement("p", "history-item-preview", previewText);
    const footer = historyElement("div", "history-item-footer");
    footer.append(
      historyElement("span", "", `${String(record.source_lang || "").toUpperCase()} → Cangjie`),
      historyElement("span", "", record.project_file_count ? `${record.project_file_count} 个文件` : `${record.source_lines || 0} 行`),
      historyElement("span", "", formatHistoryDuration(record.duration_ms))
    );
    item.append(top, title, preview, footer);
    item.addEventListener("click", () => selectHistoryRecord(record.id));
    historyList.appendChild(item);
  });
}

function historyMetaItem(label, value) {
  const item = historyElement("div", "history-meta-item");
  item.append(historyElement("span", "", label), historyElement("strong", "", value || "—"));
  return item;
}

function historyCodePanel(title, language, code) {
  const panel = historyElement("section", "history-code-panel");
  const head = historyElement("div", "history-code-head");
  const labelWrap = historyElement("div");
  labelWrap.append(historyElement("strong", "", title), historyElement("span", "", language));
  const copyButton = historyElement("button", "ghost-btn", "复制代码");
  copyButton.type = "button";
  copyButton.addEventListener("click", async () => {
    await navigator.clipboard.writeText(code || "");
    copyButton.textContent = "已复制";
    window.setTimeout(() => { copyButton.textContent = "复制代码"; }, 1200);
  });
  head.append(labelWrap, copyButton);
  const pre = document.createElement("pre");
  pre.textContent = code || "// 暂无内容";
  panel.append(head, pre);
  return panel;
}

function repairHistoryLabel(repair = {}) {
  if (!repair.enabled) return "未启用";
  if (repair.error) return "诊断异常";
  if (repair.used_for_translation) return "已修复后翻译";
  if (repair.needs_repair) return "发现问题";
  return "检查通过";
}

function compilerHistoryLabel(record) {
  const validation = record.artifact?.validation || {};
  if (validation.build_verified === true) return "项目构建通过";
  if (validation.build_verified === false) return "项目构建未通过";
  return record.compiler?.status === "available" ? "编译器可用" : "未执行构建";
}

function exportHistoryRecord(record) {
  const payload = JSON.stringify(record, null, 2);
  const blob = new Blob([payload], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `translation-${record.id.slice(0, 8)}.json`;
  link.click();
  URL.revokeObjectURL(url);
}

function resetProjectResult() {
  downloadableProject = null;
  projectResult.hidden = true;
  targetCode.hidden = false;
  copyBtn.hidden = false;
  projectDownloadStatus.textContent = "";
}

function renderTranslationOutput(text, taskType, artifact) {
  resetProjectResult();
  targetCode.textContent = String(text || "").trim();
  if (taskType !== "project" || !artifact?.download_url) return;
  downloadableProject = artifact;
  targetCode.hidden = true;
  copyBtn.hidden = true;
  projectResult.hidden = false;
  const build = artifact.validation?.build;
  const buildNote = build?.build_verified ? "仓颉构建已通过。"
    : build?.status === "compiler_unavailable" ? "未找到仓颉工具链，构建尚未验证。"
    : "仓颉构建未通过，请查看翻译报告。";
  projectResultSummary.textContent = `已将 ${artifact.files?.length || 0} 个生成文件打包为一个 ZIP 文件，保留项目目录结构。${buildNote}`;
}

async function downloadTranslatedProject() {
  const artifact = downloadableProject;
  if (!artifact) return;
  let writable;
  downloadProjectBtn.disabled = true;
  projectDownloadStatus.textContent = "请选择保存位置…";
  try {
    // Open the picker during the click gesture, before starting the download.
    const handle = typeof window.showSaveFilePicker === "function"
      ? await window.showSaveFilePicker({
        suggestedName: artifact.download_name,
        types: [{ description: "项目压缩包", accept: { "application/zip": [".zip"] } }]
      })
      : null;
    projectDownloadStatus.textContent = "正在下载项目文件…";
    const response = await fetch(`${API_BASE}${artifact.download_url}`);
    if (!response.ok) {
      throw new Error("项目下载文件不存在或下载失败，请重新翻译后再试。");
    }
    const blob = await response.blob();
    if (handle) {
      writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      writable = null;
      projectDownloadStatus.textContent = "项目文件已保存到所选位置。";
    } else {
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = artifact.download_name;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
      projectDownloadStatus.textContent = "已开始下载，请查看浏览器的下载记录。";
    }
  } catch (error) {
    if (writable) await writable.abort().catch(() => {});
    projectDownloadStatus.textContent = error.name === "AbortError"
      ? "已取消保存，可以再次点击下载。"
      : `保存失败：${error.message}`;
  } finally {
    downloadProjectBtn.disabled = false;
  }
}

function loadHistoryIntoWorkbench(record) {
  const taskType = ["snippet", "project", "ui"].includes(record.task_type) ? record.task_type : "snippet";
  setModule(taskType, false);
  if ([...sourceLang.options].some((option) => option.value === record.source_lang)) {
    sourceLang.value = record.source_lang;
  }
  if ([...strategy.options].some((option) => option.value === record.strategy)) {
    strategy.value = record.strategy;
  }
  sourceCode.value = record.source_code || "";
  renderTranslationOutput(record.target_code || `// 历史任务失败\n// ${record.error || "无输出"}`, taskType, record.status === "success" ? record.artifact : null);
  if (taskType === "project") {
    uploadedProjectFiles = Array.isArray(record.project_files) ? record.project_files : [];
    renderProjectFiles();
  } else if (taskType === "ui") {
    uploadedUiFiles = Array.isArray(record.project_files) ? record.project_files : [];
    uploadedUiImages = [];
    renderUiFiles();
  }
  resetRepairReport();
  resetRuntimeReport();
  updateChatContext();
  setView("workbench");
  setRunState("已载入历史翻译", "busy");
}

function renderHistoryDetailEmpty(message = "选择左侧的一条翻译记录，查看完整代码与运行信息") {
  historyDetail.classList.remove("loading");
  historyDetail.replaceChildren(historyElement("div", "history-empty", message));
}

function renderHistoryDetail(record) {
  historyDetail.replaceChildren();
  const header = historyElement("header", "history-detail-head");
  const heading = historyElement("div");
  const badgeRow = historyElement("div", "history-detail-badges");
  badgeRow.append(
    historyElement("span", "history-task-badge", historyTaskLabel(record.task_type)),
    historyElement("span", `history-status ${record.status}`, historyStatusLabel(record.status))
  );
  heading.append(badgeRow, historyElement("h3", "", record.title || "未命名翻译"), historyElement("p", "", `${new Date(record.created_at).toLocaleString("zh-CN")} · ${record.id.slice(0, 8)}`));
  const actions = historyElement("div", "history-detail-actions");
  const loadButton = historyElement("button", "primary-btn small-btn", "载入工作台");
  loadButton.type = "button";
  loadButton.addEventListener("click", () => loadHistoryIntoWorkbench(record));
  const exportButton = historyElement("button", "secondary-btn small-btn", "导出 JSON");
  exportButton.type = "button";
  exportButton.addEventListener("click", () => exportHistoryRecord(record));
  actions.append(loadButton, exportButton);
  header.append(heading, actions);

  const meta = historyElement("div", "history-meta-grid");
  meta.append(
    historyMetaItem("源语言", `${String(record.source_lang || "").toUpperCase()} → Cangjie`),
    historyMetaItem("翻译策略", historyStrategyLabel(record.strategy)),
    historyMetaItem("模型服务", historyProviderLabel(record.provider)),
    historyMetaItem("模型", record.model),
    historyMetaItem("耗时", formatHistoryDuration(record.duration_ms)),
    historyMetaItem("代码规模", `${record.source_lines} → ${record.target_lines} 行`),
    historyMetaItem("项目文件", `${record.project_file_count || 0} 个`),
    historyMetaItem("智能体阶段", `${record.agent_stages?.length || 0} 个`),
    historyMetaItem("诊断修复", repairHistoryLabel(record.repair)),
    historyMetaItem("编译验证", compilerHistoryLabel(record))
  );

  historyDetail.append(header, meta);
  if (record.error) {
    const errorBox = historyElement("div", "history-error-box");
    errorBox.append(historyElement("strong", "", "失败原因"), historyElement("p", "", record.error));
    historyDetail.appendChild(errorBox);
  }

  if (record.artifact?.output_dir) {
    const artifactBox = historyElement("div", "history-artifact-box");
    const artifactCopy = historyElement("div");
    artifactCopy.append(
      historyElement("strong", "", "生成产物"),
      historyElement("code", "", record.artifact.output_dir),
      historyElement("span", "", `${record.artifact.files?.length || 0} 个输出文件 · ${compilerHistoryLabel(record)}`)
    );
    artifactBox.appendChild(artifactCopy);
    historyDetail.appendChild(artifactBox);
  }

  if (Array.isArray(record.project_files) && record.project_files.length) {
    const fileDetails = document.createElement("details");
    fileDetails.className = "history-file-details";
    const summary = document.createElement("summary");
    summary.textContent = `查看项目文件清单（${record.project_files.length}）`;
    const list = historyElement("div", "history-file-grid");
    record.project_files.forEach((file) => {
      list.appendChild(historyElement("span", "", `${file.path} · ${file.language} · ${file.lines} 行`));
    });
    fileDetails.append(summary, list);
    historyDetail.appendChild(fileDetails);
  }

  const codeGrid = historyElement("div", "history-code-grid");
  codeGrid.append(
    historyCodePanel("原始代码", String(record.source_lang || "source").toUpperCase(), record.source_code),
    historyCodePanel("仓颉结果", "CANGJIE", record.target_code || (record.error ? `// ${record.error}` : ""))
  );
  historyDetail.appendChild(codeGrid);
}

async function selectHistoryRecord(recordId) {
  activeHistoryId = recordId;
  renderHistoryList();
  historyDetail.classList.add("loading");
  try {
    const response = await fetch(`${API_BASE}/history/${encodeURIComponent(recordId)}`, { cache: "no-store" });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
    renderHistoryDetail(data.item);
  } catch (error) {
    historyDetail.replaceChildren(historyElement("div", "history-empty", `读取记录失败：${error.message}`));
  } finally {
    historyDetail.classList.remove("loading");
  }
}

async function loadHistoryRecords(selectFirst = true) {
  if (!historyList) return;
  refreshHistoryBtn.disabled = true;
  const params = new URLSearchParams({ limit: "100" });
  if (historySearch.value.trim()) params.set("q", historySearch.value.trim());
  if (historyModuleFilter.value) params.set("task_type", historyModuleFilter.value);
  if (historyStatusFilter.value) params.set("status", historyStatusFilter.value);
  try {
    const response = await fetch(`${API_BASE}/history?${params}`, { cache: "no-store" });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
    historyRecords = Array.isArray(data.items) ? data.items : [];
    renderHistoryStats(data.stats || {});
    const activeRecordIsVisible = historyRecords.some((item) => item.id === activeHistoryId);
    if (!activeRecordIsVisible) {
      activeHistoryId = "";
      renderHistoryDetailEmpty(
        historyRecords.length
          ? "选择左侧的一条翻译记录，查看完整代码与运行信息"
          : "当前条件下没有可查看的翻译记录"
      );
    }
    renderHistoryList();
    if (selectFirst && !activeHistoryId && historyRecords.length) {
      selectHistoryRecord(historyRecords[0].id);
    }
  } catch (error) {
    historyList.replaceChildren(historyElement("div", "history-empty", `无法读取翻译记录：${error.message}`));
    renderHistoryDetailEmpty("翻译记录加载失败，请确认后端服务正常运行");
  } finally {
    refreshHistoryBtn.disabled = false;
  }
}

function initDatasetExamples() {
  if (!datasetExamples.length) {
    exampleSelect.innerHTML = "<option>未找到数据集样例</option>";
    exampleSelect.disabled = true;
    prevExampleBtn.disabled = true;
    nextExampleBtn.disabled = true;
    randomExampleBtn.disabled = true;
    referenceExampleBtn.disabled = true;
    exampleMeta.textContent = "未生成 examples.js";
    return;
  }

  exampleSelect.innerHTML = datasetExamples
    .map((example, index) => `<option value="${index}">${index + 1}. ${example.title}</option>`)
    .join("");
  exampleSelect.disabled = false;
  prevExampleBtn.disabled = false;
  nextExampleBtn.disabled = false;
  randomExampleBtn.disabled = false;
  referenceExampleBtn.disabled = false;
  updateExampleMeta();
}

function updateExampleMeta() {
  if (!datasetExamples.length) {
    exampleMeta.textContent = "没有可用样例";
    return;
  }

  const example = datasetExamples[activeExampleIndex];
  exampleMeta.textContent = `${activeExampleIndex + 1}/${datasetExamples.length} · ${example.family} · Java ${example.javaLines} 行 / 仓颉 ${example.cangjieLines} 行`;
}

function applyDatasetExample(index) {
  if (!datasetExamples.length) {
    loadBuiltinSampleCode();
    return;
  }

  activeExampleIndex = (index + datasetExamples.length) % datasetExamples.length;
  const example = datasetExamples[activeExampleIndex];
  sourceLang.value = "java";
  exampleSelect.value = String(activeExampleIndex);
  sourceCode.value = example.java;
  targetCode.textContent = `// 已载入 GitHub 数据集样例
// 右侧暂不显示仓颉参考答案。
// 点击“运行翻译”后这里会显示模型翻译结果。
// 如需对照标准答案，点击“参考答案”。
//
// case: ${example.id}
// java_file: ${example.javaFile}
// ast_tokens: ${example.ast ? "available" : "missing"}`;
  setRunState("已载入数据集样例", "busy");
  updateExampleMeta();
  resetRepairReport();
  resetRuntimeReport();
  updateChatContext();
}

function showDatasetReference() {
  if (!datasetExamples.length || activeModule !== "snippet") {
    return;
  }

  const example = datasetExamples[activeExampleIndex];
  targetCode.textContent = `${example.cangjie}

// dataset reference
// case: ${example.id}
// java_file: ${example.javaFile}
// cangjie_file: ${example.cangjieFile}
// ast_tokens: ${example.ast ? "available" : "missing"}`;
  setRunState("已显示参考答案", "info");
  updateChatContext();
}

function loadBuiltinSampleCode() {
  const data = getActiveData();
  if (activeModule === "project") {
    clearProjectUpload();
    if (Array.isArray(data.projectFiles)) {
      uploadedProjectFiles = data.projectFiles.map((file) => ({
        ...file,
        originalSize: file.content.length,
        truncated: false
      }));
      sourceCode.value = formatProjectSource(uploadedProjectFiles);
      targetCode.textContent = data.output;
      renderProjectFiles();
      resetRepairReport();
      resetRuntimeReport();
      updateChatContext();
      return;
    }
  }
  sourceCode.value = data.samples[sourceLang.value] || data.samples.java;
  targetCode.textContent = data.output;
  resetRepairReport();
  resetRuntimeReport();
  updateChatContext();
}

function getUiExample(exampleId) {
  return uiMigrationExamples.find((example) => example.id === exampleId) || uiMigrationExamples[0];
}

function updateUiExampleState(exampleId) {
  const example = getUiExample(exampleId);
  activeUiExampleId = example.id;
  uiExampleSummary.textContent = `${example.title}：${example.summary}`;
  uiExampleBtns.forEach((button) => {
    button.classList.toggle("active-case", button.dataset.uiExample === example.id);
  });
}

function applyUiExample(exampleId = activeUiExampleId) {
  const example = getUiExample(exampleId);
  if (activeModule !== "ui") {
    setModule("ui", false);
  }
  sourceLang.value = "web";
  strategy.value = "vision";
  sourceCode.value = example.source;
  targetCode.textContent = `// 已载入 UI 迁移测试用例：${example.title}
// ${example.summary}
// 点击“运行翻译”后，将生成仓颉 Web 托管项目并保留页面设计与交互。`;
  updateUiExampleState(example.id);
  resetRepairReport();
  resetRuntimeReport();
  setRunState("UI 测试用例已载入", "busy");
  updateChatContext();
}

function setModule(moduleName, loadSample = true) {
  resetProjectResult();
  activeModule = moduleName;
  const data = getActiveData();

  segments.forEach((segment) => {
    const active = segment.dataset.module === moduleName;
    segment.classList.toggle("active", active);
    segment.setAttribute("aria-selected", String(active));
  });

  sourceTitle.textContent = data.title;
  moduleNote.textContent = data.note;
  strategy.value = data.strategy;
  if (moduleName === "ui") {
    sourceLang.value = "web";
  } else if (sourceLang.value === "web") {
    sourceLang.value = "java";
  }
  updateLocalImportControls();
  setRunState("等待运行翻译");
  renderPipeline();
  exampleStrip.style.display = moduleName === "snippet" ? "" : "none";
  projectUploadPanel.hidden = moduleName !== "project";
  uiExamplePanel.hidden = moduleName !== "ui";
  uiUploadPanel.hidden = moduleName !== "ui";
  if (moduleName === "ui") {
    updateUiExampleState(activeUiExampleId);
    renderUiFiles();
  }

  if (loadSample) {
    loadSampleCode();
  }
  updateLanguageDetection();
  updateChatContext();
}

function loadSampleCode() {
  if (activeModule === "snippet" && sourceLang.value === "java" && datasetExamples.length) {
    applyDatasetExample(activeExampleIndex);
    updateLanguageDetection();
    return;
  }

  if (activeModule === "ui" && sourceLang.value === "web") {
    applyUiExample(activeUiExampleId);
    return;
  }

  loadBuiltinSampleCode();
  updateLanguageDetection();
}

function runTranslation() {
  runRealBackendTranslation();
}

function showProjectJobProgress(job) {
  if (activeModule !== "project") return;
  const completed = Number(job.completed_files || 0);
  const total = Number(job.total_files || 0);
  const phase = job.stage === "building" ? "正在构建并打包项目"
    : job.stage === "translating_project" ? "正在整项目翻译并生成仓颉项目"
    : job.stage === "analyzing" ? "正在分析项目文件"
    : `逐文件翻译：已完成 ${completed}/${total} 个源码文件`;
  const current = job.current_file ? `\n// 当前文件：${job.current_file}` : "";
  targetCode.textContent = `// ${phase}${current}\n// ${job.stage === "translating_project" ? "模型正在统一生成项目文件，完成后将进行编译检查。" : "逐文件模式下，完成的文件会保存到后端检查点。"}`;
  setRunState(phase, "busy");
  renderPipeline(job.stage === "building" ? 3 : ["translating", "translating_project"].includes(job.stage) ? 2 : 1);
}

async function waitForProjectJob(jobId) {
  let pollErrors = 0;
  while (true) {
    let job;
    try {
      const response = await fetch(`${API_BASE}/project-jobs/${encodeURIComponent(jobId)}`, { cache: "no-store" });
      job = await response.json();
      if (!response.ok || !job.ok) {
        const failure = new Error(job.error || `HTTP ${response.status}`);
        failure.status = response.status;
        throw failure;
      }
      pollErrors = 0;
    } catch (error) {
      if (error.status === 404) {
        localStorage.removeItem(PROJECT_JOB_STORAGE_KEY);
        throw new Error("后端已重启，原任务无法继续查询；请重新运行项目翻译。");
      }
      pollErrors += 1;
      if (pollErrors >= 5) throw new Error(`无法读取项目翻译进度：${error.message}。任务可能仍在后端运行。`);
      await delay(2000);
      continue;
    }
    showProjectJobProgress(job);
    if (job.status === "completed") {
      localStorage.removeItem(PROJECT_JOB_STORAGE_KEY);
      return job.result;
    }
    if (job.status === "failed") {
      localStorage.removeItem(PROJECT_JOB_STORAGE_KEY);
      throw new Error(`项目翻译停在 ${job.current_file || "当前阶段"}：${job.error || "未知错误"}`);
    }
    await delay(1500);
  }
}

async function resumeActiveProjectJob() {
  const jobId = localStorage.getItem(PROJECT_JOB_STORAGE_KEY);
  if (!jobId) return;
  setModule("project", false);
  translateBtn.disabled = true;
  setBackendStatus("idle", "项目翻译中");
  try {
    const data = await waitForProjectJob(jobId);
    if (!data?.artifact?.download_url) throw new Error("项目任务已完成，但没有生成 ZIP 下载地址。");
    renderTranslationOutput(data.translation, "project", data.artifact);
    renderRepairReport(data.repair, sourceCode.value);
    renderRuntimeReport(data);
    setBackendStatus("ok", "已连接");
    await finishPipelineProgress(data.artifact.validation?.build_verified ? "项目迁移与构建完成" : "项目文件已生成，构建未验证或未通过");
  } catch (error) {
    targetCode.textContent = `// 无法恢复项目任务\n// ${error.message}`;
    setRunState("项目任务需要重试", "warn");
    setBackendStatus("fail", "调用失败");
  } finally {
    translateBtn.disabled = false;
    loadHistoryRecords(false);
  }
}

async function runRealBackendTranslation() {
  resetProjectResult();
  const taskType = activeModule;
  const input = sourceCode.value.trim();
  if (!input) {
    targetCode.textContent = "// 请输入源代码后再运行翻译。";
    setRunState("等待输入", "warn");
    resetRepairReport();
    updateChatContext();
    return;
  }

  const languageMismatch = updateLanguageDetection();
  if (languageMismatch) {
    const selectedLabel = SOURCE_LANGUAGE_LABELS[sourceLang.value]
      || sourceLang.options[sourceLang.selectedIndex]?.text
      || sourceLang.value;
    targetCode.textContent = `// 源语言选择不一致
// 检测到当前代码可能是 ${languageMismatch.label}，但已选择 ${selectedLabel}。
// 请重新选择源语言后再运行翻译。`;
    setRunState("请重新选择源语言", "warn");
    setBackendStatus("fail", "语言不匹配");
    resetRepairReport();
    resetRuntimeReport();
    updateChatContext();
    switchDetectedLanguageBtn.focus();
    return;
  }

  if (activeModule === "snippet") {
    const validation = validateSnippetSource(input);
    if (!validation.ok) {
      targetCode.textContent = `// ${validation.message}`;
      setRunState("片段过长", "warn");
      setBackendStatus("fail", "已拦截");
      resetRepairReport();
      updateChatContext();
      return;
    }
  }

  if (activeModule === "ui") {
    const validation = validateWebUiSource(input, sourceLang.value);
    if (!validation.ok) {
      targetCode.textContent = `// ${validation.message}`;
      setRunState("UI 输入不符", "warn");
      setBackendStatus("fail", "已拦截");
      resetRepairReport();
      updateChatContext();
      return;
    }
  }

  clearPipelineProgress();

  translateBtn.disabled = true;
  if (taskType === "project") targetCode.textContent = "正在翻译项目，完成后可下载 ZIP 文件…";
  setRunState(activeModule === "project" ? (strategy.value === "whole-project" ? "准备整项目翻译" : "准备逐文件翻译") : repairToggle.checked ? "诊断并修复源代码" : "调用翻译后端", "busy");
  setBackendStatus("idle", "调用中");
  resetRepairReport();
  startPipelineProgress();

  try {
    if (taskType === "project") {
      const healthResponse = await fetch(`${API_BASE}/health`, { cache: "no-store" });
      const health = await healthResponse.json();
      if (!healthResponse.ok || !health.project_jobs_supported || (strategy.value === "whole-project" && !health.project_whole_supported)) {
        throw new Error("当前运行的是旧版后端，不支持所选项目翻译策略。请关闭旧后端并重新运行 start_backend.bat。");
      }
    }
    const activeExample = activeModule === "snippet" && datasetExamples.length
      ? datasetExamples[activeExampleIndex]
      : null;
    const payload = {
      source_code: input,
      source_lang: sourceLang.value,
      mode: "zeroshot",
      task_type: activeModule,
      strategy: strategy.value,
      ast_text: activeExample ? activeExample.ast : "",
      repair: repairToggle.checked,
      project_files: activeModule === "project" ? uploadedProjectFiles : activeModule === "ui" ? uploadedUiFiles : [],
      images: activeModule === "ui" ? uploadedUiImages : []
    };
    let data;
    if (taskType === "project") {
      let jobId = localStorage.getItem(PROJECT_JOB_STORAGE_KEY);
      if (!jobId) {
        const response = await fetch(`${API_BASE}/project-jobs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const job = await response.json();
        if (!response.ok || !job.ok) throw new Error(job.error || `HTTP ${response.status}`);
        jobId = job.job_id;
        localStorage.setItem(PROJECT_JOB_STORAGE_KEY, jobId);
        showProjectJobProgress(job);
      }
      data = await waitForProjectJob(jobId);
    } else {
      const controller = new AbortController();
      const timeoutMs = taskType === "snippet" ? SNIPPET_REQUEST_TIMEOUT_MS : UI_REQUEST_TIMEOUT_MS;
      const requestTimer = window.setTimeout(() => controller.abort(), timeoutMs);
      let response;
      try {
        response = await fetch(`${API_BASE}/translate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: controller.signal,
          body: JSON.stringify(payload)
        });
      } catch (error) {
        if (error.name === "AbortError") {
          throw new Error(`翻译请求超过 ${timeoutMs / 1000} 秒，已停止等待。请重试或检查模型服务状态。`);
        }
        throw error;
      } finally {
        window.clearTimeout(requestTimer);
      }
      data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
    }
    if (!data?.ok) throw new Error(data?.error || "项目翻译未返回结果。");

    if (taskType !== activeModule) return;
    if (taskType === "project" && !data.artifact?.download_url) {
      throw new Error("后端未返回项目下载文件，请重启后端后重新翻译。");
    }
    renderTranslationOutput(data.translation, taskType, data.artifact);
    renderRepairReport(data.repair, input);
    updateChatContext();
    setBackendStatus("ok", ["local_dataset", "local_model"].includes(data.provider) ? "离线可用" : "已连接");
    renderRuntimeReport(data);
    await finishPipelineProgress(data.provider === "local_dataset"
      ? "本地数据集翻译完成"
      : data.provider === "local_model" ? "本地训练模型翻译完成"
      : activeModule === "project" ? (data.artifact?.validation?.build_verified ? "项目迁移与构建完成" : "项目文件已生成，构建未验证或未通过") : "翻译完成");
  } catch (error) {
    targetCode.textContent = `// 翻译后端调用失败
// ${error.message}
//
// 请确认：
// 1. 已双击当前项目目录中的 start_backend.bat
// 2. 已安装 backend\\requirements.txt 中的依赖
// 3. Java 片段翻译请确认本地模型权重和 Python 环境完整
// 4. 项目/UI 翻译请检查 .env 中的在线模型配置。`;
    renderRepairReport({ enabled: repairToggle.checked, error: error.message, issues: [] }, input);
    resetRuntimeReport();
    updateChatContext();
    const isNetworkFailure = /Failed to fetch|NetworkError|ERR_CONNECTION|连接被拒绝|network/i.test(error.message);
    setBackendStatus("fail", isNetworkFailure ? "连接中断" : "调用失败");
    await finishPipelineProgress(isNetworkFailure ? "后端调用失败" : "模型请求失败", false);
  } finally {
    translateBtn.disabled = false;
    loadHistoryRecords(false);
  }
}

async function checkBackend() {
  setBackendStatus("idle", "检测中");
  try {
    const response = await fetchHealthWithRetry();
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }

    if (!data.translator_importable) {
      throw new Error(data.import_error || "translator import failed");
    }

    if (data.java_snippet_provider === "local_model" && !data.java_snippet_model_ready) {
      throw new Error(data.java_snippet_model_error || "本地训练模型文件不完整");
    }

    if (data.provider === "spark" && !data.spark_credentials_present) {
      throw new Error("Spark credentials are missing");
    }

    if (data.provider === "spark_http" && !data.spark_api_password_present) {
      throw new Error("Spark API password is missing");
    }

    setBackendStatus("ok", data.java_snippet_provider === "local_model" || data.provider === "local_dataset" ? "离线可用" : "已连接");
    runState.textContent = data.java_snippet_provider === "local_model"
      ? `Java 片段：本地训练模型已就绪；项目/UI：${data.provider}`
      : data.provider === "local_dataset"
      ? `本地数据集后端可用：${data.local_dataset_cases || 0} 个 Java/仓颉样例`
      : data.provider === "spark_http"
      ? `星火 HTTP 后端可用：${data.spark_http_model}，本地样例 ${data.local_dataset_cases || 0} 个`
      : data.provider === "spark"
      ? `星火后端可用：${data.spark_domain}，本地样例 ${data.local_dataset_cases || 0} 个`
      : `后端可用：${data.model}`;
  } catch (error) {
    setBackendStatus("fail", "未连接");
    runState.textContent = "后端未就绪";
    targetCode.textContent = `// 后端检测失败
// ${error.message}
// 可运行 start_backend.bat 后再次检测。`;
  }
}

function clearSource() {
  resetProjectResult();
  if (activeModule === "project") {
    clearProjectUpload();
  }
  sourceCode.value = "";
  targetCode.textContent = "// 等待输入源代码";
  setRunState("等待输入", "warn");
  resetRepairReport();
  resetRuntimeReport();
  detectedSourceLanguage = null;
  hideLanguageDetection();
  updateChatContext();
}

async function copyOutput() {
  const text = targetCode.textContent;
  try {
    await navigator.clipboard.writeText(text);
    runState.textContent = "输出已复制";
  } catch {
    const temp = document.createElement("textarea");
    temp.value = text;
    document.body.appendChild(temp);
    temp.select();
    document.execCommand("copy");
    temp.remove();
    runState.textContent = "输出已复制";
  }
}

function readTextFile(file) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(`// file: ${file.name}\n${reader.result}`);
    reader.onerror = () => resolve(`// file: ${file.name}\n// 读取失败`);
    reader.readAsText(file);
  });
}

function readRawProjectFile(file) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => resolve("// 读取失败");
    reader.readAsText(file);
  });
}

function readImageFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve({ name: file.name, data_url: String(reader.result || "") });
    reader.onerror = () => reject(new Error(`无法读取图片：${file.name}`));
    reader.readAsDataURL(file);
  });
}

async function loadProjectFilesFromSelection(fileList) {
  const selectedFiles = Array.from(fileList || []);
  if (!selectedFiles.length) {
    return;
  }

  const readableFiles = selectedFiles
    .filter(shouldIncludeProjectFile)
    .sort((a, b) => projectFilePath(a).localeCompare(projectFilePath(b), "zh-CN"))
    .slice(0, PROJECT_MAX_FILES);
  const skippedCount = selectedFiles.length - readableFiles.length;

  if (!readableFiles.length) {
    setModule("project", false);
    clearProjectUpload();
    sourceCode.value = "";
    targetCode.textContent = "// 未读取到可翻译的项目源码文件。请上传 Java、C++、Python 或构建配置等文本文件。";
    projectFileSummary.textContent = `已跳过 ${selectedFiles.length} 个不支持或过大的文件`;
    setRunState("项目文件不可用", "warn");
    resetRepairReport();
    updateChatContext();
    return;
  }

  let totalChars = 0;
  const loadedFiles = [];
  for (const file of readableFiles) {
    const rawContent = await readRawProjectFile(file);
    const remainingChars = PROJECT_MAX_TOTAL_CHARS - totalChars;
    if (remainingChars <= 0) {
      break;
    }

    const content = rawContent.slice(0, Math.min(PROJECT_MAX_FILE_CHARS, remainingChars));
    totalChars += content.length;
    const path = uploadedProjectRelativePath(file);
    loadedFiles.push({
      path,
      language: projectFileLanguage(path),
      content,
      lines: content.split(/\r?\n/).filter((line) => line.trim()).length,
      originalSize: file.size,
      truncated: content.length < rawContent.length
    });
  }

  localStorage.removeItem(PROJECT_JOB_STORAGE_KEY);
  setModule("project", false);
  sourceLang.value = detectProjectSourceLanguage(loadedFiles);
  strategy.value = "whole-project";
  uploadedProjectFiles = loadedFiles;
  sourceCode.value = formatProjectSource(loadedFiles, skippedCount + (readableFiles.length - loadedFiles.length));
  targetCode.textContent = `// 已读取本地项目文件 ${loadedFiles.length} 个
// 点击“运行翻译”后，后端会统一翻译小型项目并进行编译检查。
// 翻译完成后，输出区将显示“翻译已完成”和 ZIP 下载按钮。`;
  renderProjectFiles();
  resetRepairReport();
  resetRuntimeReport();
  setRunState("项目文件已读取", "busy");
  updateChatContext();
}

async function loadUiFilesFromSelection(fileList) {
  const selectedFiles = Array.from(fileList || []);
  if (!selectedFiles.length) {
    return;
  }

  const acceptedFiles = selectedFiles
    .filter(shouldIncludeUiFile)
    .sort((a, b) => projectFilePath(a).localeCompare(projectFilePath(b), "zh-CN"));
  const textFiles = acceptedFiles.filter((file) => !file.type.startsWith("image/"));
  const imageFiles = acceptedFiles.filter((file) => file.type.startsWith("image/"));
  const loadedFiles = [];

  for (const file of textFiles) {
    const content = await readRawProjectFile(file);
    const path = projectFilePath(file);
    loadedFiles.push({
      path,
      language: projectFileLanguage(path),
      content,
      lines: countNonEmptyLines(content),
      originalSize: file.size,
      truncated: false
    });
  }

  uploadedUiFiles = loadedFiles;
  uploadedUiImages = await Promise.all(imageFiles.map(readImageFile));
  sourceLang.value = "web";
  strategy.value = "vision";
  sourceCode.value = formatProjectSource(loadedFiles) || (uploadedUiImages.length ? "<!-- 已导入 UI 截图 -->" : "");
  renderUiFiles();

  const validation = validateWebUiSource(sourceCode.value, sourceLang.value, loadedFiles);
  if (validation.ok) {
    targetCode.textContent = `// 已读取本地网页项目 ${loadedFiles.length + uploadedUiImages.length} 个文件
// 点击“运行翻译”后，将按所选网页文件生成仓颉 Web 托管项目。`;
    setRunState("网页项目已读取", "busy");
    setBackendStatus("idle", "已验收");
  } else {
    targetCode.textContent = `// ${validation.message}`;
    setRunState("网页项目不符合要求", "warn");
    setBackendStatus("fail", "已拦截");
  }
  resetRepairReport();
  resetRuntimeReport();
  updateChatContext();
}

function detectProjectSourceLanguage(files) {
  const counts = files.reduce((result, file) => {
    const language = file.language;
    result[language] = (result[language] || 0) + 1;
    return result;
  }, {});
  if ((counts.Java || 0) >= Math.max(counts["C++"] || 0, counts.Python || 0)) {
    return "java";
  }
  if ((counts["C++"] || 0) >= (counts.Python || 0)) {
    return "cpp";
  }
  return "python";
}

async function loadFiles(event) {
  const files = Array.from(event.target.files || []);
  if (!files.length) {
    return;
  }

  uploadedUiImages = [];
  const textParts = await Promise.all(files.filter((file) => !file.type.startsWith("image/")).map(readTextFile));

  const mergedText = textParts.join("\n\n");
  sourceLang.value = detectSnippetLanguageFromFiles(files);

  sourceCode.value = mergedText;
  const validation = validateSnippetSource(mergedText);

  if (validation.ok) {
    targetCode.textContent = `// 已读取 ${files.length} 个文件，点击“运行翻译”生成仓颉输出。`;
    setRunState(`片段已读取：${sourceLang.value.toUpperCase()}`, "busy");
    setBackendStatus("idle", "已验收");
  } else {
    targetCode.textContent = `// ${validation.message}`;
    setRunState("片段不符合要求", "warn");
    setBackendStatus("fail", "已拦截");
  }
  resetRepairReport();
  resetRuntimeReport();
  updateLanguageDetection();
  updateChatContext();
  fileInput.value = "";
}

navItems.forEach((item) => {
  item.addEventListener("click", () => setView(item.dataset.view));
});

workbenchTabs.forEach((tab) => {
  tab.nextElementSibling.addEventListener("click", (event) => {
    if (tab.checked) {
      event.preventDefault();
      tab.checked = false;
    }
  });
});

homeActions.forEach((item) => {
  item.addEventListener("click", () => {
    if (item.dataset.homeModule) setModule(item.dataset.homeModule);
    setView(item.dataset.homeTarget);
  });
});

segments.forEach((segment) => {
  segment.addEventListener("click", () => setModule(segment.dataset.module));
});

sourceLang.addEventListener("change", () => {
  resetRepairReport();
  resetRuntimeReport();
  updateLanguageDetection();
  updateChatContext();
});
strategy.addEventListener("change", () => {
  resetRepairReport();
  resetRuntimeReport();
  updateChatContext();
});
sourceCode.addEventListener("input", () => {
  resetRepairReport();
  resetRuntimeReport();
  scheduleLanguageDetection();
  updateChatContext();
});
switchDetectedLanguageBtn.addEventListener("click", applyDetectedSourceLanguage);
sampleBtn.addEventListener("click", loadSampleCode);
translateBtn.addEventListener("click", runTranslation);
evaluateBtn.addEventListener("click", () => runDatasetEvaluation(true));
clearBtn.addEventListener("click", clearSource);
copyBtn.addEventListener("click", copyOutput);
downloadProjectBtn.addEventListener("click", downloadTranslatedProject);
uploadBtn.addEventListener("click", () => {
  if (activeModule === "project") {
    requestImport(projectFolderInput);
    return;
  }
  if (activeModule === "ui") {
    requestImport(uiFilesInput);
    return;
  }
  requestImport(fileInput);
});
importConfirmBtn.addEventListener("click", () => {
  const input = pendingImportInput;
  pendingImportInput = null;
  importDialog.close();
  if (input) input.click();
});
importCancelBtn.addEventListener("click", () => importDialog.close());
importDialog.addEventListener("close", () => { pendingImportInput = null; });
fileInput.addEventListener("change", loadFiles);
projectFolderBtn.addEventListener("click", () => requestImport(projectFolderInput));
projectFolderInput.addEventListener("change", async (event) => {
  await loadProjectFilesFromSelection(event.target.files);
  projectFolderInput.value = "";
});
clearProjectFilesBtn.addEventListener("click", () => {
  clearProjectUpload();
  sourceCode.value = "";
  targetCode.textContent = "// 等待上传项目文件";
  setRunState("等待项目文件", "warn");
  resetRepairReport();
  resetRuntimeReport();
  updateChatContext();
});
uiFilesBtn.addEventListener("click", () => requestImport(uiFilesInput));
uiFilesInput.addEventListener("change", async (event) => {
  await loadUiFilesFromSelection(event.target.files);
  uiFilesInput.value = "";
});
clearUiFilesBtn.addEventListener("click", () => {
  clearUiUpload();
  sourceCode.value = "";
  targetCode.textContent = "// 等待上传网页项目";
  setRunState("等待网页文件", "warn");
  resetRepairReport();
  resetRuntimeReport();
  updateChatContext();
});
uiExampleBtns.forEach((button) => {
  button.addEventListener("click", () => applyUiExample(button.dataset.uiExample));
});
healthBtn.addEventListener("click", checkBackend);
exampleSelect.addEventListener("change", () => applyDatasetExample(Number(exampleSelect.value)));
prevExampleBtn.addEventListener("click", () => applyDatasetExample(activeExampleIndex - 1));
nextExampleBtn.addEventListener("click", () => applyDatasetExample(activeExampleIndex + 1));
randomExampleBtn.addEventListener("click", () => {
  if (!datasetExamples.length) {
    return;
  }
  let nextIndex = Math.floor(Math.random() * datasetExamples.length);
  if (datasetExamples.length > 1 && nextIndex === activeExampleIndex) {
    nextIndex = (nextIndex + 1) % datasetExamples.length;
  }
  applyDatasetExample(nextIndex);
});
referenceExampleBtn.addEventListener("click", showDatasetReference);
repairToggle.addEventListener("change", resetRepairReport);
applyRepairBtn.addEventListener("click", () => {
  if (!latestRepairedSource) {
    return;
  }
  sourceCode.value = latestRepairedSource;
  resetRepairReport();
  updateLanguageDetection();
  updateChatContext();
});

chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  sendChatMessage(chatInput.value);
});

chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});

chatInput.addEventListener("input", updateChatInputState);
chatStopBtn.addEventListener("click", () => {
  if (chatAbortController) chatAbortController.abort();
});
clearChatBtn.addEventListener("click", clearChatSession);

refreshHistoryBtn.addEventListener("click", () => loadHistoryRecords());
historyModuleFilter.addEventListener("change", () => loadHistoryRecords());
historyStatusFilter.addEventListener("change", () => loadHistoryRecords());
historySearch.addEventListener("input", () => {
  window.clearTimeout(historySearchTimer);
  historySearchTimer = window.setTimeout(() => loadHistoryRecords(), 260);
});

quickPromptBtns.forEach((button) => {
  button.addEventListener("click", () => {
    const prompt = button.dataset.prompt || button.textContent.trim();
    chatInput.value = prompt;
    sendChatMessage(prompt);
  });
});

initDatasetExamples();
setModule("snippet");
updateChatContext();
restoreChatSession();
updateChatInputState();
loadHistoryRecords(false);
resumeActiveProjectJob();
