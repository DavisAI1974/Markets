"""Exercise only the recorder's actual schedule-index guard, without model/classroom work."""
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parents[1]
RECORDER=ROOT/"research/kalshi/frankie_boss/operations/record_actual_frankie_response.py"

def check_index(index,schedule):
    main=next(node for node in ast.parse(RECORDER.read_text()).body if isinstance(node,ast.FunctionDef) and node.name=="main")
    selected=[]
    for node in main.body:
        if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id in ("schedule","steps") for target in node.targets):
            selected.append(node)
        elif isinstance(node,ast.If) and "args.cycle_index" in ast.unparse(node.test):
            selected.append(node)
    assert selected,"recorder must retain its actual cycle admission guard"
    namespace=dict(args=SimpleNamespace(cycle_index=index),h=dict(schedule=dict(path="fixture",sha256="fixture")),
        verified_json=lambda path,digest:schedule)
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(RECORDER),"exec"),namespace)

@pytest.mark.parametrize("index",[19,20,23])
@pytest.mark.parametrize("wrapped",[False,True])
def test_declared_schedule_admits_cycles_after_historical_nineteen(index,wrapped):
    steps=[{} for _ in range(24)]
    check_index(index,dict(steps=steps) if wrapped else steps)

@pytest.mark.parametrize("count,index",[(24,-1),(24,24),(4,4),(1,1)])
def test_recorder_rejects_any_index_outside_actual_declared_schedule(count,index):
    with pytest.raises(ValueError):
        check_index(index,dict(steps=[{} for _ in range(count)]))
