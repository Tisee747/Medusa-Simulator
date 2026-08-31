"""Lightweight AST checks used only when a question explicitly requires a technique."""

from __future__ import annotations

import ast
from typing import Any

from app.questions.base import TechniqueResult


def evaluate_technique(
    source: str,
    required: str | None,
    required_function: str | None = None,
) -> TechniqueResult:
    if not required:
        return TechniqueResult(None, True, {})
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return TechniqueResult(required, False, {"syntax_valid": False})

    required = required.upper()
    if required == "WHILE":
        whiles = [node for node in ast.walk(tree) if isinstance(node, ast.While)]
        non_dummy = [node for node in whiles if _while_not_dummy(node)]
        repeated_input = any(_contains_input(node) for node in non_dummy)
        checks: dict[str, Any] = {
            "while_exists": bool(whiles),
            "while_not_dummy": bool(non_dummy),
            "while_processes_repeated_input": repeated_input,
        }
        return TechniqueResult(required, all(checks.values()), checks)

    if required == "FUNCTION":
        exists = any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in ast.walk(tree))
        return TechniqueResult(required, exists, {"function_exists": exists})

    if required == "BFS":
        if not required_function:
            names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
            calls = {
                node.func.attr
                for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            }
            queue_like = "deque" in names or "antrean" in names or "queue" in names
            fifo_like = "popleft" in calls
            visited_like = any(name.lower() in {"dikunjungi", "visited"} for name in names)
            legacy_checks = {"queue_exists": queue_like, "fifo_pop_exists": fifo_like, "visited_exists": visited_like}
            return TechniqueResult(required, all(legacy_checks.values()), legacy_checks)
        checks = _evaluate_bfs(tree, required_function)
        return TechniqueResult(required, all(checks.values()), checks)

    if required == "RECURSION":
        functions = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        call_graph: dict[str, set[str]] = {}
        recursive_functions: set[str] = set()
        for name, node in functions.items():
            called = {
                item.func.id
                for item in ast.walk(node)
                if isinstance(item, ast.Call) and isinstance(item.func, ast.Name)
            }
            call_graph[name] = called
            if name in called:
                recursive_functions.add(name)

        root = required_function or ""
        reachable = _reachable_functions(root, call_graph) if root else set(functions)
        recursive_call_exists = bool(recursive_functions)
        reachable_from_required = bool(recursive_functions & reachable) and root in functions
        checks = {
            "recursive_call_exists": recursive_call_exists,
            "reachable_from_required_function": reachable_from_required,
        }
        return TechniqueResult(required, all(checks.values()), checks)

    return TechniqueResult(required, False, {"unsupported_required_technique": required})


def _reachable_functions(root: str, graph: dict[str, set[str]]) -> set[str]:
    if root not in graph:
        return set()
    seen: set[str] = set()
    stack = [root]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(name for name in graph.get(current, set()) if name in graph and name not in seen)
    return seen


def _while_not_dummy(node: ast.While) -> bool:
    if isinstance(node.test, ast.Constant) and node.test.value is False:
        return False
    meaningful = [item for item in node.body if not isinstance(item, (ast.Pass, ast.Expr))]
    if meaningful:
        return True
    return any(isinstance(item, (ast.Assign, ast.AugAssign, ast.Call, ast.If)) for item in ast.walk(node))


def _contains_input(node: ast.AST) -> bool:
    return any(
        isinstance(item, ast.Call)
        and isinstance(item.func, ast.Name)
        and item.func.id == "input"
        for item in ast.walk(node)
    )


def _evaluate_bfs(tree: ast.AST, required_function: str | None) -> dict[str, bool]:
    functions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    root_name = required_function or ""
    root = functions.get(root_name)
    if root is None:
        return {
            "bfs_exists": False,
            "bfs_not_dummy": False,
            "bfs_controls_search": False,
            "queue_or_equivalent_frontier": False,
            "visited_state_prevents_repeat": False,
        }

    call_graph: dict[str, set[str]] = {}
    for name, node in functions.items():
        call_graph[name] = {
            item.func.id
            for item in ast.walk(node)
            if isinstance(item, ast.Call) and isinstance(item.func, ast.Name)
        }
    reachable_names = _reachable_functions(root_name, call_graph)
    reachable_nodes = [functions[name] for name in reachable_names if name in functions]
    all_nodes = [item for node in reachable_nodes for item in ast.walk(node)]

    assigned_names: set[str] = set()
    frontier_names: set[str] = set()
    visited_names: set[str] = set()
    append_targets: set[str] = set()
    dequeue_targets: set[str] = set()
    visited_add_targets: set[str] = set()
    membership_names: set[str] = set()

    for node in all_nodes:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            for target in targets:
                if isinstance(target, ast.Name):
                    assigned_names.add(target.id)
                    lowered = target.id.lower()
                    if any(part in lowered for part in ("queue", "antrean", "frontier", "antrian")):
                        frontier_names.add(target.id)
                    if any(part in lowered for part in ("visited", "dikunjungi", "seen")):
                        visited_names.add(target.id)
                    if isinstance(value, (ast.List, ast.ListComp)):
                        frontier_names.add(target.id)
                    if isinstance(value, (ast.Set, ast.SetComp)):
                        visited_names.add(target.id)
                    if isinstance(value, ast.Call):
                        call_name = _call_name(value.func).split(".")[-1]
                        if call_name == "deque":
                            frontier_names.add(target.id)
                        if call_name == "set":
                            visited_names.add(target.id)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            owner = node.func.value.id
            method = node.func.attr
            if method == "append":
                append_targets.add(owner)
            elif method == "popleft":
                dequeue_targets.add(owner)
            elif method == "pop" and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == 0:
                dequeue_targets.add(owner)
            elif method == "add":
                visited_add_targets.add(owner)
        elif isinstance(node, ast.Compare):
            for operator, comparator in zip(node.ops, node.comparators):
                if isinstance(operator, (ast.In, ast.NotIn)) and isinstance(comparator, ast.Name):
                    membership_names.add(comparator.id)

    queue_names = frontier_names | append_targets | dequeue_targets
    queue_ok = bool(queue_names & append_targets & dequeue_targets)
    visited_ok = bool(visited_names & visited_add_targets & membership_names)
    loops = [node for node in all_nodes if isinstance(node, (ast.While, ast.For))]
    conditionals = [node for node in all_nodes if isinstance(node, ast.If)]
    dynamic_returns = [
        node for node in all_nodes
        if isinstance(node, ast.Return) and node.value is not None
        and not (isinstance(node.value, ast.Constant) and node.value.value in (None, False, True))
    ]
    neighbor_iteration = any(isinstance(node, ast.For) for node in all_nodes)
    bfs_not_dummy = bool(loops and queue_ok and dynamic_returns)
    bfs_controls_search = bool(queue_ok and visited_ok and neighbor_iteration and conditionals and dynamic_returns)
    return {
        "bfs_exists": True,
        "bfs_not_dummy": bfs_not_dummy,
        "bfs_controls_search": bfs_controls_search,
        "queue_or_equivalent_frontier": queue_ok,
        "visited_state_prevents_repeat": visited_ok,
    }


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""
