#!/usr/bin/env python3
"""
Example script that deliberately contains an IndentationError.
The docstring inside the function is NOT indented, which triggers the error.
"""
def add_numbers(a, b):
"""Add two numbers and return the result."""
return a + b
def main():
# This call will never be reached because the script fails to compile
result = add_numbers(3, 5)
print(f"The sum of 3 and 5 is {result}")
if __name__ == "__main__":
main()