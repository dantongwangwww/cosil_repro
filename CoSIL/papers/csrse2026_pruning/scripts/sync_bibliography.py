#!/usr/bin/env python3
"""Copy the compiled English bibliography order into the Chinese manuscript.

This reads only the paper's .bbl and JSON. It preserves 17 verified references
and checks that every reference is actually cited in both language versions.
"""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def sync():
    bbl = (ROOT / 'build/main.bbl').read_text(encoding='utf-8')
    chunks = re.split(r'\\bibitem\{([^{}]+)\}', bbl)
    refs = []
    for pos in range(1, len(chunks), 2):
        key, raw = chunks[pos], chunks[pos + 1].split(r'\end{thebibliography}')[0]
        urls = re.findall(r'\\url\{([^{}]+)\}', raw)
        raw = re.sub(r'\\urlprefix\s*\\url\{[^{}]+\}\.?', '', raw)
        raw = re.sub(r'\\doi\{([^{}]+)\}', r'DOI: \1', raw)
        raw = raw.replace(r'\newblock', ' ')
        raw = re.sub(r'\\(?:emph|textbf|textit)\{([^{}]*)\}', r'\1', raw)
        raw = raw.replace(r'\&', '&').replace(r'\_', '_')
        raw = raw.replace('{', '').replace('}', '').replace('~', ' ').replace('--', '–')
        text = ' '.join(raw.split()).strip()
        assert '\\' not in text, (key, text)
        refs.append({'key': key, 'number': len(refs) + 1, 'text': text, 'url': urls[0] if urls else ''})
    assert len(refs) == 17 and len({r['key'] for r in refs}) == 17
    tex = (ROOT / 'main.tex').read_text(encoding='utf-8')
    en_keys = {key.strip() for group in re.findall(r'\\cite\{([^}]+)\}', tex) for key in group.split(',')}
    source = ROOT / 'chinese_manuscript.json'
    manuscript = json.loads(source.read_text(encoding='utf-8'))
    cn_keys = {key.strip() for block in manuscript['blocks'] for group in re.findall(r'\{cite:([^}]+)\}', block.get('text', '')) for key in group.split(',')}
    expected = {r['key'] for r in refs}
    assert en_keys == cn_keys == expected, {'english_only': sorted(en_keys - cn_keys), 'chinese_only': sorted(cn_keys - en_keys), 'uncited': sorted(expected - cn_keys)}
    manuscript['references'] = refs
    source.write_text(json.dumps(manuscript, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Synchronized {len(refs)} references, all cited in both manuscripts.')


if __name__ == '__main__':
    sync()
