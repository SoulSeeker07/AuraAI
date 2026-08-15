# sum_list.py
"""
A tiny utility that returns the sum of the numbers in a list.
⚠️  COMMON BUG (intentionally left in):
The function uses a mutable default argument (`nums=[]`).
If the function is called without providing a list, the same list
object is reused across calls, which can lead to surprising results
when the caller mutates the argument.
"""
def list_sum(nums=[]):                     # <-- mutable default argument (bug)
"""
Return the sum of all numeric values in *nums*.
Parameters
----------
nums : list, optional
List of numbers to add.  Defaults to an empty list.
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
# ---- Test case 1: normal usage ----
data = [1, 2, 3, 4, 5]
print("Sum of", data, "=", list_sum(data))   # Expected: 15
# ---- Test case 2: calling without an argument (exposes the bug) ----
# First call – should be 0, but because the default list is reused it stays 0.
print("Sum with no argument (first call) =", list_sum())  # Expected: 0
# Modify the default list unintentionally
# (simulating a caller that mutates the argument)
list_sum([]).append(10)   # <-- this line would raise an error, but demonstrates the risk
# A more realistic accidental mutation:
default_list = []          # reference to the same default list
default_list.append(10)
# Second call – now the default list already contains 10
print("Sum with no argument (second call) =", list_sum())  # Unexpected: 10