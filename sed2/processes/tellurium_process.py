import os
from pathlib import Path
from typing import Dict, Any

from process_bigraph import Step, ProcessTypes
import tellurium as te


class TelluriumUTCStep(Step):

    config_schema = {
        "model_source": "string",
        "time": "float",
        "n_points": "integer"
    }

    def __init__(self, config=None, core=None):
        super().__init__(config, core)

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
        self.interval = float(self.config.get("time", 1.0))
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
        return {"results": "any"}

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
        tc = self.rr.simulate(0, self.interval, self.n_points)
        colnames = list(tc.colnames)

        # Time
        time = tc[:, colnames.index("time")].tolist()

        # 4) Species trajectories
        species_json: Dict[str, list] = {}
        species_cols: Dict[str, int] = {}
        for sid in self.species_ids:
            if sid in colnames:
                idx = colnames.index(sid)
                species_cols[sid] = idx
                species_json[sid] = tc[:, idx].tolist()

        # 5) Reaction flux time series
        flux_json = {rid: [] for rid in self.reaction_ids}

        # For each time point, set state and query reaction rates
        for row in range(tc.shape[0]):
            # build concentration vector at this row
            for sid in self.species_ids:
                if sid in species_cols:
                    self.rr.setValue(sid, float(tc[row, species_cols[sid]]))

            rates = self.rr.getReactionRates()
            for j, rid in enumerate(self.reaction_ids):
                flux_json[rid].append(float(rates[j]))

        # 6) Restore last state (final row of the timecourse)
        last_row = tc.shape[0] - 1
        for sid in self.species_ids:
            if sid in species_cols:
                self.rr.setValue(sid, float(tc[last_row, species_cols[sid]]))

        # 7) Send update
        return {
            "results": {
                "time": time,
                "species_concentrations": species_json,
                "reaction_fluxes": flux_json,
            }
        }


# Simple test like Copasi
def run_test(core):
    step = TelluriumUTCStep(
        {
            "model_source": "models/BIOMD0000000012_url.xml",
            'time': 10.0,
            'n_points': 5,
        },
        core=core,
    )

    init = step.initial_state()
    print("Initial:", init)

    results = step.update(init)
    print("Results:", results)


if __name__ == "__main__":
    core = ProcessTypes()
    core.register_process("tellurium_utc", TelluriumUTCStep)
    run_test(core)
