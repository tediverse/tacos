import math


def calculate_reading_time(text: str) -> str:
    words = text.split()
    minutes = math.ceil(len(words) / 200) or 1
    return f"{minutes} min"
