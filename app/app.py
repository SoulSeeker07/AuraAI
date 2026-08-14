import sys

def add(x, y):
    return x + y

def subtract(x, y):
    return x - y

def multiply(x, y):
    return x * y

def divide(x, y):
    if y == 0:
        raise ValueError("Cannot divide by zero")
    return x / y

def display_help():
    print("Python Calculator App")
    print("Usage:")
    print("  Enter calculations in the format: number operator number (e.g., 5 + 3)")
    print("  Supported operators: +, -, *, /")
    print("  Type 'help' to see this message again")
    print("  Type 'quit' or 'exit' to end the session")

def main():
    display_help()
    
    while True:
        try:
            user_input = input("\nCalculate > ").strip()
            
            if user_input.lower() in ('quit', 'exit'):
                print("Goodbye!")
                break
            elif user_input.lower() == 'help':
                display_help()
                continue
            elif not user_input:
                continue
                
            parts = user_input.split()
            if len(parts) != 3:
                print("Error: Invalid format. Please use: number operator number (e.g., 5 + 3)")
                continue
                
            num1 = float(parts[0])
            operator = parts[1]
            num2 = float(parts[2])
            
            if operator == '+':
                result = add(num1, num2)
            elif operator == '-':
                result = subtract(num1, num2)
            elif operator == '*':
                result = multiply(num1, num2)
            elif operator == '/':
                try:
                    result = divide(num1, num2)
                except ValueError as e:
                    print(f"Error: {e}")
                    continue
            else:
                print(f"Error: Unsupported operator '{operator}'")
                continue
                
            print(f"Result: {result}")
            
        except ValueError:
            print("Error: Invalid numbers. Please ensure you are entering valid numeric values.")
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
