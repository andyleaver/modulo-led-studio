"""runtime.kernel_dsl_v1

Export-safe per-pixel kernel DSL.

See behaviors/effects/kernel_dsl.py and export/arduino_exporter.py.
"""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass
from typing import Callable


SAFE_NAMES = {"x", "y", "t", "seed", "pi"}


def _fract(v: float) -> float:
    return v - math.floor(v)


SAFE_FUNCS_PY = {
    "sin": math.sin,
    "cos": math.cos,
    "abs": abs,
    "min": min,
    "max": max,
    "fract": _fract,
}


SAFE_FUNCS_CPP = {
    "sin": "sinf",
    "cos": "cosf",
    "abs": "fabsf",
    "min": "fminf",
    "max": "fmaxf",
    "fract": "fractf_modulo",  # helper emitted by exporter
}


ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.IfExp,
)


@dataclass(frozen=True)
class KernelCompileResult:
    py_fn: Callable[[float, float, float, int], float]
    cpp_expr: str


class KernelCompileError(ValueError):
    pass


def _validate(node: ast.AST) -> None:
    for n in ast.walk(node):
        if not isinstance(n, ALLOWED_NODES):
            raise KernelCompileError(f"DSL node not allowed: {type(n).__name__}")

        if isinstance(n, ast.Name):
            if n.id not in SAFE_NAMES and n.id not in SAFE_FUNCS_PY:
                raise KernelCompileError(f"Unknown name: {n.id}")

        if isinstance(n, ast.Call):
            if not isinstance(n.func, ast.Name):
                raise KernelCompileError("Only direct function calls allowed")
            fn = n.func.id
            if fn not in SAFE_FUNCS_PY:
                raise KernelCompileError(f"Function not allowed: {fn}")

        if isinstance(n, ast.Constant):
            if not isinstance(n.value, (int, float, bool)):
                raise KernelCompileError("Only numeric/bool constants allowed")


def compile_kernel_expr(expr: str) -> KernelCompileResult:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise KernelCompileError(str(e))
    _validate(tree)

    code = compile(tree, "<kernel_dsl>", "eval")

    def py_fn(x: float, y: float, t: float, seed: int) -> float:
        env = {
            "x": float(x),
            "y": float(y),
            "t": float(t),
            "seed": float(seed) * 0.001,
            "pi": math.pi,
            **SAFE_FUNCS_PY,
        }
        v = eval(code, {"__builtins__": {}}, env)  # noqa: S307
        fv = float(v)
        if fv < 0.0:
            return 0.0
        if fv > 1.0:
            return 1.0
        return fv

    cpp_expr = _to_cpp_expr(tree.body)
    return KernelCompileResult(py_fn=py_fn, cpp_expr=cpp_expr)


def _to_cpp_expr(node: ast.AST) -> str:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return "1.0f" if node.value else "0.0f"
        if isinstance(node.value, int):
            return f"{node.value}.0f"
        return f"{float(node.value)}f"

    if isinstance(node, ast.Name):
        if node.id == "pi":
            return "3.14159265f"
        return node.id

    if isinstance(node, ast.UnaryOp):
        op = "+" if isinstance(node.op, ast.UAdd) else "-"
        return f"({op}{_to_cpp_expr(node.operand)})"

    if isinstance(node, ast.BinOp):
        a = _to_cpp_expr(node.left)
        b = _to_cpp_expr(node.right)
        if isinstance(node.op, ast.Add):
            o = "+"
        elif isinstance(node.op, ast.Sub):
            o = "-"
        elif isinstance(node.op, ast.Mult):
            o = "*"
        elif isinstance(node.op, ast.Div):
            o = "/"
        elif isinstance(node.op, ast.Mod):
            o = "%"
        elif isinstance(node.op, ast.Pow):
            return f"powf({a}, {b})"
        else:
            raise KernelCompileError(f"Unsupported binop: {type(node.op).__name__}")
        return f"({a} {o} {b})"

    if isinstance(node, ast.Call):
        fn = node.func.id
        cfn = SAFE_FUNCS_CPP[fn]
        args = ", ".join(_to_cpp_expr(a) for a in node.args)
        return f"{cfn}({args})"

    if isinstance(node, ast.IfExp):
        tst = _to_cpp_expr(node.test)
        a = _to_cpp_expr(node.body)
        b = _to_cpp_expr(node.orelse)
        return f"(({tst}) ? ({a}) : ({b}))"

    if isinstance(node, ast.Compare):
        if len(node.ops) != 1 or len(node.comparators) != 1:
            raise KernelCompileError("Only single comparisons supported")
        a = _to_cpp_expr(node.left)
        b = _to_cpp_expr(node.comparators[0])
        op = node.ops[0]
        if isinstance(op, ast.Lt):
            o = "<"
        elif isinstance(op, ast.LtE):
            o = "<="
        elif isinstance(op, ast.Gt):
            o = ">"
        elif isinstance(op, ast.GtE):
            o = ">="
        elif isinstance(op, ast.Eq):
            o = "=="
        elif isinstance(op, ast.NotEq):
            o = "!="
        else:
            raise KernelCompileError("Unsupported comparison")
        return f"(({a} {o} {b}) ? 1.0f : 0.0f)"

    if isinstance(node, ast.BoolOp):
        parts = [_to_cpp_expr(v) for v in node.values]
        if isinstance(node.op, ast.And):
            expr = " && ".join(f"({p} > 0.5f)" for p in parts)
        else:
            expr = " || ".join(f"({p} > 0.5f)" for p in parts)
        return f"(({expr}) ? 1.0f : 0.0f)"

    raise KernelCompileError(f"Unsupported DSL node: {type(node).__name__}")
