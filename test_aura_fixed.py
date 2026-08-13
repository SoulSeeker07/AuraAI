Here’s a clean, production‑ready version of the factorial function that:
* Handles negative inputs with a clear exception.
* Uses a type hint and a docstring for readability.
* Provides both a recursive implementation (kept for illustration) **and** an iterative version that avoids recursion‑depth limits.
* Includes a small test harness you can run directly in VS Code.
```python
def factorial_recursive(n: int) -> int:
"""
Return the factorial of a non‑negative integer *n* using recursion.
Raises:
ValueError: If *n* is negative.
"""
if n < 0:
raise ValueError("n must be a non‑negative integer")
if n == 0:
return 1
return n * factorial_recursive(n - 1)
def factorial_iterative(n: int) -> int:
"""
Return the factorial of a non‑negative integer *n* using an iterative loop.
This version is safe for large *n* (e.g., > 1000) because it never hits
Python's recursion limit.
"""
if n < 0:
raise ValueError("n must be a non‑negative integer")
result = 1
for i in range(2, n + 1):
result *= i
return result
# ------------------------------
# Simple test / demo (run this file)
# ------------------------------
if __name__ == "__main__":
test_vals = [0, 1, 5, 10]
print("Recursive version:")
for v in test_vals:
print(f"  {v}! = {factorial_recursive(v)}")
print("\nIterative version:")
for v in test_vals:
print(f"  {v}! = {factorial_iterative(v)}")
```
### How to run in VS Code
1. **Save** the file as `factorial_demo.py`.
2. Make sure the **Python** extension is installed (it gives you IntelliSense, linting, etc.).
3. Press **Ctrl + Shift + B** (or right‑click → *Run Python File in Terminal*) to execute.
4. You should see:
```
Recursive version:
0! = 1
1! = 1
5! = 120
10! = 3628800
Iterative version:
0! = 1
1! = 1
5! = 120
10! = 3628800
```
Feel free to use either implementation; the iterative one is generally safer for large inputs.