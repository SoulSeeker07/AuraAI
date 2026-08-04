def calculate_fibonacci(n):
    """
    Calculate the Fibonacci number at position n.
    
    Args:
    n (int): The position of the Fibonacci number to calculate.
    
    Returns:
    int: The Fibonacci number at position n.
    
    Raises:
    ValueError: If n is a negative integer.
    TypeError: If n is not an integer.
    """
    # Check if n is an integer
    if not isinstance(n, int):
        raise TypeError("Input must be an integer.")
        
    # Check if n is a non-negative integer
    if n < 0:
        raise ValueError("Input must be a non-negative integer.")
        
    # Base cases for Fibonacci sequence
    if n == 0:
        return 0
    elif n == 1:
        return 1
    else:
        # Recursive case for Fibonacci sequence
        return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)


def main():
    try:
        # Calculate Fibonacci number for 10
        fib_number = calculate_fibonacci(10)
        print(f"The Fibonacci number at position 10 is {fib_number}.")
    except (ValueError, TypeError) as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()