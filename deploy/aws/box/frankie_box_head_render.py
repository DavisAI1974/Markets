"""HEAD_TEXT_V1: exact, reversible transforms of the request head (the text of prompt.md before the producer-evidence
block: the continuation, the run-findings ledger, the A_MEMORY findings, the delivered-artifact and knowledge-layer
tables, the preserved historical prompt). Greg, 2026-09-21 12:2xZ: shrink every category the BOSS reads, stack the
stacks. Profile 35603160044: the head is 191,195 bytes / 68,506 tokens; the findings 32.6k tokens over 316 lines with
four line prefixes repeated 5-44 times; three Markdown tables (73, 24 and 108 rows) whose rows share long path prefixes.

Two transforms, each applied per section (a section = a `#`, `##` or `###` heading and its text) and each undone by
`parse`; `render` returns the text only when parse(render(text)) == text:
  1. Markdown tables of at least TABLE_MIN rows: rows spelled `| a | b | c |` become one line per row with cells
     separated by a tab, `^` for a cell equal to the cell above, and per-column common prefixes declared once
     (`prefix:` line) and omitted from the cells. Applied only to a table whose every row rebuilds exactly from its
     cells (`| ` + ` | `.join(cells) + ` |`); the heading row and the `|---|` row stay verbatim.
  2. Repeated lines: a line of at least LINE_MIN characters that occurs at least twice in the section is written once
     on a `<<HEAD_TEXT_V1 lines n>>` dictionary and `<<@i>>` where it occurred. Applied only when no line of the
     section starts with `<<`.
Nothing is summarized: every transformed section carries its byte count and sha256 in its marker, and the text is
recovered exactly by `parse`.
"""
from __future__ import annotations

import hashlib
import re

SCHEMA = 'HEAD_TEXT_V1'
TABLE_MIN = 8
LINE_MIN = 24
PREFIX_MIN = 8
_HEADING = re.compile(r'^#{1,3} ', re.M)
_SEP_ROW = re.compile(r'^\|(\s*:?-+:?\s*\|)+\s*$')


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def sections(text):
    """[(start, end)] of the head's sections: the text before the first heading, then each heading with its text."""
    starts = [m.start() for m in _HEADING.finditer(text)]
    if not starts:
        return [(0, len(text))]
    bounds = ([(0, starts[0])] if starts[0] > 0 else []) + list(zip(starts, starts[1:] + [len(text)]))
    return bounds


# ---- 1. Markdown tables ----------------------------------------------------------------------------------------
def _cells(line):
    """The cells of a `| a | b |` row when the row rebuilds exactly from them, else None."""
    if not (line.startswith('| ') and line.endswith(' |')):
        return None
    inner = line[2:-2]
    cells = inner.split(' | ')
    if '| ' + ' | '.join(cells) + ' |' != line or any('\t' in c for c in cells):
        return None
    return cells


def _common_prefix(values):
    if not values:
        return ''
    first = min(values)
    last = max(values)
    i = 0
    while i < len(first) and i < len(last) and first[i] == last[i]:
        i += 1
    return first[:i]


def _table_blocks(lines):
    """[(first_row_index, end_index)] of Markdown tables with a heading row, a separator row and >= TABLE_MIN rows
    whose every data row splits into the same number of cells and rebuilds exactly."""
    out, i = [], 0
    while i < len(lines) - 2:
        if lines[i].startswith('|') and _SEP_ROW.match(lines[i + 1]):
            j = i + 2
            while j < len(lines) and lines[j].startswith('|'):
                j += 1
            rows = [_cells(l) for l in lines[i + 2:j]]
            width = len(rows[0]) if rows and rows[0] else 0
            if len(rows) >= TABLE_MIN and width and all(r is not None and len(r) == width and '^' not in r for r in rows):
                out.append((i, j))          # a literal `^` cell would read as a repeat: such a table stays verbatim
            i = j
        else:
            i += 1
    return out


def _render_table(rows):
    width = len(rows[0])
    prefixes = []
    for c in range(width):
        p = _common_prefix([r[c] for r in rows])
        prefixes.append(p if len(p) >= PREFIX_MIN else '')
    body, prev = [], None
    for r in rows:
        cells = []
        for c in range(width):
            v = r[c][len(prefixes[c]):]
            cells.append('^' if prev is not None and r[c] == prev[c] else v)
        body.append('\t'.join(cells))
        prev = r
    head = f'<<{SCHEMA} table rows={len(rows)} cols={width}>>'
    if any(prefixes):
        head += '\nprefix:\t' + '\t'.join(prefixes)
    return head + '\n' + '\n'.join(body) + f'\n<<{SCHEMA} end>>'


def _parse_table(block_lines):
    m = re.match(rf'<<{SCHEMA} table rows=(\d+) cols=(\d+)>>$', block_lines[0])
    n, width = int(m.group(1)), int(m.group(2))
    idx, prefixes = 1, [''] * width
    if idx < len(block_lines) and block_lines[idx].startswith('prefix:\t'):
        prefixes = block_lines[idx][len('prefix:\t'):].split('\t')
        idx += 1
    rows, prev = [], None
    for line in block_lines[idx:idx + n]:
        cells = line.split('\t')
        if len(cells) != width:
            raise ValueError('table row width differs')
        row = [(prev[c] if cells[c] == '^' and prev is not None else prefixes[c] + cells[c]) for c in range(width)]
        rows.append(row)
        prev = row
    if block_lines[idx + n] != f'<<{SCHEMA} end>>':
        raise ValueError('table end marker missing')
    return ['| ' + ' | '.join(r) + ' |' for r in rows]


# ---- 2. repeated lines ---------------------------------------------------------------------------------------------
def _render_lines(lines):
    counts = {}
    for l in lines:
        if len(l) >= LINE_MIN:
            counts[l] = counts.get(l, 0) + 1
    repeated = [l for l, n in counts.items() if n >= 2]
    if not repeated or any(l.startswith('<<') for l in lines):
        return None
    index = {l: i for i, l in enumerate(repeated)}
    body = [f'<<@{index[l]}>>' if l in index else l for l in lines]
    return [f'<<{SCHEMA} lines {len(repeated)}>>'] + repeated + [f'<<{SCHEMA} end>>'] + body


def _parse_lines(lines):
    m = re.match(rf'<<{SCHEMA} lines (\d+)>>$', lines[0])
    n = int(m.group(1))
    dictionary = lines[1:1 + n]
    if lines[1 + n] != f'<<{SCHEMA} end>>':
        raise ValueError('lines end marker missing')
    out = []
    for l in lines[2 + n:]:
        mm = re.fullmatch(r'<<@(\d+)>>', l)
        out.append(dictionary[int(mm.group(1))] if mm else l)
    return out


# ---- sections -------------------------------------------------------------------------------------------------------
def _render_section(text):
    """(rendered, changed): tables first, then the line dictionary over the result; a section that gains nothing
    is returned as it was."""
    lines = text.split('\n')
    blocks = _table_blocks(lines)
    out, pos, tables = [], 0, 0
    for i, j in blocks:
        out.extend(lines[pos:i + 2])
        out.append(_render_table([_cells(l) for l in lines[i + 2:j]]))
        pos = j
        tables += 1
    out.extend(lines[pos:])
    lines2 = '\n'.join(out).split('\n')
    dictionary = _render_lines(lines2)
    if dictionary is not None and len('\n'.join(dictionary)) < len('\n'.join(lines2)):
        lines2 = dictionary
        changed = True
    else:
        changed = tables > 0
    return '\n'.join(lines2), changed


def render(text):
    """The HEAD_TEXT_V1 text of a head: transformed sections are wrapped
    `<<HEAD_TEXT_V1 section bytes=N sha256=...>>` ... `<<HEAD_TEXT_V1 section end>>`; parse(render(text)) == text is
    checked here and a mismatch raises. Returns (rendered, report)."""
    out, report = [], dict(schema=SCHEMA, sections=0, transformed=0, tables=0, table_rows=0, line_dictionaries=0, bytes_before=len(text.encode('utf-8')))
    for s, e in sections(text):
        section = text[s:e]
        report['sections'] += 1
        rendered, changed = _render_section(section)
        if changed and len(rendered) < len(section):
            report['transformed'] += 1
            report['tables'] += rendered.count(f'<<{SCHEMA} table rows=')
            report['table_rows'] += sum(int(m) for m in re.findall(rf'<<{SCHEMA} table rows=(\d+)', rendered))
            report['line_dictionaries'] += rendered.count(f'<<{SCHEMA} lines ')
            out.append(f'<<{SCHEMA} section bytes={len(section.encode("utf-8"))} sha256={_sha(section)}>>\n{rendered}\n<<{SCHEMA} section end>>\n')
        else:
            out.append(section)
    rendered = ''.join(out)
    if parse(rendered) != text:
        raise ValueError('HEAD_TEXT_V1 render does not parse back to the head')
    report['bytes_after'] = len(rendered.encode('utf-8'))
    return rendered, report


def _parse_section(body, expected_bytes, expected_sha):
    lines = body.split('\n')
    if lines and lines[0].startswith(f'<<{SCHEMA} lines '):
        lines = _parse_lines(lines)
    out, i = [], 0
    while i < len(lines):
        if lines[i].startswith(f'<<{SCHEMA} table rows='):
            j = i
            while lines[j] != f'<<{SCHEMA} end>>':
                j += 1
            out.extend(_parse_table(lines[i:j + 1]))
            i = j + 1
        else:
            out.append(lines[i])
            i += 1
    text = '\n'.join(out)
    if len(text.encode('utf-8')) != expected_bytes or _sha(text) != expected_sha:
        raise ValueError('a HEAD_TEXT_V1 section does not rebuild to its recorded bytes')
    return text


def parse(rendered):
    """The head text the render was made from."""
    pattern = re.compile(rf'<<{SCHEMA} section bytes=(\d+) sha256=([0-9a-f]{{64}})>>\n(.*?)\n<<{SCHEMA} section end>>\n', re.S)
    out, pos = [], 0
    for m in pattern.finditer(rendered):
        out.append(rendered[pos:m.start()])
        out.append(_parse_section(m.group(3), int(m.group(1)), m.group(2)))
        pos = m.end()
    out.append(rendered[pos:])
    return ''.join(out)
