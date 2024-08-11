def triangular_number(n: int) -> int:
    """Return the nth triangular number.

    The nth triangular number is the sum of the first n positive integers.

    Example: triangular_number(3) == 6
    """
    return n * (n + 1) // 2
