import argparse
import sys
from .calculator import Calculator


def main():
    parser = argparse.ArgumentParser(description="Calculator App")
    parser.add_argument(
        "expression",
        nargs="*",
        help="Expression to evaluate (if omitted, starts interactive mode)",
    )
    args = parser.parse_args()

    calc = Calculator()

    if args.expression:
        # Evaluate a single expression passed via command line
        expr = " ".join(args.expression)
        try:
            result = calc.evaluate(expr)
            print(result)
        except ValueError as err:
            print(f"Error: {err}", file=sys.stderr)
            sys.exit(1)
    else:
        # Simple REPL when no expression is provided
        print("Calculator REPL – type 'exit' or 'quit' to leave.")
        while True:
            try:
                line = input("> ").strip()
                if line.lower() in {"exit", "quit"}:
                    break
                if not line:
                    continue
                result = calc.evaluate(line)
                print(result)
            except (ValueError, KeyboardInterrupt) as err:
                print(f"Error: {err}")


if __name__ == "__main__":
    main()
