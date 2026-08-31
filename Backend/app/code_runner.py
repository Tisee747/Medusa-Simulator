"""Run participant Python code in a bounded subprocess.

This limits common failures and server impact, but is not claimed to be a complete
security sandbox. Production should still use an OS/container isolation boundary.
"""

from __future__ import annotations

import ast
import json
import os
import resource
import selectors
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import RUNNER_MAX_OUTPUT, RUNNER_MEMORY_MB, RUNNER_TIMEOUT_SECONDS

_ALLOWED_IMPORTS = {"math", "random", "collections", "json"}
_BLOCKED_CALLS = {
    "breakpoint", "compile", "eval", "exec", "globals", "help", "locals",
    "open", "quit", "exit", "vars", "__import__", "getattr", "setattr", "delattr",
}
_BLOCKED_NAMES = {
    "builtins", "ctypes", "inspect", "multiprocessing", "os", "pathlib", "resource",
    "shutil", "signal", "socket", "subprocess", "sys", "__builtins__",
}
_RETURN_MARKER = "__SIMULATOR_FUNCTION_RETURN__"


@dataclass(slots=True)
class RunResult:
    ok: bool
    stdout: str
    stderr: str
    return_code: int
    timed_out: bool = False
    validation_error: str = ""
    output_limit_exceeded: bool = False
    duration_ms: int = 0


@dataclass(slots=True)
class FunctionRunResult(RunResult):
    return_value: Any = None
    function_error: str = ""
    return_limit_exceeded: bool = False
    arguments_after: Any = None


def validate_source(source: str) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return f"SyntaxError pada baris {exc.lineno or 0}: {exc.msg}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root not in _ALLOWED_IMPORTS:
                    return f"Import '{alias.name}' tidak diizinkan pada simulator."
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            if root not in _ALLOWED_IMPORTS:
                return f"Import dari '{node.module}' tidak diizinkan pada simulator."
        elif isinstance(node, ast.Name) and node.id in _BLOCKED_NAMES:
            return f"Nama '{node.id}' tidak diizinkan pada simulator."
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            return "Akses atribut internal Python tidak diizinkan."
        elif isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Name) and node.value.id == "__builtins__":
                return "Akses dinamis ke builtins tidak diizinkan."
        elif isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name in _BLOCKED_CALLS or name.split(".")[-1] in _BLOCKED_CALLS:
                return f"Pemanggilan '{name}' tidak diizinkan pada simulator."
    return ""


def run_source(
    source: str,
    *,
    stdin_text: str = "",
    timeout_seconds: float | None = None,
) -> RunResult:
    validation_error = validate_source(source)
    if validation_error:
        return RunResult(False, "", "", 2, validation_error=validation_error)
    return _run_script(source, stdin_text=stdin_text, timeout_seconds=timeout_seconds)


def run_function(
    source: str,
    *,
    function_name: str,
    args: list[Any],
    timeout_seconds: float | None = None,
) -> FunctionRunResult:
    """Call one participant function once without executing its canonical main guard.

    Every invocation creates one subprocess and therefore maps cleanly to one immutable
    execution record. Return values are transferred through a bounded tagged JSON form;
    no type coercion is applied by the parent process.
    """

    validation_error = validate_source(source)
    if validation_error:
        return FunctionRunResult(False, "", "", 2, validation_error=validation_error)
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:  # validate_source already handles this; defensive only
        return FunctionRunResult(False, "", "", 2, validation_error=f"SyntaxError: {exc}")

    tree.body = [node for node in tree.body if not _is_main_guard(node)]
    ast.fix_missing_locations(tree)
    cleaned = ast.unparse(tree)
    args_literal = repr(args)
    harness = f'''
import json as _simulator_json

_SIMULATOR_TRUNCATED = False

def _simulator_encode(value, depth=0):
    global _SIMULATOR_TRUNCATED
    if depth > 12:
        _SIMULATOR_TRUNCATED = True
        return {{"t":"truncated"}}
    if value is None:
        return {{"t":"none"}}
    if isinstance(value, bool):
        return {{"t":"bool","v":value}}
    if isinstance(value, int):
        return {{"t":"int","v":value}}
    if isinstance(value, float):
        return {{"t":"float","v":value}}
    if isinstance(value, str):
        if len(value) > 10000:
            _SIMULATOR_TRUNCATED = True
            value = value[:10000]
        return {{"t":"str","v":value}}
    if isinstance(value, list):
        if len(value) > 1000:
            _SIMULATOR_TRUNCATED = True
        return {{"t":"list","v":[_simulator_encode(item, depth + 1) for item in value[:1000]]}}
    if isinstance(value, tuple):
        if len(value) > 1000:
            _SIMULATOR_TRUNCATED = True
        return {{"t":"tuple","v":[_simulator_encode(item, depth + 1) for item in value[:1000]]}}
    if isinstance(value, dict):
        items = list(value.items())
        if len(items) > 1000:
            _SIMULATOR_TRUNCATED = True
        return {{"t":"dict","v":[[_simulator_encode(k, depth + 1), _simulator_encode(v, depth + 1)] for k, v in items[:1000]]}}
    return {{"t":"unsupported","python_type":type(value).__name__,"repr":repr(value)[:1000]}}

_simulator_args = {args_literal}
_simulator_function = globals().get({function_name!r})
if not callable(_simulator_function):
    raise NameError("Required function {function_name} tidak ditemukan.")
_simulator_value = _simulator_function(*_simulator_args)
_simulator_payload = {{"value":_simulator_encode(_simulator_value),"args_after":_simulator_encode(_simulator_args),"truncated":_SIMULATOR_TRUNCATED}}
print({_RETURN_MARKER!r} + _simulator_json.dumps(_simulator_payload, ensure_ascii=False, separators=(",", ":")))
'''
    raw = _run_script(cleaned + "\n" + harness, timeout_seconds=timeout_seconds)
    if raw.validation_error:
        return FunctionRunResult(**raw.__dict__)

    marker_payload: dict[str, Any] | None = None
    user_lines: list[str] = []
    for line in raw.stdout.splitlines(keepends=True):
        stripped = line.rstrip("\r\n")
        if stripped.startswith(_RETURN_MARKER):
            try:
                marker_payload = json.loads(stripped[len(_RETURN_MARKER):])
            except json.JSONDecodeError:
                marker_payload = None
        else:
            user_lines.append(line)
    user_stdout = "".join(user_lines)
    if marker_payload is None:
        return FunctionRunResult(
            ok=False,
            stdout=user_stdout,
            stderr=raw.stderr,
            return_code=raw.return_code,
            timed_out=raw.timed_out,
            validation_error=raw.validation_error,
            output_limit_exceeded=raw.output_limit_exceeded,
            duration_ms=raw.duration_ms,
            function_error=(raw.stderr.strip() or "Function return marker tidak ditemukan."),
        )
    value = _decode_tagged(marker_payload.get("value"))
    arguments_after = _decode_tagged(marker_payload.get("args_after"))
    truncated = bool(marker_payload.get("truncated"))
    return FunctionRunResult(
        ok=raw.ok and not truncated,
        stdout=user_stdout,
        stderr=raw.stderr,
        return_code=raw.return_code,
        timed_out=raw.timed_out,
        validation_error=raw.validation_error,
        output_limit_exceeded=raw.output_limit_exceeded,
        duration_ms=raw.duration_ms,
        return_value=value,
        function_error="Return object melebihi batas aman." if truncated else "",
        return_limit_exceeded=truncated,
        arguments_after=arguments_after,
    )


def normalize_output(value: str) -> str:
    lines = [line.rstrip() for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines).strip()


def _run_script(
    source: str,
    *,
    stdin_text: str = "",
    timeout_seconds: float | None = None,
) -> RunResult:
    timeout = timeout_seconds or RUNNER_TIMEOUT_SECONDS
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="simulator-run-") as temp_dir:
        script_path = Path(temp_dir) / "submission.py"
        script_path.write_text(source, encoding="utf-8")
        process = subprocess.Popen(
            [sys.executable, "-I", "-S", str(script_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=temp_dir,
            env={"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"},
            preexec_fn=_apply_limits,
            text=False,
        )
        assert process.stdin and process.stdout and process.stderr
        try:
            process.stdin.write(stdin_text.encode("utf-8", errors="replace"))
            process.stdin.close()
        except BrokenPipeError:
            # Participant process may exit before consuming stdin. This is a normal
            # execution failure and must not crash the FastAPI request.
            try:
                process.stdin.close()
            except BrokenPipeError:
                pass

        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        chunks: dict[str, list[bytes]] = {"stdout": [], "stderr": []}
        totals: dict[str, int] = {"stdout": 0, "stderr": 0}
        timed_out = False
        output_limit = False

        while selector.get_map():
            if time.monotonic() - started > timeout:
                timed_out = True
                _terminate(process)
                break
            events = selector.select(timeout=0.05)
            for key, _ in events:
                data = os.read(key.fileobj.fileno(), 4096)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                remaining = RUNNER_MAX_OUTPUT - totals[key.data]
                if remaining > 0:
                    chunks[key.data].append(data[:remaining])
                    totals[key.data] += min(len(data), remaining)
                if len(data) > remaining or totals[key.data] >= RUNNER_MAX_OUTPUT:
                    output_limit = True
                    _terminate(process)
                    selector.close()
                    break
            if process.poll() is not None and not events:
                for stream in list(selector.get_map().values()):
                    try:
                        data = os.read(stream.fileobj.fileno(), 4096)
                    except OSError:
                        data = b""
                    if data:
                        remaining = max(0, RUNNER_MAX_OUTPUT - totals[stream.data])
                        chunks[stream.data].append(data[:remaining])
                        totals[stream.data] += min(len(data), remaining)
                    selector.unregister(stream.fileobj)

        try:
            return_code = process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            _terminate(process)
            return_code = 124

    duration_ms = int((time.monotonic() - started) * 1000)
    stdout = b"".join(chunks["stdout"]).decode("utf-8", errors="replace")
    stderr = b"".join(chunks["stderr"]).decode("utf-8", errors="replace")
    if output_limit:
        marker = "\n...[output melebihi batas dan proses dihentikan]"
        stderr = (stderr + marker)[: RUNNER_MAX_OUTPUT]
    return RunResult(
        ok=return_code == 0 and not timed_out and not output_limit,
        stdout=stdout,
        stderr=stderr,
        return_code=return_code,
        timed_out=timed_out,
        output_limit_exceeded=output_limit,
        duration_ms=duration_ms,
    )


def _decode_tagged(encoded: Any) -> Any:
    if not isinstance(encoded, dict):
        return {"__simulator_unsupported__": "malformed_tag"}
    kind = encoded.get("t")
    if kind == "none":
        return None
    if kind in {"bool", "int", "float", "str"}:
        return encoded.get("v")
    if kind == "list":
        return [_decode_tagged(item) for item in encoded.get("v", [])]
    if kind == "tuple":
        return tuple(_decode_tagged(item) for item in encoded.get("v", []))
    if kind == "dict":
        result: dict[Any, Any] = {}
        try:
            for key, value in encoded.get("v", []):
                result[_decode_tagged(key)] = _decode_tagged(value)
        except (TypeError, ValueError):
            return {"__simulator_unsupported__": "unhashable_dict_key"}
        return result
    if kind == "unsupported":
        return {
            "__simulator_unsupported__": encoded.get("python_type", "unknown"),
            "repr": encoded.get("repr", ""),
        }
    return {"__simulator_unsupported__": kind or "truncated"}


def _is_main_guard(node: ast.AST) -> bool:
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
        return False
    return (
        isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
        and isinstance(test.ops[0], ast.Eq)
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == "__main__"
    )


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _terminate(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.kill()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass


def _apply_limits() -> None:
    memory_bytes = RUNNER_MEMORY_MB * 1024 * 1024
    cpu_seconds = max(1, int(RUNNER_TIMEOUT_SECONDS) + 1)
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    try:
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    except (ValueError, OSError):
        pass
    os.umask(0o077)
