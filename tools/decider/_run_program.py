"""Runs one decider program on the packet given on stdin; prints its decision as JSON. Started by serve in isolated
mode (python -I) with an empty environment in an empty folder: it imports nothing of Markets."""
import importlib.util
import json
import sys

spec = importlib.util.spec_from_file_location("decider_program", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
json.dump(module.decide(json.loads(sys.stdin.read())), sys.stdout)
