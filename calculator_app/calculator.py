import ast
import operator
import math


class Calculator(ast.NodeVisitor):
    """Safely evaluate arithmetic expressions.

    Supported:
        - +, -, *, /, %, **
        - Parentheses via AST grouping
        - Unary + and -
        - sqrt() function from math module
        - Integer and floating point numbers
    """

    operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }

    def __init__(self):
        pass

    def evaluate(self, expression: str):
        """Parse and evaluate *expression*.

        Raises:
            ValueError: If the expression contains unsupported syntax or runtime errors.
        """
        try:
            node = ast.parse(expression, mode="eval")
            return self.visit(node.body)
        except Exception as exc:
            raise ValueError(f"Invalid expression: {exc}")

    def visit_BinOp(self, node: ast.BinOp):
        left = self.visit(node.left)
        right = self.visit(node.right)
        op_type = type(node.op)
        if op_type in self.operators:
            return self.operators[op_type](left, right)
        raise ValueError(f"Unsupported operator: {op_type}")

    def visit_UnaryOp(self, node: ast.UnaryOp):
        operand = self.visit(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.USub):
            return -operand
        raise ValueError(f"Unsupported unary operator: {type(node.op)}")

    def visit_Num(self, node: ast.Num):
        return node.n

    def visit_Constant(self, node: ast.Constant):
        # Python 3.8+ uses Constant instead of Num
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Only numeric constants are allowed")

    def visit_Call(self, node: ast.Call):
        # Only allow sqrt(x)
        if isinstance(node.func, ast.Name) and node.func.id == "sqrt":
            if len(node.args) != 1:
                raise ValueError("sqrt() takes exactly one argument")
            arg = self.visit(node.args[0])
            return math.sqrt(arg)
        raise ValueError("Only sqrt() function is supported")

    def generic_visit(self, node):
        raise ValueError(f"Unsupported expression: {type(node).__name__}")
