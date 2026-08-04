#!/usr/bin/env python3
"""
sum_numbers.py – Calculate the sum of numbers in a list (with a classic beginner bug).
Bug introduced:
The function uses a mutable default argument (numbers=[]) and appends a zero
to it, causing the default list to grow across multiple calls.
"""
def sum_numbers(numbers=[]):
"""Return the sum of all numeric values in *numbers*."""
# Beginner bug: mutating the default list
numbers.append(0)          # ensures the list is never empty, but corrupts future calls
total = 0
for n in numbers:
total += n
return total
def main():
# Test case 1 – normal usage
data = [1, 2, 3, 4.5]
expected = 10.5
result = sum_numbers(data)
print(f"Test 1 – input {data}: expected {expected}, got {result}")
# Test case 2 – using the default argument (should be 0, but bug makes it 0)
result_default_first = sum_numbers()
print(f"Test 2 – first default call: expected 0, got {result_default_first}")
# Test case 3 – calling default again to show the bug
result_default_second = sum_numbers()
print(f"Test 3 – second default call (bug manifested): expected 0, got {result_default_second}")
if __name__ == "__main__":
main()