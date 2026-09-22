"""Greg's standing rule (2026-09-16, said again 2026-09-22): the 4,096 context is retired. The Granite context is 131,072
with output = the remaining context; the NATIVE ROW WINDOW is declared once, in the verified schedule's
`model_context_rows` (data, pinned by digest) and carried into the prefix binding and every receipt, never as a code
literal or a default. This test is the guard that keeps the number from coming back."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BOSS = ROOT / 'research' / 'kalshi' / 'frankie_boss'
EXCLUDED = ('sunday_20260915_package', '/records/', '/tests/')
ROLE_LITERALS = re.compile(
    r"\bT_CTX\b|t_ctx\s*=\s*4096|context_rows\s*=\s*4096|model_context_rows\s*=\s*4096|context\s*=\s*4096"
    r"|service_context\W{0,3}\s*4096|max_model_len\s*=\s*4096|MAX_MODEL_LEN\W{0,6}4096|\(\s*4096\s*,\s*131072\s*\)|!=\s*4096")


def _sources():
    files = list(BOSS.rglob('*.py')) + list((ROOT / 'deploy' / 'aws').rglob('*.py')) + list((ROOT / 'deploy' / 'aws').rglob('*.sh'))
    files += list((ROOT / '.github' / 'workflows').glob('*.yml'))
    return [f for f in files if not any(x in f.as_posix() for x in EXCLUDED)]


def test_no_code_declares_the_row_window_or_a_granite_context_as_a_4096_literal():
    offending = []
    for f in _sources():
        for n, line in enumerate(f.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
            if ROLE_LITERALS.search(line):
                offending.append(f'{f.relative_to(ROOT)}:{n}: {line.strip()[:120]}')
    assert offending == [], 'the row window and the Granite context are declared data, never code literals:\n' + '\n'.join(offending)


def test_the_context_session_and_the_runtime_take_the_row_window_as_a_required_argument():
    import inspect
    from research.kalshi.frankie_boss import context_session, sunday_native_runtime, native_mbo_encoder
    assert inspect.signature(context_session.ContextSessionRunner.__init__).parameters['t_ctx'].default is inspect.Parameter.empty
    assert inspect.signature(sunday_native_runtime.initialize).parameters['context_rows'].default is inspect.Parameter.empty
    assert not hasattr(native_mbo_encoder, 'T_CTX') and 'context_rows' not in sunday_native_runtime.DEVELOPMENT
    assert 't_ctx' not in native_mbo_encoder.NativeRegistry().payload()   # model context is the session's declaration, not the encoder's
