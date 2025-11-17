from typing import Dict, Any

from process_bigraph import Step, Process

from math import sqrt
from typing import Dict, List, Tuple


def mean_squared_error_dict(a, b):
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



class CompareResults(Step):
    config_schema = {}

    def __init__(self, config, core):
        super().__init__(config, core)

    def inputs(self):
        return {
            'results': 'results',
        }

    def outputs(self):
        return {
            'comparison_result': 'map[float]',
        }

    def update(self, inputs):
        import ipdb; ipdb.set_trace()

        results_map = inputs.get("results", {})
        if not isinstance(results_map, dict) or len(results_map) < 2:
            raise ValueError(
                "update expects inputs['results'] to be a dict with at least two entries."
            )

        # 1) Choose reference (first key)
        result_ids = list(results_map.keys())
        ref_id = result_ids[0]
        ref_res = results_map[ref_id]

        ref_species = ref_res.get("species_concentrations", {})
        ref_flux = ref_res.get("reaction_fluxes", {})

        species_mse_by_id = {}
        flux_mse_by_id = {}

        # 2) Compare each other result against the reference
        for rid in result_ids[1:]:
            res = results_map[rid]

            species = res.get("species_concentrations", {})
            flux = res.get("reaction_fluxes", {})

            species_mse = mean_squared_error_dict(ref_species, species)
            flux_mse = mean_squared_error_dict(ref_flux, flux)

            species_mse_by_id[rid] = species_mse
            flux_mse_by_id[rid] = flux_mse

        return {
            'comparison_result': {
                'species_mse_by_id': species_mse_by_id,
                'flux_mse_by_id': flux_mse_by_id,
            }
        }
