Here’s a cleaned‑up, production‑ready version of the factorial function that addresses the only hidden issue — handling invalid inputs (negative numbers or non‑integers) and adding proper type hints and indentation.
```python
def factorial(n: int) -> int:
"""
Compute n! (the factorial of n) using recursion.
Args:
n: A non‑negative integer.
Returns:
The factorial of n.
Raises:
ValueError: If n is negative.
TypeError:  If n is not an integer.
"""
# Guard‑clauses for invalid input
if not isinstance(n, int):
raise TypeError("n must be an integer")
if n < 0:
raise ValueError("n must be non‑negative")
# Base case
if n == 0:
return 1
# Recursive case
return n * factorial(n - 1)
# ---- Test the function -------------------------------------------------
if __name__ == "__main__":
result = factorial(5)
print(f"Factorial of 5 is {result}")   # → Factorial of 5 is 120
```
### What changed?
| Change | Reason |
|--------|--------|
| **Added type hints (`n: int -> int`)** | Improves readability and IDE assistance (you love VS Code!). |
| **Input validation (`isinstance`, `n < 0`)** | Prevents infinite recursion for negative numbers and gives clear error messages for wrong types. |
| **Docstring** | Documents the function’s purpose, parameters, return value, and possible exceptions. |
| **`if __name__ == "__main__":` guard** | Allows the file to be imported without automatically running the test code. |
| **Proper indentation** | Ensures the code runs without `IndentationError`. |
The core recursion (`return n * factorial(n‑1)`) remains the same, so the logic and performance for valid inputs are unchanged. If you ever need to compute very large factorials (e.g., > 1000), you could switch to an iterative version to avoid hitting Python’s recursion limit, but for typical use this recursive implementation works perfectly.