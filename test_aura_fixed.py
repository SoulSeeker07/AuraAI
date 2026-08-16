```python
def factorial(n: int) -> int:
"""
Compute the factorial of a non‑negative integer n.
Args:
n: A non‑negative integer.
Returns:
The factorial of n.
Raises:
ValueError: If n is negative.
TypeError: If n is not an integer.
"""
if not isinstance(n, int):
raise TypeError("factorial() only accepts integer values")
if n < 0:
raise ValueError("factorial() is undefined for negative integers")
# Base case
if n == 0:
return 1
# Recursive case
return n * factorial(n - 1)
# Test it
if __name__ == "__main__":
result = factorial(5)
print(f"Factorial of 5 is {result}")  # Expected output: 120
```