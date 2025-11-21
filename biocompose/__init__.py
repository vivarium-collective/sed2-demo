from biocompose.processes import register_processes, get_sed_core

sed_types = {
    'result': {
        'time': 'list[float]',
        'species_concentrations': 'map[list[float]]',
    },
    'results': 'map[result]'
}

standard_types = {
    'numeric_result': {
        'time': 'list[float]',
        'columns': 'list[string]',
        'values': 'list[float]',
        'n_spacial_dimensions': 'tuple[int, int]'
    },
    'numeric_results': 'map[numeric_result]',
    'columns_of_interest': 'list[string]'
}


def register_types(core):
    for key, schema in sed_types.items():
        core.register(key, schema)
    for k, s in standard_types.items():
        core.register(k, s)
    return core

def create_core():
    core = get_sed_core()
    core = register_types(core)
    return core
