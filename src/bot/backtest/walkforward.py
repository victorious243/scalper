from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class WalkForwardSplit:
    train_start: int
    train_end: int
    test_start: int
    test_end: int


def generate_splits(total_bars: int, train_size: int, test_size: int, step: int) -> List[WalkForwardSplit]:
    splits = []
    start = 0
    while start + train_size + test_size <= total_bars:
        splits.append(
            WalkForwardSplit(
                train_start=start,
                train_end=start + train_size,
                test_start=start + train_size,
                test_end=start + train_size + test_size,
            )
        )
        start += step
    return splits
