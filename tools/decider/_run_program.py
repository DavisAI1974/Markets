"""Runs one decider program on the packet given on stdin; prints its decision as JSON. Started by serve in isolated
mode (python -I) with an empty environment in an empty folder: it imports nothing of Markets. The packet it passes on
is whole: `state` (the engine's state at the signal), `flow_lines`, `exchange_ns` and `layers` too, as structure."""
import importlib.util
import json
import sys

spec = importlib.util.spec_from_file_location("decider_program", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
json.dump(module.decide(json.loads(sys.stdin.read())), sys.stdout)
