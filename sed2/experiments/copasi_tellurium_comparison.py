"""
Experiment comparing simulation results from Copasi and Tellurium
"""
from sed2.processes import get_sed_core
from process_bigraph import Composite

def run_comparison_experiment(core):
    doc = {
        "tellurium_step": {
            "_type": "step",
            "address": "local:TelluriumUTCStep",
            "config": {
                "model_source": "models/BIOMD0000000012_url.xml",
                "interval": 10,
                "n_points": 100,
            },
            "outputs": {
                "results": ["tellurium_results"],
            },
        },
        "copasi_step": {
            "_type": "step",
            "address": "local:CopasiUTCStep",
            "config": {
                "model_source": "models/BIOMD0000000012_url.xml",
                "interval": 10,
                "n_points": 100,
            },
            "outputs": {
                "results": ["copasi_results"],
            },
        },
        'comparison': {
            "_type": "step",
            "address": "local:CompareResults",
            "config": {},
            "inputs": {
                "tellurium_results": ["tellurium_results",],
                "copasi_results": ["copasi_results",],
            },
            "outputs": {
                "comparison": ["comparison"],
            },
        },
    }

    doc = {"state": doc}
    sim = Composite(doc, core=core)
    result = sim.run({})




if __name__ == "__main__":
    core = get_sed_core()
    run_comparison_experiment(core)
