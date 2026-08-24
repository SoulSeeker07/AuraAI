"""places/main.py

Calculate π to 1000 decimal places using the Chudnovsky algorithm.

The script can be executed directly::

    python -m places.main

It will print π with the requested precision (default 1000 digits).

The implementation relies on Python's :mod:`decimal` module for arbitrary‑precision
arithmetic and the fast‑converging Chudnovsky series.  The series provides roughly
14 correct decimal digits per term, so a few dozen terms are sufficient for a
thousand‑digit result.
"""

from __future__ import annotations

import math
import sys
from decimal import Decimal, getcontext


def compute_pi(digits: int) -> Decimal:
    """Return π rounded to *digits* decimal places.

    The function sets the global decimal context precision to ``digits + 10``
    to keep a small safety margin during the intermediate calculations.
    It then evaluates the Chudnovsky series until the absolute value of a
    term becomes smaller than ``10**(-(digits + 5))`` – far below the required
    precision – which guarantees that the final result is correctly rounded.

    Parameters
    ----------
    digits:
        Number of decimal places to produce.

    Returns
    -------
    Decimal
        The value of π rounded to the requested precision.
    """
    # Extra guard digits to avoid loss of significance during the sum.
    extra = 10
    getcontext().prec = digits + extra

    # Constant term C = 426880 * sqrt(10005)
    C = Decimal(426880) * Decimal(10005).sqrt()

    # Initialise the series sum.
    total = Decimal(0)
    k = 0
    # The series converges quickly; we stop when the term is negligible.
    while True:
        # (-1)^k
        sign = -1 if k % 2 else 1
        # (6k)!
        numerator_factorial = math.factorial(6 * k)
        # (13591409 + 545140134k)
        linear_term = 13591409 + 545140134 * k
        # Numerator of the term.
        numerator = Decimal(sign * numerator_factorial * linear_term)

        # Denominator components.
        denominator_factorial = (
            math.factorial(3 * k) * (math.factorial(k) ** 3)
        )
        # (640320)^(3k)
        power = Decimal(640320) ** (3 * k)
        denominator = Decimal(denominator_factorial) * power

        term = numerator / denominator
        total += term

        # Stop condition: term is far smaller than the required precision.
        if abs(term) < Decimal(10) ** (-(digits + 5)):
            break
        k += 1

    pi = C / total
    # Round to the exact number of requested digits.
    getcontext().prec = digits
    return +pi  # unary plus applies the new precision


def main(argv: list[str] | None = None) -> None:
    """Entry point for the script.

    Optional command‑line argument: number of decimal places (default 1000).
    Example::

        python -m places.main 500
    """
    if argv is None:
        argv = sys.argv[1:]
    try:
        digits = int(argv[0]) if argv else 1000
    except ValueError:
        print("The argument must be an integer specifying the number of decimal places.")
        sys.exit(1)

    if digits <= 0:
        print("Number of decimal places must be positive.")
        sys.exit(1)

    pi_val = compute_pi(digits)
    # Format with the requested number of digits after the decimal point.
    # The string representation of Decimal already contains all significant digits.
    print(str(pi_val))


if __name__ == "__main__":
    main()
