from typing import Dict, Any

from process_bigraph import Step, Process


class CompareResults(Step):

    config_schema = {}

    def __init__(self, config, core):
        super().__init__(config, core)

    def inputs(self):
        return {
            'results': 'map[map[list[float]]]',
            'tellurium_results': 'any',
            'copasi_results': 'any',
        }

    def outputs(self):
        return {
            'comparison': 'string',
        }

    def update(self, inputs):
        return {}
