from biocompose.processes import register_processes, get_sed_core

sed_types = {
    'result': {
        'time': 'list[float]',
        'species_concentrations': 'map[list[float]]',
    },
    'results': 'map[result]'
}

def register_types(core):
    for key, schema in sed_types.items():
        core.register(key, schema)
    return core

def create_core():
    core = get_sed_core()
    core = register_types(core)
    return core
