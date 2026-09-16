"""Focused integration seams for the reviewed Dipole classroom; no model/cloud calls."""
import inspect
from types import SimpleNamespace

from research.kalshi.frankie_boss import dipole_classroom as classroom
from research.kalshi.frankie_boss import source_contract_runtime
from research.kalshi.frankie_boss.dipole_classroom_hardening import (
    HardenedDipoleClassroomPrincipalAdapter,
)
from research.kalshi.frankie_boss.dipole_classroom_integration import (
    IntegratedDipoleClassroomPrincipalAdapter,
    select_integrated_mode,
)
from research.kalshi.frankie_boss.frankie_dipole_classroom_adapter import (
    DipoleClassroomPrincipalAdapter,
)
from research.kalshi.frankie_boss.operations import run_actual_sunday as lawful
from research.kalshi.frankie_boss.operations import run_actual_sunday_classroom as integrated


def _completion(mode, *, mastered, acknowledged=True):
    return {
        "schema": classroom.COMPLETION_SCHEMA,
        "mode": mode,
        "teacher_complete": True,
        "mastered": mastered,
        "acknowledged": acknowledged,
    }


def test_integrated_adapter_skips_superseded_hardening_adapter_in_live_mro():
    assert issubclass(IntegratedDipoleClassroomPrincipalAdapter, DipoleClassroomPrincipalAdapter)
    assert HardenedDipoleClassroomPrincipalAdapter not in IntegratedDipoleClassroomPrincipalAdapter.__mro__
    assert integrated.ActualHost.principal_adapter_class is IntegratedDipoleClassroomPrincipalAdapter
    assert "adapter_class" in inspect.signature(source_contract_runtime.make_principal_adapter).parameters


def test_integrated_taper_still_requires_two_mastered_cycles_and_regresses():
    teach = classroom.ClassroomMode.TEACH.value
    guided = classroom.ClassroomMode.GUIDED.value
    socratic = classroom.ClassroomMode.SOCRATIC.value
    assert select_integrated_mode(()) == teach
    assert select_integrated_mode((_completion(teach, mastered=True),)) == teach
    assert select_integrated_mode((
        _completion(teach, mastered=True),
        _completion(teach, mastered=True),
    )) == guided
    assert select_integrated_mode((
        _completion(teach, mastered=True),
        _completion(teach, mastered=True),
        _completion(guided, mastered=True),
        _completion(guided, mastered=True),
    )) == socratic
    assert select_integrated_mode((
        _completion(teach, mastered=True),
        _completion(teach, mastered=True),
        _completion(guided, mastered=False),
    )) == teach


def test_classroom_runtime_attaches_package_and_adapter_without_runtime_class_rebinding(monkeypatch):
    host = object.__new__(integrated.ClassroomActualHost)
    package = {"binding": {"request_id": "run-cycle-00"}}
    host.classroom_package = package
    host._load_classroom_package = lambda cycle_directory: package
    saved = []
    host.api = SimpleNamespace(driver=SimpleNamespace(_save=lambda path, body: saved.append((path, body))))
    returned = SimpleNamespace(classroom_package=None, principal_adapter_class=None)
    host_class_before = lawful.ActualHost
    monkeypatch.setattr(lawful.ActualHost, "runtime", lambda self, *args: returned)
    result = integrated.ClassroomActualHost.runtime(host, {}, "cycle", None)
    assert result is returned
    assert result.classroom_package is package
    assert result.principal_adapter_class is IntegratedDipoleClassroomPrincipalAdapter
    assert lawful.ActualHost is host_class_before
    assert saved and saved[-1][1]["qualname"] == "IntegratedDipoleClassroomPrincipalAdapter"


def test_classroom_main_has_explicit_host_class_seam_instead_of_global_rebind():
    parameters = inspect.signature(integrated.main).parameters
    assert "host_class" in parameters
    source = inspect.getsource(integrated.main)
    assert "base.ActualHost =" not in source
    assert "DipoleClassroomPrincipalAdapter =" not in source


def _ast_modulo_seam(function, *, substitutions=()):
    """The function's AST dump (quote style and layout erased), docstring dropped, seam names mapped."""
    import ast, textwrap
    source = textwrap.dedent(inspect.getsource(function))
    for old, new in substitutions:
        source = source.replace(old, new)
    tree = ast.parse(source)
    node = tree.body[0]
    if node.body and isinstance(node.body[0], ast.Expr) and isinstance(getattr(node.body[0], 'value', None), ast.Constant) \
            and isinstance(node.body[0].value.value, str):
        node.body = node.body[1:]                       # the classroom copy carries a docstring; the lawful one a comment
    node.args = ast.arguments(posonlyargs=[], args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[])
    node.name = 'f'
    return ast.dump(node, include_attributes=False)


def test_classroom_run_and_main_are_the_lawful_bodies_modulo_the_named_seam():
    """Drift guard, like the compact-source host's prefix() guard: the classroom host copies the lawful
    host's run() and main() instead of rebinding globals, so the copies must stay the lawful text.
    If the lawful body changes, this fails and the copy is re-synced by hand."""
    assert _ast_modulo_seam(integrated.ClassroomActualHost.run) == _ast_modulo_seam(lawful.ActualHost.run)
    classroom_main = _ast_modulo_seam(integrated.main, substitutions=(
        ('host = host_class(configuration', 'host = ActualHost(configuration'),
        ('base.incomplete_output_alert(', 'incomplete_output_alert(')))
    assert classroom_main == _ast_modulo_seam(lawful.main)
