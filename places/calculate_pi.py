"""
PI Calculator (Chudnovsky Algorithm)
Calculates pi to an arbitrary number of decimal places (default: 1000)
using Python's standard `decimal` library and the Chudnovsky formula.
"""

import sys
import math
import argparse
from decimal import Decimal, getcontext


def calculate_pi(decimal_places: int = 1000) -> str:
    """
    Calculate the value of Pi (π) to the specified number of decimal places
    using the Chudnovsky algorithm.

    Args:
        decimal_places (int): Number of decimal places to calculate (>= 0).

    Returns:
        str: String representation of Pi formatted to the specified decimal places.

    Raises:
        ValueError: If decimal_places is negative.
    """
    if not isinstance(decimal_places, int):
        raise TypeError("decimal_places must be an integer.")
    if decimal_places < 0:
        raise ValueError("Number of decimal places must be non-negative (>= 0).")
    if decimal_places == 0:
        return "3"

    # Set internal working precision higher than requested to avoid rounding errors
    guard_digits = 15
    getcontext().prec = decimal_places + guard_digits

    # Chudnovsky series constants
    # pi = (426880 * sqrt(10005)) / sum_{k=0}^inf (M_k * L_k) / X_k
    c_factor = Decimal(426880) * Decimal(10005).sqrt()
    m_val = Decimal(1)
    l_val = Decimal(13591409)
    x_val = Decimal(1)
    k_val = Decimal(6)
    series_sum = Decimal(13591409)

    # Number of iterations needed (Chudnovsky yields ~14.181647 decimal digits per term)
    iterations = math.ceil(decimal_places / 14.181647462725477) + 2

    for i in range(1, iterations):
        # Update recurrence terms
        m_val = m_val * (k_val**3 - 16 * k_val) / (Decimal(i)**3)
        l_val += Decimal(545140134)
        x_val *= Decimal(-262537412640768000)  # (-640320)**3
        series_sum += (m_val * l_val) / x_val
        k_val += Decimal(12)

    # Compute final value of pi
    pi_val = c_factor / series_sum

    # Set precision to exact output length and round
    getcontext().prec = decimal_places + 1
    pi_normalized = +pi_val  # Applies current context precision

    # Format result to ensure exact number of decimal places
    pi_str = str(pi_normalized)
    parts = pi_str.split(".")
    if len(parts) == 1:
        return parts[0]
    
    integer_part = parts[0]
    decimals = parts[1][:decimal_places].ljust(decimal_places, "0")
    return f"{integer_part}.{decimals}"


def main() -> None:
    """Command-line entry point for the PI calculator."""
    parser = argparse.ArgumentParser(
        description="Calculate the value of Pi (π) to high precision using the Chudnovsky algorithm."
    )
    parser.add_argument(
        "places",
        type=int,
        nargs="?",
        default=1000,
        help="Number of decimal places to calculate (default: 1000)"
    )

    try:
        args = parser.parse_args()
        if args.places < 0:
            parser.error("Decimal places must be a non-negative integer.")
        
        result = calculate_pi(args.places)
        print(result)
    except Exception as exc:
        sys.stderr.write(f"Error calculating Pi: {exc}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
