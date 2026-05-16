from __future__ import annotations

import ast
import operator
from typing import Callable
# 这是 Python 代码，作用是把 AST（抽象语法树）中的运算符节点类映射到实际执行运算的函数，常用于安全地根据解析后的 `ast` 表达式做计算（替代直接使用 `eval`）。
#
# 要点：
# - 两个字典分别是 `\_BINARY_OPS`（二元运算）和 `\_UNARY_OPS`（一元运算）。
# - 字典的键是 `ast` 中表示运算符的类（例如 `ast.Add`、`ast.USub`），值是标准库 `operator` 模块里的对应函数（例如 `operator.add`、`operator.neg`）。
# - 类型注解（像 `dict[type[ast.operator], Callable[[float, float], float]]`）说明键是运算符类，值是接收/返回 `float` 的可调用对象。
# - 在解析 `ast.BinOp` 或 `ast.UnaryOp` 节点时，代码通过查表得到对应函数并对子节点递归求值，从而只允许预定义的安全操作。

_BINARY_OPS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def calculator(expression: str) -> str:
    """Safely evaluate a basic arithmetic expression."""
    tree = ast.parse(expression, mode="eval")
    value = _eval_node(tree.body)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)

    if isinstance(node, ast.BinOp):
        op = _BINARY_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op(_eval_node(node.left), _eval_node(node.right))

    if isinstance(node, ast.UnaryOp):
        op = _UNARY_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op(_eval_node(node.operand))

    raise ValueError(f"Unsupported expression node: {type(node).__name__}")
