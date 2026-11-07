#!/usr/bin/env python3
"""Build the bring-up wizards: one standalone HTML page per board.

Each boards/<name>.js defines `const BOARD = {...}` and starts with a line
`// out: <path relative to PCB/>`. The page is engine.html with that data
pasted in, so it works offline from a plain clone (double-click to open).

    python3 PCB/wizard/build.py
"""
import pathlib, re, html
HERE = pathlib.Path(__file__).resolve().parent
PCB = HERE.parent
engine = (HERE / 'engine.html').read_text(encoding='utf-8')
for src in sorted((HERE / 'boards').glob('*.js')):
    data = src.read_text(encoding='utf-8')
    out = re.search(r'^// out: (\S+)', data, re.M).group(1)
    title = re.search(r"title:\s*'([^']+)'", data).group(1)
    page = (engine.replace('%%TITLE%%', html.escape(title))
                  .replace('%%SRC%%', src.name)
                  .replace('%%DATA%%', data))
    dst = PCB / out
    dst.write_text(page, encoding='utf-8')
    print(f'{src.name} -> PCB/{out}')
