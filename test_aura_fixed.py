Here’s a clean, ready‑to‑run version that fixes the indentation issue and adds a few safety checks (negative numbers, non‑integers). I kept the recursive style because it’s simple to read, but you can switch to the iterative version if you prefer.
```python
def factorial(n: int) -> int:
"""
Compute n! (factorial) for a non‑negative integer n.
Raises
------
TypeError  : if n is not an integer
ValueError : if n is negative
"""
# ---- input validation -------------------------------------------------
if not isinstance(n, int):
raise TypeError("factorial() argument must be an integer")
if n < 0:
raise ValueError("factorial() not defined for negative integers")
# ---- base case ---------------------------------------------------------
if n == 0:
return 1
# ---- recursive step ----------------------------------------------------
return n * factorial(n - 1)
# ----- simple test ---------------------------------------------------------
if __name__ == "__main__":
result = factorial(5)
print(f"Factorial of 5 is {result}")   # → Factorial of 5 is 120
```
### Why the changes?
| Change | Reason |
|--------|--------|
| Proper indentation (4 spaces) | Python relies on indentation to define blocks. The original snippet had no indentation, which would raise an `IndentationError`. |
| Type hint `-> int` and docstring | Improves readability and helps tools like VS Code’s IntelliSense (your favorite editor) give you better suggestions. |
| Input validation (`isinstance`, `n < 0`) | Prevents infinite recursion for negative numbers and gives a clear error for non‑integers. |
| `if __name__ == "__main__":` guard | Allows the module to be imported elsewhere without automatically running the test code. |
If you ever need to compute factorials for very large `n` (e.g., > 1000), consider using an **iterative** implementation to avoid hitting Python’s recursion limit. Let me know if you’d like that version or any other tweaks!