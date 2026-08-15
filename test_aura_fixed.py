Here’s a clean, fully‑working version that also guards against a few edge‑cases (negative numbers and non‑integers) and includes type hints and a docstring:
```python
def factorial(n: int) -> int:
"""
Return the factorial of a non‑negative integer n.
Raises:
ValueError: If n is negative.
TypeError:  If n is not an integer.
"""
# Validate the input
if not isinstance(n, int):
raise TypeError(f"factorial() expects an integer, got {type(n).__name__}")
if n < 0:
raise ValueError("factorial() is not defined for negative numbers")
# Base case
if n == 0:
return 1
# Recursive step
return n * factorial(n - 1)
# Test it
if __name__ == "__main__":
result = factorial(5)
print(f"Factorial of 5 is {result}")   # → Factorial of 5 is 120
```
### What changed?
| Change | Reason |
|--------|--------|
| Added type hint `n: int -> int` | Improves readability and helps static analysis tools. |
| Added docstring | Documents the function’s purpose and its error behavior. |
| Input validation (`isinstance` & `n < 0`) | Prevents infinite recursion on negative numbers and gives a clear error for non‑integers. |
| Wrapped test in `if __name__ == "__main__":` | Makes the script safe to import without automatically running the test code. |
| Fixed indentation (4 spaces) | Ensures the code runs correctly. |
The core recursion (`return n * factorial(n - 1)`) remains the same, so the logic and output (`120` for `factorial(5)`) are unchanged. Feel free to drop the extra checks if you don’t need them, but this version is robust and ready for production use.