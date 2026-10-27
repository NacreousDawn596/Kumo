"""Safe, constrained formula evaluation for database formula properties.

Uses Python's ``ast`` to parse the expression and evaluates only a whitelist of
node types and functions — arbitrary code, attribute access, and imports are
rejected. Formulas reference other properties by name (e.g. ``score * 0.3``).
"""

from __future__ import annotations

import ast
import math
import operator
from collections.abc import Mapping

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Not: operator.not_,
}
_COMPARE_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}
_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "len": len,
    "sqrt": math.sqrt,
    "floor": math.floor,
    "ceil": math.ceil,
}

_ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.Constant,
    ast.Name,
    ast.Call,
    ast.Load,
    ast.And,
    ast.Or,
    ast.Not,
    ast.IfExp,
    ast.Tuple,
    ast.List,
    ast.operator,
    ast.unaryop,
    ast.cmpop,
    ast.boolop,
)


class FormulaError(ValueError):
    pass


def evaluate(expr: str, context: Mapping[str, object]) -> object:
    if not expr or not expr.strip():
        return None
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise FormulaError(f"invalid formula: {exc}") from exc

    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise FormulaError(f"disallowed expression element: {type(node).__name__}")

    def _eval(node: ast.AST) -> object:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in ("True", "False"):
                return node.id == "True"
            if node.id in context:
                return context[node.id]
            raise FormulaError(f"unknown property: {node.id}")
        if isinstance(node, ast.BinOp):
            op = _BIN_OPS.get(type(node.op))
            if op is None:
                raise FormulaError("unsupported operator")
            return op(_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp):
            op = _UNARY_OPS.get(type(node.op))
            if op is None:
                raise FormulaError("unsupported unary operator")
            return op(_eval(node.operand))
        if isinstance(node, ast.BoolOp):
            vals = [_eval(v) for v in node.values]
            if isinstance(node.op, ast.And):
                return all(vals)
            if isinstance(node.op, ast.Or):
                return any(vals)
            raise FormulaError("unsupported boolean operator")
        if isinstance(node, ast.Compare):
            left = _eval(node.left)
            for op_node, comparator in zip(node.ops, node.comparators):
                op = _COMPARE_OPS.get(type(op_node))
                if op is None:
                    raise FormulaError("unsupported comparison")
                if not op(left, _eval(comparator)):
                    return False
                left = _eval(comparator)
            return True
        if isinstance(node, ast.IfExp):
            return _eval(node.body) if _eval(node.test) else _eval(node.orelse)
        if isinstance(node, (ast.Tuple, ast.List)):
            return [_eval(e) for e in node.elts]
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS:
                raise FormulaError("unknown function")
            args = [_eval(a) for a in node.args]
            try:
                return _FUNCTIONS[node.func.id](*args)
            except (TypeError, ValueError) as exc:
                raise FormulaError(f"function error: {exc}") from exc
        raise FormulaError("unsupported expression")

    try:
        return _eval(tree.body)
    except ZeroDivisionError as exc:
        raise FormulaError("division by zero") from exc


def coerce_number(value: object) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None
