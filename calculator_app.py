#!/usr/bin/env python3
"""
Simple command-line calculator supporting basic arithmetic operations.
Designed for easy extensibility.
"""

from typing import Callable, Dict

class Calculator:
    """Performs basic arithmetic operations."""

    def __init__(self) -> None:
        self.operations: Dict[str, Callable[[float, float], float]] = {
            '+': self.add,
            '-': self.subtract,
            '*': self.multiply,
            '/': self.divide,
        }

    @staticmethod
    def add(a: float, b: float) -> float:
        return a + b

    @staticmethod
    def subtract(a: float, b: float) -> float:
        return a - b

    @staticmethod
    def multiply(a: float, b: float) -> float:
        return a * b

    @staticmethod
    def divide(a: float, b: float) -> float:
        if b == 0:
            raise ZeroDivisionError("Division by zero is undefined.")
        return a / b

    def evaluate(self, expression: str) -> float:
        """
        Evaluate a simple binary expression like '3 + 4'.
        Supports floating point and integer numbers.
        """
        tokens = expression.strip().split()
        if len(tokens) != 3:
            raise ValueError("Expression must be in the format: <number> <operator> <number>")
        left_str, op, right_str = tokens
        if op not in self.operations:
            raise ValueError(f"Unsupported operator '{op}'. Supported operators: {', '.join(self.operations)}")
        try:
            left = float(left_str)
            right = float(right_str)
        except ValueError:
            raise ValueError("Both operands must be numeric.")
        return self.operations[op](left, right)

def print_help() -> None:
    help_text = """
Simple Calculator
Enter expressions in the form: <number> <operator> <number>
Supported operators:
  +  addition
  -  subtraction
  *  multiplication
  /  division
Commands:
  help   Show this help message
  exit   Quit the application
"""
    print(help_text.strip())

def main() -> None:
    calc = Calculator()
    print("Welcome to the Calculator. Type 'help' for instructions or 'exit' to quit.")
    while True:
        try:
            user_input = input("calc> ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break
            if user_input.lower() == "help":
                print_help()
                continue
            result = calc.evaluate(user_input)
            if result.is_integer():
                print(int(result))
            else:
                print(result)
        except ZeroDivisionError as zde:
            print(f"Error: {zde}")
        except ValueError as ve:
            print(f"Error: {ve}")
        except KeyboardInterrupt:
            print("\\nInterrupted. Exiting.")
            break

if __name__ == "__main__":
    main()
