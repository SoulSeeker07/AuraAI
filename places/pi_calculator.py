#!/usr/bin/env python3
"""Pi Calculator

This script computes the value of \u03c0 (pi) to a user‑specified number of decimal
places (default: 1000). It uses the `mpmath` library for arbitrary‑precision
floating‑point arithmetic.

Usage:
    python -m places.pi_calculator [--digits N]

Options:
    --digits N   Number of decimal digits to compute (default: 1000).

The script prints the computed value of pi to standard output.

If `mpmath` is not installed, the script will display an informative error
message.
"""

import sys
import argparse

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calculate \u03c0 (pi) to a specified number of decimal places."
    )
    parser.add_argument(
        "--digits",
        type=int,
        default=1000,
        help="Number of decimal digits to compute (default: 1000).",
    )
    args = parser.parse_args()

    # Validate the requested precision
    if args.digits <= 0:
        sys.stderr.write("Error: Number of digits must be a positive integer.\n")
        sys.exit(1)

    try:
        # Import inside the try block so we can give a clear error if missing.
        import mpmath
    except ImportError as exc:
        sys.stderr.write(
            "Error: The 'mpmath' library is required but not installed.\n"
            "You can install it via pip: pip install mpmath\n"
        )
        sys.exit(1)

    # mpmath uses "decimal places" as the precision setting (dps).
    # We add a small safety margin (2 extra digits) to ensure correct rounding.
    mpmath.mp.dps = args.digits + 2

    try:
        pi_val = mpmath.pi
    except Exception as exc:
        sys.stderr.write(f"Error during pi computation: {exc}\n")
        sys.exit(1)

    # Convert to string with the exact number of requested digits.
    # The string representation includes "3." followed by the fractional part.
    pi_str = mpmath.nstr(pi_val, n=args.digits + 2, strip_zeros=False)
    # nstr may round the last digit; we truncate to the exact length.
    # Ensure we have "3." plus the requested digits.
    if pi_str.startswith("3."):
        pi_str = pi_str[: 2 + args.digits]
    else:
        # Fallback: just slice the string to the required length.
        pi_str = pi_str[: args.digits]

    print(pi_str)

if __name__ == "__main__":
    main()
