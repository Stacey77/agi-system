"""Calculator tool — mathematical expression evaluation and statistics."""

from __future__ import annotations

import ast
import logging
import math
import operator
import statistics
from typing import Any, Dict, List, Union

from src.tools.base_tool import BaseTool, ToolMetadata

logger = logging.getLogger(__name__)

_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_SAFE_FUNCS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "pi": math.pi,
    "e": math.e,
}


def _safe_eval(node: ast.expr) -> float:
    """Recursively evaluate an AST node using only safe operations."""
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.BinOp):
        op_fn = _SAFE_OPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op_fn(_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        op_fn = _SAFE_OPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op_fn(_safe_eval(node.operand))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only simple function calls are allowed")
        fn = _SAFE_FUNCS.get(node.func.id)
        if fn is None:
            raise ValueError(f"Function not allowed: {node.func.id!r}")
        args = [_safe_eval(a) for a in node.args]
        return fn(*args)  # type: ignore[call-arg]
    if isinstance(node, ast.Name):
        val = _SAFE_FUNCS.get(node.id)
        if val is None or callable(val):
            raise ValueError(f"Unknown name: {node.id!r}")
        return float(val)
    raise ValueError(f"Unsupported expression type: {type(node).__name__}")


class CalculatorTool(BaseTool):
    """Evaluates mathematical expressions and performs statistical computations."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="calculator",
            description="Evaluate mathematical expressions and compute statistics",
            parameters={
                "required": ["expression"],
                "optional": ["operation", "data"],
                "properties": {
                    "expression": {"type": "string", "description": "Math expression to evaluate"},
                    "operation": {
                        "type": "string",
                        "enum": ["evaluate", "statistics"],
                        "default": "evaluate",
                    },
                    "data": {"type": "array", "description": "Numeric data for statistics"},
                },
            },
            return_type="Union[float, Dict]",
            category="analytical",
        )

    def execute(self, **kwargs: Any) -> Any:
        if not self.validate_parameters(**kwargs):
            return {"error": "Missing required parameters"}

        operation = kwargs.get("operation", "evaluate")
        expression = kwargs["expression"]

        if operation == "statistics":
            data: List[float] = kwargs.get("data", [])
            return self._compute_statistics(data)
        return self._evaluate_expression(expression)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def _evaluate_expression(self, expression: str) -> Union[float, Dict[str, str]]:
        """Safely evaluate *expression*."""
        try:
            tree = ast.parse(expression.strip(), mode="eval")
            result = _safe_eval(tree.body)
            logger.debug("Evaluated '%s' = %s", expression, result)
            return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("Expression evaluation failed: %s", exc)
            return {"error": str(exc)}

    def _compute_statistics(self, data: List[float]) -> Dict[str, Any]:
        if not data:
            return {"error": "No data provided"}
        nums = [float(x) for x in data]
        result: Dict[str, Any] = {
            "count": len(nums),
            "mean": statistics.mean(nums),
            "median": statistics.median(nums),
            "min": min(nums),
            "max": max(nums),
        }
        if len(nums) > 1:
            result["stdev"] = statistics.stdev(nums)
            result["variance"] = statistics.variance(nums)
        return result
