'''
Experiment comparing simulation results from Copasi and Tellurium
'''
from sed2 import create_core
from process_bigraph import Composite

def run_comparison_experiment(core):
    doc = {
        'tellurium_step': {
            '_type': 'step',
            'address': 'local:TelluriumUTCStep',
            'config': {
                'model_source': 'models/BIOMD0000000012_url.xml',
                'interval': 10,
                'n_points': 100,
            },
            'outputs': {
                'results': ['results', 'tellurium'],
            },
        },
        'copasi_step': {
            '_type': 'step',
            'address': 'local:CopasiUTCStep',
            'config': {
                'model_source': 'models/BIOMD0000000012_url.xml',
                'interval': 10,
                'n_points': 100,
            },
            'outputs': {
                'results': ['results', 'copasi'],
            },
        },
        'comparison': {
            '_type': 'step',
            'address': 'local:CompareResults',
            'config': {},
            'inputs': {
                'results': ['results'],
            },
            'outputs': {
                'comparison': ['comparison'],
            },
        },
    }

    doc = {'state': doc}
    sim = Composite(doc, core=core)
    result = sim.run({})




if __name__ == '__main__':
    core = create_core()
    run_comparison_experiment(core)
