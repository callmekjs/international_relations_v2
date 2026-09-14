"""Quick checks of chapter_of() on the generated structure.json (no PDF access needed).
Run: python test_toc.py"""
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from toc import chapter_of  # noqa: E402

S = json.load(open(os.path.join(HERE, 'structure.json'), encoding='utf-8'))
V = {v['year']: v['toc'] for v in S['volumes']}


def lab(y, p):
    r = chapter_of(V[y], p)
    if r is None:
        return None
    return (r['chapter']['label'], r['section']['label'] if r['section'] else None)


cases = [
    # front matter -> None
    (2020, 5, None), (2025, 3, None),
    # chapter divider pages -> chapter, no section
    (2020, 6, ('제1장', None)), (2020, 7, ('제1장', None)), (2021, 21, ('제2장', None)), (2025, 31, ('제2장', None)),
    # first section page and boundaries
    (2020, 8, ('제1장', '제1절')), (2020, 20, ('제1장', '제1절')), (2020, 21, ('제1장', '제2절')),
    (2021, 6, ('제1장', None)), (2021, 7, ('제1장', '제1절')), (2021, 22, ('제2장', '제1절')),
    (2023, 395, ('부록', '부록 11')), (2025, 339, ('부록', '부록 11')), (2025, 274, ('부록', '부록 1')),
    (2024, 335, ('부록', '부록 8')), (2024, 336, ('부록', '부록 9')),
    # past the last printed page -> None
    (2020, 376, None), (2025, 340, None), (2022, 0, None),
]
bad = 0
for y, p, want in cases:
    got = lab(y, p)
    ok = got == want
    bad += not ok
    print('OK ' if ok else 'BAD', y, p, got, '' if ok else f'(want {want})')
# every printed page 1..last resolves monotonically (chapter numbers never go backwards)
for y, toc in V.items():
    last = max(e['printed_end'] for e in toc if e['level'] == 1)
    seen = []
    for p in range(1, last + 1):
        r = chapter_of(toc, p)
        if r:
            k = r['chapter']['label']
            if not seen or seen[-1] != k:
                seen.append(k)
    dup = len(seen) != len(set(seen))
    bad += dup
    print(y, 'chapter order', ' > '.join(seen), 'DUPLICATE' if dup else '')
print('FAILURES', bad)
sys.exit(1 if bad else 0)
