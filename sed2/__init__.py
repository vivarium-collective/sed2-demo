from sed2.processes import register_processes, get_sed_core

sed_types = {
    'result': 'map[list[float]]]',
    'results': 'map[result]'}

def register_types(core):
    core.register_types(sed_types)
    return core

def create_core():
    core = get_sed_core()
    core = register_types(core)
    return core
