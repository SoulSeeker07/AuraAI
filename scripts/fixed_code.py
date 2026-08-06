#!/usr/bin/env python3
"""
sum_numbers.py – Calculate the sum of numbers in a list.
Fixed issues:
1️⃣ Replaced the mutable default argument (`numbers=[]`) with `numbers: Optional[List[float]] = None`.
2️⃣ Removed the unintended `numbers.append(0)` which altered the default list across calls.
3️⃣ Added proper type hints and indentation.
"""
from typing import List, Optional


def sum_numbers(numbers: Optional[List[float]] = None) -> float:
"""
Return the sum of all numeric values in *numbers*.
If *numbers* is omitted, an empty list is used, returning 0.0.
"""
# Fixed bug: avoid mutable default argument and do not modify the input list.
if numbers is None:
numbers = []          # create a fresh list for each call
total = 0.0
for n in numbers:
total += n
return total
def main() -> None:
# Test case 1 – normal usage
data = [1, 2, 3, 4.5]
expected = 10.5
result = sum_numbers(data)
print(f"Test 1 – input {data}: expected {expected}, got {result}")
# Test case 2 – using the default argument (should be 0.0)
result_default_first = sum_numbers()
print(f"Test 2 – first default call: expected 0.0, got {result_default_first}")
# Test case 3 – calling default again to confirm no side‑effects
result_default_second = sum_numbers()
print(f"Test 3 – second default call: expected 0.0, got {result_default_second}")
if __name__ == "__main__":
main()