"""Sanity checks of the search_proto API contract (run with the venv python)."""
import json, os, shutil, tempfile
import search_proto as sp

pages = [
    dict(page_id='2018|a.pdf|p1L', year=2018, chapter='제2장', printed_page=36, text='역사적인 북미 정상회담이\n2018년 6월 12일 싱가포르 센토사섬에서 개최됐다.'),
    dict(page_id='2018|a.pdf|p1R', year=2018, chapter='제2장', printed_page=37, text='한·미 양국은 긴밀히 공조했다.'),
    dict(page_id='2006|b.pdf|p3', year=2006, chapter='제1장', printed_page=None, text='국제사회는7월15일유엔안보리결의1695호를만장일치로채택하였다.'),
    dict(page_id='2024|c.pdf|p30L', year=2024, chapter='제3장', printed_page=58, text='4년 5개월 만인 5월 27일 서울에서 제9차 한·일·중 정상회의를 개최'),
    dict(page_id='2024|c.pdf|p30R', year=2024, chapter='제3장', printed_page=59, text=''),
]
idx = sp.build_index(pages)
r = sp.search(idx, '북미 정상회담 장소', None, 10)
assert r and r[0]['page_id'] == '2018|a.pdf|p1L', r
assert set(r[0]) >= {'page_id', 'year', 'chapter', 'printed_page', 'rank', 'score', 'snippet'}
assert sp.search(idx, '한미 공조', [2018], 3)[0]['page_id'] == '2018|a.pdf|p1R'          # 한·미 == 한미
assert sp.search(idx, '안보리 결의 1695호 만장일치', [2006], 3)[0]['page_id'] == '2006|b.pdf|p3'   # space-lost text
assert sp.search(idx, '한일중 정상회의 서울', None, 3)[0]['page_id'] == '2024|c.pdf|p30L'   # 한·일·중 == 한일중
assert sp.search(idx, '북미 정상회담', [2006], 10) == []                                   # filtered out
assert sp.search(idx, '', None, 10) == [] and sp.search(idx, '?!', None, 10) == []            # empty query
assert sp.search(idx, 'zzzz 없는말', None, 10) == []                                         # OOV only
assert len(sp.search(idx, '정상회의 정상회담', [2018, 2024], 10, balance_years=True)) == 2
d = tempfile.mkdtemp()
try:
    sp.save_index(idx, d); idx2 = sp.load_index(d)
    assert [h['page_id'] for h in sp.search(idx2, '북미 정상회담', None, 5)] == [h['page_id'] for h in sp.search(idx, '북미 정상회담', None, 5)]
finally:
    shutil.rmtree(d)
print('ok', json.dumps(r[0], ensure_ascii=False))
