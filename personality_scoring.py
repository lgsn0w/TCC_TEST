from typing import Dict, List, Tuple
import math
import numpy as np


def center_response(r: int, k: int = 5) -> float:
    mid = (1 + k) / 2
    return r - mid


def reverse_response(r: int, k: int = 5) -> int:
    return (k + 1) - r


def score_axis(responses: Dict[str, int],
               axis_map: List[Tuple[str, float]],
               scale_k: int = 5,
               reverse_items: Dict[str, bool] = None,
               handle_missing: str = "adjust_denominator") -> float:
    if reverse_items is None:
        reverse_items = {}

    mid = (1 + scale_k) / 2
    weighted_sum = 0.0
    denom = 0.0

    item_abs_max = (scale_k - 1) / 2  # since c_i in [-item_abs_max, +item_abs_max]

    for q_id, w in axis_map:
        if q_id not in responses or responses[q_id] is None:
            continue
        r = responses[q_id]
        if reverse_items.get(q_id, False):
            r = reverse_response(r, k=scale_k)
        c = r - mid
        weighted_sum += w * c
        denom += abs(w) * item_abs_max

    if denom == 0:
        return 0.0

    normalized = weighted_sum / denom
    normalized = max(-1.0, min(1.0, normalized))
    return normalized


if __name__ == "__main__":
    user_answers = {
        "q1": 4, "q2": 2, "q3": 5, "q4": 3, "q5": 4,
        "q6": 1, "q7": 5, "q8": 3, "q9": 2
    }

    axes = {
        "EI": [("q1", 1.0), ("q2", -1.0), ("q3", 1.0)],
        "SN": [("q4", -1.0), ("q5", 1.0)],
        "TF": [("q6", 1.0), ("q7", -1.0)],
        "JP": [("q8", -1.0), ("q9", 1.0)],
    }

    reverse_items = {"q2": True, "q7": True}  # example

    results = {}
    for axis, mapping in axes.items():
        s = score_axis(user_answers, mapping, scale_k=5, reverse_items=reverse_items)
        results[axis] = s

    print(results)



def cronbach_alpha(item_matrix: np.ndarray) -> float:
    n_items = item_matrix.shape[1]
    if n_items < 2:
        return 0.0

    item_vars = item_matrix.var(axis=0, ddof=1)
    total_scores = item_matrix.sum(axis=1)
    total_var = total_scores.var(ddof=1)

    if total_var == 0:
        return 0.0

    alpha = (n_items / (n_items - 1.0)) * (1 - (item_vars.sum() / total_var))
    return alpha


def item_total_correlation(item_matrix: np.ndarray) -> np.ndarray:
    n_people, n_items = item_matrix.shape
    correlations = np.zeros(n_items)

    for j in range(n_items):
        item = item_matrix[:, j]
        total_excl = item_matrix.sum(axis=1) - item

        if np.std(item, ddof=1) == 0 or np.std(total_excl, ddof=1) == 0:
            correlations[j] = 0.0
        else:
            correlations[j] = np.corrcoef(item, total_excl)[0, 1]

    return correlations