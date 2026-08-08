#!/usr/bin/env python3
"""
Example script that correctly defines a function with an indented docstring.
"""
def add_numbers(a, b):
"""Add two numbers and return the result."""
return a + b
def main():
# Test the function
result = add_numbers(3, 5)
print(f"The sum of 3 and 5 is {result}")
if __name__ == "__main__":
main()