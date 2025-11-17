import os
from pathlib import Path
from typing import Dict, Any

from process_bigraph import Step, ProcessTypes
import tellurium as te


class TelluriumUTCStep(Step):

    config_schema = {
        "model_source": "string",
        "time": "float",
        "n_points": "integer",
    }

    def initialize(self, config):
        model_source = self.config["model_source"]

        # ----- Resolve path -----------
        if not model_source.startswith(("http://", "https://")):
            model_path = Path(model_source)
            if not model_path.is_absolute():
                project_root = Path(__file__).parent.parent
                model_path = project_root / model_path
            model_source = str(model_path)

        # ----- Minimal Tellurium load (SBML) -----
        try:
            self.rr = te.loadSBMLModel(model_source)
        except Exception as e:
            raise RuntimeError(f"Could not load SBML model: {model_source}\n{e}")

        # ----- Cache IDs -----
        self.species_ids = list(self.rr.getFloatingSpeciesIds())
        self.reaction_ids = list(self.rr.getReactionIds())
        self._species_index = {sid: i for i, sid in enumerate(self.species_ids)}

        # ----- sim parameters -----
        self.time = float(self.config.get("time", 1.0))
        self.n_points = int(self.config.get("n_points", 2))

    # ------------------------------------------------
    # process-bigraph API
    # ------------------------------------------------
    def initial_state(self) -> Dict[str, Any]:
        conc = self.rr.getFloatingSpeciesConcentrations()
        return {
            "species_concentrations": {
                sid: float(conc[i]) for i, sid in enumerate(self.species_ids)
            }
        }

    def inputs(self):
        return {
            "species_concentrations": "map[float]",
            "species_counts": "map[float]",
        }

    def outputs(self):
        return {"result": "result"}

    # ------------------------------------------------
    # update logic
    # ------------------------------------------------
    def update(self, inputs):
        # 1) Choose source
        incoming = (
            inputs.get("species_counts")
            or inputs.get("species_concentrations")
            or {}
        )

        # 2) Update species concentrations using Tellurium's setValue
        for sid, value in incoming.items():
            if sid in self._species_index:
                self.rr.setValue(sid, float(value))

        # 3) Run simulation: from 0 -> interval, n_points samples
        tc = self.rr.simulate(0, self.time, self.n_points)
        colnames = list(tc.colnames)

        # Build a mapping from *normalized* column names to indices.
        # This turns "[S1]" -> "S1", etc.
        norm_to_index: Dict[str, int] = {
            name.strip("[]"): i for i, name in enumerate(colnames)
        }

        # Time
        if "time" not in norm_to_index:
            raise RuntimeError(f"'time' column not found in Tellurium result. Columns: {colnames}")
        time_idx = norm_to_index["time"]
        time = tc[:, time_idx].tolist()

        # 4) Species trajectories
        species_update: Dict[str, list] = {}
        species_cols: Dict[str, int] = {}
        for sid in self.species_ids:
            idx = norm_to_index.get(sid)
            if idx is not None:
                species_cols[sid] = idx
                species_update[sid] = tc[:, idx].tolist()

        # 5) Reaction flux time series
        flux_json = {rid: [] for rid in self.reaction_ids}

        # For each time point, set state and query reaction rates
        for row in range(tc.shape[0]):
            for sid, idx in species_cols.items():
                self.rr.setValue(sid, float(tc[row, idx]))

            rates = self.rr.getReactionRates()
            for j, rid in enumerate(self.reaction_ids):
                flux_json[rid].append(float(rates[j]))

        # 6) Restore last state (final row of the timecourse)
        last_row = tc.shape[0] - 1
        for sid, idx in species_cols.items():
            self.rr.setValue(sid, float(tc[last_row, idx]))

        import ipdb; ipdb.set_trace()

        # 7) Send update
        return {
            "result": {
                "time": time,
                "concentrations": {'_add': species_update},
                "fluxes": {'_add': flux_json},
            }
        }


class TelluriumSteadyStateStep(Step):

    config_schema = {
        "model_source": "string",
        "time": "float",   # unused, kept for symmetry
    }

    def __init__(self, config=None, core=None):
        super().__init__(config, core)

        model_source = self.config["model_source"]

        # ----- Resolve path ------
        if not model_source.startswith(("http://", "https://")):
            model_path = Path(model_source)
            if not model_path.is_absolute():
                project_root = Path(__file__).parent.parent
                model_path = project_root / model_path
            model_source = str(model_path)

        # ----- Load SBML via Tellurium -----
        try:
            self.rr = te.loadSBMLModel(model_source)
        except Exception as e:
            raise RuntimeError(f"Could not load SBML model: {model_source}\n{e}")

        # Cache species & reactions
        self.species_ids = list(self.rr.getFloatingSpeciesIds())
        self.reaction_ids = list(self.rr.getReactionIds())
        self._species_index = {sid: i for i, sid in enumerate(self.species_ids)}

    # ------------------------------------------------
    # process-bigraph API
    # ------------------------------------------------
    def initial_state(self) -> Dict[str, Any]:
        conc = self.rr.getFloatingSpeciesConcentrations()
        species_concs = {
            sid: float(conc[i])
            for i, sid in enumerate(self.species_ids)
        }
        return {
            "species_concentrations": species_concs,
        }

    def inputs(self):
        return {
            "species_concentrations": "map[float]",
            "species_counts": "map[float]",
        }

    def outputs(self):
        return {"result": "result"}

    # ------------------------------------------------
    # steady-state computation
    # ------------------------------------------------
    def update(self, inputs):
        # 1) Prefer counts, fall back to concentrations
        spec_data = (
            inputs.get("species_counts")
            or inputs.get("species_concentrations")
            or {}
        )

        # 2) Set incoming values on the model
        for sid, value in spec_data.items():
            if sid in self._species_index:
                self.rr.setValue(sid, float(value))

        # 3) Run steady-state computation
        #    RoadRunner steadyState() modifies the internal state to a (near-)steady state.
        try:
            self.rr.steadyState()
        except Exception as e:
            raise RuntimeError(f"Tellurium steadyState() failed: {e}")

        # 4) Read back steady-state species concentrations
        conc_ss = self.rr.getFloatingSpeciesConcentrations()
        species_ss = {
            sid: float(conc_ss[i])
            for i, sid in enumerate(self.species_ids)
        }

        # 5) Read back steady-state reaction fluxes
        rates_ss = self.rr.getReactionRates()
        flux_ss = {
            rid: float(rates_ss[i])
            for i, rid in enumerate(self.reaction_ids)
        }

        # 6) Package as a one-point "time series", time = 0.0
        time_list = [0.0]
        species_json = {sid: [val] for sid, val in species_ss.items()}
        flux_json = {rid: [val] for rid, val in flux_ss.items()}

        result = {
            "time": time_list,
            "concentrations": species_json,
            "fluxes": flux_json,
        }

        return {"result": result}


# Simple test like Copasi
def run_utc_test(core):
    step = TelluriumUTCStep(
        {
            "model_source": "models/BIOMD0000000012_url.xml",
            "time": 10.0,
            "n_points": 5,
        },
        core=core,
    )

    init = step.initial_state()
    print("Initial:", init)

    result = step.update(init)
    print("Result:", result)


def run_ss_test(core):
    step = TelluriumSteadyStateStep(
        {
            "model_source": "models/BIOMD0000000012_url.xml",
            "time": 0.0,   # unused
        },
        core=core,
    )

    init = step.initial_state()
    print("Initial:", init)

    out = step.update(init)
    print("Steady-state result:", out)

if __name__ == "__main__":
    core = ProcessTypes()
    core.register_process("tellurium_utc", TelluriumUTCStep)
    run_utc_test(core)
    run_ss_test(core)
