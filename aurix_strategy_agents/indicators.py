from __future__ import annotations

from typing import Optional


def calculate_sma(values: list[Optional[float]], period: int) -> list[Optional[float]]:
    if period <= 0:
        return [None for _ in values]
    output: list[Optional[float]] = []
    for index in range(len(values)):
        window = values[index - period + 1 : index + 1]
        if len(window) < period or any(value is None for value in window):
            output.append(None)
            continue
        numeric = [float(value) for value in window if value is not None]
        output.append(sum(numeric) / period)
    return output


def calculate_rsi(closes: list[float], period: int) -> list[Optional[float]]:
    if period <= 0:
        return [None for _ in closes]
    if len(closes) < period + 1:
        return [None for _ in closes]
    output: list[Optional[float]] = [None for _ in closes]
    for index in range(period, len(closes)):
        gains = 0.0
        losses = 0.0
        for cursor in range(index - period + 1, index + 1):
            delta = float(closes[cursor]) - float(closes[cursor - 1])
            if delta >= 0:
                gains += delta
            else:
                losses += abs(delta)
        average_gain = gains / period
        average_loss = losses / period
        if average_loss == 0 and average_gain == 0:
            output[index] = 50.0
        elif average_loss == 0:
            output[index] = 100.0
        else:
            rs = average_gain / average_loss
            output[index] = 100.0 - (100.0 / (1.0 + rs))
    return output


def detect_cross_up(prev_value: Optional[float], prev_sma: Optional[float], current_value: Optional[float], current_sma: Optional[float]) -> bool:
    if prev_value is None or prev_sma is None or current_value is None or current_sma is None:
        return False
    return float(prev_value) <= float(prev_sma) and float(current_value) > float(current_sma)


def detect_cross_down(prev_value: Optional[float], prev_sma: Optional[float], current_value: Optional[float], current_sma: Optional[float]) -> bool:
    if prev_value is None or prev_sma is None or current_value is None or current_sma is None:
        return False
    return float(prev_value) >= float(prev_sma) and float(current_value) < float(current_sma)
