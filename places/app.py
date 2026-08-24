#!/usr/bin/env python3
"""places/app.py

A small command‑line utility that prints the value of π (pi) to a specified number of decimal
places.  By default it prints 1000 decimal digits, as required by the project description.

The script uses the *mpmath* library, which provides arbitrary‑precision arithmetic.  If mpmath
is not installed the script falls back to the standard library's ``decimal`` module, albeit
with a slightly slower algorithm.

Usage
-----
::

    python -m places.app [DIGITS]

If ``DIGITS`` is omitted the script prints 1000 decimal places.  The value is printed to
standard output; redirect the output to a file if desired.

Adjusting precision
-------------------
Change the ``default_digits`` constant below or pass a different integer on the command line.
The script ensures that the requested number of decimal places is produced exactly.
"""

import sys
import argparse
import traceback

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
default_digits = 1000  # Number of decimal places to output when no argument is given

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def compute_pi_mpmath(digits: int) -> str:
    """Return π as a string with *digits* decimal places using mpmath.

    Parameters
    ----------
    digits: int
        Desired number of decimal places (must be >= 0).

    Returns
    -------
    str
        π rounded to the requested precision.
    """
    try:
        from mpmath import mp
    except ImportError as exc:
        raise RuntimeError("mpmath is not installed") from exc

    # mpmath's ``dps`` (decimal places) includes the digit before the decimal point,
    # so we request a couple of extra digits to guard against rounding errors.
    mp.dps = digits + 5
    pi_val = mp.pi
    # Format with exactly *digits* places after the decimal point.
    fmt = f"{{0:.{digits}f}}"
    return fmt.format(pi_val)


def compute_pi_decimal(digits: int) -> str:
    """Return π as a string with *digits* decimal places using the decimal module.

    This implementation uses the Gauss–Legendre algorithm, which converges quadratically.
    It is slower than mpmath but works with only the standard library.
    """
    from decimal import Decimal, getcontext, localcontext

    # Set a higher precision internally to avoid loss during intermediate steps.
    internal_prec = digits + 10
    getcontext().prec = internal_prec

    # Initial values for the Gauss‑Legendre algorithm
    a = Decimal(1)
    b = Decimal(1) / Decimal(2).sqrt()
    t = Decimal(1) / Decimal(4)
    p = Decimal(1)

    # Iterate until the desired precision is reached.
    # The algorithm doubles the number of correct digits each iteration.
    for _ in range(0, 10):  # 10 iterations are more than enough for 1000+ digits
        a_next = (a + b) / 2
        b = (a * b).sqrt()
        t -= p * (a - a_next) ** 2
        a = a_next
        p *= 2
    pi = (a + b) ** 2 / (4 * t)

    # Now round to the exact number of decimal places requested.
    with localcontext() as ctx:
        ctx.prec = digits + 2  # a tiny buffer for rounding
        pi = +pi  # unary plus applies the new context rounding
        fmt = f"{{0:.{digits}f}}"
        return fmt.format(pi)


def compute_pi(digits: int) -> str:
    """Compute π to *digits* decimal places, trying mpmath first, then falling back.
    """
    if digits < 0:
        raise ValueError("Number of digits must be non‑negative")
    try:
        return compute_pi_mpmath(digits)
    except Exception as exc:
        # If mpmath is unavailable or fails, fall back to decimal.
        sys.stderr.write("[info] Falling back to decimal implementation: {}\n".format(exc))
        return compute_pi_decimal(digits)

# ---------------------------------------------------------------------------
# Command‑line interface
# ---------------------------------------------------------------------------

def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="places",
        description="Print π (pi) to a specified number of decimal places.")
    parser.add_argument(
        "digits",
        nargs="?",
        type=int,
        default=default_digits,
        help=f"Number of decimal places (default: {default_digits})")
    return parser.parse_args(argv)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        args = parse_args(argv)
        pi_str = compute_pi(args.digits)
        print(pi_str)
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.stderr.write(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
