"""fmt.py – number formatting matching the CW-Ranking Bot style"""

def fmt(n) -> str:
    """
    Format a number like the CW-Ranking bot:
      11640000000  →  11.64b
      1460         →  1.46k
      50000000     →  50.00m
      117640       →  117.64k
    """
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "0"
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}b"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}m"
    if n >= 1_000:
        return f"{n / 1_000:.2f}k"
    return str(int(n))


def rank_medal(i: int) -> str:
    """0-indexed rank medal."""
    return ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i + 1}."


def bar(value: float, maximum: float, length: int = 8) -> str:
    """Simple ASCII progress bar."""
    if maximum <= 0:
        return "░" * length
    filled = min(length, round((value / maximum) * length))
    return "█" * filled + "░" * (length - filled)
