from typing import Dict, Any

from process_bigraph import Step, Process

from math import sqrt
from typing import Dict, List, Tuple


def mean_squared_error_dict(a: Dict[str, List[float]],
                            b: Dict[str, List[float]]) -> float:
    sum_sq = 0.0
    count = 0

    common_keys = set(a.keys()) & set(b.keys())
    if not common_keys:
        raise ValueError("No overlapping keys between result dictionaries")

    for key in common_keys:
        va = a[key]
        vb = b[key]
        if len(va) != len(vb):
            raise ValueError(f"Length mismatch for key '{key}': {len(va)} vs {len(vb)}")
        for xa, xb in zip(va, vb):
            diff = xa - xb
            sum_sq += diff * diff
            count += 1

    if count == 0:
        raise ValueError("No data points to compare (count == 0)")

    return sum_sq / count


def safe_mse(a: Dict[str, List[float]],
             b: Dict[str, List[float]]) -> float | None:
    """Return MSE or None if we can't compute it (no overlap, etc.)."""
    try:
        return mean_squared_error_dict(a, b)
    except ValueError:
        return None

class CompareResults(Step):
    config_schema = {}

    def inputs(self):
        return {
            'results': 'results',
        }

    def outputs(self):
        return {
            'comparison': 'map[map[map[float]]]',
        }

    def update(self, inputs):
        results_map = inputs.get("results", {})
        if not isinstance(results_map, dict) or len(results_map) < 2:
            raise ValueError(
                "CompareResults.update expects inputs['results'] "
                "to be a dict with at least two entries."
            )

        engine_ids = list(results_map.keys())

        # Extract species time-series per engine
        species_by_id = {
            rid: (results_map[rid].get("concentrations", {}) or {})
            for rid in engine_ids
        }

        # Initialize symmetric MSE matrix
        species_mse = {
            i: {j: None for j in engine_ids} for i in engine_ids
        }

        # Pairwise MSE computation
        for i_idx, i in enumerate(engine_ids):
            for j_idx, j in enumerate(engine_ids):

                if i == j:
                    species_mse[i][j] = 0.0
                    continue

                # Only compute once per pair (i < j)
                if j_idx <= i_idx:
                    continue

                try:
                    mse = mean_squared_error_dict(species_by_id[i], species_by_id[j])
                except Exception:
                    mse = None

                species_mse[i][j] = mse
                species_mse[j][i] = mse

        return {
            "comparison": {
                '_add': {"species_mse": species_mse}
            }
        }

