def generate_fibonacci(n):
    """
    Generate the first n Fibonacci numbers.

    Args:
        n (int): The number of Fibonacci numbers to generate.

    Returns:
        list: A list of the first n Fibonacci numbers.
    """
    fib_sequence = [0, 1]
    while len(fib_sequence) < n:
        fib_sequence.append(fib_sequence[-1] + fib_sequence[-2])
    return fib_sequence

def main():
    try:
        n = 10
        fib_numbers = generate_fibonacci(n)
        print("The first {} Fibonacci numbers are:".format(n))
        print(fib_numbers)
    except Exception as e:
        print("An error occurred: {}".format(str(e)))

if __name__ == "__main__":
    main()