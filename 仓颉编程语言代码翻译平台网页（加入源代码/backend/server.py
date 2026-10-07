import argparse
import base64
import hashlib
import hmac
import importlib
import importlib.util
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
import uuid
import zipfile
from collections import Counter
from contextlib import closing
from datetime import datetime
from email.utils import formatdate
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse
from urllib.request import Request, urlopen

from analysis_tools import analyze_project, parse_source
from verification_tools import verify_cangjie_artifact


TRANSLATOR_CACHE = {}
DATASET_CACHE = None
PROJECT_JOBS: dict[str, dict] = {}
PROJECT_JOBS_LOCK = threading.RLock()
WEB_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = WEB_ROOT / "outputs"
HISTORY_DB = WEB_ROOT / "backend" / "data" / "translation_history.db"
SNIPPET_MAX_LINES = 240
SNIPPET_MAX_CHARS = 12000
WEB_UI_MARKER_PATTERN = re.compile(r"<!doctype\s+html|<html\b|</html>|<head\b|<body\b|<script\b|<style\b", re.I)
UI_INTERACTION_PATTERN = re.compile(r"<button\b|<form\b|<input\b|<select\b|<textarea\b|onclick\s*=|addEventListener\s*\(", re.I)
PLACEHOLDER_VALUE_PATTERN = re.compile(r"请.*填写|你的|现有|占位|your[_ -]?|example|xxx+", re.I)


def load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_dotenv_file(WEB_ROOT / ".env")


def configured_value(name: str) -> str:
    """Return a usable environment value; documentation placeholders count as empty."""
    value = os.environ.get(name, "").strip()
    return "" if PLACEHOLDER_VALUE_PATTERN.search(value) else value


def default_repo_path() -> str:
    here = Path(__file__).resolve()
    return str(here.parents[2] / "translator-repo")


def default_local_training_path() -> Path:
    return Path(__file__).resolve().parents[2] / "local_cpu_training"


def get_config() -> dict:
    provider = os.environ.get("TRANSLATOR_PROVIDER", "local_dataset").strip().lower() or "local_dataset"
    return {
        "provider": provider,
        "java_snippet_provider": os.environ.get("JAVA_SNIPPET_PROVIDER", "local_model").strip().lower() or "local_model",
        "repo": os.environ.get("TRANSLATOR_REPO", default_repo_path()),
        "model": os.environ.get("TRANSLATOR_MODEL", "LLAMA3-1"),
        "local_model_python": os.environ.get("LOCAL_MODEL_PYTHON", str(default_local_training_path() / ".venv" / "Scripts" / "python.exe")),
        "local_model_script": os.environ.get("LOCAL_MODEL_SCRIPT", str(default_local_training_path() / "translate_local.py")),
        "local_model_adapter": os.environ.get("LOCAL_MODEL_ADAPTER", str(default_local_training_path() / "runs" / "cpu_3stage_main" / "parallel")),
        "vision_model": os.environ.get("VISION_MODEL", "qwen3-vl-flash"),
        "openai_base_url": configured_value("OPENAI_BASE_URL"),
        "openai_enable_thinking": os.environ.get("OPENAI_ENABLE_THINKING", "false").strip().lower() in {"1", "true", "yes", "on"},
        "openai_api_key_present": bool(configured_value("OPENAI_API_KEY")),
        "spark_app_id_present": bool(os.environ.get("SPARK_APP_ID")),
        "spark_api_key_present": bool(os.environ.get("SPARK_API_KEY")),
        "spark_api_secret_present": bool(os.environ.get("SPARK_API_SECRET")),
        "spark_api_url": os.environ.get("SPARK_API_URL", "wss://spark-api.xf-yun.com/v4.0/chat"),
        "spark_domain": os.environ.get("SPARK_DOMAIN", "4.0Ultra"),
        "spark_api_password_present": bool(os.environ.get("SPARK_API_PASSWORD")),
        "spark_http_url": os.environ.get("SPARK_HTTP_URL", "https://spark-api-open.xf-yun.com/v1/chat/completions"),
        "spark_http_model": os.environ.get("SPARK_HTTP_MODEL", "4.0Ultra"),
        "output_root": os.environ.get("CANGJIE_OUTPUT_ROOT", str(OUTPUT_ROOT)),
        "cangjie_compiler": os.environ.get("CANGJIE_COMPILER", "cjc"),
        "cangjie_project_build": os.environ.get("CANGJIE_PROJECT_BUILD", "cjpm build"),
    }


def config_for_translation(config: dict, source_lang: str, task_type: str) -> dict:
    """Use the trained offline model only for Java snippet requests."""
    if source_lang == "java" and task_type == "snippet":
        return {**config, "provider": config["java_snippet_provider"]}
    return config


def missing_local_model_files(config: dict) -> list[str]:
    missing = [name for name in ("local_model_python", "local_model_script") if not Path(config[name]).is_file()]
    adapter = Path(config["local_model_adapter"])
    for name in ("adapter_config.json", "adapter_model.safetensors"):
        if not (adapter / name).is_file():
            missing.append(name)
    adapter_config = adapter / "adapter_config.json"
    if adapter_config.is_file():
        try:
            base_model = Path(json.loads(adapter_config.read_text(encoding="utf-8"))["base_model_name_or_path"])
            if not (base_model / "model.safetensors").is_file():
                missing.append("base_model/model.safetensors")
        except (OSError, ValueError, KeyError, TypeError):
            missing.append("adapter_config.json (invalid base model path)")
    return missing


def provider_credential_error(*missing: str) -> ValueError:
    joined = ", ".join(name for name in missing if name)
    return ValueError(f"provider credential missing: {joined}")


def configured_provider_missing_credentials(config: dict) -> list[str]:
    if config["provider"] in {"local_dataset", "local_model"}:
        return []
    if config["provider"] == "spark_http":
        return [] if os.environ.get("SPARK_API_PASSWORD", "").strip() else ["SPARK_API_PASSWORD"]
    if config["provider"] == "spark":
        return [
            name for name in ("SPARK_APP_ID", "SPARK_API_KEY", "SPARK_API_SECRET")
            if not os.environ.get(name, "").strip()
        ]
    if config["provider"] in {"openai_repo", "openai_compatible"}:
        return [] if configured_value("OPENAI_API_KEY") else ["OPENAI_API_KEY"]
    return ["TRANSLATOR_PROVIDER"]


def validate_provider_credentials(config: dict) -> dict:
    """Perform a real, minimal provider request. This never fabricates validity."""
    missing = configured_provider_missing_credentials(config)
    if missing:
        return {
            "ok": False,
            "provider": config["provider"],
            "status": "missing_credentials",
            "missing": missing,
            "message": f"Provider credentials are missing: {', '.join(missing)}. Fill .env and restart the backend.",
        }
    if config["provider"] == "local_dataset":
        case_count = len(load_local_dataset(config["repo"]))
        return {
            "ok": case_count > 0,
            "provider": "local_dataset",
            "status": "local_dataset_ready" if case_count > 0 else "local_dataset_empty",
            "message": f"Local Java/Cangjie dataset is ready ({case_count} cases).",
            "dataset_cases": case_count,
        }
    if config["provider"] == "local_model":
        missing = missing_local_model_files(config)
        return {
            "ok": not missing,
            "provider": "local_model",
            "status": "local_model_ready" if not missing else "local_model_missing",
            "message": "Local model files are present." if not missing else f"Missing local model files: {', '.join(missing)}",
        }
    try:
        if config["provider"] == "spark_http":
            reply = call_spark_http(
                config,
                [{"role": "user", "content": "Reply with exactly: CANGJIE_TRANSLATOR_READY"}],
                temperature=0.0,
                max_tokens=16,
            )
        elif config["provider"] == "spark":
            reply = translate_with_spark(config, "class Ping {}", "java", "snippet", "credential-check", "", [])
        else:
            reply = call_model(
                config,
                [{"role": "user", "content": "Reply with exactly: CANGJIE_TRANSLATOR_READY"}],
                temperature=0.0,
                max_tokens=16,
            )
        return {
            "ok": True,
            "provider": config["provider"],
            "status": "validated",
            "message": "Provider accepted a real validation request.",
            "response_preview": limit_text(reply, 160),
        }
    except Exception as exc:
        return {
            "ok": False,
            "provider": config["provider"],
            "status": "invalid_or_unreachable",
            "message": str(exc),
        }


def json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def history_connection() -> sqlite3.Connection:
    HISTORY_DB.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(HISTORY_DB, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=15000")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS translation_history (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL,
            task_type TEXT NOT NULL,
            source_lang TEXT NOT NULL,
            target_lang TEXT NOT NULL DEFAULT 'cangjie',
            strategy TEXT NOT NULL,
            mode TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            duration_ms INTEGER NOT NULL DEFAULT 0,
            source_code TEXT NOT NULL,
            target_code TEXT NOT NULL,
            source_preview TEXT NOT NULL,
            target_preview TEXT NOT NULL,
            source_lines INTEGER NOT NULL DEFAULT 0,
            source_chars INTEGER NOT NULL DEFAULT 0,
            target_lines INTEGER NOT NULL DEFAULT 0,
            target_chars INTEGER NOT NULL DEFAULT 0,
            project_file_count INTEGER NOT NULL DEFAULT 0,
            project_files_json TEXT NOT NULL DEFAULT '[]',
            repair_json TEXT NOT NULL DEFAULT '{}',
            compiler_json TEXT NOT NULL DEFAULT '{}',
            artifact_json TEXT NOT NULL DEFAULT '{}',
            agent_stages_json TEXT NOT NULL DEFAULT '[]',
            dataset_case TEXT NOT NULL DEFAULT '',
            error TEXT NOT NULL DEFAULT ''
        )
        """
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_translation_history_created ON translation_history(created_at DESC)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_translation_history_task ON translation_history(task_type, status)")
    return connection


def compact_preview(text: object, max_chars: int = 180) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    return value if len(value) <= max_chars else value[:max_chars].rstrip() + "…"


def history_title(request: dict, source_code: str) -> str:
    task_type = str(request.get("task_type") or "snippet")
    project_files = request.get("project_files", [])
    if isinstance(project_files, list) and project_files:
        first = project_files[0] if isinstance(project_files[0], dict) else {}
        first_path = str(first.get("path") or "").strip()
        if first_path:
            suffix = f" 等 {len(project_files)} 个文件" if len(project_files) > 1 else ""
            return compact_preview(f"{first_path}{suffix}", 90)
    first_line = next((line.strip() for line in source_code.splitlines() if line.strip()), "未命名翻译")
    labels = {"snippet": "片段", "project": "项目", "ui": "UI"}
    return compact_preview(f"{labels.get(task_type, task_type)} · {first_line}", 90)


def json_field(value: object, fallback: object) -> str:
    try:
        return json.dumps(value if value is not None else fallback, ensure_ascii=False)
    except (TypeError, ValueError):
        return json.dumps(fallback, ensure_ascii=False)


def save_translation_history(
    request: dict,
    result: dict | None,
    status: str,
    duration_ms: int,
    error: str = "",
) -> str:
    config = get_config()
    source_code = str(request.get("source_code") or "")
    target_code = str((result or {}).get("translation") or "")
    raw_project_files = request.get("project_files", [])
    project_files = []
    if isinstance(raw_project_files, list):
        for item in raw_project_files:
            if not isinstance(item, dict):
                continue
            project_files.append({
                "path": str(item.get("path") or ""),
                "language": str(item.get("language") or "Text"),
                "content": str(item.get("content") or ""),
                "lines": int(item.get("lines") or count_non_empty_lines(item.get("content", ""))),
                "original_size": int(item.get("originalSize") or 0),
                "truncated": bool(item.get("truncated", False)),
            })

    record_id = uuid.uuid4().hex
    record = {
        "id": record_id,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "title": history_title(request, source_code),
        "status": status,
        "task_type": str(request.get("task_type") or "snippet"),
        "source_lang": str(request.get("source_lang") or "java"),
        "target_lang": "cangjie",
        "strategy": str(request.get("strategy") or "translator-api"),
        "mode": str(request.get("mode") or "zeroshot"),
        "provider": str((result or {}).get("provider") or config["provider"]),
        "model": str((result or {}).get("model") or config.get("model") or ""),
        "duration_ms": max(int(duration_ms), 0),
        "source_code": source_code,
        "target_code": target_code,
        "source_preview": compact_preview(source_code),
        "target_preview": compact_preview(target_code),
        "source_lines": count_non_empty_lines(source_code),
        "source_chars": len(source_code),
        "target_lines": count_non_empty_lines(target_code),
        "target_chars": len(target_code),
        "project_file_count": len(project_files),
        "project_files_json": json_field(project_files, []),
        "repair_json": json_field((result or {}).get("repair"), {}),
        "compiler_json": json_field((result or {}).get("compiler"), {}),
        "artifact_json": json_field((result or {}).get("artifact"), {}),
        "agent_stages_json": json_field((result or {}).get("agent_stages"), []),
        "dataset_case": str((result or {}).get("dataset_case") or ""),
        "error": limit_text(error, 3000),
    }
    columns = list(record.keys())
    placeholders = ", ".join("?" for _ in columns)
    with closing(history_connection()) as connection:
        with connection:
            connection.execute(
                f"INSERT INTO translation_history ({', '.join(columns)}) VALUES ({placeholders})",
                [record[column] for column in columns],
            )
    return record_id


def run_translation_with_history(request: dict, project_progress=None, project_checkpoint: Path | None = None) -> dict:
    started = time.perf_counter()
    try:
        result = translate_payload(request, project_progress, project_checkpoint)
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started) * 1000)
        try:
            save_translation_history(request, None, "failed", duration_ms, str(exc))
        except Exception:
            pass
        raise

    duration_ms = round((time.perf_counter() - started) * 1000)
    try:
        result["history_id"] = save_translation_history(request, result, "success", duration_ms)
        result["duration_ms"] = duration_ms
    except Exception as exc:
        result["history_id"] = ""
        result["history_warning"] = f"翻译成功，但记录保存失败：{exc}"
        result["duration_ms"] = duration_ms
    return result


def decode_history_row(row: sqlite3.Row, include_content: bool = False) -> dict:
    item = dict(row)
    for key, fallback in (
        ("project_files_json", []),
        ("repair_json", {}),
        ("compiler_json", {}),
        ("artifact_json", {}),
        ("agent_stages_json", []),
    ):
        raw = item.pop(key, "")
        try:
            item[key.removesuffix("_json")] = json.loads(raw) if raw else fallback
        except (TypeError, ValueError):
            item[key.removesuffix("_json")] = fallback
    if not include_content:
        item.pop("source_code", None)
        item.pop("target_code", None)
        item.pop("project_files", None)
        item.pop("repair", None)
        item.pop("compiler", None)
        item.pop("artifact", None)
        item.pop("agent_stages", None)
    return item


def history_list_payload(params: dict[str, list[str]]) -> dict:
    query = str((params.get("q") or [""])[0]).strip().lower()
    task_type = str((params.get("task_type") or [""])[0]).strip().lower()
    status = str((params.get("status") or [""])[0]).strip().lower()
    try:
        limit = min(max(int((params.get("limit") or ["100"])[0]), 1), 200)
    except ValueError:
        limit = 100

    clauses = []
    values: list[object] = []
    if query:
        clauses.append("LOWER(title || ' ' || source_preview || ' ' || target_preview || ' ' || model) LIKE ?")
        values.append(f"%{query}%")
    if task_type:
        clauses.append("task_type = ?")
        values.append(task_type)
    if status:
        clauses.append("status = ?")
        values.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    summary_columns = (
        "id, created_at, title, status, task_type, source_lang, target_lang, strategy, provider, model, "
        "duration_ms, source_preview, target_preview, source_lines, source_chars, target_lines, target_chars, "
        "project_file_count, dataset_case, error"
    )
    with closing(history_connection()) as connection:
        rows = connection.execute(
            f"SELECT {summary_columns} FROM translation_history {where} ORDER BY created_at DESC LIMIT ?",
            [*values, limit],
        ).fetchall()
        stats = dict(connection.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                   SUM(CASE WHEN task_type = 'project' THEN 1 ELSE 0 END) AS projects,
                   COALESCE(SUM(source_chars), 0) AS source_chars,
                   COALESCE(AVG(CASE WHEN status = 'success' THEN duration_ms END), 0) AS average_duration_ms
            FROM translation_history
            """
        ).fetchone())
    return {"ok": True, "items": [dict(row) for row in rows], "stats": stats}


def history_detail_payload(record_id: str) -> dict:
    with closing(history_connection()) as connection:
        row = connection.execute("SELECT * FROM translation_history WHERE id = ?", (record_id,)).fetchone()
    if not row:
        raise KeyError("翻译记录不存在。")
    item = decode_history_row(row, include_content=True)
    if item.get("task_type") == "project" and isinstance(item.get("artifact"), dict):
        try:
            item["artifact"] = restore_project_download(item["artifact"], get_config())
        except (OSError, ValueError):
            pass
    return {"ok": True, "item": item}


def import_translator(repo_path: str):
    repo = Path(repo_path)
    if not repo.exists():
        raise FileNotFoundError(f"Translator repository not found: {repo}")
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    module = importlib.import_module("translator")
    return module.Translator


def get_translator(repo_path: str, model: str):
    cache_key = (str(Path(repo_path).resolve()), model)
    if cache_key not in TRANSLATOR_CACHE:
        translator_cls = import_translator(repo_path)
        TRANSLATOR_CACHE[cache_key] = translator_cls(model_name=model)
    return TRANSLATOR_CACHE[cache_key]


def normalize_code(code: str) -> str:
    return "\n".join(line.rstrip() for line in code.strip().splitlines()).strip()


def count_non_empty_lines(text: str) -> int:
    return sum(1 for line in str(text or "").splitlines() if line.strip())


def validate_snippet_source(source_code: str) -> None:
    line_count = count_non_empty_lines(source_code)
    char_count = len(str(source_code or ""))
    if line_count > SNIPPET_MAX_LINES or char_count > SNIPPET_MAX_CHARS:
        raise ValueError(
            f"片段级翻译要求更短一些，请控制在 {SNIPPET_MAX_LINES} 行或 {SNIPPET_MAX_CHARS} 个字符以内。当前为 {line_count} 行、{char_count} 个字符。"
        )


def validate_web_ui_source(source_code: str, source_lang: str, project_files: list[dict], images: list[dict] | None = None) -> None:
    if str(source_lang or "").strip().lower() != "web":
        raise ValueError("UI 迁移请先把源语言切换为 HTML/CSS/JS。")

    has_html_marker = bool(WEB_UI_MARKER_PATTERN.search(str(source_code or "")))
    has_html_file = any(
        str(file.get("path", "")).lower().endswith((".html", ".htm"))
        for file in (project_files or [])
        if isinstance(file, dict)
    )
    if not has_html_marker and not has_html_file and not images:
        raise ValueError("UI 迁移只接受网页代码，请导入 HTML/CSS/JS 文件，或确保内容包含 HTML 结构。")


def load_local_dataset(repo_path: str) -> dict:
    global DATASET_CACHE
    if DATASET_CACHE is not None:
        return DATASET_CACHE

    dataset_root = Path(repo_path) / "Dataset" / "parallel_j2cj" / "java_cj_parallel"
    examples = {}
    if not dataset_root.exists():
        DATASET_CACHE = examples
        return examples

    for case_dir in dataset_root.iterdir():
        if not case_dir.is_dir():
            continue
        java_files = sorted(case_dir.glob("*.java"))
        cj_files = sorted(case_dir.glob("*.cj"))
        if not java_files or not cj_files:
            continue
        try:
            java_code = java_files[0].read_text(encoding="utf-8", errors="replace")
            cj_code = cj_files[0].read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            continue
        examples[normalize_code(java_code)] = {
            "translation": cj_code,
            "case": case_dir.name,
            "java_file": java_files[0].name,
            "cangjie_file": cj_files[0].name,
        }

    DATASET_CACHE = examples
    return examples


def count_local_dataset_cases(repo_path: str) -> int:
    """Count dataset folders without opening every Java/Cangjie source file.

    The health endpoint is called with a short browser timeout. Fully loading
    more than two thousand examples here made a healthy backend appear offline
    on the first request. Translation/evaluation still use load_local_dataset
    and retain the exact-pair validation there.
    """
    if DATASET_CACHE is not None:
        return len(DATASET_CACHE)

    dataset_root = Path(repo_path) / "Dataset" / "parallel_j2cj" / "java_cj_parallel"
    if not dataset_root.is_dir():
        return 0
    with os.scandir(dataset_root) as entries:
        return sum(1 for entry in entries if entry.is_dir(follow_symlinks=False))


def translate_with_local_dataset(repo_path: str, source_code: str) -> dict | None:
    examples = load_local_dataset(repo_path)
    return examples.get(normalize_code(source_code))


def tokenize_for_bleu(text: str) -> list[str]:
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+|==|!=|<=|>=|&&|\|\||[^\s]", text or "")


def ngram_counts(tokens: list[str], n: int) -> Counter:
    if len(tokens) < n:
        return Counter()
    return Counter(tuple(tokens[index:index + n]) for index in range(len(tokens) - n + 1))


def simple_bleu(candidate: str, reference: str, max_n: int = 4) -> float:
    candidate_tokens = tokenize_for_bleu(candidate)
    reference_tokens = tokenize_for_bleu(reference)
    if not candidate_tokens or not reference_tokens:
        return 0.0

    precisions = []
    for n in range(1, max_n + 1):
        candidate_counts = ngram_counts(candidate_tokens, n)
        reference_counts = ngram_counts(reference_tokens, n)
        if not candidate_counts:
            precisions.append(0.0)
            continue
        overlap = sum(min(count, reference_counts[gram]) for gram, count in candidate_counts.items())
        # Add-one smoothing keeps short snippets from collapsing to zero too easily.
        precisions.append((overlap + 1) / (sum(candidate_counts.values()) + 1))

    brevity_penalty = 1.0
    if len(candidate_tokens) < len(reference_tokens):
        brevity_penalty = math.exp(1 - len(reference_tokens) / max(len(candidate_tokens), 1))

    log_precision = sum(math.log(max(score, 1e-9)) for score in precisions) / max_n
    return round(brevity_penalty * math.exp(log_precision) * 100, 2)


def compiler_status(config: dict) -> dict:
    compiler = str(config.get("cangjie_compiler") or "cjc").split()[0]
    project_build = str(config.get("cangjie_project_build") or "cjpm build").split()[0]
    compiler_path = shutil.which(compiler)
    project_build_path = shutil.which(project_build)
    return {
        "status": "available" if compiler_path or project_build_path else "compiler_unavailable",
        "compiler": compiler,
        "compiler_path": compiler_path or "",
        "project_build": project_build,
        "project_build_path": project_build_path or "",
    }


def evaluate_dataset_payload(request: dict) -> dict:
    config = config_for_translation(get_config(), "java", "snippet")
    examples = load_local_dataset(config["repo"])
    requested_limit = positive_int(request.get("limit")) or 50
    use_model = bool_from_request(request.get("use_model"), True)
    if not use_model:
        raise ValueError("Reference replay evaluation is disabled. Set use_model=true to evaluate real model outputs.")
    limit = min(requested_limit, len(examples), 40)
    rows = []
    exact_matches = 0
    success_count = 0
    bleu_total = 0.0

    for index, (java_code, item) in enumerate(examples.items()):
        if index >= limit:
            break
        reference = str(item.get("translation") or "")
        error = ""
        if use_model:
            try:
                if config["provider"] == "local_dataset":
                    match = translate_with_local_dataset(config["repo"], java_code)
                    if not match:
                        raise RuntimeError("本地数据集未命中当前样例。")
                    candidate = str(match.get("translation") or "")
                elif config["provider"] == "local_model":
                    candidate = translate_with_local_model(config, java_code)
                elif config["provider"] in {"spark_http", "openai_compatible"}:
                    candidate = translate_with_model(config, java_code, "java", "snippet", "translator-api", "", [])
                elif config["provider"] == "spark":
                    candidate = translate_with_spark(config, java_code, "java", "snippet", "translator-api", "", [])
                else:
                    candidate = translate_with_openai_repo(config, java_code, "java", "zeroshot", "", config["model"])
            except Exception as exc:
                candidate = ""
                error = str(exc)
        else:
            raise AssertionError("Reference replay is disabled.")
        success = bool(candidate.strip())
        exact = normalize_code(candidate) == normalize_code(reference)
        bleu = simple_bleu(candidate, reference) if success else 0.0
        success_count += 1 if success else 0
        exact_matches += 1 if exact else 0
        bleu_total += bleu
        rows.append({
            "case": item.get("case", ""),
            "java_file": item.get("java_file", ""),
            "cangjie_file": item.get("cangjie_file", ""),
            "success": success,
            "exact_match": exact,
            "bleu": bleu,
            "source_lines": count_non_empty_lines(java_code),
            "reference_lines": count_non_empty_lines(reference),
            "error": limit_text(error, 500),
        })

    compiler = compiler_status(config)
    return {
        "ok": True,
        "dataset": "parallel_j2cj/java_cj_parallel",
        "evaluation_mode": "dataset_lookup" if config["provider"] == "local_dataset" else "model_translation",
        "repo": config["repo"],
        "total_cases_available": len(examples),
        "cases_evaluated": len(rows),
        "metrics": {
            "translation_success_rate": round(success_count / max(len(rows), 1) * 100, 2),
            "exact_match_rate": round(exact_matches / max(len(rows), 1) * 100, 2),
            "simple_bleu": round(bleu_total / max(len(rows), 1), 2),
            "syntax_status": compiler["status"],
        },
        "compiler": compiler,
        "note": (
            ("This endpoint reports real dataset lookup verification. " if config["provider"] == "local_dataset" else
             "This endpoint reports real model/reference comparison. ") +
            "Syntax pass rate is not fabricated; it stays compiler_unavailable until a local Cangjie compiler or cjpm is configured."
        ),
        "rows": rows[:30],
    }


def sanitize_project_path(path: object, fallback: str) -> str:
    cleaned = str(path or fallback).replace("\\", "/").strip().strip("/")
    cleaned = cleaned.replace("../", "").replace("..\\", "")
    return cleaned or fallback


def sanitize_project_files(raw_files: object) -> list[dict]:
    if not isinstance(raw_files, list):
        return []

    sanitized = []
    for index, item in enumerate(raw_files, start=1):
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "")
        if not content.strip():
            continue
        path = sanitize_project_path(item.get("path"), f"file_{index}.txt")
        language = str(item.get("language") or "").strip() or "Text"
        line_count = positive_int(item.get("lines")) or len([line for line in content.splitlines() if line.strip()])
        sanitized.append({
            "path": path,
            "language": language,
            "content": content,
            "lines": line_count,
            "truncated": bool(item.get("truncated")),
        })
    return sanitized


def format_project_files(project_files: list[dict], fallback_source: str = "") -> str:
    if not project_files:
        return fallback_source

    total_lines = sum(int(file.get("lines") or 0) for file in project_files)
    parts = [
        "project: uploaded-local-project",
        f"uploaded_files: {len(project_files)}",
        f"total_source_lines: {total_lines}",
        "source_format: structured local project files",
    ]
    for file in project_files:
        truncated_note = "\n// note: file content truncated before model input" if file.get("truncated") else ""
        parts.append(
            "\n".join([
                f"// file: {file['path']}",
                f"// language: {file['language']}",
                "```",
                file["content"],
                f"```{truncated_note}",
            ])
        )
    return "\n\n".join(parts)


def build_messages(source_code: str, source_lang: str, task_type: str = "snippet", strategy: str = "translator-api", ast_text: str = "", project_files: list[dict] | None = None) -> list[dict]:
    if task_type == "project":
        project_source = format_project_files(project_files or [], source_code)
        prompt = (
            "You are a multi-agent code migration system for Cangjie programming language.\n"
            "The input is a real local project uploaded by the user. Preserve file boundaries and cross-file relationships.\n\n"
            "Simulate the following agents in order:\n"
            "1. Planner: identify project files, entry points, dependencies, and migration risks.\n"
            "2. Dependency Agent: map imports, classes, functions, and cross-file references.\n"
            "3. Translator Agents: translate each source file into Cangjie source files and create any required Cangjie project files.\n"
            "4. Verifier: review syntax consistency, missing symbols, import/module mapping, and likely build issues.\n\n"
            f"Source language: {source_lang}\n"
            f"Frontend strategy: {strategy}\n\n"
            "Return the migration result in this order:\n"
            "1. `// migration_plan`: concise agent decisions.\n"
            "2. `// file_map`: source path -> generated Cangjie path.\n"
            "3. Generated Cangjie project files. Each generated file must start with `// file: <path>`.\n"
            "4. `// verifier_report`: unresolved dependencies, assumptions, and likely build fixes.\n\n"
            "Do not return a generic template. Translate the concrete uploaded project below. "
            "Keep names consistent across files and prefer compilable Cangjie-style code.\n\n"
            f"{project_source}"
        )
        return [
            {"role": "system", "content": "You coordinate specialized agents for project-level code migration to Cangjie."},
            {"role": "user", "content": prompt},
        ]

    if task_type == "ui":
        prompt = (
            "You are a UI migration assistant for Cangjie programming language.\n"
            "The user may provide webpage UI code such as HTML, CSS, JavaScript, Vue/React-like markup, "
            "or legacy desktop UI snippets. For webpage UI input, the primary goal is fidelity: "
            "the page design, layout, styling, and browser-side interactions must remain unchanged after migration.\n\n"
            "Use this migration strategy for webpage UI code:\n"
            "1. Treat Cangjie as the application runtime that starts a local HTTP service.\n"
            "2. Preserve the original HTML structure, CSS rules, JavaScript DOM/event behavior, text, colors, spacing, and responsive layout as static assets.\n"
            "3. Split inline UI code into `static/index.html`, `static/styles.css`, and `static/app.js` when useful; otherwise preserve inline style/script exactly.\n"
            "4. Generate a Cangjie project entry such as `src/main.cj` that serves the static files and maps `/` to `index.html`.\n"
            "5. If the UI calls backend APIs, generate matching Cangjie HTTP routes or clearly mark the route contract.\n"
            "6. Include a verifier checklist for visual fidelity and clickable interaction tests.\n\n"
            f"Source language: {source_lang}\n"
            f"Input:\n{source_code}\n\n"
            "Return the result in this order:\n"
            "1. `// migration_plan`: summarize preserved UI structure, styling, and interactions.\n"
            "2. `// file_map`: source UI pieces -> generated Cangjie/static project files.\n"
            "3. Generated files. Every file must start with `// file: <path>`.\n"
            "4. `// run_instructions`: commands such as `cjpm run` and the local URL to open.\n"
            "5. `// verifier_report`: list exact UI behavior checks, such as button clicks, forms, DOM updates, and layout fidelity.\n\n"
            "Do not replace the design with a new design. Do not simplify away JavaScript behavior. "
            "Do not return only a conceptual explanation; return concrete generated project files."
        )
        return [
            {"role": "system", "content": "You migrate webpage UI code into a runnable Cangjie-hosted web project while preserving visual and interaction fidelity."},
            {"role": "user", "content": prompt},
        ]

    semantic_rules = (
        "Preserve observable behavior and all control-flow boundary conditions exactly. "
        "In Cangjie, `a..b` excludes `b` while `a..=b` includes `b`: a Java loop using "
        "`i <= end` must use `..=end` (or an exactly equivalent loop), while `i < end` "
        "must use `..end`. Check the translated boundaries before returning code. "
    )
    prompt = (
        f"Please convert the following {source_lang} code into Cangjie programming language. "
        "Only return the code, no additional explanation is required. "
        "Preserve function names and parameter structures exactly. "
        f"{semantic_rules}"
    )
    if ast_text.strip():
        prompt = (
            f"The following is the Abstract Syntax Tree (AST) tokens of the Java code:\n{ast_text}\n\n"
            f"Now translate the following {source_lang} code into Cangjie programming language. "
            "Only return the code, no additional explanation is required. "
            f"{semantic_rules}\n\n"
            f"{source_code}"
        )
    else:
        prompt = f"{prompt}\n\n{source_code}"

    return [
        {"role": "system", "content": "You are a helpful assistant that translates programming code."},
        {"role": "user", "content": prompt},
    ]


def bool_from_request(value: object, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off", "disabled"}
    return bool(value)


def sanitize_image_inputs(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    images = []
    for item in value[:4]:
        if not isinstance(item, dict):
            continue
        data_url = str(item.get("data_url") or "")
        if not re.match(r"^data:image/(png|jpe?g|webp|gif);base64,[A-Za-z0-9+/=]+$", data_url, re.I):
            continue
        if len(data_url) > 8_000_000:
            continue
        images.append({"name": limit_text(item.get("name") or "image", 160), "data_url": data_url})
    return images


def attach_images_to_messages(messages: list[dict], images: list[dict]) -> list[dict]:
    if not images:
        return messages
    result = [dict(message) for message in messages]
    for message in reversed(result):
        if message.get("role") == "user":
            original = str(message.get("content") or "")
            message["content"] = [{"type": "text", "text": original}] + [
                {"type": "image_url", "image_url": {"url": image["data_url"]}}
                for image in images
            ]
            return result
    raise ValueError("Unable to attach image input: no user message exists.")


def number_source_lines(source_code: str) -> str:
    return "\n".join(f"{index}: {line}" for index, line in enumerate(source_code.splitlines(), start=1))


def extract_json_object(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(cleaned[start:end + 1])


def positive_int(value: object) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def sanitize_repair_report(raw_report: dict, source_code: str) -> dict:
    issues = raw_report.get("issues", [])
    if not isinstance(issues, list):
        issues = []

    clean_issues = []
    for item in issues[:30]:
        if not isinstance(item, dict):
            continue
        line_start = positive_int(item.get("line_start") or item.get("line") or item.get("start_line"))
        line_end = positive_int(item.get("line_end") or item.get("end_line") or line_start)
        if line_start and line_end and line_end < line_start:
            line_end = line_start
        clean_issues.append({
            "source_file": sanitize_project_path(item.get("source_file") or item.get("file"), ""),
            "line_start": line_start,
            "line_end": line_end,
            "column": positive_int(item.get("column")),
            "type": str(item.get("type") or item.get("category") or "代码问题")[:80],
            "severity": str(item.get("severity") or "warning")[:40],
            "original": limit_text(item.get("original", ""), 500),
            "explanation": limit_text(item.get("explanation") or item.get("reason") or "", 700),
            "repair": limit_text(item.get("repair") or item.get("fix") or "", 700),
        })

    repaired_code = str(raw_report.get("repaired_code") or source_code).strip()
    needs_repair = bool(raw_report.get("needs_repair")) or bool(raw_report.get("is_incomplete")) or bool(raw_report.get("has_errors"))
    if clean_issues and str(raw_report.get("status", "")).lower() not in {"valid", "ok", "pass"}:
        needs_repair = True

    return {
        "enabled": True,
        "needs_repair": needs_repair,
        "used_for_translation": False,
        "issues": clean_issues,
        "repaired_code": repaired_code,
        "error": "",
    }


def source_language_for_file(path: str, declared_language: str, fallback_language: str) -> str:
    extension = Path(str(path or "")).suffix.lower()
    by_extension = {
        ".py": "python", ".pyw": "python",
        ".java": "java", ".kt": "java", ".kts": "java",
        ".c": "cpp", ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp", ".h": "cpp", ".hpp": "cpp",
        ".html": "html", ".htm": "html", ".css": "css", ".js": "javascript", ".ts": "javascript", ".jsx": "javascript", ".tsx": "javascript",
    }
    return by_extension.get(extension, str(declared_language or fallback_language or "text").lower())


def scan_web_asset_syntax(content: str, language: str) -> dict:
    """Fast local structural check for CSS/JS/HTML without an LLM request."""
    text = str(content or "")
    stack: list[tuple[str, int, int]] = []
    errors: list[dict] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    quote = ""
    escaped = False
    line = 1
    column = 0
    index = 0
    in_line_comment = False
    in_block_comment = False

    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        column += 1
        if char == "\n":
            line += 1
            column = 0
            in_line_comment = False
            index += 1
            continue
        if in_line_comment:
            index += 1
            continue
        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                index += 2
                column += 1
            else:
                index += 1
            continue
        if not quote and char == "/" and next_char == "/" and language == "javascript":
            in_line_comment = True
            index += 2
            column += 1
            continue
        if not quote and char == "/" and next_char == "*":
            in_block_comment = True
            index += 2
            column += 1
            continue
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            index += 1
            continue
        if char in {"'", '"', "`"}:
            quote = char
        elif char in "([{":
            stack.append((char, line, column))
        elif char in ")]}":
            expected = pairs[char]
            if not stack or stack[-1][0] != expected:
                errors.append({"line": line, "column": column, "message": f"unmatched '{char}'"})
            else:
                stack.pop()
        index += 1

    if quote:
        errors.append({"line": line, "column": column, "message": f"unclosed quote {quote}"})
    if in_block_comment:
        errors.append({"line": line, "column": column, "message": "unclosed block comment"})
    for opener, opener_line, opener_column in stack[-8:]:
        errors.append({"line": opener_line, "column": opener_column, "message": f"unclosed '{opener}'"})
    return {"parser": f"local-{language}-scanner", "syntax_ok": not errors, "errors": errors[:30]}


def local_file_diagnostics(project_files: list[dict], source_code: str, source_lang: str, task_type: str) -> dict:
    """Diagnose every uploaded file independently; never send a whole project to JSON repair."""
    files = project_files or [{
        "path": f"main.{source_lang_extension(source_lang)}",
        "language": source_lang,
        "content": source_code,
    }]
    issues = []
    file_checks = []
    for file in files:
        path = sanitize_project_path(file.get("path"), "unknown")
        content = str(file.get("content") or "")
        language = source_language_for_file(path, str(file.get("language") or ""), source_lang)
        if language in {"python", "java", "cpp"}:
            parsed = parse_source(content, language, path)
        elif language in {"html", "css", "javascript"}:
            parsed = scan_web_asset_syntax(content, language)
        else:
            parsed = {"parser": "not_applicable", "syntax_ok": True, "errors": []}

        file_checks.append({"path": path, "language": language, "parser": parsed["parser"], "syntax_ok": parsed["syntax_ok"]})
        for error in parsed.get("errors", [])[:10]:
            issues.append({
                "source_file": path,
                "line_start": positive_int(error.get("line")),
                "line_end": positive_int(error.get("line")),
                "column": positive_int(error.get("column")),
                "type": "文件语法错误",
                "severity": "error",
                "original": "",
                "explanation": str(error.get("message") or "local parser error"),
                "repair": "请先修复该文件后再执行迁移。",
            })
    return {
        "enabled": True,
        "needs_repair": bool(issues),
        "used_for_translation": False,
        "issues": issues[:60],
        "repaired_code": source_code,
        "error": "",
        "diagnostic_source": "逐文件本地语法检查",
        "file_checks": file_checks,
        "repair_mode": "report_only",
    }


def build_repair_messages(source_code: str, source_lang: str, task_type: str, strategy: str) -> list[dict]:
    numbered_source = limit_text(number_source_lines(source_code), 14000)
    prompt = (
        "请检查下面需要迁移到仓颉语言的源代码是否存在语法错误、明显缺失的括号/分号/缩进、"
        "未闭合代码块、残缺函数、残缺类、残缺 UI 事件逻辑或项目级文件内容不完整。\n\n"
        "要求：\n"
        "1. 如果代码作为片段可以被合理翻译，不要因为缺少完整项目外壳而判定为错误。\n"
        "2. 只做最小必要修复，尽量保留原函数名、变量名、参数、业务逻辑和文件标记。\n"
        "3. repaired_code 必须是不带行号的修复后源代码。\n"
        "4. issues 中必须标出错误或不完整位置；能确定行号时填写 line_start/line_end。\n"
        "5. 只返回 JSON，不要 Markdown，不要解释性前后缀。\n\n"
        "JSON 格式：\n"
        "{\n"
        '  "needs_repair": true,\n'
        '  "repaired_code": "...",\n'
        '  "issues": [\n'
        '    {"line_start": 1, "line_end": 1, "column": 1, "type": "syntax_error", "severity": "error", "original": "...", "explanation": "...", "repair": "..."}\n'
        "  ]\n"
        "}\n\n"
        f"源语言：{source_lang}\n"
        f"任务类型：{task_type}\n"
        f"翻译策略：{strategy}\n"
        "带行号的源代码如下：\n"
        f"{numbered_source}"
    )
    return [
        {
            "role": "system",
            "content": (
                "你是代码迁移平台的翻译前诊断与修复智能体。"
                "你只输出可解析 JSON，用于后续自动翻译流程。"
            ),
        },
        {"role": "user", "content": prompt},
    ]


def analyze_and_repair_source(config: dict, source_code: str, source_lang: str, task_type: str, strategy: str) -> dict:
    # Valid snippets do not need a second LLM round-trip. Use the concrete
    # parser first; reserve model repair for syntax errors or unavailable parsers.
    if task_type == "snippet":
        local_report = parse_source(source_code, source_lang)
        if local_report.get("parser") != "unavailable" and local_report.get("syntax_ok"):
            return {
                "enabled": True,
                "needs_repair": False,
                "used_for_translation": False,
                "issues": [],
                "repaired_code": source_code,
                "error": "",
                "diagnostic_source": local_report.get("parser", "local parser"),
            }
    try:
        response_text = call_model(
            config,
            build_repair_messages(source_code, source_lang, task_type, strategy),
            temperature=0.1,
            max_tokens=1200,
            timeout_seconds=9 if task_type == "snippet" else 90,
        )
        parsed = extract_json_object(response_text)
        if not isinstance(parsed, dict):
            raise ValueError("repair model did not return a JSON object")
        return sanitize_repair_report(parsed, source_code)
    except Exception as exc:
        return {
            "enabled": True,
            "needs_repair": False,
            "used_for_translation": False,
            "issues": [],
            "repaired_code": source_code,
            "error": str(exc),
            "diagnostic_source": "model",
        }


def health_payload() -> dict:
    config = get_config()
    snippet_config = config_for_translation(config, "java", "snippet")
    snippet_missing = missing_local_model_files(snippet_config) if snippet_config["provider"] == "local_model" else []
    payload = {
        "ok": True,
        "project_download_supported": True,
        "project_jobs_supported": True,
        "project_whole_supported": True,
        "provider": config["provider"],
        "java_snippet_provider": snippet_config["provider"],
        "java_snippet_model_ready": not snippet_missing if snippet_config["provider"] == "local_model" else None,
        "java_snippet_model_error": f"Missing local model files: {', '.join(snippet_missing)}" if snippet_missing else "",
        "repo": config["repo"],
        "local_dataset_cases": 0,
        "model": config["model"],
        "openai_base_url": config["openai_base_url"],
        "openai_api_key_present": config["openai_api_key_present"],
        "spark_api_url": config["spark_api_url"],
        "spark_domain": config["spark_domain"],
        "spark_http_url": config["spark_http_url"],
        "spark_http_model": config["spark_http_model"],
        "output_root": config["output_root"],
        "compiler_status": compiler_status(config),
        "evaluation_supported": True,
        "repair_supported": config["provider"] in {"spark_http", "openai_compatible"},
        "spark_credentials_present": (
            config["spark_app_id_present"]
            and config["spark_api_key_present"]
            and config["spark_api_secret_present"]
        ),
        "spark_api_password_present": config["spark_api_password_present"],
        "translator_importable": False,
        "import_error": "",
    }

    try:
        payload["local_dataset_cases"] = count_local_dataset_cases(config["repo"])
    except Exception as exc:
        payload["local_dataset_error"] = str(exc)

    if config["provider"] == "spark_http":
        payload["translator_importable"] = True
        return payload

    if config["provider"] == "local_dataset":
        payload["translator_importable"] = payload["local_dataset_cases"] > 0
        if not payload["translator_importable"]:
            payload["import_error"] = "No Java/Cangjie pairs were found in the local dataset."
        return payload

    if config["provider"] == "local_model":
        missing = missing_local_model_files(config)
        payload["translator_importable"] = not missing
        if missing:
            payload["import_error"] = f"Missing local model files: {', '.join(missing)}"
        return payload

    if config["provider"] == "spark":
        try:
            import websocket  # noqa: F401
            payload["translator_importable"] = True
        except Exception as exc:
            payload["import_error"] = str(exc)
        return payload

    if config["provider"] == "openai_compatible":
        # The online provider does not need to import the heavyweight research
        # translator package. Keeping health checks lightweight makes page
        # startup and connection feedback immediate.
        payload["translator_importable"] = importlib.util.find_spec("openai") is not None
        if not payload["translator_importable"]:
            payload["import_error"] = "No module named 'openai'"
        return payload

    try:
        import_translator(config["repo"])
        payload["translator_importable"] = True
    except Exception as exc:
        payload["import_error"] = str(exc)
    return payload


def translate_with_local_model(config: dict, source_code: str, repair_enabled: bool = False) -> str:
    """Run the trained small model fully offline for a Java snippet."""
    command = [
        config["local_model_python"],
        config["local_model_script"],
        "--adapter",
        config["local_model_adapter"],
    ]
    if repair_enabled:
        command.extend(["--repair-iterations", "2"])
    environment = os.environ.copy()
    environment["HF_HUB_OFFLINE"] = "1"
    environment["TRANSFORMERS_OFFLINE"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        command,
        input=source_code,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=240,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"Local model failed: {completed.stderr[-3000:]}")
    translation = completed.stdout.strip()
    if not translation:
        raise RuntimeError("Local model returned empty Cangjie code.")
    return translation


def translate_with_openai_repo(config: dict, source_code: str, source_lang: str, mode: str, ast_text: str, model: str) -> str:
    translator = get_translator(config["repo"], model)
    requested_mode = str(mode or "zeroshot").strip().lower() or "zeroshot"
    try:
        return translator.translate(
            source_code=source_code,
            source_lang=source_lang,
            mode=requested_mode,
            ast_text=ast_text,
            temperature=0.2,
            top_p=1.0,
        )
    except Exception as exc:
        if requested_mode != "zeroshot":
            try:
                return translator.translate(
                    source_code=source_code,
                    source_lang=source_lang,
                    mode="zeroshot",
                    ast_text=ast_text,
                    temperature=0.2,
                    top_p=1.0,
                )
            except Exception as fallback_exc:
                raise RuntimeError(
                    f"Local translator rejected mode '{requested_mode}' and zeroshot fallback also failed: {fallback_exc}"
                ) from exc
        raise


def spark_authorized_url(api_url: str, api_key: str, api_secret: str) -> str:
    parsed = urlparse(api_url)
    host = parsed.netloc
    path = parsed.path or "/"
    date = formatdate(usegmt=True)
    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    signature_sha = hmac.new(
        api_secret.encode("utf-8"),
        signature_origin.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    signature = base64.b64encode(signature_sha).decode("utf-8")
    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")
    query = urlencode({"authorization": authorization, "date": date, "host": host}, quote_via=quote)
    separator = "&" if parsed.query else "?"
    return f"{api_url}{separator}{query}"


def translate_with_spark(config: dict, source_code: str, source_lang: str, task_type: str, strategy: str, ast_text: str, project_files: list[dict] | None = None) -> str:
    try:
        import websocket
    except Exception as exc:
        raise RuntimeError("Missing dependency websocket-client. Run: pip install websocket-client") from exc

    app_id = os.environ.get("SPARK_APP_ID", "").strip()
    api_key = os.environ.get("SPARK_API_KEY", "").strip()
    api_secret = os.environ.get("SPARK_API_SECRET", "").strip()
    if not (app_id and api_key and api_secret):
        raise RuntimeError("SPARK_APP_ID, SPARK_API_KEY and SPARK_API_SECRET are required.")

    api_url = config["spark_api_url"]
    domain = config["spark_domain"]
    messages = build_messages(
        source_code=source_code,
        source_lang=source_lang,
        task_type=task_type,
        strategy=strategy,
        ast_text=ast_text,
        project_files=project_files,
    )
    payload = {
        "header": {
            "app_id": app_id,
            "uid": "cangjie-translator-web",
        },
        "parameter": {
            "chat": {
                "domain": domain,
                "temperature": 0.2,
                "max_tokens": 2048,
            }
        },
        "payload": {
            "message": {
                "text": messages
            }
        },
    }

    ws = websocket.create_connection(spark_authorized_url(api_url, api_key, api_secret), timeout=90)
    try:
        ws.send(json.dumps(payload, ensure_ascii=False))
        chunks = []
        while True:
            raw = ws.recv()
            data = json.loads(raw)
            header = data.get("header", {})
            code = int(header.get("code", 0))
            if code != 0:
                message = header.get("message") or data.get("message") or raw
                raise RuntimeError(f"Spark API error {code}: {message}")

            choices = data.get("payload", {}).get("choices", {})
            for item in choices.get("text", []):
                chunks.append(item.get("content", ""))
            if int(choices.get("status", header.get("status", 2))) == 2:
                break
        return "".join(chunks).strip()
    finally:
        ws.close()


def limit_text(text: object, max_chars: int) -> str:
    value = str(text or "")
    if len(value) <= max_chars:
        return value
    return f"{value[:max_chars]}\n\n...（内容过长，已截断，原始长度 {len(value)} 字符）"


def strip_code_fence(text: str) -> str:
    """Return code-only output when a model wrapped the entire answer in Markdown."""
    value = str(text or "").strip()
    match = re.fullmatch(r"```(?:cangjie|cj|[A-Za-z0-9_-]+)?\s*\n?(.*?)\n?```", value, flags=re.S | re.I)
    return match.group(1).strip() if match else value


def call_spark_http(config: dict, messages: list[dict], temperature: float = 0.2, max_tokens: int = 2048, timeout_seconds: int = 90) -> str:
    api_password = os.environ.get("SPARK_API_PASSWORD", "").strip()
    if not api_password:
        raise provider_credential_error("SPARK_API_PASSWORD")

    body = {
        "model": config["spark_http_model"],
        "messages": messages,
        "stream": False,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = Request(
        config["spark_http_url"],
        data=data,
        headers={
            "Authorization": f"Bearer {api_password}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Spark HTTP request failed: {exc}") from exc

    if "error" in payload:
        error = payload["error"]
        raise RuntimeError(f"Spark HTTP error: {error}")

    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError(f"Spark HTTP returned no choices: {payload}")

    message = choices[0].get("message") or {}
    content = message.get("content", "")
    if isinstance(content, list):
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content).strip()
    return str(content).strip()


def call_openai_compatible(
    config: dict,
    messages: list[dict],
    temperature: float = 0.2,
    max_tokens: int = 2048,
    model: str = "",
    timeout_seconds: int = 90,
) -> str:
    """Send the exact messages to the configured OpenAI-compatible API."""
    try:
        from openai import OpenAI
    except Exception as exc:
        raise RuntimeError("Missing dependency openai. Run: pip install -r backend/requirements.txt") from exc
    api_key = configured_value("OPENAI_API_KEY")
    base_url = str(config.get("openai_base_url") or "").strip()
    selected_model = model or str(config.get("model") or "").strip()
    if not api_key:
        raise provider_credential_error("OPENAI_API_KEY")
    if not base_url:
        raise ValueError("OPENAI_BASE_URL is required for openai_compatible provider.")
    if not selected_model:
        raise ValueError("TRANSLATOR_MODEL is required for openai_compatible provider.")
    client = OpenAI(base_url=base_url, api_key=api_key, timeout=float(timeout_seconds), max_retries=0)
    request_options = {}
    if not config.get("openai_enable_thinking", False):
        request_options["extra_body"] = {"enable_thinking": False}
    response = client.chat.completions.create(
        model=selected_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        **request_options,
    )
    content = response.choices[0].message.content if response.choices else ""
    if not content or not content.strip():
        raise RuntimeError("Model returned an empty response.")
    return strip_code_fence(content)


def stream_openai_compatible(
    config: dict,
    messages: list[dict],
    temperature: float = 0.35,
    max_tokens: int = 1800,
    timeout_seconds: int = 90,
):
    """Yield model text as it arrives from an OpenAI-compatible provider."""
    try:
        from openai import OpenAI
    except Exception as exc:
        raise RuntimeError("Missing dependency openai. Run: pip install -r backend/requirements.txt") from exc

    api_key = configured_value("OPENAI_API_KEY")
    base_url = str(config.get("openai_base_url") or "").strip()
    selected_model = str(config.get("model") or "").strip()
    if not api_key:
        raise provider_credential_error("OPENAI_API_KEY")
    if not base_url:
        raise ValueError("OPENAI_BASE_URL is required for openai_compatible provider.")
    if not selected_model:
        raise ValueError("TRANSLATOR_MODEL is required for openai_compatible provider.")

    client = OpenAI(base_url=base_url, api_key=api_key, timeout=float(timeout_seconds), max_retries=1)
    request_options = {}
    if not config.get("openai_enable_thinking", False):
        request_options["extra_body"] = {"enable_thinking": False}
    response = client.chat.completions.create(
        model=selected_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
        **request_options,
    )
    received = False
    try:
        for chunk in response:
            if not chunk.choices:
                continue
            content = chunk.choices[0].delta.content or ""
            if content:
                received = True
                yield content
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()
    if not received:
        raise RuntimeError("Model returned an empty response.")


def call_model(config: dict, messages: list[dict], temperature: float = 0.2, max_tokens: int = 2048, model: str = "", timeout_seconds: int = 90) -> str:
    if config["provider"] == "spark_http":
        return call_spark_http(config, messages, temperature, max_tokens, timeout_seconds)
    if config["provider"] == "openai_compatible":
        return call_openai_compatible(config, messages, temperature, max_tokens, model, timeout_seconds)
    raise RuntimeError(f"Provider {config['provider']} does not support generic chat messages.")


def transient_model_error(exc: Exception) -> bool:
    """Retry transport failures and provider throttling, not bad requests."""
    current = exc
    while current is not None:
        status = getattr(current, "status_code", None)
        if status == 429 or isinstance(status, int) and status >= 500:
            return True
        if isinstance(current, (ConnectionError, TimeoutError)) or type(current).__name__ in {
            "APIConnectionError", "APITimeoutError", "RateLimitError", "InternalServerError", "URLError"
        }:
            return True
        current = current.__cause__
    return False


def call_project_model(config: dict, messages: list[dict], stage: str, **kwargs) -> str:
    """A short outage must not discard all completed project stages."""
    for attempt in range(3):
        try:
            return call_model(config, messages, **kwargs)
        except Exception as exc:
            if not transient_model_error(exc) or attempt == 2:
                raise RuntimeError(f"项目级{stage}阶段模型请求失败：{exc}") from exc
            time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


def translate_with_spark_http(config: dict, source_code: str, source_lang: str, task_type: str, strategy: str, ast_text: str, project_files: list[dict] | None = None) -> str:
    messages = build_messages(
        source_code=source_code,
        source_lang=source_lang,
        task_type=task_type,
        strategy=strategy,
        ast_text=ast_text,
        project_files=project_files,
    )
    max_tokens = 4096 if task_type == "project" else 2048
    return call_spark_http(config, messages, temperature=0.2, max_tokens=max_tokens)


def translate_with_model(config: dict, source_code: str, source_lang: str, task_type: str, strategy: str, ast_text: str, project_files: list[dict] | None = None, images: list[dict] | None = None) -> str:
    messages = build_messages(source_code, source_lang, task_type, strategy, ast_text, project_files)
    if images:
        if config["provider"] != "openai_compatible":
            raise RuntimeError("Image input requires TRANSLATOR_PROVIDER=openai_compatible and a vision-capable model.")
        messages = attach_images_to_messages(messages, images)
    return call_model(
        config,
        messages,
        temperature=0.2,
        max_tokens=4096 if task_type in {"project", "ui"} else 512,
        model=str(config.get("vision_model") or "") if images else "",
        timeout_seconds=90 if task_type in {"project", "ui"} else 9,
    )


def source_lang_extension(source_lang: str) -> str:
    return {"java": "java", "python": "py", "cpp": "cpp", "web": "html"}.get(source_lang, "txt")


def project_files_for_agent(source_code: str, source_lang: str, project_files: list[dict]) -> list[dict]:
    if project_files:
        return project_files
    return [{
        "path": f"main.{source_lang_extension(source_lang)}",
        "language": source_lang.upper(),
        "content": source_code,
        "lines": count_non_empty_lines(source_code),
        "truncated": False,
    }]


def map_to_cangjie_path(source_path: str) -> str:
    path = sanitize_project_path(source_path, "main.txt")
    lower = path.lower()
    if lower.endswith(("pom.xml", "build.gradle", "settings.gradle", "pyproject.toml", "requirements.txt", "cmakelists.txt")):
        return "cjpm.toml"
    is_test = bool(re.match(r"^(src/)?tests?/", path, flags=re.I))
    path = re.sub(r"^src/main/(java|kotlin|cpp|python)/", "src/", path, flags=re.I)
    path = re.sub(r"^src/test/(java|kotlin|cpp|python)/", "", path, flags=re.I)
    path = re.sub(r"^src/", "", path, flags=re.I)
    path = re.sub(r"^tests?/", "", path, flags=re.I)
    stem = re.sub(r"\.[A-Za-z0-9_+-]+$", "", path)
    # cjpm needs source files in src/ itself; nested folders are separate packages.
    parts = [re.sub(r"\W", "_", part, flags=re.ASCII) for part in PurePosixPath(stem).parts]
    base = "_".join(part for part in parts if part) or "main"
    if base[0].isdigit():
        base = f"_{base}"
    return f"{'tests' if is_test else 'src'}/{base}.cj"


PROJECT_SOURCE_EXTENSIONS = {".java", ".kt", ".kts", ".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".hh", ".py", ".js", ".ts", ".jsx", ".tsx"}
PROJECT_BUILD_FILES = {"pom.xml", "build.gradle", "settings.gradle", "gradlew", "gradlew.bat", "requirements.txt", "pyproject.toml", "cmakelists.txt", "package.json"}
PROJECT_PACKAGE_NAME = "translated_project"
WHOLE_PROJECT_MAX_SOURCE_FILES = 12
WHOLE_PROJECT_MAX_SOURCE_CHARS = 24000


def project_source_file(path: str) -> bool:
    return Path(path).suffix.lower() in PROJECT_SOURCE_EXTENSIONS


def project_package_for_target(path: str) -> str:
    parts = PurePosixPath(path).parts
    folders = parts[1:-1] if parts and parts[0] == "src" else ()
    return ".".join((PROJECT_PACKAGE_NAME, *folders))


def normalize_cangjie_package(content: str, path: str) -> str:
    expected = f"package {project_package_for_target(path)}"
    value = clean_generated_content(content)
    if path.startswith("src/"):
        value = re.sub(
            r"(?m)^(?:public\s+)?(?:static\s+)?(?:func\s+)?main\s*\([^\n)]*\)\s*(?::\s*Unit)?\s*\{",
            "main() {",
            value,
        )
    if re.search(r"(?m)^\s*package\s+[A-Za-z_][\w.]*\s*$", value):
        return re.sub(r"(?m)^\s*package\s+[A-Za-z_][\w.]*\s*$", expected, value, count=1)
    return f"{expected}\n\n{value}"


def default_cjpm_manifest(config: dict) -> str:
    version = str(os.environ.get("CANGJIE_CJC_VERSION") or "").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        command = str(config.get("cangjie_compiler") or "cjc").split()[0]
        try:
            result = subprocess.run([command, "--version"], capture_output=True, text=True, timeout=5, check=False)
            match = re.search(r"Cangjie Compiler:\s*(\d+\.\d+\.\d+)", result.stdout)
            version = match.group(1) if match else "1.0.0"
        except (OSError, subprocess.TimeoutExpired):
            version = "1.0.0"
    return (
        "[package]\n"
        f'cjc-version = "{version}"\n'
        f'name = "{PROJECT_PACKAGE_NAME}"\n'
        'version = "1.0.0"\n'
        'output-type = "executable"\n\n'
        "[dependencies]\n"
    )


def agent_stage(name: str, title: str, status: str, content: str) -> dict:
    return {
        "name": name,
        "title": title,
        "status": status,
        "content": limit_text(content, 5000),
    }


def build_project_stage_messages(stage: str, source_lang: str, strategy: str, files: list[dict], context: dict | None = None) -> list[dict]:
    context = context or {}
    file_summary = "\n".join(
        f"- {file.get('path')} ({file.get('language')}, {file.get('lines')} lines)"
        for file in files
    )
    source_bundle = format_project_files(files, "")
    if stage == "planner":
        prompt = (
            "You are Planner Agent for project-level migration to Cangjie.\n"
            "Analyze the uploaded project and return a concrete migration plan: entry points, source files, build files, risks, and output structure.\n"
            f"Source language: {source_lang}\nStrategy: {strategy}\nFiles:\n{file_summary}\n\n{limit_text(source_bundle, 16000)}"
        )
        system = "You are the project migration planner. Return concise structured text."
    elif stage == "dependency":
        prompt = (
            "You are Dependency Agent for project-level migration to Cangjie.\n"
            "Use the Planner result and source files to map imports, classes, functions, cross-file calls, and external dependencies.\n"
            f"Planner result:\n{limit_text(context.get('planner', ''), 6000)}\n\nFiles:\n{file_summary}\n\n{limit_text(source_bundle, 18000)}"
        )
        system = "You are the dependency analysis agent. Return dependency map and migration constraints."
    elif stage == "translator":
        file = context.get("file", {})
        target_path = context.get("target_path", map_to_cangjie_path(str(file.get("path", "main.txt"))))
        prompt = (
            "You are a file-level Translator Agent for Cangjie migration.\n"
            "Translate this one source file only. Keep identifiers consistent with the dependency map.\n"
            f"Source language: {file.get('language') or source_lang}\n"
            f"Source path: {file.get('path')}\n"
            f"Target path: {target_path}\n\n"
            f"Target package: {project_package_for_target(target_path)}\n"
            f"Planner result:\n{limit_text(context.get('planner', ''), 2500)}\n\n"
            f"Dependency map:\n{limit_text(context.get('dependency', ''), 3500)}\n\n"
            "Return a concrete generated file block starting exactly with:\n"
            f"// file: {target_path}\n\n"
            "For an executable entry point, use a top-level `main() { ... }` declaration; do not write `public static func main(args: Array<String>)`.\n"
            f"Source content:\n```text\n{limit_text(file.get('content', ''), 12000)}\n```"
        )
        system = "You are a Cangjie file translator. Return one file block, not a generic explanation."
    else:
        generated = context.get("generated", "")
        prompt = (
            "You are Verifier Agent for project-level Cangjie migration.\n"
            "Review the generated files for missing symbols, inconsistent names, dependency mismatches, and likely build issues.\n"
            "Return verifier_report with concrete fixes and unresolved assumptions. Do not claim compilation unless compiler output is provided.\n\n"
            f"Planner result:\n{limit_text(context.get('planner', ''), 4000)}\n\n"
            f"Dependency map:\n{limit_text(context.get('dependency', ''), 4000)}\n\n"
            f"Generated files:\n{limit_text(generated, 16000)}"
        )
        system = "You are the migration verifier. Return a rigorous validation report."
    return [{"role": "system", "content": system}, {"role": "user", "content": prompt}]


def clean_generated_content(content: str) -> str:
    text = str(content or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        text = "\n".join(lines).strip()
    lines = text.splitlines()
    if lines and lines[-1].strip() == "```":
        text = "\n".join(lines[:-1]).strip()
    return text.rstrip() + "\n"


def extract_file_blocks(text: str) -> list[dict]:
    matches = list(re.finditer(r"(?m)^//\s*file:\s*(.+?)\s*$", text or ""))
    files = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        path = sanitize_project_path(match.group(1), f"generated_{index + 1}.txt")
        content = clean_generated_content(text[start:end])
        if content.strip():
            files.append({"path": path, "content": content})
    return files


def add_file_if_missing(files: list[dict], path: str, content: str, clean: bool = True) -> None:
    normalized = sanitize_project_path(path, path).lower()
    if not any(sanitize_project_path(file.get("path"), "").lower() == normalized for file in files):
        files.append({"path": sanitize_project_path(path, path), "content": clean_generated_content(content) if clean else content})


def compiler_repair_messages(files: list[dict], build_result: dict) -> list[dict]:
    source_files = [
        file for file in files
        if str(file.get("path") or "").lower().endswith((".cj", ".toml"))
    ]
    file_bundle = "\n\n".join(
        f"// file: {file.get('path')}\n```text\n{file.get('content', '')}\n```"
        for file in source_files
    )
    prompt = (
        "You are the compiler-repair agent in a Cangjie migration pipeline.\n"
        "The following is an actual local compiler/build failure, not a hypothetical review. "
        "Repair only the generated Cangjie project files needed to resolve the reported error. "
        "Return complete replacement files, each beginning exactly with `// file: <existing path>`. "
        "Do not claim success; the host will compile your result again.\n\n"
        f"Command: {build_result.get('command')}\n"
        f"Exit code: {build_result.get('returncode')}\n"
        f"Actual compiler log:\n```text\n{limit_text(build_result.get('log', ''), 12000)}\n```\n\n"
        f"Generated project files:\n{limit_text(file_bundle, 52000)}"
    )
    return [
        {"role": "system", "content": "You repair Cangjie code from real compiler diagnostics and return only replacement file blocks."},
        {"role": "user", "content": prompt},
    ]


def repair_artifact_from_compiler(config: dict, artifact_dir: Path, files: list[dict], initial_build: dict) -> dict:
    """Run at most two model-guided repairs, each gated by an actual failed build."""
    if not initial_build.get("attempted") or initial_build.get("status") != "failed":
        return {
            "attempted": False,
            "status": "not_applicable",
            "reason": "Compiler repair is only entered after a real failed cjc/cjpm invocation.",
            "attempts": [],
            "final_build": initial_build,
        }

    current_files = [dict(file) for file in files]
    current_build = initial_build
    attempts = []
    for attempt_number in range(1, 3):
        try:
            model_output = call_model(
                config,
                compiler_repair_messages(current_files, current_build),
                temperature=0.05,
                max_tokens=7000,
            )
            replacements = extract_file_blocks(model_output)
            allowed_paths = {
                sanitize_project_path(file.get("path"), "").lower()
                for file in current_files
            }
            replacements = [
                file for file in replacements
                if sanitize_project_path(file.get("path"), "").lower() in allowed_paths
            ]
            if not replacements:
                attempts.append({
                    "attempt": attempt_number,
                    "status": "model_output_unusable",
                    "model_output": limit_text(model_output, 4000),
                    "build": current_build,
                })
                break

            replacement_by_path = {
                sanitize_project_path(file.get("path"), "").lower(): clean_generated_content(file.get("content", ""))
                for file in replacements
            }
            changed_paths = []
            for file in current_files:
                normalized = sanitize_project_path(file.get("path"), "").lower()
                if normalized in replacement_by_path:
                    file["content"] = replacement_by_path[normalized]
                    target = artifact_dir / sanitize_project_path(file.get("path"), "generated.txt")
                    target.write_text(file["content"], encoding="utf-8", errors="replace")
                    changed_paths.append(str(file.get("path")))

            current_build = verify_cangjie_artifact(
                str(artifact_dir),
                str(config.get("cangjie_compiler") or "cjc"),
                str(config.get("cangjie_project_build") or "cjpm build"),
            )
            attempts.append({
                "attempt": attempt_number,
                "status": "recompiled",
                "changed_files": changed_paths,
                "build": current_build,
            })
            if current_build.get("build_verified"):
                break
        except Exception as exc:
            attempts.append({
                "attempt": attempt_number,
                "status": "model_or_repair_error",
                "error": str(exc),
                "build": current_build,
            })
            break

    return {
        "attempted": bool(attempts),
        "status": "passed" if current_build.get("build_verified") else "failed",
        "attempts": attempts,
        "final_build": current_build,
    }


def package_project_artifact(artifact_dir: Path, written: list[str]) -> dict:
    """Package generated files after compiler repairs, preserving relative paths."""
    artifact_root = artifact_dir.resolve()
    archive_path = artifact_root / "translated_project.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative_path in dict.fromkeys(written):
            target = (artifact_root / relative_path).resolve()
            target.relative_to(artifact_root)
            if not target.is_file() or target == archive_path:
                raise ValueError(f"Cannot package generated file: {relative_path}")
            archive.write(target, arcname=target.relative_to(artifact_root).as_posix())
    return {
        "download_url": f"/artifacts/{artifact_dir.name}/download",
        "download_name": f"{artifact_dir.name}.zip",
        "download_size": archive_path.stat().st_size,
    }


def restore_project_download(artifact: dict, config: dict) -> dict:
    """Make projects generated by older backends downloadable from history."""
    output_root = Path(str(config.get("output_root") or OUTPUT_ROOT)).resolve()
    artifact_dir = Path(str(artifact.get("output_dir") or "")).resolve()
    if artifact_dir.parent != output_root or not re.fullmatch(r"project_migration_\d{8}_\d{6}_[0-9a-f]{8}", artifact_dir.name):
        raise ValueError("Invalid project artifact directory")
    files = artifact.get("files")
    if not isinstance(files, list) or not files or not all(isinstance(path, str) for path in files):
        raise ValueError("Project artifact has no generated files")
    archive_path = artifact_dir / "translated_project.zip"
    if archive_path.is_file():
        download = {
            "download_url": f"/artifacts/{artifact_dir.name}/download",
            "download_name": f"{artifact_dir.name}.zip",
            "download_size": archive_path.stat().st_size,
        }
    else:
        download = package_project_artifact(artifact_dir, files)
    return {**artifact, **download}


def resolve_project_download(artifact_id: str, config: dict) -> Path:
    if not re.fullmatch(r"project_migration_\d{8}_\d{6}_[0-9a-f]{8}", artifact_id):
        raise ValueError("Invalid project artifact ID")
    output_root = Path(str(config.get("output_root") or OUTPUT_ROOT)).resolve()
    archive_path = (output_root / artifact_id / "translated_project.zip").resolve()
    archive_path.relative_to(output_root)
    if not archive_path.is_file():
        raise FileNotFoundError("Project download is unavailable")
    return archive_path


def write_generated_artifact(task_type: str, files: list[dict], raw_text: str, config: dict, compiler_repair_enabled: bool = True) -> dict:
    output_root = Path(str(config.get("output_root") or OUTPUT_ROOT))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    artifact_dir = output_root / f"{task_type}_{stamp}_{uuid.uuid4().hex[:8]}"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for index, file in enumerate(files, start=1):
        path = sanitize_project_path(file.get("path"), f"generated_{index}.txt")
        target = (artifact_dir / path).resolve()
        target.relative_to(artifact_dir.resolve())
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(file.get("content") or ""), encoding="utf-8", errors="replace")
        written.append(path)

    (artifact_dir / "migration_output.txt").write_text(raw_text or "", encoding="utf-8", errors="replace")
    compiler = compiler_status(config)
    static_index = artifact_dir / "static" / "index.html"
    if not static_index.exists():
        nested_entries = sorted(
            path for path in (artifact_dir / "static").rglob("index.html")
            if path.is_file()
        ) if (artifact_dir / "static").exists() else []
        if nested_entries:
            static_index = nested_entries[0]
    html_preview_url = static_index.resolve().as_uri() if static_index.exists() else ""
    html_text = static_index.read_text(encoding="utf-8", errors="replace") if static_index.exists() else ""
    js_text = "\n".join(
        (artifact_dir / path).read_text(encoding="utf-8", errors="replace")
        for path in written
        if path.lower().endswith((".js", ".jsx", ".tsx", ".ts")) and (artifact_dir / path).exists()
    )
    ui_static_checks = {}
    if task_type == "ui_migration" or not compiler_repair_enabled:
        ui_static_checks = {
            "html_entry_exists": static_index.exists(),
            "html_preview_url": html_preview_url,
            "html_structure_detected": bool(WEB_UI_MARKER_PATTERN.search(html_text)),
            "interactive_markers_detected": bool(UI_INTERACTION_PATTERN.search(html_text) or UI_INTERACTION_PATTERN.search(js_text)),
            "browser_runtime_tested": False,
            "browser_runtime_reason": "Static files are written and previewable by file URL; automated browser interaction testing is not enabled in this backend.",
        }
    build_result = verify_cangjie_artifact(
        str(artifact_dir),
        str(config.get("cangjie_compiler") or "cjc"),
        str(config.get("cangjie_project_build") or "cjpm build"),
    )
    if task_type == "ui_migration" or not compiler_repair_enabled:
        # UI web assets are preserved byte-for-byte. A generic code-repair model
        # cannot invent SDK dependencies safely, so it must not rewrite cjpm.toml.
        compiler_repair = {
            "attempted": False,
            "status": "not_applicable",
            "reason": "Automatic compiler repair is disabled for this migration; the reported build result is from the actual toolchain.",
            "attempts": [],
            "final_build": build_result,
        }
    else:
        compiler_repair = repair_artifact_from_compiler(config, artifact_dir, files, build_result)
    final_build = compiler_repair.get("final_build", build_result)
    validation = {
        "files_written": len(written),
        "compiler_status": compiler["status"],
        "build_attempted": final_build["attempted"],
        "build_verified": final_build["build_verified"],
        "reason": final_build.get("log") or final_build.get("status"),
        "build": final_build,
        "compiler_repair": compiler_repair,
        "ui_static_checks": ui_static_checks,
    }
    download = package_project_artifact(artifact_dir, written) if task_type == "project_migration" else {}
    return {
        "output_dir": str(artifact_dir),
        "files": written,
        "html_preview_url": html_preview_url,
        "validation": validation,
        "compiler": compiler,
        **download,
    }


def ui_static_path(path: str) -> str:
    """Keep uploaded asset names and relative paths intact under static/."""
    clean_path = sanitize_project_path(path, "asset.txt").lstrip("/")
    if clean_path.startswith("static/"):
        return clean_path
    return f"static/{clean_path}"


def ui_content_type(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".mjs": "application/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".html": "text/html; charset=utf-8",
        ".htm": "text/html; charset=utf-8",
    }.get(suffix, "application/octet-stream")


def build_ui_server_source(static_files: list[str], entry_path: str) -> str:
    routes = []
    entry_parent = PurePosixPath(entry_path).parent
    for path in static_files:
        url = "/" + path.removeprefix("static/")
        routes.append(
            f'  server.distributor.register("{url}", {{ ctx => serveText(ctx, "{path}", "{ui_content_type(path)}") }})'
        )
        # The root route serves the entry HTML directly, so relative references
        # inside it resolve from /. Register sibling assets at that location too.
        if PurePosixPath(path).parent == entry_parent and path != entry_path:
            routes.append(
                f'  server.distributor.register("/{PurePosixPath(path).name}", {{ ctx => serveText(ctx, "{path}", "{ui_content_type(path)}") }})'
            )
    route_lines = "\n".join(dict.fromkeys(routes))
    return (
        "// Generated Cangjie HTTP host for migrated static UI assets.\n"
        "package migrated_web_ui\n\n"
        "import net.http.*\n"
        "import std.fs.{File, OpenOption}\n\n"
        "func readAsset(path: String): String {\n"
        "  try (file = File(path, OpenOption.Open(true, false))) {\n"
        "    return String.fromUtf8(file.readToEnd())\n"
        "  }\n"
        "}\n\n"
        "func serveText(ctx: HttpContext, path: String, contentType: String): Unit {\n"
        "  ctx.responseBuilder.header(\"Content-Type\", contentType).body(readAsset(path))\n"
        "}\n\n"
        "main() {\n"
        "  let server = ServerBuilder().addr(\"127.0.0.1\").port(8080).build()\n"
        f'  server.distributor.register("/", {{ ctx => serveText(ctx, "{entry_path}", "text/html; charset=utf-8") }})\n'
        f"{route_lines}\n"
        "  server.distributor.register(\"/api/health\", { ctx => ctx.responseBuilder.body(\"{\\\"ok\\\":true}\") })\n"
        "  server.serve()\n"
        "}\n"
    )


def default_ui_files(source_code: str, project_files: list[dict] | None = None) -> list[dict]:
    files = []
    for file in project_files or []:
        path = str(file.get("path") or "").replace("\\", "/")
        lower = path.lower()
        if lower.endswith((".html", ".htm", ".css", ".js", ".mjs", ".ts", ".jsx", ".tsx", ".json", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp")):
            files.append({"path": ui_static_path(path), "content": clean_generated_content(file.get("content", ""))})

    if not any(str(file["path"]).lower().endswith((".html", ".htm")) for file in files):
        files.append({"path": "static/index.html", "content": clean_generated_content(source_code)})
    static_files = [str(file["path"]) for file in files if str(file["path"]).startswith("static/")]
    entry_path = next(
        (path for path in static_files if PurePosixPath(path).name.lower() in {"index.html", "index.htm"}),
        next((path for path in static_files if path.lower().endswith((".html", ".htm"))), "static/index.html"),
    )
    add_file_if_missing(
        files,
        "cjpm.toml",
        "[package]\n  name = \"migrated_web_ui\"\n  version = \"1.0.0\"\n  cjc-version = \"1.0.0\"\n  output-type = \"executable\"\n",
    )
    add_file_if_missing(
        files,
        "src/main.cj",
        build_ui_server_source(static_files, entry_path),
    )
    return files


def build_ui_manifest_messages(source_code: str, source_lang: str, strategy: str, project_files: list[dict]) -> list[dict]:
    source_bundle = format_project_files(project_files, source_code) if project_files else source_code
    prompt = (
        "You are a UI migration agent. Convert the webpage UI input into a Cangjie-hosted web project manifest.\n"
        "Return JSON only. Do not wrap it in Markdown.\n"
        "The JSON schema is:\n"
        "{\n"
        '  "migration_plan": "...",\n'
        '  "files": [{"path": "static/index.html", "content": "..."}, {"path": "static/styles.css", "content": "..."}, {"path": "static/app.js", "content": "..."}, {"path": "src/main.cj", "content": "..."}],\n'
        '  "run_instructions": ["..."],\n'
        '  "verifier_checklist": ["..."]\n'
        "}\n"
        "Preserve the original page design, DOM text, CSS, JavaScript events, forms, buttons, and responsive behavior. "
        "If source CSS/JS is inline, preserving it inside static/index.html is acceptable.\n\n"
        f"Source language: {source_lang}\nStrategy: {strategy}\nInput:\n{limit_text(source_bundle, 24000)}"
    )
    return [
        {"role": "system", "content": "You output a strict JSON file manifest for Cangjie UI migration."},
        {"role": "user", "content": prompt},
    ]


def parse_ui_manifest(text: str) -> dict:
    parsed = extract_json_object(text)
    if not isinstance(parsed, dict):
        raise ValueError("UI manifest is not a JSON object")
    files = []
    for item in parsed.get("files", []):
        if not isinstance(item, dict):
            continue
        path = sanitize_project_path(item.get("path"), "")
        content = str(item.get("content") or "")
        if path and content.strip():
            files.append({"path": path, "content": clean_generated_content(content)})
    return {
        "migration_plan": str(parsed.get("migration_plan") or ""),
        "files": files,
        "run_instructions": parsed.get("run_instructions", []),
        "verifier_checklist": parsed.get("verifier_checklist", []),
    }


def format_ui_translation_output(manifest: dict, artifact: dict, raw_model_text: str) -> str:
    plan = manifest.get("migration_plan") or "Preserve webpage UI as static assets and serve it with a Cangjie runtime entry."
    run_instructions = manifest.get("run_instructions") if isinstance(manifest.get("run_instructions"), list) else []
    checklist = manifest.get("verifier_checklist") if isinstance(manifest.get("verifier_checklist"), list) else []
    file_lines = "\n".join(f"// - {path}" for path in artifact.get("files", []))
    run_lines = "\n".join(f"// - {item}" for item in run_instructions[:12]) or "// - cjpm run, then open the configured local URL."
    check_lines = "\n".join(f"// - {item}" for item in checklist[:12]) or "// - Check layout, forms, buttons, DOM updates, and responsive behavior."
    compiler_reason = artifact.get("validation", {}).get("reason", "")
    return (
        f"// migration_plan\n// {plan}\n\n"
        f"// artifact_output_dir\n// {artifact.get('output_dir', '')}\n\n"
        f"// generated_files\n{file_lines}\n\n"
        f"// run_instructions\n{run_lines}\n\n"
        f"// verifier_report\n{check_lines}\n"
        f"// compiler_status: {artifact.get('validation', {}).get('compiler_status', 'unknown')}\n"
        f"// build_verified: {artifact.get('validation', {}).get('build_verified', False)}\n"
        f"// unverified_reason: {compiler_reason}\n\n"
        f"// raw_model_manifest_or_output\n{limit_text(raw_model_text, 9000)}"
    ).strip()


def run_ui_migration(config: dict, source_code: str, source_lang: str, strategy: str, project_files: list[dict], images: list[dict] | None = None) -> dict:
    messages = build_ui_manifest_messages(source_code, source_lang, strategy, project_files)
    if images:
        if config["provider"] != "openai_compatible":
            raise RuntimeError("Image UI migration requires an OpenAI-compatible vision provider.")
        messages = attach_images_to_messages(messages, images)
    raw_text = call_model(
        config,
        messages,
        temperature=0.15,
        max_tokens=4096,
        model=str(config.get("vision_model") or "") if images else "",
    )
    try:
        manifest = parse_ui_manifest(raw_text)
    except Exception:
        manifest = {
            "migration_plan": "Model did not return strict JSON; preserved the original UI as static assets and saved raw output.",
            "files": extract_file_blocks(raw_text),
            "run_instructions": ["cjpm run", "open the local HTTP URL served by src/main.cj"],
            "verifier_checklist": ["manual visual comparison", "manual click/form interaction checks"],
        }

    files = manifest.get("files", [])
    default_files = default_ui_files(source_code, project_files)
    if project_files:
        # A local upload is the source of truth. Model JSON is analysis metadata;
        # its copied files can be truncated, renamed, or polluted with source bundles.
        files = list(default_files)
    else:
        authoritative_paths = {"cjpm.toml", "src/main.cj"}
        for file in default_files:
            path = str(file["path"])
            if path.startswith("static/") or path in authoritative_paths:
                files = [item for item in files if str(item.get("path") or "") != path]
                files.append(file)
            else:
                add_file_if_missing(files, path, file["content"])
    manifest["files"] = files
    artifact = write_generated_artifact("ui_migration", files, raw_text, config)
    translation = format_ui_translation_output(manifest, artifact, raw_text)
    return {
        "translation": translation,
        "artifact": artifact,
        "agent_stages": [
            agent_stage("ui_manifest", "UI 文件清单生成", "completed", raw_text),
            agent_stage("artifact_writer", "迁移项目落盘", "completed", json.dumps(artifact, ensure_ascii=False, indent=2)),
        ],
    }


def run_project_file_by_file(config: dict, source_code: str, source_lang: str, strategy: str, project_files: list[dict], progress_callback=None, checkpoint_dir: Path | None = None) -> dict:
    """Call the model once per source file and checkpoint each completed file."""
    files = project_files_for_agent(source_code, source_lang, project_files)
    stages = []

    dependency_graph = analyze_project(files)
    stages.append(agent_stage("dependency_parser", "AST 与依赖解析器", "completed" if dependency_graph["syntax_ok"] else "syntax_errors", json.dumps(dependency_graph, ensure_ascii=False, indent=2)))

    inventory = "\n".join(f"- {file.get('path')} ({file.get('language')})" for file in files)
    dependency = json.dumps({"edges": dependency_graph["edges"], "symbol_owners": dependency_graph["symbol_owners"]}, ensure_ascii=False)

    translated_blocks = []
    translated_file_records = []
    translation_targets = [file for file in files if project_source_file(str(file.get("path") or ""))]
    if not translation_targets:
        raise ValueError("项目中没有可翻译的源代码文件，请选择包含 Java、Python、C/C++ 等源码的文件夹。")
    total = len(translation_targets)
    for index, file in enumerate(translation_targets, start=1):
        target_path = map_to_cangjie_path(str(file.get("path") or f"file_{index}.txt"))
        if progress_callback:
            progress_callback("translating", index - 1, total, str(file.get("path") or ""))
        block = call_project_model(
            config,
            build_project_stage_messages(
                "translator",
                source_lang,
                strategy,
                files,
                {"planner": inventory, "dependency": dependency, "file": file, "target_path": target_path},
            ),
            f"翻译文件 {file.get('path', '')}",
            temperature=0.15,
            max_tokens=2600,
        )
        parsed_blocks = extract_file_blocks(block)
        matching_blocks = [
            item for item in parsed_blocks
            if item["path"].lower() == target_path.lower()
        ]
        if len(matching_blocks) != 1:
            raise ValueError(f"文件 {file.get('path', '')} 的模型输出缺少有效的 // file: {target_path} 文件块。")
        translated_content = normalize_cangjie_package(matching_blocks[0]["content"], target_path)
        translated_blocks.append(f"// file: {target_path}\n{translated_content}")
        translated_file_records.append({"source": file.get("path", ""), "target": target_path, "status": "completed"})
        if checkpoint_dir:
            checkpoint_path = (checkpoint_dir / target_path).resolve()
            checkpoint_path.relative_to(checkpoint_dir.resolve())
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            checkpoint_path.write_text(translated_content, encoding="utf-8")
        if progress_callback:
            progress_callback("translating", index, total, str(file.get("path") or ""))

    generated = "\n\n".join(translated_blocks)
    stages.append(agent_stage("translator", "逐文件翻译", "completed", json.dumps(translated_file_records, ensure_ascii=False, indent=2)))

    translation = (
        f"// source_files\n{inventory}\n\n"
        f"// local_dependency_report\n{dependency}\n\n"
        f"// generated_project_files\n{generated}"
    ).strip()
    files_to_write = extract_file_blocks(generated)
    generated_paths = [item["path"].lower() for item in files_to_write]
    if len(files_to_write) != len(translation_targets) or len(set(generated_paths)) != len(generated_paths):
        raise ValueError("项目生成文件数量或路径不正确，已停止打包不完整的迁移结果。")
    if not any(path.startswith("src/") and path.endswith(".cj") for path in generated_paths):
        raise ValueError("项目没有生成可构建的仓颉 src/ 源文件，已停止打包。")
    add_file_if_missing(files_to_write, "cjpm.toml", default_cjpm_manifest(config))
    for file in files:
        path = str(file.get("path") or "")
        if not project_source_file(path) and Path(path).name.lower() not in PROJECT_BUILD_FILES:
            add_file_if_missing(files_to_write, path, str(file.get("content") or ""), clean=False)
    if progress_callback:
        progress_callback("building", total, total, "")
    artifact = write_generated_artifact("project_migration", files_to_write, translation, config, compiler_repair_enabled=False)
    return {
        "translation": translation,
        "agent_stages": stages,
        "artifact": artifact,
    }


def run_project_as_whole(config: dict, source_code: str, source_lang: str, strategy: str, project_files: list[dict], progress_callback=None) -> dict:
    """Translate a bounded project in one model request, then verify the assembled project."""
    files = project_files_for_agent(source_code, source_lang, project_files)
    sources = [file for file in files if project_source_file(str(file.get("path") or ""))]
    if not sources:
        raise ValueError("项目中没有可翻译的源代码文件。")
    if len(sources) > WHOLE_PROJECT_MAX_SOURCE_FILES:
        raise ValueError(f"项目含 {len(sources)} 个源码文件，超过整项目模型上限 {WHOLE_PROJECT_MAX_SOURCE_FILES} 个；请缩小项目或选择逐文件翻译。")
    if any(file.get("truncated") for file in files):
        raise ValueError("整项目翻译需要完整项目文件；上传的文件已被截断，请缩小项目后重试。")
    source_chars = sum(len(str(file.get("content") or "")) for file in sources)
    if source_chars > WHOLE_PROJECT_MAX_SOURCE_CHARS:
        raise ValueError(f"项目源码共 {source_chars} 字符，超过整项目模型输入上限 {WHOLE_PROJECT_MAX_SOURCE_CHARS} 字符；请缩小项目或选择逐文件翻译。")

    expected_paths = [map_to_cangjie_path(str(file.get("path") or "")) for file in sources]
    if len(set(path.lower() for path in expected_paths)) != len(expected_paths):
        raise ValueError("多个源文件映射到同一个仓颉路径；请调整源文件路径后重试。")
    source_bundle = format_project_files(files, source_code)
    if len(source_bundle) > 36000:
        raise ValueError("项目文件总内容超过整项目模型输入上限 36000 字符；请缩小项目或选择逐文件翻译。")
    graph = analyze_project(files)
    if progress_callback:
        progress_callback("translating_project", 0, len(sources), "")
    expected_map = "\n".join(f"- {file['path']} -> {path}" for file, path in zip(sources, expected_paths))
    prompt = (
        "Translate the following complete small source project into one coherent, compilable Cangjie cjpm project. "
        "Reason about all source files and cross-file references together before writing any output. "
        "Return ONLY complete generated file blocks; every block begins on its own line with `// file: <path>`. "
        "Generate every required Cangjie source file in the exact target path listed below. Do not generate cjpm.toml; the host creates it. "
        "Do not omit, summarize, or leave TODO placeholders for any source file. "
        "Use package translated_project for files directly under src/. "
        "For an executable entry point use top-level `main() { ... }`. "
        "Files under src/ share one package; do not import sibling files as modules. "
        "For Java static helper methods, prefer public top-level functions and call them directly from sibling files. "
        "Keep public symbols and cross-file calls consistent. Avoid dependencies absent from the Cangjie SDK.\n\n"
        f"Source language: {source_lang}\n"
        f"Required source mapping:\n{expected_map}\n\n"
        f"Local dependency analysis:\n{json.dumps({'edges': graph['edges'], 'symbol_owners': graph['symbol_owners']}, ensure_ascii=False)}\n\n"
        f"Full uploaded project:\n{source_bundle}"
    )
    model_output = call_project_model(
        config,
        [{"role": "system", "content": "You are a Cangjie project migration engineer. Produce a complete project, not an explanation."},
         {"role": "user", "content": prompt}],
        "整项目翻译",
        temperature=0.1,
        max_tokens=12000,
        timeout_seconds=600,
    )
    generated = extract_file_blocks(model_output)
    generated_paths = [item["path"].lower() for item in generated]
    missing = sorted(set(path.lower() for path in expected_paths) - set(generated_paths))
    if missing or len(set(generated_paths)) != len(generated_paths):
        raise ValueError(f"整项目模型输出不完整或存在重复文件；缺少：{', '.join(missing) or '无'}。请缩小项目后重试。")
    allowed = set(path.lower() for path in expected_paths)
    for item in generated:
        path = item["path"]
        if path.lower() not in allowed and path.lower() != "cjpm.toml" and not (path.startswith("src/") and path.endswith(".cj")):
            raise ValueError(f"整项目模型输出了不支持的额外文件：{path}")
        if path.lower().endswith(".cj"):
            item["content"] = normalize_cangjie_package(item["content"], path)
    generated = [item for item in generated if item["path"].lower() != "cjpm.toml"]
    add_file_if_missing(generated, "cjpm.toml", default_cjpm_manifest(config))
    for file in files:
        path = str(file.get("path") or "")
        if not project_source_file(path) and Path(path).name.lower() not in PROJECT_BUILD_FILES:
            add_file_if_missing(generated, path, str(file.get("content") or ""), clean=False)
    if progress_callback:
        progress_callback("building", len(sources), len(sources), "")
    artifact = write_generated_artifact("project_migration", generated, model_output, config, compiler_repair_enabled=True)
    return {
        "translation": model_output,
        "agent_stages": [agent_stage("dependency_parser", "本地依赖分析", "completed", json.dumps(graph, ensure_ascii=False)),
                         agent_stage("translator", "整项目模型翻译", "completed", json.dumps({"source_files": len(sources), "generated_files": len(generated)}, ensure_ascii=False))],
        "artifact": artifact,
    }


def translate_payload(request: dict, project_progress=None, project_checkpoint: Path | None = None) -> dict:
    config = get_config()
    source_code = str(request.get("source_code", "")).strip()
    source_lang = str(request.get("source_lang", "java")).strip().lower() or "java"
    mode = str(request.get("mode", "zeroshot")).strip().lower() or "zeroshot"
    task_type = str(request.get("task_type", "snippet")).strip().lower() or "snippet"
    config = config_for_translation(config, source_lang, task_type)
    strategy = str(request.get("strategy", "translator-api")).strip().lower() or "translator-api"
    ast_text = str(request.get("ast_text", ""))
    model = str(request.get("model") or config["model"])
    repair_enabled = bool_from_request(request.get("repair"), True)
    project_files = sanitize_project_files(request.get("project_files", []))
    image_inputs = sanitize_image_inputs(request.get("images", []))
    if task_type == "project" and project_files:
        source_code = format_project_files(project_files, source_code).strip()

    if not source_code:
        raise ValueError("source_code is required.")
    if task_type == "snippet":
        validate_snippet_source(source_code)
    elif task_type == "ui":
        validate_web_ui_source(source_code, source_lang, project_files, image_inputs)

    missing_credentials = configured_provider_missing_credentials(config)
    if missing_credentials:
        raise provider_credential_error(*missing_credentials)

    if config["provider"] not in ["spark", "spark_http", "openai_compatible", "local_dataset"] and (source_lang != "java" or task_type != "snippet"):
        raise ValueError("The selected provider only supports Java snippet translation. Use TRANSLATOR_PROVIDER=openai_compatible for project/UI translation.")
    if config["provider"] == "local_dataset" and (source_lang != "java" or task_type != "snippet"):
        raise ValueError("本地数据集模式支持 Java 片段翻译；项目/UI 迁移需要配置真实的 OpenAI 兼容模型。")

    translation_source_code = source_code
    translation_ast_text = ast_text
    repair_report = {
        "enabled": repair_enabled,
        "needs_repair": False,
        "used_for_translation": False,
        "issues": [],
        "repaired_code": source_code,
        "error": "",
    }

    if repair_enabled and task_type in {"project", "ui"}:
        repair_report = local_file_diagnostics(project_files, source_code, source_lang, task_type)
    elif repair_enabled and config["provider"] in {"spark_http", "openai_compatible"}:
        repair_report = analyze_and_repair_source(config, source_code, source_lang, task_type, strategy)
        repaired_candidate = str(repair_report.get("repaired_code") or "").strip()
        if repair_report.get("needs_repair") and repaired_candidate and repaired_candidate != source_code:
            translation_source_code = repaired_candidate
            translation_ast_text = ""
            repair_report["used_for_translation"] = True
    elif repair_enabled and config["provider"] == "local_model":
        repair_report["error"] = "本地小模型支持编译反馈与案例检索修复，但未接入测试用例的功能等价性验证。"
    elif repair_enabled and config["provider"] != "local_dataset":
        repair_report["error"] = "当前后端 provider 不支持大模型翻译前修复，请使用 TRANSLATOR_PROVIDER=openai_compatible。"

    agent_stages = []
    artifact = None

    if config["provider"] == "local_dataset":
        match = translate_with_local_dataset(config["repo"], translation_source_code)
        if not match:
            raise ValueError(
                "当前 Java 代码未命中本地平行数据集。"
                "请从页面的数据集样例中选择代码，或在 .env 中配置真实的模型接口。"
            )
        translation = str(match.get("translation") or "").strip()
        provider = "local_dataset"
        provider_model = "parallel_j2cj exact-match dataset"
        api_error = ""
        dataset_case = str(match.get("case") or "")
    elif config["provider"] == "local_model":
        translation = translate_with_local_model(config, translation_source_code, repair_enabled)
        provider = "local_model"
        provider_model = "Qwen2.5-0.5B-Instruct + local LoRA"
        api_error = ""
        dataset_case = ""
    elif config["provider"] in {"spark_http", "openai_compatible"}:
        try:
            if task_type == "project":
                migration_result = (run_project_as_whole(config, translation_source_code, source_lang, strategy, project_files, project_progress)
                                    if strategy == "whole-project" else
                                    run_project_file_by_file(config, translation_source_code, source_lang, strategy, project_files, project_progress, project_checkpoint))
                translation = migration_result["translation"]
                agent_stages = migration_result.get("agent_stages", [])
                artifact = migration_result.get("artifact")
            elif task_type == "ui":
                migration_result = run_ui_migration(config, translation_source_code, source_lang, strategy, project_files, image_inputs)
                translation = migration_result["translation"]
                agent_stages = migration_result.get("agent_stages", [])
                artifact = migration_result.get("artifact")
            else:
                translation = translate_with_model(config, translation_source_code, source_lang, task_type, strategy, translation_ast_text, project_files, image_inputs)
            provider = config["provider"]
            provider_model = (f"{config['spark_http_model']} @ {config['spark_http_url']}" if config["provider"] == "spark_http" else f"{config['model']} @ {config['openai_base_url']}")
            api_error = ""
            dataset_case = ""
        except Exception:
            raise
    elif config["provider"] == "spark":
        try:
            translation = translate_with_spark(config, translation_source_code, source_lang, task_type, strategy, translation_ast_text, project_files)
            provider = config["provider"]
            provider_model = f"{config['spark_domain']} @ {config['spark_api_url']}"
            api_error = ""
            dataset_case = ""
        except Exception:
            raise
    else:
        translation = translate_with_openai_repo(config, translation_source_code, source_lang, mode, translation_ast_text, model)
        provider = config["provider"]
        provider_model = model
        api_error = ""
        dataset_case = ""

    return {
        "ok": True,
        "translation": translation,
        "provider": provider,
        "model": provider_model,
        "mode": mode,
        "task_type": task_type,
        "strategy": strategy,
        "api_error": api_error,
        "dataset_case": dataset_case,
        "repo": config["repo"],
        "repair": repair_report,
        "project_file_count": len(project_files),
        "agent_stages": agent_stages,
        "artifact": artifact,
        "compiler": compiler_status(config),
    }


def project_job_snapshot(job_id: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise KeyError("项目翻译任务不存在。")
    with PROJECT_JOBS_LOCK:
        job = PROJECT_JOBS.get(job_id)
        if job is None:
            raise KeyError("项目翻译任务不存在或后端已重启。")
        return {"ok": True, **job.copy()}


def start_project_job(request: dict) -> dict:
    if str(request.get("task_type") or "").lower() != "project":
        raise ValueError("Only project translations can start a project job.")
    files = sanitize_project_files(request.get("project_files", []))
    targets = [file for file in files if project_source_file(str(file.get("path") or ""))]
    if not targets:
        raise ValueError("项目中没有可翻译的源代码文件。")
    config = get_config()
    if config["provider"] not in {"openai_compatible", "spark_http"}:
        raise ValueError("项目逐文件翻译需要配置 OpenAI 兼容或星火 HTTP 模型。")
    missing = configured_provider_missing_credentials(config)
    if missing:
        raise provider_credential_error(*missing)

    job_id = uuid.uuid4().hex
    checkpoint_dir = Path(str(config.get("output_root") or OUTPUT_ROOT)) / "_project_jobs" / job_id
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    job = {
        "job_id": job_id,
        "status": "queued",
        "stage": "queued",
        "completed_files": 0,
        "total_files": len(targets),
        "current_file": "",
        "error": "",
        "result": None,
    }
    with PROJECT_JOBS_LOCK:
        PROJECT_JOBS[job_id] = job

    def update(stage: str, completed: int, total: int, current_file: str) -> None:
        with PROJECT_JOBS_LOCK:
            job.update(status="running", stage=stage, completed_files=completed, total_files=total, current_file=current_file)
            checkpoint = {key: job[key] for key in ("job_id", "status", "stage", "completed_files", "total_files", "current_file", "error")}
        (checkpoint_dir / "progress.json").write_text(json.dumps(checkpoint, ensure_ascii=False), encoding="utf-8")

    def run() -> None:
        try:
            update("analyzing", 0, len(targets), "")
            result = run_translation_with_history(request, update, checkpoint_dir)
            with PROJECT_JOBS_LOCK:
                job.update(status="completed", stage="completed", completed_files=len(targets), current_file="", result=result)
        except Exception as exc:
            with PROJECT_JOBS_LOCK:
                job.update(status="failed", stage="failed", error=str(exc))
        finally:
            with PROJECT_JOBS_LOCK:
                checkpoint = {key: job[key] for key in ("job_id", "status", "stage", "completed_files", "total_files", "current_file", "error")}
            (checkpoint_dir / "progress.json").write_text(json.dumps(checkpoint, ensure_ascii=False), encoding="utf-8")

    threading.Thread(target=run, name=f"project-translation-{job_id[:8]}", daemon=True).start()
    return project_job_snapshot(job_id)


def build_chat_messages(question: str, history: list, context: dict) -> list[dict]:
    source_code = limit_text(context.get("source_code", ""), 9000)
    target_code = limit_text(context.get("target_code", ""), 7000)
    module_label = str(context.get("module_label") or context.get("module") or "未知模块")
    strategy_label = str(context.get("strategy_label") or context.get("strategy") or "未选择")
    source_lang = str(context.get("source_lang_label") or context.get("source_lang") or "未知语言")
    dataset_case = str(context.get("dataset_case") or "无")
    example_title = str(context.get("example_title") or "无")
    project_files = context.get("project_files", [])
    if isinstance(project_files, list) and project_files:
        project_file_summary = "\n".join(
            f"- {file.get('path', 'unknown')} ({file.get('language', 'Text')}, {file.get('lines', 0)} 行)"
            for file in project_files[:30]
            if isinstance(file, dict)
        )
    else:
        project_file_summary = "无"

    messages = [
        {
            "role": "system",
            "content": (
                "你是仓颉编程语言代码翻译平台的智能问答助手。"
                "你需要用中文回答用户关于代码翻译、仓颉语法、片段级翻译、项目级多智能体迁移、"
                "UI 迁移、评估指标和答辩表述的问题。"
                "回答要结合当前上下文，具体、可执行、不要编造不存在的运行结果；不确定时说明依据和限制。"
            ),
        }
    ]

    for item in history[-8:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip()
        content = limit_text(item.get("content", ""), 1800).strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})

    prompt = (
        "当前平台上下文如下：\n"
        f"- 功能模块：{module_label}\n"
        f"- 翻译策略：{strategy_label}\n"
        f"- 源语言：{source_lang}\n"
        f"- 数据集样例：{dataset_case}\n"
        f"- 样例标题：{example_title}\n\n"
        f"项目文件清单：\n{project_file_summary}\n\n"
        "当前源代码：\n"
        f"```text\n{source_code}\n```\n\n"
        "当前翻译输出或参考内容：\n"
        f"```text\n{target_code}\n```\n\n"
        f"用户问题：{question}\n\n"
        "请直接回答问题；如果需要指出代码修改建议，请给出清晰的小段代码或步骤。"
    )
    messages.append({"role": "user", "content": prompt})
    return messages


def chat_payload(request: dict) -> dict:
    config = get_config()
    question = str(request.get("question", "")).strip()
    history = request.get("history", [])
    context = request.get("context", {})

    if not question:
        raise ValueError("question is required.")
    if not isinstance(history, list):
        history = []
    if not isinstance(context, dict):
        context = {}
    if config["provider"] == "local_dataset":
        source_code = str(context.get("source_code") or "").strip()
        match = translate_with_local_dataset(config["repo"], source_code) if source_code else None
        match_text = (
            f"当前代码已命中本地数据集样例 {match.get('case')}，可以直接点击“开始智能翻译”。"
            if match else
            "当前代码未命中本地数据集；请选择页面内置样例，或配置真实模型密钥。"
        )
        return {
            "ok": True,
            "answer": f"当前为离线数据集模式。{match_text}\n\n你的问题是：{question}",
            "provider": "local_dataset",
            "model": "parallel_j2cj exact-match dataset",
        }
    if config["provider"] not in {"spark_http", "openai_compatible"}:
        raise RuntimeError("智能问答当前需要支持 Chat Completions 的 provider。")

    messages = build_chat_messages(question, history, context)
    answer = call_model(config, messages, temperature=0.35, max_tokens=1800)
    return {
        "ok": True,
        "answer": answer,
        "provider": config["provider"],
        "model": (f"{config['spark_http_model']} @ {config['spark_http_url']}" if config["provider"] == "spark_http" else f"{config['model']} @ {config['openai_base_url']}"),
    }


def stream_chat_events(request: dict):
    """Yield newline-delimited chat events so the browser can paint immediately."""
    config = get_config()
    question = str(request.get("question", "")).strip()
    history = request.get("history", [])
    context = request.get("context", {})
    if not question:
        raise ValueError("question is required.")
    if not isinstance(history, list):
        history = []
    if not isinstance(context, dict):
        context = {}

    if config["provider"] == "local_dataset":
        source_code = str(context.get("source_code") or "").strip()
        match = translate_with_local_dataset(config["repo"], source_code) if source_code else None
        answer = (
            f"当前为离线数据集模式。当前代码已命中本地数据集样例 {match.get('case')}，"
            "可以直接点击“运行翻译”。"
            if match else
            "当前为离线数据集模式。当前代码未命中本地数据集；请选择页面内置样例，或配置真实模型密钥。"
        )
        yield {"type": "meta", "provider": "local_dataset", "model": "本地数据集"}
        yield {"type": "delta", "content": f"{answer}\n\n你的问题是：{question}"}
        yield {"type": "done"}
        return

    if config["provider"] not in {"spark_http", "openai_compatible"}:
        raise RuntimeError("智能问答当前需要支持 Chat Completions 的 provider。")

    messages = build_chat_messages(question, history, context)
    model_label = config["spark_http_model"] if config["provider"] == "spark_http" else config["model"]
    yield {"type": "meta", "provider": config["provider"], "model": model_label}

    if config["provider"] == "openai_compatible":
        for delta in stream_openai_compatible(config, messages):
            yield {"type": "delta", "content": delta}
    else:
        # Spark's configured HTTP endpoint is not guaranteed to expose a
        # compatible event stream. Keep one browser protocol and progressively
        # paint its complete response in readable chunks.
        answer = call_spark_http(config, messages, temperature=0.35, max_tokens=1800)
        for start in range(0, len(answer), 48):
            yield {"type": "delta", "content": answer[start:start + 48]}
    yield {"type": "done"}


class Handler(BaseHTTPRequestHandler):
    server_version = "CangjieTranslatorAPI/0.9"

    STATIC_TYPES = {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def send_json(self, status: int, payload: dict):
        data = json_bytes(payload)
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            # The browser can cancel a long request while the model is still
            # responding. That must not turn into a server-side failure.
            return

    def send_chat_stream(self, request: dict):
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            for event in stream_chat_events(request):
                line = json.dumps(event, ensure_ascii=False).encode("utf-8") + b"\n"
                self.wfile.write(line)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return
        except Exception as exc:
            try:
                line = json.dumps({"type": "error", "error": str(exc)}, ensure_ascii=False).encode("utf-8") + b"\n"
                self.wfile.write(line)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                return

    def do_OPTIONS(self):
        self.send_json(200, {"ok": True})

    def do_GET(self):
        parsed = urlparse(self.path)
        request_path = unquote(parsed.path).rstrip("/") or "/"
        if request_path == "/health":
            self.send_json(200, health_payload())
            return
        if request_path.startswith("/project-jobs/"):
            try:
                self.send_json(200, project_job_snapshot(request_path.rsplit("/", 1)[-1]))
            except KeyError as exc:
                self.send_json(404, {"ok": False, "error": str(exc.args[0])})
            return
        if request_path.startswith("/artifacts/"):
            parts = request_path.split("/")
            if len(parts) != 4 or parts[3] != "download":
                self.send_json(404, {"ok": False, "error": "Not found"})
                return
            try:
                archive_path = resolve_project_download(parts[2], get_config())
                data = archive_path.read_bytes()
            except (ValueError, OSError):
                self.send_json(404, {"ok": False, "error": "项目下载文件不存在或已被清理。"})
                return
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition", f'attachment; filename="{parts[2]}.zip"')
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                pass
            return
        if request_path == "/history":
            try:
                self.send_json(200, history_list_payload(parse_qs(parsed.query)))
            except Exception as exc:
                self.send_json(500, {"ok": False, "error": str(exc)})
            return
        if request_path.startswith("/history/"):
            record_id = request_path.split("/", 2)[2]
            try:
                self.send_json(200, history_detail_payload(record_id))
            except KeyError as exc:
                self.send_json(404, {"ok": False, "error": str(exc.args[0])})
            except Exception as exc:
                self.send_json(500, {"ok": False, "error": str(exc)})
            return
        if request_path.startswith("/"):
            relative_path = "index.html" if request_path == "/" else request_path.lstrip("/")
            target = (WEB_ROOT / relative_path).resolve()
            try:
                target.relative_to(WEB_ROOT.resolve())
                is_safe_path = True
            except ValueError:
                is_safe_path = False
            if is_safe_path and target.is_file() and target.suffix.lower() in self.STATIC_TYPES:
                data = target.read_bytes()
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", self.STATIC_TYPES.get(target.suffix.lower(), "application/octet-stream"))
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                    return
                return
        self.send_json(404, {"ok": False, "error": "Not found"})

    def do_POST(self):
        path = self.path.rstrip("/")
        if path not in {"/translate", "/project-jobs", "/chat", "/chat/stream", "/evaluate", "/credentials/validate"}:
            self.send_json(404, {"ok": False, "error": "Not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            request = json.loads(raw) if raw else {}
            if path == "/project-jobs":
                self.send_json(202, start_project_job(request))
            elif path == "/chat/stream":
                self.send_chat_stream(request)
            elif path == "/chat":
                self.send_json(200, chat_payload(request))
            elif path == "/credentials/validate":
                self.send_json(200, validate_provider_credentials(get_config()))
            elif path == "/evaluate":
                self.send_json(200, evaluate_dataset_payload(request))
            else:
                self.send_json(200, run_translation_with_history(request))
        except Exception as exc:
            self.send_json(
                500,
                {
                    "ok": False,
                    "error": str(exc),
                    "traceback": traceback.format_exc(limit=4),
                },
            )

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main():
    parser = argparse.ArgumentParser(description="Local API bridge for Cangjie translation.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--check", action="store_true", help="Print health payload and exit.")
    parser.add_argument("--validate-credentials", action="store_true", help="Send a real minimal provider request and exit.")
    args = parser.parse_args()

    if args.check:
        print(json.dumps(health_payload(), ensure_ascii=False, indent=2))
        return
    if args.validate_credentials:
        result = validate_provider_credentials(get_config())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(0 if result.get("ok") else 2)

    ThreadingHTTPServer.daemon_threads = True
    # On Windows, address reuse can leave multiple backend instances bound to
    # the same port and requests may then hit stale configuration at random.
    ThreadingHTTPServer.allow_reuse_address = False
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    config = get_config()
    print(f"Translator API listening on http://{args.host}:{args.port}")
    print(f"Provider: {config['provider']}")
    print(f"Spark domain: {config['spark_domain']}")
    print(f"Spark HTTP model: {config['spark_http_model']}")
    print(f"Using translator repo: {config['repo']}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
