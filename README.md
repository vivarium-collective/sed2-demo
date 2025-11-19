# biocompose

biocompose is a package of process-bigraph processes and types for running fundamental biological simulation workflows and composites.

## install

This project uses `uv` so all you have to do is clone and run `uv sync` (as long as you have uv installed)

## usage

You can run as either a command or a server.

### command

To run the copasi/tellurium comparison demo you can invoke the `process_bigraph.run` command with the comparison document json:

```
uv run python -m process_bigraph.run --document biocompose/documents/copasi_tellurium_comparison.json
```

The resulting matrix is the MSE of the two runs in the respective simulators.

```
{'result': {'species_mse': {'tellurium': {'tellurium': 0.0, 'copasi': 4.5200220985492734e-07}, 'copasi': {'tellurium': 4.5200220985492734e-07, 'copasi': 0.0}}}}
```

### server

To run the same thing using the process server you can invoke the `rest_process.start` command with the same comparison document:

```
uv run python -m rest_process.start --host 0.0.0.0 --port 22222
```

Then you can send the server REST calls from another program. Here is an example with curl:

List all types in the registry:

```
> curl http://0.0.0.0:22222/list-types

["any","quote","tuple","union","boolean","number","integer","float","string","enum","list","map","tree","array","maybe","function","method","meta","mark","path","wires","schema","edge","length","time","current","luminosity","mass","substance","temperature","","length/time","length^2*mass/time","current*time","length^2*mass/temperature*time^2","length/time^2","mass/length*time^2","current*time^2/length^2*mass","length^2*mass/current^2*time^3","mass/length^3","/substance","length^2*mass/substance*temperature*time^2","current*time/substance","current^2*time^3/length^2*mass","length^2*mass/current*time^2","mass/temperature^4*time^3","length^4*mass/time^3","length*temperature","/temperature*time","length^3/mass*time^2","/length","length*mass/current^2*time^2","current^2*time^4/length^3*mass","length^3*mass/current^2*time^4","length^2","/time","length^3","length^3/time","length*mass/time^2","length^2*mass/time^2","length^2*mass/time^3","mass/length*time","length^2/time","length*time/mass","substance/length^3","substance/time","length^2/time^2","current*time/mass","mass/time^2","luminosity/length^2","mass/time^3","length^2*mass/current*time^3","length*mass/current*time^3","length^4*mass/current*time^3","current^2*time^4/length^2*mass","length^2*mass/current^2*time^2","mass/current*time^2","current*length*time","current*length^2*time","current*length^2","printing_unit","printing_unit/length","/printing_unit","mass/length","length/mass","length^1_5*mass^0_5/time","length^0_5*mass^0_5/time","length^1_5*mass^0_5/time^2","mass^0_5/length^0_5*time","time/length","length^0_5*mass^0_5","mass^0_5/length^1_5","time^2/length","protocol","emitter_mode","interval","step","process","result","results"]
```

List all processes in the process registry (these are discovered from imported packages):

```
> curl http://0.0.0.0:22222/list-processes

["console-emitter","ram-emitter","json-emitter","composite","biocompose.experiments.copasi_tellurium_comparison.Composite","biocompose.processes.CompareResults","biocompose.processes.CopasiSteadyStateStep","biocompose.processes.CopasiUTCProcess","biocompose.processes.CopasiUTCStep","biocompose.processes.TelluriumSteadyStateStep","biocompose.processes.TelluriumUTCStep","biocompose.processes.comparison_processes.CompareResults","biocompose.processes.copasi_process.Composite","biocompose.processes.copasi_process.CopasiSteadyStateStep","biocompose.processes.copasi_process.CopasiUTCProcess","biocompose.processes.copasi_process.CopasiUTCStep","biocompose.processes.tellurium_process.TelluriumSteadyStateStep","biocompose.processes.tellurium_process.TelluriumUTCStep","rest_process.processes.grow.GrowProcess","rest_process.tests.GrowProcess","Composite","CompareResults","CopasiSteadyStateStep","CopasiUTCProcess","CopasiUTCStep","TelluriumSteadyStateStep","TelluriumUTCStep","Process","Step"]
```

Initialize a new composite from the comparison document:

```
> curl -X POST -H "Content-Type: application/json" -d @sed2/documents/copasi_tellurium_comparison.json http://0.0.0.0:22222/process/composite/initialize

"6775b066-c821-480d-a881-c06655ba009d"
```

Get the results of the workflow:

```
> curl -X POST -H "Content-Type: application/json" -d '{"state": {}, "interval": 0.0}' http://0.0.0.0:22222/process/composite/update/6775b066-c821-480d-a881-c06655ba009d

[{"result":{}},{"result":{}},{"result":{"species_mse":{"tellurium":{"tellurium":0.0,"copasi":4.5200220985492734e-07},"copasi":{"tellurium":4.5200220985492734e-07,"copasi":0.0}}}}]
```