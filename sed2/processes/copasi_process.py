import os
from pathlib import Path
from typing import Dict, Any
from process_bigraph import Process, Step, Composite, ProcessTypes, gather_emitter_results
import COPASI
from basico import (
    load_model,
    get_species,
    get_reactions,
    set_species,
    run_time_course,
    run_steadystate,
)
import COPASI

def _set_initial_concentrations(changes, dm):
    """
    changes: iterable of (species_name, value) pairs
    dm: COPASI DataModel as returned by basico.load_model
    """
    model = dm.getModel()
    assert isinstance(model, COPASI.CModel)

    references = COPASI.ObjectStdVector()

    for name, value in changes:
        species = model.getMetabolite(name)
        if species is None:
            print(f"Species {name} not found in model")
            continue
        assert isinstance(species, COPASI.CMetab)
        species.setInitialConcentration(float(value))
        references.append(species.getInitialConcentrationReference())

    if len(references) > 0:
        model.updateInitialValues(references)


def _get_transient_concentration(name, dm):
    """
    Return the *current* concentration (not initial) of a species.
    """
    model = dm.getModel()
    assert isinstance(model, COPASI.CModel)

    species = model.getMetabolite(name)
    if species is None:
        print(f"Species {name} not found in model")
        return None
    assert isinstance(species, COPASI.CMetab)
    return float(species.getConcentration())


class CopasiUTCStep(Step):

    config_schema = {
        'model_source': 'string',
        'time': 'float',
        'n_points': 'integer',
    }

    def __init__(self, config=None, core=None):
        super().__init__(config, core)

        model_source = self.config['model_source']

        # Path resolution
        if not model_source.startswith(('http://', 'https://')):
            model_path = Path(model_source)
            if not model_path.is_absolute():
                project_root = Path(__file__).parent.parent
                model_path = project_root / model_path
            model_source = str(model_path)

        # Load COPASI model
        self.dm = load_model(model_source)
        if self.dm is None:
            raise RuntimeError(
                f"load_model({model_source!r}) returned None. "
                "Check that the file exists and is a valid COPASI/SBML model."
            )

        self.cmodel = self.dm.getModel()

        # Cache identifiers
        spec_df = get_species(model=self.dm)
        self.species_names = spec_df.index.tolist()

        rxn_df = get_reactions(model=self.dm)
        self.reaction_names = rxn_df.index.tolist()

        # Simulation parameters
        self.interval = float(self.config.get('time', 1.0))
        self.n_points = int(self.config.get('n_points', 2))   # <-- NEW
        if self.n_points < 2:
            raise ValueError("n_points must be >= 2")

        self.intervals = self.n_points - 1   # COPASI requires this

    def initial_state(self) -> Dict[str, Any]:
        species_concentrations = {
            name: _get_transient_concentration(name=name, dm=self.dm)
            for name in self.species_names
        }

        rxn_df = get_reactions(model=self.dm)
        reaction_fluxes = {
            rxn_id: float(rxn_df.loc[rxn_id, 'flux'])
            for rxn_id in self.reaction_names
        }

        return {
            'species_concentrations': species_concentrations,
        }

    def inputs(self):
        return {
            'species_concentrations': 'map[float]',
            'species_counts': 'map[float]',
        }

    def outputs(self):
        return {
            'result': 'result',
        }

    def update(self, inputs):
        # Apply incoming concentrations
        spec_data = inputs.get('species_counts', {}) or {}
        changes = [
            (name, float(value))
            for name, value in spec_data.items()
            if name in self.species_names
        ]

        if changes:
            _set_initial_concentrations(changes, self.dm)

        # --- Run COPASI time course with intervals = n_points - 1 ---
        tc = run_time_course(
            start_time=0.0,
            duration=self.interval,
            intervals=self.intervals,   # <-- NEW
            update_model=True,
            model=self.dm,
        )

        # Time series
        time_list = tc.index.to_list()

        species_json = {
            s: tc[s].to_list()
            for s in self.species_names
            if s in tc.columns
        }

        flux_json = {
            r: tc[r].to_list()
            for r in self.reaction_names
            if r in tc.columns
        }

        result = {
            "time": time_list,
            "concentrations": species_json,
            "fluxes": flux_json,
        }

        return {"result": result}



class CopasiSteadyStateStep(Step):

    config_schema = {
        'model_source': 'string',
        'time': 'float',  # kept for symmetry with CopasiUTCStep, not used
    }

    def __init__(self, config=None, core=None):
        super().__init__(config, core)

        model_source = self.config['model_source']

        # Make sure the path is correct (relative to this file if needed)
        if not (model_source.startswith('http://') or model_source.startswith('https://')):
            model_path = Path(model_source)
            if not model_path.is_absolute():
                # go to the *project root*, not the processes/ directory
                project_root = Path(__file__).parent.parent
                model_path = project_root / model_path
            model_source = str(model_path)

        # basico DataModel
        self.dm = load_model(model_source)

        if self.dm is None:
            raise RuntimeError(
                f"load_model({model_source!r}) returned None. "
                "Check that the file exists and is a valid COPASI/SBML model."
            )

        # underlying COPASI CModel
        self.cmodel = self.dm.getModel()

        spec_df = get_species(model=self.dm)
        self.species_names = spec_df.index.tolist()

        rxn_df = get_reactions(model=self.dm)
        self.reaction_names = rxn_df.index.tolist()

    def initial_state(self) -> Dict[str, Any]:
        """
        Just report the current transient concentrations as the starting point.
        (Same pattern as CopasiUTCStep.)
        """
        species_concentrations = {
            name: _get_transient_concentration(name=name, dm=self.dm)
            for name in self.species_names
        }

        return {
            'species_concentrations': species_concentrations,
        }

    def inputs(self):
        return {
            'species_concentrations': 'map[float]',
            'species_counts': 'map[float]',
        }

    def outputs(self):
        return {
            'results': 'any',
        }

    def update(self, inputs):
        # --- 1) Prepare changes and update initial values efficiently ---

        # Prefer counts if present, otherwise concentrations
        spec_data = inputs.get('species_counts') or inputs.get('species_concentrations') or {}

        changes = [
            (name, float(value))
            for name, value in spec_data.items()
            if name in self.species_names
        ]

        if changes:
            _set_initial_concentrations(changes, self.dm)

        # --- 2) Run COPASI steady-state task ---
        # After run_steadystate(update_model=True), get_species/get_reactions
        # contain steady-state values.
        run_steadystate(update_model=True, model=self.dm)

        # --- 3) Read back steady-state species concentrations ---
        spec_df = get_species(model=self.dm)
        # basico steady-state example uses the 'concentration' column
        species_conc_ss = {
            name: float(spec_df.loc[name, 'concentration'])
            for name in self.species_names
            if name in spec_df.index
        }

        # --- 4) Read back steady-state reaction fluxes ---
        rxn_df = get_reactions(model=self.dm)
        reaction_fluxes_ss = {
            rxn_id: float(rxn_df.loc[rxn_id, 'flux'])
            for rxn_id in self.reaction_names
            if rxn_id in rxn_df.index
        }

        # --- 5) Package as a one-point "time series" to match CopasiUTCStep ---
        time_list = [0.0]  # single steady-state time point

        species_json = {name: [value] for name, value in species_conc_ss.items()}
        flux_json = {rid: [value] for rid, value in reaction_fluxes_ss.items()}

        results = {
            "time": time_list,
            "species_concentrations": species_json,
            "reaction_fluxes": flux_json,
        }

        return {"results": results}


class CopasiUTCProcess(Process):

    config_schema = {
        'model_source': 'string',
    }

    def __init__(self, config=None, core=None):
        super().__init__(config, core)

        model_source = self.config['model_source']

        # Make sure the path is correct (relative to this file if needed)
        if not (model_source.startswith('http://') or model_source.startswith('https://')):
            model_path = Path(model_source)
            if not model_path.is_absolute():
                # go to the *project root*, not the processes/ directory
                project_root = Path(__file__).parent.parent
                model_path = project_root / model_path
            model_source = str(model_path)

        # basico DataModel
        self.dm = load_model(model_source)

        if self.dm is None:
            raise RuntimeError(
                f"load_model({model_source!r}) returned None. "
                "Check that the file exists and is a valid COPASI/SBML model."
            )

        # underlying COPASI CModel (used by the speed-up helpers)
        self.cmodel = self.dm.getModel()

        spec_df = get_species(model=self.dm)
        self.species_names = spec_df.index.tolist()

        rxn_df = get_reactions(model=self.dm)
        self.reaction_names = rxn_df.index.tolist()

    def initial_state(self) -> Dict[str, Any]:
        species_concentrations = {
            name: _get_transient_concentration(name=name, dm=self.dm)
            for name in self.species_names
        }

        rxn_df = get_reactions(model=self.dm)
        reaction_fluxes = {
            rxn_id: float(rxn_df.loc[rxn_id, 'flux'])
            for rxn_id in self.reaction_names
        }

        return {
            'species_concentrations': species_concentrations,
            # 'reaction_fluxes': reaction_fluxes,
        }

    def inputs(self):
        return {
            'species_concentrations': 'map[float]',
            'species_counts': 'map[float]',
        }

    def outputs(self):
        # Keep nested 'results' for now to match your original API.
        return {
            'species_concentrations': 'map[float]',
            'reaction_fluxes': 'map[float]',
        }

    def update(self, inputs, interval):
        # --- 1) Prepare changes and update initial values efficiently ---

        # You can swap this to inputs['species_concentrations'] if that’s the true source
        spec_data = inputs.get('species_counts', {}) or {}

        # Only include species that actually exist in the model
        changes = [
            (name, float(value))
            for name, value in spec_data.items()
            if name in self.species_names
        ]

        if changes:
            _set_initial_concentrations(changes, self.dm)

        # --- 2) Run COPASI time course ---
        tc = run_time_course(
            start_time=0.0,
            duration=interval,
            update_model=True,
            model=self.dm,
        )

        # --- 3) Read back state using the fast helper ---
        species_concentrations = {
            name: _get_transient_concentration(name=name, dm=self.dm)
            for name in self.species_names
        }

        # --- 4) Reaction fluxes  ---
        rxn_df = get_reactions(model=self.dm)
        reaction_fluxes = {
            rxn_id: float(rxn_df.loc[rxn_id, 'flux'])
            for rxn_id in self.reaction_names
        }

        return {
            'species_concentrations': species_concentrations,
            'reaction_fluxes': reaction_fluxes,
        }



def run_copasi_utc(core):

    copasi_process = CopasiUTCStep({
                'model_source': 'models/BIOMD0000000012_url.xml',  # represillator model
                'time': 10.0,
                'n_points': 5,
            }, core=core)

    initial_state = copasi_process.initial_state()

    print(f'Initial state: {initial_state}')

    results = copasi_process.update(initial_state)

    print(f'Results: {results}')


def run_copasi_ss(core):

    copasi_process = CopasiSteadyStateStep({
                'model_source': 'models/BIOMD0000000012_url.xml',  # represillator model
            }, core=core)

    initial_state = copasi_process.initial_state()

    print(f'Initial state: {initial_state}')

    results = copasi_process.update(initial_state)

    print(f'Results: {results}')


if __name__ == '__main__':
    core = ProcessTypes()
    core.register_process('copasi_utc', CopasiUTCStep)
    core.register_process('copasi_ss', CopasiSteadyStateStep)
    core.register_process('copasi_process', CopasiUTCProcess)

    run_copasi_utc(core=core)
    run_copasi_ss(core=core)
