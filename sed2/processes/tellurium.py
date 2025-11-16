import os
from pathlib import Path
from typing import Dict, Any

from process_bigraph import Step, ProcessTypes
import tellurium as te


class TelluriumUTCStep(Step):
    """
    Minimal Tellurium ODE Step.
    Uses only:
        - te.loadSBMLModel()
        - rr.simulate()

    Output format matches CopasiUTCStep exactly.
    """

    config_schema = {
        "model_source": "string",
        "time": "float",      # duration
        "n_points": "integer" # time samples
    }

    def __init__(self, config=None, core=None):
        super().__init__(config, core)

        model_source = self.config["model_source"]

        # ----- Resolve path like CopasiUTCStep -----
        if not model_source.startswith(("http://", "https://")):
            model_path = Path(model_source)
            if not model_path.is_absolute():
                project_root = Path(__file__).parent.parent
                model_path = project_root / model_path
            model_source = str(model_path)

        # ----- Minimal Tellurium load -----
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
        # Choose source (like CopasiUTCStep)
        incoming = (
            inputs.get("species_counts")
            or inputs.get("species_concentrations")
            or {}
        )

        # Update concentrations
        conc_vec = list(self.rr.getFloatingSpeciesConcentrations())
        for sid, value in incoming.items():
            idx = self._species_index.get(sid)
            if idx is not None:
                conc_vec[idx] = float(value)
        self.rr.setFloatingSpeciesConcentrations(conc_vec)

        # Run simulation
        tc = self.rr.simulate(0, self.interval, self.n_points)
        colnames = list(tc.colnames)

        # Time
        time = tc[:, colnames.index("time")].tolist()

        # Species trajectories
        species_json = {}
        species_cols = {}
        for sid in self.species_ids:
            if sid in colnames:
                idx = colnames.index(sid)
                species_cols[sid] = idx
                species_json[sid] = tc[:, idx].tolist()

        # Reaction fluxes
        flux_json = {rid: [] for rid in self.reaction_ids}
        saved = list(self.rr.getFloatingSpeciesConcentrations())

        for row in range(tc.shape[0]):
            row_conc = [tc[row, species_cols[sid]] for sid in self.species_ids]
            self.rr.setFloatingSpeciesConcentrations(row_conc)

            rates = self.rr.getReactionRates()
            for j, rid in enumerate(self.reaction_ids):
                flux_json[rid].append(float(rates[j]))

        # restore last state
        self.rr.setFloatingSpeciesConcentrations(row_conc)

        # JSON-safe result
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
            "time": 3000,
            "n_points": 5000,
        },
        core=core,
    )

    print("Initial:", step.initial_state())
    print("Results:", step.update(step.initial_state()))


if __name__ == "__main__":
    core = ProcessTypes()
    core.register_process("tellurium_utc", TelluriumUTCStep)
    run_test(core)
