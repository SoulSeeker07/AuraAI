def greet(name):
"""Return a greeting string."""
# Properly indented function body
return f"Hello, {name}!"
if __name__ == "__main__":
# Test the function (this line will never be reached because of the IndentationError above)
print(greet("World"))