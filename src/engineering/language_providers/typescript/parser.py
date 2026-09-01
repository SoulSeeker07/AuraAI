"""
TypeScript & JSX AST Parser
===========================
Location: src/engineering/language_providers/typescript/parser.py

Tree-sitter powered AST parser and symbol extraction engine for TypeScript (.ts),
TypeScript JSX (.tsx), JavaScript (.js), and JavaScript JSX (.jsx).

Extracts:
- Functions, Arrow Functions & React Functional Components (with JSX detection)
- TypeScript Interfaces & Type Aliases
- Enums & ES6 Classes with Methods
- React Hooks & Hook Dependency Arrays (useEffect, useCallback, useMemo)
- ES6 / CommonJS Imports, Exports & Re-exports
- Call Edges & JSX Component Usage
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Tuple, List, Dict, Set

import tree_sitter_javascript as tsj
import tree_sitter_typescript as tst
from tree_sitter import Language, Node, Parser, Tree, Query, QueryCursor

from ...symbol_graph import Symbol, SymbolType

logger = logging.getLogger(__name__)


@dataclass
class HookInfo:
    """Represents a React hook call found in component/function body."""
    name: str
    line: int
    dependencies: list[str] = field(default_factory=list)


@dataclass
class ParsedTypeScriptFile:
    """Structured extraction output from a parsed TypeScript/JavaScript file."""
    file_path: str
    language: str
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[dict[str, Any]] = field(default_factory=list)
    exports: list[dict[str, Any]] = field(default_factory=list)
    call_edges: list[tuple[str, str]] = field(default_factory=list)  # (caller_name, callee_name)
    hooks: list[HookInfo] = field(default_factory=list)
    jsx_elements_used: list[str] = field(default_factory=list)


class TypeScriptASTParser:
    """
    High-performance, in-process AST parser for JS/TS/JSX/TSX.
    """

    def __init__(self) -> None:
        self._ts_language = Language(tst.language_typescript())
        self._tsx_language = Language(tst.language_tsx())
        self._js_language = Language(tsj.language())

        self._ts_parser = Parser(self._ts_language)
        self._tsx_parser = Parser(self._tsx_language)
        self._js_parser = Parser(self._js_language)

    def _get_parser_and_lang(self, file_path: str | Path) -> tuple[Parser, str]:
        ext = Path(file_path).suffix.lower()
        if ext == ".tsx":
            return self._tsx_parser, "tsx"
        elif ext == ".ts":
            return self._ts_parser, "typescript"
        elif ext == ".jsx":
            return self._js_parser, "jsx"
        else:
            return self._js_parser, "javascript"

    def parse_source(self, source: str | bytes, file_path: str | Path = "temp.tsx") -> ParsedTypeScriptFile:
        """
        Parses source code and returns comprehensive symbol and dependency metadata.
        """
        if isinstance(source, str):
            source_bytes = source.encode("utf-8")
        else:
            source_bytes = source

        file_path_str = str(file_path)
        parser, lang_name = self._get_parser_and_lang(file_path)
        tree = parser.parse(source_bytes)

        result = ParsedTypeScriptFile(
            file_path=file_path_str,
            language=lang_name,
        )

        root = tree.root_node
        for idx in range(root.named_child_count):
            child = root.named_child(idx)
            if child:
                self._visit_node(child, source_bytes, result, file_path_str, is_exported=False)

        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Import & Export Extraction
    # ─────────────────────────────────────────────────────────────────────────
    def _parse_import_statement(self, node: Node, source: bytes, result: ParsedTypeScriptFile) -> None:
        module_path = ""
        imported_symbols: list[str] = []
        is_type_only = b"type" in source[node.start_byte : node.start_byte + 30].split()

        for idx in range(node.named_child_count):
            child = node.named_child(idx)
            if not child:
                continue
            if child.type == "import_clause":
                for c_idx in range(child.named_child_count):
                    clause_child = child.named_child(c_idx)
                    if not clause_child:
                        continue
                    if clause_child.type == "identifier":
                        imported_symbols.append(self._get_node_text(clause_child, source))
                    elif clause_child.type == "named_imports":
                        for s_idx in range(clause_child.named_child_count):
                            spec = clause_child.named_child(s_idx)
                            if spec and spec.type == "import_specifier":
                                name_node = spec.child_by_field_name("name") or (spec.named_child(0) if spec.named_child_count else None)
                                if name_node:
                                    imported_symbols.append(self._get_node_text(name_node, source))
                    elif clause_child.type == "namespace_import":
                        for n_idx in range(clause_child.named_child_count):
                            ns_child = clause_child.named_child(n_idx)
                            if ns_child and ns_child.type == "identifier":
                                imported_symbols.append(f"* as {self._get_node_text(ns_child, source)}")
            elif child.type == "string":
                module_path = self._get_node_text(child, source).strip("'\"`")

        if module_path:
            line_no = self._get_line_number(node, source)
            result.imports.append({
                "module": module_path,
                "symbols": imported_symbols,
                "is_type_only": is_type_only,
                "line": line_no,
            })
            sym = Symbol(
                name=f"import:{module_path}",
                symbol_type=SymbolType.IMPORT,
                file_path=result.file_path,
                line_number=line_no,
                module=module_path,
                imports=imported_symbols,
                tags=["type_only"] if is_type_only else [],
            )
            result.symbols.append(sym)

    # ─────────────────────────────────────────────────────────────────────────
    # Node Visiting & Declarations Extraction
    # ─────────────────────────────────────────────────────────────────────────
    def _visit_node(
        self,
        node: Node,
        source: bytes,
        result: ParsedTypeScriptFile,
        file_path_str: str,
        is_exported: bool = False,
    ) -> None:
        node_type = node.type

        if node_type == "import_statement":
            self._parse_import_statement(node, source, result)
            return

        if node_type == "export_statement":
            source_module = ""
            exported_names: list[str] = []
            is_default = b"default" in source[node.start_byte : node.start_byte + 30].split()

            for idx in range(node.named_child_count):
                child = node.named_child(idx)
                if not child:
                    continue
                if child.type == "export_clause":
                    for s_idx in range(child.named_child_count):
                        spec = child.named_child(s_idx)
                        if spec and spec.type == "export_specifier":
                            name_node = spec.child_by_field_name("name") or (spec.named_child(0) if spec.named_child_count else None)
                            if name_node:
                                exported_names.append(self._get_node_text(name_node, source))
                elif child.type == "string":
                    source_module = self._get_node_text(child, source).strip("'\"`")
                elif child.type == "identifier":
                    exported_names.append(self._get_node_text(child, source))
                else:
                    self._visit_node(child, source, result, file_path_str, is_exported=True)

            result.exports.append({
                "names": exported_names,
                "is_default": is_default,
                "source_module": source_module,
                "line": self._get_line_number(node, source),
            })
            return

        if node_type == "ambient_declaration":
            body = node.child_by_field_name("body") or (node.named_child(0) if node.named_child_count else None)
            if body:
                if body.type == "statement_block":
                    for idx in range(body.named_child_count):
                        child = body.named_child(idx)
                        if child:
                            self._visit_node(child, source, result, file_path_str, is_exported)
                else:
                    self._visit_node(body, source, result, file_path_str, is_exported)
            return

        if node_type == "ERROR":
            # Search children for declarations that might be partially parsed
            children = node.children
            for i, child in enumerate(children):
                if child.type == "function" and i + 1 < len(children) and children[i + 1].type == "identifier":
                    fn_name = self._get_node_text(children[i + 1], source)
                    sym = Symbol(
                        name=fn_name,
                        symbol_type=SymbolType.FUNCTION,
                        file_path=file_path_str,
                        line_number=self._get_line_number(child, source),
                        is_public=is_exported,
                        tags=["partially_parsed"],
                    )
                    result.symbols.append(sym)
                else:
                    self._visit_node(child, source, result, file_path_str, is_exported)
            return

        if node_type == "function_declaration":
            self._parse_function_declaration(node, source, result, file_path_str, is_exported)
        elif node_type == "interface_declaration":
            self._parse_interface_declaration(node, source, result, file_path_str, is_exported)
        elif node_type == "type_alias_declaration":
            self._parse_type_alias_declaration(node, source, result, file_path_str, is_exported)
        elif node_type == "enum_declaration":
            self._parse_enum_declaration(node, source, result, file_path_str, is_exported)
        elif node_type == "class_declaration":
            self._parse_class_declaration(node, source, result, file_path_str, is_exported)
        elif node_type in ("lexical_declaration", "variable_declaration"):
            self._parse_variable_declarations(node, source, result, file_path_str, is_exported)

    # ─────────────────────────────────────────────────────────────────────────
    # Functions & Components
    # ─────────────────────────────────────────────────────────────────────────
    def _parse_function_declaration(
        self, node: Node, source: bytes, result: ParsedTypeScriptFile, file_path_str: str, is_exported: bool
    ) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        func_name = self._get_node_text(name_node, source)
        line_num = self._get_line_number(node, source)
        params, return_type = self._extract_params_and_return_type(node, source)
        docstring = self._extract_leading_docstring(node, source)

        tags = []
        if is_exported:
            tags.append("exported")
        if func_name.startswith("use") and len(func_name) > 3 and func_name[3].isupper():
            tags.append("react_hook")

        # Extract internal calls, hooks, and dependencies
        hooks_found, calls_found, jsx_used, has_jsx = self._analyze_body(node, source, result.language)
        for h in hooks_found:
            result.hooks.append(h)
            # Store dependency metadata in symbol tags
            if h.dependencies:
                dep_str = ",".join(h.dependencies)
                tags.append(f"hook_deps:{h.name}#[{dep_str}]")
            tags.append(f"hook_call:{h.name}")

        for callee in calls_found:
            result.call_edges.append((func_name, callee))
        result.jsx_elements_used.extend(jsx_used)

        if self._is_react_component_name(func_name) or has_jsx:
            tags.append("react_component")

        sym = Symbol(
            name=func_name,
            symbol_type=SymbolType.FUNCTION,
            file_path=file_path_str,
            line_number=line_num,
            parameters=params,
            return_type=return_type,
            documentation=docstring,
            references=calls_found + [h.name for h in hooks_found],
            is_public=is_exported,
            tags=tags,
        )
        result.symbols.append(sym)

    def _parse_variable_declarations(
        self, node: Node, source: bytes, result: ParsedTypeScriptFile, file_path_str: str, is_exported: bool
    ) -> None:
        line_num = self._get_line_number(node, source)
        for idx in range(node.named_child_count):
            child = node.named_child(idx)
            if not child or child.type != "variable_declarator":
                continue

            name_node = None
            value_node = None
            declared_type = None

            for c_idx in range(child.named_child_count):
                c = child.named_child(c_idx)
                if not c:
                    continue
                if c.type in ("identifier", "object_pattern", "array_pattern"):
                    name_node = c
                elif c.type == "type_annotation":
                    declared_type = self._get_node_text(c, source).lstrip(": ").strip()
                else:
                    value_node = c

            if not name_node:
                continue

            var_name = self._get_node_text(name_node, source)

            # Check if it's an arrow function, function expression, or React component wrapper (memo/forwardRef)
            if value_node and value_node.type in ("arrow_function", "function_expression", "call_expression"):
                self._parse_function_like_variable(
                    var_name, value_node, declared_type, node, source, result, file_path_str, is_exported
                )
            else:
                # Regular variable / constant
                is_const = b"const" in source[node.start_byte : node.end_byte]
                sym_type = SymbolType.CONSTANT if is_const else SymbolType.VARIABLE
                sym = Symbol(
                    name=var_name,
                    symbol_type=sym_type,
                    file_path=file_path_str,
                    line_number=line_num,
                    return_type=declared_type,
                    is_public=is_exported,
                    tags=["exported"] if is_exported else [],
                )
                result.symbols.append(sym)

    def _parse_function_like_variable(
        self,
        name: str,
        value_node: Node,
        declared_type: Optional[str],
        parent_decl: Node,
        source: bytes,
        result: ParsedTypeScriptFile,
        file_path_str: str,
        is_exported: bool,
    ) -> None:
        line_num = self._get_line_number(parent_decl, source)
        docstring = self._extract_leading_docstring(parent_decl, source)
        params, return_type = self._extract_params_and_return_type(value_node, source)
        if declared_type and not return_type:
            return_type = declared_type

        tags = []
        if is_exported:
            tags.append("exported")

        if name.startswith("use") and len(name) > 3 and name[3].isupper():
            tags.append("react_hook")

        hooks_found, calls_found, jsx_used, has_jsx = self._analyze_body(value_node, source, result.language)
        for h in hooks_found:
            result.hooks.append(h)
            if h.dependencies:
                dep_str = ",".join(h.dependencies)
                tags.append(f"hook_deps:{h.name}#[{dep_str}]")
            tags.append(f"hook_call:{h.name}")

        for callee in calls_found:
            result.call_edges.append((name, callee))
        result.jsx_elements_used.extend(jsx_used)

        is_component = (
            self._is_react_component_name(name)
            or (declared_type and ("FC" in declared_type or "Component" in declared_type))
            or has_jsx
        )
        if is_component:
            tags.append("react_component")

        sym = Symbol(
            name=name,
            symbol_type=SymbolType.FUNCTION,
            file_path=file_path_str,
            line_number=line_num,
            parameters=params,
            return_type=return_type,
            documentation=docstring,
            references=calls_found + [h.name for h in hooks_found],
            is_public=is_exported,
            tags=tags,
        )
        result.symbols.append(sym)

    # ─────────────────────────────────────────────────────────────────────────
    # Interfaces, Types & Enums
    # ─────────────────────────────────────────────────────────────────────────
    def _parse_interface_declaration(
        self, node: Node, source: bytes, result: ParsedTypeScriptFile, file_path_str: str, is_exported: bool
    ) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        line_num = self._get_line_number(node, source)
        name = self._get_node_text(name_node, source)
        docstring = self._extract_leading_docstring(node, source)

        # Extract heritage (extends InterfaceA, InterfaceB)
        extends_list = []
        for idx in range(node.named_child_count):
            child = node.named_child(idx)
            if child and child.type in ("extends_type_clause", "extends_clause"):
                for h_idx in range(child.named_child_count):
                    hc = child.named_child(h_idx)
                    if hc and hc.type in ("type_identifier", "identifier"):
                        extends_list.append(self._get_node_text(hc, source))

        tags = ["interface"]
        if is_exported:
            tags.append("exported")
        if extends_list:
            tags.append(f"extends:{','.join(extends_list)}")

        sym = Symbol(
            name=name,
            symbol_type=SymbolType.INTERFACE,
            file_path=file_path_str,
            line_number=line_num,
            documentation=docstring,
            references=extends_list,
            is_public=is_exported,
            tags=tags,
        )
        result.symbols.append(sym)

    def _parse_type_alias_declaration(
        self, node: Node, source: bytes, result: ParsedTypeScriptFile, file_path_str: str, is_exported: bool
    ) -> None:
        name_node = node.child_by_field_name("name")
        value_node = node.child_by_field_name("value") or node.child_by_field_name("type")
        if not name_node:
            return

        line_num = self._get_line_number(node, source)
        name = self._get_node_text(name_node, source)
        type_val = self._get_node_text(value_node, source) if value_node else ""
        docstring = self._extract_leading_docstring(node, source)

        tags = ["type_alias"]
        if is_exported:
            tags.append("exported")

        sym = Symbol(
            name=name,
            symbol_type=SymbolType.TYPE_ALIAS,
            file_path=file_path_str,
            line_number=line_num,
            return_type=type_val[:120] if type_val else None,
            documentation=docstring,
            is_public=is_exported,
            tags=tags,
        )
        result.symbols.append(sym)

    def _parse_enum_declaration(
        self, node: Node, source: bytes, result: ParsedTypeScriptFile, file_path_str: str, is_exported: bool
    ) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        line_num = self._get_line_number(node, source)
        name = self._get_node_text(name_node, source)
        docstring = self._extract_leading_docstring(node, source)

        # Extract enum members
        members = []
        body_node = node.child_by_field_name("body")
        if body_node:
            for idx in range(body_node.named_child_count):
                child = body_node.named_child(idx)
                if not child:
                    continue
                if child.type == "enum_assignment":
                    m_name = child.child_by_field_name("name")
                    if m_name:
                        members.append(self._get_node_text(m_name, source))
                elif child.type in ("identifier", "property_identifier"):
                    members.append(self._get_node_text(child, source))

        tags = ["enum"]
        if is_exported:
            tags.append("exported")
        if members:
            tags.append(f"members:{','.join(members)}")

        sym = Symbol(
            name=name,
            symbol_type=SymbolType.ENUM,
            file_path=file_path_str,
            line_number=line_num,
            documentation=docstring,
            parameters=members,
            is_public=is_exported,
            tags=tags,
        )
        result.symbols.append(sym)

    def _parse_class_declaration(
        self, node: Node, source: bytes, result: ParsedTypeScriptFile, file_path_str: str, is_exported: bool
    ) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        line_num = self._get_line_number(node, source)
        name = self._get_node_text(name_node, source)
        docstring = self._extract_leading_docstring(node, source)

        # Extends & Implements
        heritage = []
        body_node = node.child_by_field_name("body")
        for idx in range(node.named_child_count):
            child = node.named_child(idx)
            if child and child.type in ("class_heritage", "extends_clause", "implements_clause"):
                for h_idx in range(child.named_child_count):
                    hc = child.named_child(h_idx)
                    if hc and hc.type in ("type_identifier", "identifier"):
                        heritage.append(self._get_node_text(hc, source))

        tags = ["class"]
        if is_exported:
            tags.append("exported")
        if "Component" in heritage or "React.Component" in heritage or "PureComponent" in heritage:
            tags.append("react_class_component")

        sym = Symbol(
            name=name,
            symbol_type=SymbolType.CLASS,
            file_path=file_path_str,
            line_number=line_num,
            documentation=docstring,
            references=heritage,
            is_public=is_exported,
            tags=tags,
        )
        result.symbols.append(sym)

        # Parse member methods
        if body_node:
            for idx in range(body_node.named_child_count):
                child = body_node.named_child(idx)
                if not child:
                    continue
                if child.type in ("method_definition", "public_field_definition"):
                    m_name_node = child.child_by_field_name("name")
                    if m_name_node:
                        m_line = self._get_line_number(child, source)
                        m_name = self._get_node_text(m_name_node, source)
                        m_params, m_ret = self._extract_params_and_return_type(child, source)
                        m_sym = Symbol(
                            name=f"{name}.{m_name}",
                            symbol_type=SymbolType.FUNCTION,
                            file_path=file_path_str,
                            line_number=m_line,
                            scope=name,
                            parameters=m_params,
                            return_type=m_ret,
                            is_public=is_exported,
                            tags=["method"],
                        )
                        result.symbols.append(m_sym)

    # ─────────────────────────────────────────────────────────────────────────
    # Body & Hook Dependency Analysis
    # ─────────────────────────────────────────────────────────────────────────
    def _analyze_body(
        self, root: Node, source: bytes, lang: str = "typescript"
    ) -> tuple[list[HookInfo], list[str], list[str], bool]:
        hooks: list[HookInfo] = []
        calls: set[str] = set()
        jsx_elements: set[str] = set()
        has_jsx = False

        queue = [root]
        while queue:
            curr = queue.pop(0)
            node_type = curr.type

            if node_type == "call_expression":
                fn_node = curr.child_by_field_name("function")
                if fn_node:
                    fn_name = self._get_node_text(fn_node, source)
                    if len(fn_name) <= 80 and "\n" not in fn_name:
                        calls.add(fn_name)

                    if fn_name.startswith("use") or ".use" in fn_name:
                        line_no = self._get_line_number(curr, source)
                        hook_deps = self._extract_hook_dependency_array(curr, source)
                        hooks.append(HookInfo(
                            name=fn_name,
                            line=line_no,
                            dependencies=hook_deps,
                        ))

            elif node_type in ("jsx_opening_element", "jsx_self_closing_element"):
                has_jsx = True
                name_node = curr.child_by_field_name("name")
                if name_node:
                    elem_name = self._get_node_text(name_node, source)
                    if elem_name and elem_name[0].isupper():
                        jsx_elements.add(elem_name)
                        calls.add(elem_name)
            elif node_type in ("jsx_element", "jsx_fragment"):
                has_jsx = True

            for idx in range(curr.named_child_count):
                ch = curr.named_child(idx)
                if ch:
                    queue.append(ch)

        return hooks, sorted(list(calls)), sorted(list(jsx_elements)), has_jsx

    def _extract_hook_dependency_array(self, call_node: Node, source: bytes) -> list[str]:
        """
        Parses secondary argument in useEffect(..., [a, b, c.d]) to extract dependency names.
        """
        args_node = call_node.child_by_field_name("arguments")
        if not args_node or args_node.named_child_count < 2:
            return []

        second_arg = args_node.named_child(1)
        if second_arg and second_arg.type == "array":
            deps: list[str] = []
            for idx in range(second_arg.named_child_count):
                item = second_arg.named_child(idx)
                if item:
                    deps.append(self._get_node_text(item, source))
            return deps
        return []

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _get_node_text(node: Node, source: bytes) -> str:
        return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

    @staticmethod
    def _get_line_number(node: Node, source: bytes) -> int:
        return source[: node.start_byte].count(b"\n") + 1

    def _extract_params_and_return_type(self, node: Node, source: bytes) -> tuple[list[str], Optional[str]]:
        params: list[str] = []
        return_type = None

        params_node = node.child_by_field_name("parameters")
        if params_node:
            for idx in range(params_node.named_child_count):
                p = params_node.named_child(idx)
                if p:
                    params.append(self._get_node_text(p, source))

        ret_node = node.child_by_field_name("return_type")
        if ret_node:
            return_type = self._get_node_text(ret_node, source).lstrip(": ").strip()

        return params, return_type

    def _extract_leading_docstring(self, node: Node, source: bytes) -> Optional[str]:
        prev = node.prev_named_sibling
        if prev and prev.type == "comment":
            c_text = self._get_node_text(prev, source)
            if c_text.startswith("/**"):
                return c_text
        return None

    @staticmethod
    def _is_react_component_name(name: str) -> bool:
        return bool(name and name[0].isupper() and not name.isupper())
