"""HEAD_TEXT_V1 (deploy/aws/box/frankie_box_head_render.py): the request head's Markdown tables and repeated lines
through exact, reversible transforms; render checks parse(render(text)) == text itself. Hand-built head text shaped
like the real one (headings, a delivered-artifacts table with a shared path prefix, findings with repeated lines)."""
from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('frankie_box_head_render', ROOT / 'deploy/aws/box/frankie_box_head_render.py')
HR = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = HR
spec.loader.exec_module(HR)


def _head():
    rows = ''.join(f'| `keep_research_ng_exhaustion_{i:02d}` | by path | keep/research/ng_exhaustion/artifact_{i:02d}.json | {hashlib.sha256(bytes([i])).hexdigest()} | {1000 + i} |\n' for i in range(12))
    findings = ''.join(f'#### finding {i}\n- claim: finding number {i} says something specific\n- source: run `frankie-a-memory-20260828` seed 2ebb8ce8 (committed label permits service)\n'
                       f'- confidence_basis: The finding was measured on every retained member row without pooling.\n\n' for i in range(6))
    return ('# Current authorized continuation\nSunday 2021-10-03 is the sole source and run day.\nFeedback contract: {"as_of":1}\n\n'
            '### Delivered artifacts: 12 (0 inline, 12 by path)\n\n| artifact id | load | path | sha256 | bytes |\n|---|---|---|---|---:|\n' + rows +
            '\n### A_MEMORY findings served now\n\nOnly findings whose committed label permits service appear here.\n\n' + findings +
            '## The evidence\nComputed layer crosswalk `abc`:\n77 of 77 applicable input layers accounted.\n')


def test_tables_and_repeated_lines_render_smaller_and_parse_back():
    text = _head()
    rendered, report = HR.render(text)
    assert HR.parse(rendered) == text
    assert report['tables'] == 1 and report['table_rows'] == 12 and report['line_dictionaries'] == 1 and report['transformed'] == 2
    assert len(rendered) < len(text)
    assert '<<HEAD_TEXT_V1 table rows=12 cols=5>>' in rendered and 'prefix:\t`keep_research_ng_exhaustion_' in rendered
    assert rendered.count('- source: run `frankie-a-memory-20260828`') == 1 and rendered.count('<<@0>>') + rendered.count('<<@1>>') == 12
    assert '\t^\t' in rendered                                     # `by path` repeats down the load column
    for marker in ('<<HEAD_TEXT_V1 section bytes=', 'sha256=', '<<HEAD_TEXT_V1 section end>>'):
        assert marker in rendered


def test_untouched_sections_stay_verbatim_and_a_caret_cell_or_marker_line_blocks_the_transform():
    text = '# Title\nplain text\n\n## Next\nmore plain text\n'
    rendered, report = HR.render(text)
    assert rendered == text and report['transformed'] == 0
    caret = '## T\n\n| a | b |\n|---|---|\n' + ''.join(f'| x{i} | ^ |\n' for i in range(10))
    rendered, report = HR.render(caret)
    assert rendered == caret and report['tables'] == 0
    marker = '## T\n\n' + ('<<not a marker but starts like one>>\n' * 3)
    rendered, report = HR.render(marker)
    assert rendered == marker


def test_a_tampered_section_is_refused_on_parse():
    text = _head()
    rendered, report = HR.render(text)
    broken = rendered.replace('<<@0>>', '<<@1>>', 1)
    try:
        HR.parse(broken)
    except ValueError as err:
        assert 'does not rebuild' in str(err)
    else:
        raise AssertionError('a section that does not rebuild to its recorded bytes must refuse')
