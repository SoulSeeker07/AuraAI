# sum_list_fixed.py
"""
Utility to sum numbers in a list.
The original version had two issues that caused a runtime error:
1. Improper indentation made the code syntactically invalid.
2. The line `list_sum([]).append(10)` tried to call ``append`` on the
integer returned by ``list_sum`` – causing an ``AttributeError``.
The fix restores correct indentation and demonstrates the mutable‑default
bug without invoking an invalid method.
"""
def list_sum(nums=[]):                     # ← intentional mutable default (common beginner bug)
"""
Return the sum of all numeric values in *nums*.
Parameters
----------
nums : list, optional
List of numbers to add. Defaults to an empty list.
Returns
-------
int or float
The total of the elements.
"""
total = 0
for n in nums:
total += n
return total
if __name__ == "__main__":
# Test case 1: normal usage
data = [1, 2, 3, 4, 5]
print("Sum of", data, "=", list_sum(data))   # Expected: 15
# Test case 2: calling without an argument (exposes the mutable‑default bug)
print("Sum with no argument (first call) =", list_sum())  # Expected: 0
# Properly mutate the shared default list to illustrate the bug
# (using the function's __defaults__ tuple to access the default list)
list_sum.__defaults__[0].append(10)
# Second call – now the default list already contains 10
print("Sum with no argument (second call) =", list_sum())  # Unexpected: 10