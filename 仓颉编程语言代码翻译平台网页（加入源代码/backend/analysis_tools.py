"""Concrete source parsing helpers used before project translation.

Python uses its standard AST. Java/C++ use tree-sitter grammars. The module
returns parser evidence, imports, declared symbols and unresolved syntax errors;
it never asks an LLM to pretend a dependency graph exists.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path


def _tree_sitter_parser(language: str):
    from tree_sitter import Language, Parser
    if language == "java":
        import tree_sitter_java as grammar
    elif language in {"cpp", "c", "c++"}:
        import tree_sitter_cpp as grammar
    else:
        import tree_sitter_python as grammar
    return Parser(Language(grammar.language()))


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)


def parse_source(content: str, language: str, path: str = "") -> dict:
    language = (language or "").lower()
    if language not in {"python", "java", "cpp", "c", "c++"}:
        return {"parser": "not_applicable", "syntax_ok": True, "imports": [], "symbols": [], "errors": []}
    if language == "python":
        try:
            tree = ast.parse(content, filename=path or "source.py")
            imports = []
            symbols = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.append((node.module or "") + "." + ".".join(a.name for a in node.names))
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    symbols.append(node.name)
            return {"parser": "python.ast", "syntax_ok": True, "imports": imports, "symbols": symbols, "errors": []}
        except SyntaxError as exc:
            return {"parser": "python.ast", "syntax_ok": False, "imports": [], "symbols": [], "errors": [{"line": exc.lineno, "column": exc.offset, "message": exc.msg}]}

    try:
        parser = _tree_sitter_parser(language)
        tree = parser.parse(content.encode("utf-8"))
        root = tree.root_node
        imports = []
        symbols = []
        errors = []
        for node in _walk(root):
            text = content[node.start_byte:node.end_byte]
            if node.type in {"import_declaration", "import_header", "preproc_include"}:
                imports.append(text.strip())
            if node.type in {"class_declaration", "interface_declaration", "enum_declaration", "method_declaration", "function_definition"}:
                match = re.search(r"(?:class|interface|enum|def|func|void|int|String|bool|auto)\\s+([A-Za-z_]\\w*)", text)
                if match:
                    symbols.append(match.group(1))
            if node.type == "ERROR" or node.is_missing:
                errors.append({"line": node.start_point.row + 1, "column": node.start_point.column + 1, "message": f"tree-sitter {node.type}"})
        return {"parser": f"tree-sitter-{language}", "syntax_ok": not root.has_error and not errors, "imports": imports, "symbols": sorted(set(symbols)), "errors": errors[:30]}
    except Exception as exc:
        return {"parser": "unavailable", "syntax_ok": False, "imports": [], "symbols": [], "errors": [{"line": 0, "column": 0, "message": str(exc)}]}


def analyze_project(files: list[dict]) -> dict:
    nodes = []
    symbol_owners = {}
    for file in files:
        path = str(file.get("path") or "")
        language = str(file.get("language") or "").lower()
        parsed = parse_source(str(file.get("content") or ""), language, path)
        node = {"path": path, "language": language, **parsed}
        nodes.append(node)
        for symbol in parsed["symbols"]:
            symbol_owners.setdefault(symbol, []).append(path)
    edges = []
    for node in nodes:
        for imported in node["imports"]:
            target = imported.replace("import", "").replace(";", "").strip().replace(".", "/")
            matches = [other["path"] for other in nodes if target and (target in other["path"].replace("\\", "/") or Path(other["path"]).stem in imported)]
            edges.append({"from": node["path"], "import": imported, "targets": matches})
    return {"parser": "tree-sitter/python.ast", "files": nodes, "edges": edges, "symbol_owners": symbol_owners, "syntax_ok": all(node["syntax_ok"] for node in nodes)}
