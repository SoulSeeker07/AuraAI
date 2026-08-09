Here’s a cleaned‑up version of the factorial function that handles the common edge‑cases (negative numbers, non‑integers, and recursion‑depth limits) and includes a short docstring. The test at the bottom shows that it still produces the correct result for 5.
```python
def factorial(n: int) -> int:
"""
Return n! (n factorial) for a non‑negative integer n.
Raises
------
TypeError
If *n* is not an integer.
ValueError
If *n* is negative.
RecursionError
If *n* is too large for the recursive implementation (default limit ≈ 1000).
"""
# ---- input validation -------------------------------------------------
if not isinstance(n, int):
raise TypeError("factorial() only accepts integer arguments")
if n < 0:
raise ValueError("factorial() is undefined for negative numbers")
# ---- base case ---------------------------------------------------------
if n == 0:
return 1
# ---- recursive step ----------------------------------------------------
return n * factorial(n - 1)
# -------------------------- simple test ------------------------------------
if __name__ == "__main__":
try:
result = factorial(5)
print(f"Factorial of 5 is {result}")   # → Factorial of 5 is 120
except (TypeError, ValueError, RecursionError) as e:
print(f"Error: {e}")
```
### What changed / why
| Change | Reason |
|--------|--------|
| Added type hint (`n: int -> int`) | Improves readability and helps static analysers. |
| Added a docstring | Documents expected behavior and possible exceptions. |
| Checked `isinstance(n, int)` | Prevents obscure errors when a float or string is passed. |
| Checked `n < 0` and raised `ValueError` | Avoids infinite recursion for negative inputs. |
| Wrapped the test in `if __name__ == "__main__":` | Makes the script import‑safe (the function can be reused without running the test). |
| Added a `try/except` block around the test | Shows graceful error handling if something goes wrong. |
The function will still compute `factorial(5)` correctly (`120`). If you need to compute very large factorials (e.g., `factorial(2000)`), consider using an **iterative** version or Python’s built‑in `math.factorial`, which is optimized and not limited by recursion depth.