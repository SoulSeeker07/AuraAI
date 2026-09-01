"""
Unit & Integration Tests for TypeScript & JSX AST Provider
==========================================================
Location: tests/engineering/test_typescript_parser.py
"""

import tempfile
from pathlib import Path
import pytest

from src.engineering.language_providers.typescript import (
    TypeScriptASTParser,
    TypeScriptLanguageProvider,
)
from src.engineering.symbol_graph import SymbolType
from src.engineering.ast_manager import ASTManager
from src.engineering.project_index import ProjectIndex


@pytest.fixture
def ts_parser():
    return TypeScriptASTParser()


@pytest.fixture
def ts_provider():
    return TypeScriptLanguageProvider()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Core Symbol Extraction Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_parse_typescript_interfaces(ts_parser):
    source = """
    export interface BaseEntity {
        id: string;
        createdAt: Date;
    }

    export interface UserProfile extends BaseEntity {
        username: string;
        email: string;
        age?: number;
    }
    """
    result = ts_parser.parse_source(source, "user.ts")
    interfaces = [s for s in result.symbols if s.symbol_type == SymbolType.INTERFACE]
    assert len(interfaces) == 2

    base = next(s for s in interfaces if s.name == "BaseEntity")
    assert base.is_public is True
    assert "interface" in base.tags

    user = next(s for s in interfaces if s.name == "UserProfile")
    assert user.is_public is True
    assert "extends:BaseEntity" in user.tags
    assert "BaseEntity" in user.references


def test_parse_type_aliases_and_enums(ts_parser):
    source = """
    export type ThemeMode = 'dark' | 'light' | 'system';
    export type AsyncResult<T> = Promise<{ data: T; error?: string }>;

    export enum ActionState {
        IDLE = 'idle',
        PENDING = 'pending',
        SUCCESS = 'success',
        ERROR = 'error'
    }
    """
    result = ts_parser.parse_source(source, "types.ts")
    
    types = [s for s in result.symbols if s.symbol_type == SymbolType.TYPE_ALIAS]
    assert len(types) == 2
    assert any(t.name == "ThemeMode" for t in types)
    assert any(t.name == "AsyncResult" for t in types)

    enums = [s for s in result.symbols if s.symbol_type == SymbolType.ENUM]
    assert len(enums) == 1
    action_state = enums[0]
    assert action_state.name == "ActionState"
    assert "IDLE" in action_state.parameters
    assert "PENDING" in action_state.parameters


def test_parse_react_functional_components_and_hooks(ts_parser):
    source = """
    import React, { useState, useEffect, useCallback } from 'react';
    import { UserAvatar } from './UserAvatar';

    export interface CardProps {
        userId: string;
        initialCount?: number;
    }

    export const UserCard: React.FC<CardProps> = ({ userId, initialCount = 0 }) => {
        const [count, setCount] = useState<number>(initialCount);

        useEffect(() => {
            console.log("User changed:", userId);
        }, [userId, count]);

        const handleIncrement = useCallback(() => {
            setCount(c => c + 1);
        }, []);

        return (
            <div className="user-card">
                <UserAvatar id={userId} />
                <span>Count: {count}</span>
                <button onClick={handleIncrement}>+</button>
            </div>
        );
    };

    export default function App() {
        return <UserCard userId="usr-123" />;
    }
    """
    result = ts_parser.parse_source(source, "UserCard.tsx")

    components = [s for s in result.symbols if s.symbol_type == SymbolType.FUNCTION]
    assert len(components) >= 2

    user_card = next(s for s in components if s.name == "UserCard")
    assert "react_component" in user_card.tags
    assert user_card.is_public is True
    assert "UserAvatar" in user_card.references

    # Check hook dependency extraction
    assert len(result.hooks) >= 3
    use_effect_hook = next(h for h in result.hooks if h.name == "useEffect")
    assert "userId" in use_effect_hook.dependencies
    assert "count" in use_effect_hook.dependencies

    # Check App component
    app_fn = next(s for s in components if s.name == "App")
    assert "react_component" in app_fn.tags
    assert "UserCard" in app_fn.references


def test_parse_es6_imports_and_exports(ts_parser):
    source = """
    import React from 'react';
    import { useState, useEffect as useMount } from 'react';
    import * as Tooltip from '@radix-ui/react-tooltip';
    import type { ComponentProps } from 'react';
    import './styles.css';

    export { Button } from './Button';
    export default UserCard;
    """
    result = ts_parser.parse_source(source, "index.ts")

    assert len(result.imports) == 5
    modules = [imp["module"] for imp in result.imports]
    assert "react" in modules
    assert "@radix-ui/react-tooltip" in modules
    assert "./styles.css" in modules

    type_import = next(imp for imp in result.imports if imp["module"] == "react" and imp["is_type_only"])
    assert "ComponentProps" in type_import["symbols"]


def test_fault_tolerant_parsing_on_broken_syntax(ts_parser):
    """Tree-sitter must not throw on incomplete or broken code."""
    source = """
    interface Unfinished {
        foo: string;
        bar: 

    export function brokenComponent(props: {
        return (
            <div>
                <span>Unclosed tag
    """
    result = ts_parser.parse_source(source, "broken.tsx")
    assert result is not None
    # Still extracts what it could parse
    symbols = result.symbols
    assert any(s.name == "brokenComponent" for s in symbols)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Integration with ASTManager & ProjectIndex
# ─────────────────────────────────────────────────────────────────────────────

def test_ast_manager_typescript_integration():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ts_file = tmp_path / "Component.tsx"
        ts_file.write_text("""
        import React from 'react';
        export interface WidgetProps { id: string; }
        export function Widget({ id }: WidgetProps) {
            return <div>{id}</div>;
        }
        """, encoding="utf-8")

        ast_mgr = ASTManager(repository_path=tmp_path)
        ast_file = ast_mgr.parse_file(ts_file)

        assert ast_file.language in ("typescript", "tsx")
        assert len(ast_file.functions) >= 1
        assert any(f.name == "Widget" for f in ast_file.functions)


def test_project_index_typescript_indexing():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        db_path = tmp_path / "test_index.sqlite3"
        index = ProjectIndex(repo_root=tmp_path, db_path=db_path)

        ts_file = tmp_path / "math.ts"
        ts_file.write_text("""
        export function add(a: number, b: number): number {
            return a + b;
        }
        export function multiply(a: number, b: number): number {
            return a * b;
        }
        """, encoding="utf-8")

        stats = index.scan()
        assert stats["updated"] == 1
        assert stats["unchanged"] == 0

        # Query symbols
        symbols = index.get_file_symbols(ts_file)
        names = [s.name for s in symbols]
        assert "add" in names
        assert "multiply" in names

        # Re-scan without modifications should be unchanged
        stats2 = index.scan()
        assert stats2["updated"] == 0
        assert stats2["unchanged"] == 1
