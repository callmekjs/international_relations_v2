"""Chapter/section structure for the 1st-phase 외교백서 volumes (data folders 2020-2025).

Public API
    extract_toc(pdf_path: str, year: int) -> list[dict]
        [{level, label, title, printed_page, printed_end, source, ...}] in reading order.
        level 1 = 장 or 부록, level 2 = 절 or 부록 item.
    chapter_of(toc: list[dict], printed_page: int) -> dict | None
        {"chapter": <level-1 entry>, "section": <level-2 entry or None>} or None.

Helpers (also used by build_structure.py)
    page_labels(doc)          -> per PDF page {'L': n, 'R': n} printed page per half (detected or inferred)
    parse_toc_page(doc)       -> entries parsed from the printed 목차 page text (None if no text 목차)
    detect_headings(doc, lab) -> section headings / appendix headings / running-header chapter titles

Methods tried in order: PDF outline (doc.get_toc) -> printed 목차 text -> body headings.
Whatever the base method, 절 start pages are re-anchored to the page label of the page on which the
body heading actually appears (the 목차 number is kept in `toc_page` when it differs).
Requires PyMuPDF (import fitz). Read-only on the PDF.
"""
from __future__ import annotations

import re
import unicodedata
from bisect import bisect_right

import fitz

fitz.TOOLS.mupdf_display_errors(False)

# ----------------------------------------------------------------------------- text helpers

_DOTS = str.maketrans({'\uff65': '·', '\u318d': '·', '\u30fb': '·', '\u2027': '·', '\u2219': '·'})


def clean_title(s: str) -> str:
    s = (s or '').translate(_DOTS)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def norm(s: str) -> str:
    s = unicodedata.normalize('NFKC', (s or '').translate(_DOTS))
    return re.sub(r'[\W_]+', '', s).lower()


def _lines(page, clip=None):
    out = []
    for b in page.get_text('dict', clip=clip)['blocks']:
        for l in b.get('lines', []):
            spans = [s for s in l['spans'] if s['text'].strip()]
            if not spans:
                continue
            t = ''.join(s['text'] for s in l['spans'])
            x0, y0, x1, y1 = l['bbox']
            out.append({'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1, 'xc': (x0 + x1) / 2, 'yc': (y0 + y1) / 2,
                        'size': max(s['size'] for s in spans), 'text': t.strip()})
    return out


def _halves(page):
    r = page.rect
    if r.width > r.height * 1.2:
        mid = r.x0 + r.width / 2
        return [('L', fitz.Rect(r.x0, r.y0, mid, r.y1)), ('R', fitz.Rect(mid, r.y0, r.x1, r.y1))]
    return [('S', r)]


def _half_lines(page):
    """{side: [lines]} split at the spread middle by line centre."""
    r = page.rect
    ls = _lines(page)
    hs = _halves(page)
    if len(hs) == 1:
        return {'S': ls}
    mid = r.x0 + r.width / 2
    return {'L': [l for l in ls if l['xc'] < mid], 'R': [l for l in ls if l['xc'] >= mid]}

# ----------------------------------------------------------------------------- page labels


def _detect_numbers(page):
    """printed page numbers found in the header/footer band at the outer edge of each half."""
    r = page.rect
    W, H = r.width, r.height
    found = {}
    for side, ls in _half_lines(page).items():
        c = []
        for l in ls:
            if not re.fullmatch(r'\d{1,3}', l['text']) or not (5.5 <= l['size'] <= 13):
                continue
            if not (l['y1'] < 80 or l['y0'] > H - 80):
                continue
            if side == 'L' and l['x0'] > W * 0.25:
                continue
            if side == 'R' and l['x1'] < W * 0.75:
                continue
            if side == 'S' and not (l['x0'] < W * 0.25 or l['x1'] > W * 0.75):
                continue
            c.append(int(l['text']))
        if c:
            found[side] = c
    return found


def page_labels(doc):
    """Return list (index = PDF page - 1) of dicts {side: printed_page or None} and a parallel
    list of dicts {side: 'detected'|'inferred'|'cover'}; plus a list of anomalies.
    PDF page 1 is the cover in all six volumes and gets no label."""
    halves = []  # (pdf_index, side)
    det = {}
    for i in range(doc.page_count):
        page = doc[i]
        sides = [s for s, _ in _halves(page)]
        nums = _detect_numbers(page) if i > 0 else {}
        for s in sides:
            halves.append((i, s))
            if s in nums:
                det[(i, s)] = nums[s]
    # choose a single value per half: the candidate consistent with the dominant offset of neighbours
    seq = {h: None for h in halves}
    k_of = {}
    for (i, s), cands in det.items():
        for n in cands:
            k_of.setdefault((i, s), []).append(n - 2 * (i + 1) - (1 if s == 'R' else 0))
    # dominant k in a sliding window
    keys = [h for h in halves if h in det]
    for idx, h in enumerate(keys):
        win = keys[max(0, idx - 6): idx + 7]
        from collections import Counter
        cnt = Counter(k for w in win for k in k_of[w])
        best = None
        for n, k in zip(det[h], k_of[h]):
            if best is None or cnt[k] > cnt[best[1]]:
                best = (n, k)
        if cnt[best[1]] >= 2 or len(win) < 3:
            seq[h] = best[0]
    # drop values that break monotonicity against both neighbours
    order = [h for h in halves if seq[h] is not None]
    for a, b, c in zip(order, order[1:], order[2:]):
        if not (seq[a] < seq[b] < seq[c]) and seq[a] < seq[c]:
            if seq[b] <= seq[a] or seq[b] >= seq[c]:
                seq[b] = None
    status = {h: ('detected' if seq[h] is not None else None) for h in halves}
    anomalies = []
    order = [h for h in halves if seq[h] is not None]
    pos = {h: n for n, h in enumerate(halves)}
    # fill gaps
    for a, b in zip(order, order[1:]):
        ia, ib = pos[a], pos[b]
        va, vb = seq[a], seq[b]
        g = ib - ia - 1
        avail = vb - va - 1
        if avail > g:
            anomalies.append({'type': 'printed_gap', 'after_pdf': a[0] + 1, 'after_side': a[1], 'before_pdf': b[0] + 1,
                              'before_side': b[1], 'missing_from': va + g + 1, 'missing_to': vb - 1})
        if g == 0:
            continue
        for j in range(1, g + 1):
            h = halves[ia + j]
            if avail >= g:
                v = va + j
            elif avail <= 0:
                v = None
            else:
                v = va + -(-j * avail // g)  # ceil
            seq[h] = v
            status[h] = 'inferred' if v is not None else None
        if 0 < avail < g:
            anomalies.append({'type': 'shared_label', 'pdf_pages': sorted({halves[ia + j][0] + 1 for j in range(1, g + 1)}),
                              'printed': list(range(va + 1, vb)), 'note': 'fewer printed numbers than PDF halves (full-bleed spread)'})
    # extrapolate before first / after last detected
    if order:
        first, last = order[0], order[-1]
        for j in range(pos[first] - 1, -1, -1):
            h = halves[j]
            v = seq[first] - (pos[first] - j)
            if h[0] == 0 or v < 1:
                seq[h] = None
                status[h] = 'cover' if h[0] == 0 else None
            else:
                seq[h] = v
                status[h] = 'inferred'
        for j in range(pos[last] + 1, len(halves)):
            h = halves[j]
            seq[h] = seq[last] + (j - pos[last])
            status[h] = 'inferred_after_last'
    labels = [dict() for _ in range(doc.page_count)]
    stat = [dict() for _ in range(doc.page_count)]
    for (i, s) in halves:
        labels[i][s] = seq[(i, s)]
        stat[i][s] = status[(i, s)]
    return labels, stat, anomalies

# ----------------------------------------------------------------------------- printed 목차 page

_CH = re.compile(r'^제\s*(\d+)\s*장\s*(.*)$')
_SEC = re.compile(r'^제\s*(\d+)\s*절\s*(.*)$')
_APX_ITEM = re.compile(r'^(?:부록\s*(\d+)|(\d{1,2})\s*\.\s*(.*))$')
_NUM = re.compile(r'^\d{2,3}$')


def find_toc_page(doc, max_pages=8):
    for i in range(min(max_pages, doc.page_count)):
        for l in _lines(doc[i]):
            if l['text'].replace(' ', '') == '목차' and l['size'] >= 18:
                return i
    return None


def parse_toc_page(doc):
    """Parse the text 목차 page. Returns list of entries or None when there is no text 목차."""
    ti = find_toc_page(doc)
    if ti is None:
        return None
    ls = _lines(doc[ti])
    for l in ls:
        l['kind'] = 'text'
        t = l['text']
        if _NUM.match(t):
            l['kind'] = 'num'
        elif _CH.match(t):
            l['kind'] = 'ch'
        elif _SEC.match(t):
            l['kind'] = 'sec'
        elif t.replace(' ', '') == '부록':
            l['kind'] = 'apx'
        elif _APX_ITEM.match(t):
            l['kind'] = 'item'
    used = set()

    def row_right_text(a, maxgap=60):
        best = None
        for j, l in enumerate(ls):
            if j in used or l['kind'] != 'text':
                continue
            if abs(l['yc'] - a['yc']) <= 4 and 0 <= l['x0'] - a['x1'] <= maxgap:
                if best is None or l['x0'] < ls[best]['x0']:
                    best = j
        return best

    def below_text(a, dy=26, dx=8):
        best = None
        for j, l in enumerate(ls):
            if j in used or l['kind'] != 'text':
                continue
            if abs(l['x0'] - a['x0']) <= dx and 0 <= l['y0'] - a['y1'] <= dy:
                if best is None or l['y0'] < ls[best]['y0']:
                    best = j
        return best

    def continuation(a, title_line, anchors):
        """wrapped title lines directly under the title, left-aligned between anchor and title start."""
        parts = []
        cur = title_line
        while True:
            nxt = None
            for j, l in enumerate(ls):
                if j in used or l['kind'] != 'text':
                    continue
                if not (a['x0'] - 2 <= l['x0'] <= cur['x0'] + 30):
                    continue
                gap = l['y0'] - cur['y1']
                if not (0 <= gap <= 9):
                    continue
                # no other anchor on that row in this column
                if any(abs(o['yc'] - l['yc']) <= 4 and abs(o['x0'] - a['x0']) <= 10 for o in anchors if o is not a):
                    continue
                nxt = j
                break
            if nxt is None:
                return parts
            used.add(nxt)
            parts.append(ls[nxt]['text'])
            cur = ls[nxt]

    anchors = [l for l in ls if l['kind'] in ('ch', 'sec', 'item', 'apx')]
    # titles
    for a in anchors:
        if a['kind'] == 'ch':
            m = _CH.match(a['text'])
            a['no'] = int(m.group(1))
            title = m.group(2).strip()
            if not title:
                j = row_right_text(a)
                if j is None:
                    j = below_text(a)
                if j is not None:
                    used.add(j)
                    title = ls[j]['text']
            a['title'] = title
        elif a['kind'] == 'apx':
            a['title'] = '부록'
        else:
            if a['kind'] == 'sec':
                m = _SEC.match(a['text'])
                a['no'] = int(m.group(1))
                title = m.group(2).strip()
            else:
                m = _APX_ITEM.match(a['text'])
                a['no'] = int(m.group(1) or m.group(2))
                title = (m.group(3) or '').strip()
            tl = a
            if not title:
                j = row_right_text(a, maxgap=45)
                if j is not None:
                    used.add(j)
                    title = ls[j]['text']
                    tl = ls[j]
            extra = continuation(a, tl, anchors)
            a['title'] = ' '.join([title] + extra)
    # page numbers: per row, pair anchors with numbers in reading direction
    pairable = [a for a in anchors if a['kind'] in ('sec', 'item')]
    nums = [l for l in ls if l['kind'] == 'num']
    rows = []
    for tok in sorted(pairable + nums, key=lambda l: l['yc']):
        for r in rows:
            if abs(r[0]['yc'] - tok['yc']) <= 5:
                r.append(tok)
                break
        else:
            rows.append([tok])
    left_votes = right_votes = 0
    for r in rows:
        r.sort(key=lambda l: l['x0'])
        if r and r[0]['kind'] == 'num':
            left_votes += 1
        elif r and r[0]['kind'] != 'num':
            right_votes += 1
    num_left = left_votes > right_votes
    for r in rows:
        seqr = r if not num_left else list(reversed(r))
        pending = None
        for tok in seqr:
            if tok['kind'] == 'num':
                if pending is not None:
                    pending['page'] = int(tok['text'])
                    pending = None
            else:
                pending = tok
    # assemble: section -> nearest chapter anchor above in same column
    chs = [a for a in anchors if a['kind'] == 'ch']
    apx = [a for a in anchors if a['kind'] == 'apx']
    entries = []
    for c in sorted(chs, key=lambda c: c['no']):
        secs = [s for s in anchors if s['kind'] == 'sec' and s['y0'] > c['y0']
                and c['x0'] - 5 <= s['x0'] <= c['x0'] + 60]
        secs = [s for s in secs if not any(o is not c and o['y0'] > c['y0'] and o['y0'] < s['y0']
                                           and c['x0'] - 5 <= s['x0'] <= o['x0'] + 60 and abs(o['x0'] - c['x0']) < 20
                                           for o in chs + apx)]
        entries.append({'level': 1, 'label': f"제{c['no']}장", 'no': c['no'], 'title': clean_title(c['title'])})
        for s in sorted(secs, key=lambda s: s['no']):
            entries.append({'level': 2, 'label': f"제{s['no']}절", 'no': s['no'], 'chapter_no': c['no'],
                            'title': clean_title(s['title']), 'toc_page': s.get('page')})
    if apx:
        entries.append({'level': 1, 'label': '부록', 'no': None, 'title': '부록'})
        for it in sorted([a for a in anchors if a['kind'] == 'item'], key=lambda a: a['no']):
            entries.append({'level': 2, 'label': f"부록 {it['no']}", 'no': it['no'], 'chapter_no': None,
                            'title': clean_title(it['title']), 'toc_page': it.get('page')})
    return {'pdf_page': ti + 1, 'entries': entries}

# ----------------------------------------------------------------------------- body headings

_SEC_ANY = re.compile(r'제\s*(\d+)\s*절')


def _top_zone(ls, H, ymax=0.34):
    return [l for l in ls if l['y0'] < H * ymax]


def detect_headings(doc, labels):
    """Scan every half for 절 headings, 부록 item headings and running-header 장 titles."""
    secs, items, run_ch = [], [], {}
    halfinfo = []  # (i, side, ls, band_text)
    for i in range(doc.page_count):
        page = doc[i]
        H = page.rect.height
        page_band = ''
        for side, ls in _half_lines(page).items():
            printed = labels[i].get(side)
            top = _top_zone(ls, H)
            big = [l for l in top if l['size'] >= 12]
            no = None
            for l in big:
                m = re.fullmatch(r'제\s*(\d+)\s*절', l['text'])
                if m:
                    no = int(m.group(1))
                    break
            if no is None:
                je = [l for l in big if l['text'] == '제']
                jl = [l for l in big if l['text'] == '절']
                dg = [l for l in top if re.fullmatch(r'\d{1,2}', l['text']) and l['size'] >= 30]
                for a in je:
                    for b in jl:
                        if abs(a['yc'] - b['yc']) > 4:
                            continue
                        for d in dg:
                            if a['x1'] - 2 <= d['xc'] <= b['x0'] + 2:
                                no = int(d['text'])
            if no is not None:
                cands = [l for l in top if l['size'] >= 19 and not _SEC_ANY.search(l['text'])
                         and not re.fullmatch(r'[\d\s.]+', l['text'])]
                title = ''
                if cands:
                    mx = max(l['size'] for l in cands)
                    tl = sorted([l for l in cands if abs(l['size'] - mx) < 2.1], key=lambda l: (round(l['y0']), l['x0']))
                    title = ' '.join(l['text'] for l in tl)
                secs.append({'pdf_page': i + 1, 'side': side, 'printed': printed, 'no': no, 'title': clean_title(title)})
            # running header / footer text (small type in the top or bottom band)
            band = [l for l in ls if (l['y1'] < 75 or l['y0'] > H - 75) and l['size'] < 12]
            rows = []
            for l in sorted(band, key=lambda l: l['yc']):
                for r in rows:
                    if abs(r[0]['yc'] - l['yc']) <= 3:
                        r.append(l)
                        break
                else:
                    rows.append([l])
            for r in rows:
                txt = ' '.join(x['text'] for x in sorted(r, key=lambda x: x['x0']))
                txt = re.sub(r'^\d{1,3}\s+|\s+\d{1,3}$', '', txt.strip())
                m = re.search(r'제\s*(\d+)\s*장[\s_.]*(.*)$', txt)
                if m:
                    ttl = re.split(r'\s*제\s*\d+\s*[절장]', m.group(2))[0]
                    ttl = re.sub(r'\s+\d{1,3}$', '', ttl).strip()
                    if ttl and not re.fullmatch(r'[\d\s]+', ttl):
                        run_ch.setdefault(int(m.group(1)), {}).setdefault(clean_title(ttl), 0)
                        run_ch[int(m.group(1))][clean_title(ttl)] += 1
            hdr = ' '.join(l['text'] for l in band)
            page_band += ' ' + hdr
            halfinfo.append([i, side, ls, printed, None])
        for h in halfinfo:
            if h[0] == i:
                h[4] = page_band
    # appendix item headings: only in halves after the last 절 heading, on pages whose running
    # header/footer mentions 부록; take big rows (>=13pt) near the top of the half
    last_sec = max(((s['pdf_page'], s['side']) for s in secs), default=(0, ''))
    started = False
    for i, side, ls, printed, band in halfinfo:
        if (i + 1, side) <= last_sec:
            continue
        if '부록' in (band or ''):
            started = True
        if not started:
            continue
        rowsb = []
        for l in sorted([l for l in ls if l['y0'] < 120 and l['size'] >= 13], key=lambda l: l['yc']):
            for r in rowsb:
                if abs(r[0]['yc'] - l['yc']) <= 4:
                    r.append(l)
                    break
            else:
                rowsb.append([l])
        for r in rowsb:
            txt = ' '.join(x['text'] for x in sorted(r, key=lambda x: x['x0']))
            if re.match(r'^\d{1,2}\)', txt) or txt.replace(' ', '') in ('부록',):
                continue
            m = re.match(r'^(\d{1,2})\s*\.?\s+(\S.*)$', txt)
            if m:
                items.append({'pdf_page': i + 1, 'side': side, 'printed': printed, 'no': int(m.group(1)),
                              'title': clean_title(m.group(2)), 'row_text': txt})
            elif not re.match(r'^(\d{1,2}\)|[(※*]|[\d.,\s]+$)', txt):
                items.append({'pdf_page': i + 1, 'side': side, 'printed': printed, 'no': None,
                              'title': clean_title(txt), 'row_text': txt})
    # chapter number for each section: numbering restarts at 1 for every chapter
    ch = 0
    prev = 0
    for s in secs:
        if s['no'] <= prev:
            ch += 1
        elif ch == 0:
            ch = 1
        s['chapter_no'] = ch
        prev = s['no']
    run_titles = {c: max(v.items(), key=lambda kv: kv[1])[0] for c, v in run_ch.items()}
    return {'sections': secs, 'items': items, 'running_chapter_titles': run_titles}

# ----------------------------------------------------------------------------- assembly


def _half_seq(doc, labels):
    seq = []
    for i in range(doc.page_count):
        for s in ('L', 'R', 'S'):
            if s in labels[i]:
                seq.append((i, s))
    return seq


def _divider_start(doc, labels, stat, pdf_page, side):
    """printed start of a chapter whose first heading sits on (pdf_page, side): include the
    immediately preceding unnumbered divider half/spread."""
    i = pdf_page - 1
    start = labels[i].get(side)
    if side == 'R' and stat[i].get('L') == 'inferred' and labels[i].get('L') is not None:
        return labels[i]['L'], [(pdf_page, 'L')]
    if side in ('L', 'S') and i - 1 >= 1:
        st = stat[i - 1]
        if all(v in ('inferred',) for v in st.values()):
            vals = [v for v in labels[i - 1].values() if v is not None]
            if vals:
                return min(vals), [(pdf_page - 1, s) for s in labels[i - 1]]
    return start, []


def extract_toc(pdf_path: str, year: int, prefer: str | None = None) -> list[dict]:
    """year is the data-folder year (the year the volume covers); it is only used as a sanity check
    (chapter 1 title should mention it) and recorded in entries. prefer='headings' forces the
    body-heading method (used for accuracy checks against the printed 목차)."""
    doc = fitz.open(pdf_path)
    labels, stat, _anom = page_labels(doc)
    outline = doc.get_toc()
    heads = detect_headings(doc, labels)
    # 1) PDF outline: usable only if it names 장/절. None of the six volumes qualifies (2020 has two
    #    file-merge bookmarks, 2021-2025 have none), so no outline parser is implemented.
    outline_ok = sum(1 for lv, t, p in outline if re.search(r'제\s*\d+\s*[장절]', t)) >= 5
    if outline_ok:
        import warnings
        warnings.warn('usable PDF outline found but not used; falling back to 목차/headings')
    # 2) printed 목차 text, 3) body headings
    parsed = None if prefer == 'headings' else parse_toc_page(doc)
    if parsed and sum(1 for e in parsed['entries'] if e['level'] == 2) >= 10:
        base = parsed['entries']
        method = 'toc_page'
    else:
        base = None
        method = 'headings'
    secs = heads['sections']
    by_key = {}
    for s in secs:
        by_key.setdefault((s['chapter_no'], s['no']), s)
    toc = []
    if base is None:
        # headings only: chapters from running headers, sections from body headings, appendix from item headings
        chs = sorted({s['chapter_no'] for s in secs})
        for c in chs:
            toc.append({'level': 1, 'label': f'제{c}장', 'no': c,
                        'title': heads['running_chapter_titles'].get(c, ''), 'source': 'running_header'})
            for s in [s for s in secs if s['chapter_no'] == c]:
                toc.append({'level': 2, 'label': f"제{s['no']}절", 'no': s['no'], 'chapter_no': c,
                            'title': s['title'], 'source': 'body_heading', '_head': s})
        its = [it for it in heads['items'] if it['no'] is not None]
        if len(its) < 3:
            # unnumbered item headings (2021 style): keep first occurrence of each title, number in order
            its, seen_t = [], set()
            for it in heads['items']:
                if it['no'] is None and norm(it['title']) and norm(it['title']) not in seen_t:
                    seen_t.add(norm(it['title']))
                    its.append(dict(it, no=len(its) + 1))
        if its:
            toc.append({'level': 1, 'label': '부록', 'no': None, 'title': '부록', 'source': 'running_header'})
            seen = set()
            for it in its:
                if it['no'] in seen:
                    continue
                seen.add(it['no'])
                toc.append({'level': 2, 'label': f"부록 {it['no']}", 'no': it['no'], 'chapter_no': None,
                            'title': it['title'], 'source': 'body_heading', '_head': it})
    else:
        for e in base:
            e = dict(e)
            e['source'] = 'toc_page'
            if e['level'] == 2 and e['chapter_no'] is not None:
                h = by_key.get((e['chapter_no'], e['no']))
                if h:
                    e['_head'] = h
            elif e['level'] == 2:
                # appendix item: first 부록 half after the 부록 start whose top heading matches the title
                cand = [it for it in heads['items'] if norm(e['title']) and (norm(e['title']) in norm(it['row_text'])
                                                                          or norm(it['title']) == norm(e['title']))]
                if cand:
                    e['_head'] = cand[0]
            toc.append(e)
    # printed pages
    for e in toc:
        h = e.pop('_head', None)
        if e['level'] == 2:
            if h and h.get('printed') is not None:
                e['printed_page'] = h['printed']
                e['pdf_page'] = h['pdf_page']
                e['heading_title'] = h['title']
                if e.get('toc_page') is not None and e['toc_page'] != h['printed']:
                    e['note'] = f"목차 says {e['toc_page']}, heading printed on page labelled {h['printed']}"
            else:
                e['printed_page'] = e.get('toc_page')
                e['note'] = 'heading not found in body; page taken from 목차'
    # chapter start = divider before its first section (or the first section page)
    for n, e in enumerate(toc):
        if e['level'] != 1:
            continue
        kids = []
        for f in toc[n + 1:]:
            if f['level'] == 1:
                break
            kids.append(f)
        first = next((k for k in kids if k.get('pdf_page')), None)
        if first:
            side = None
            for s in ('L', 'R', 'S'):
                if labels[first['pdf_page'] - 1].get(s) == first['printed_page']:
                    side = s
                    break
            start, div = _divider_start(doc, labels, stat, first['pdf_page'], side or 'L')
            e['printed_page'] = start
            e['first_section_page'] = first['printed_page']
            if div:
                e['divider'] = [{'pdf_page': p, 'side': s, 'printed': labels[p - 1][s]} for p, s in div]
        else:
            e['printed_page'] = kids[0]['printed_page'] if kids else None
    # ends
    last_printed = max((v for lab, st in zip(labels, stat) for s, v in lab.items()
                        if v is not None and st[s] == 'detected'), default=None)
    l1 = [e for e in toc if e['level'] == 1]
    for a, b in zip(l1, l1[1:]):
        a['printed_end'] = b['printed_page'] - 1 if b.get('printed_page') else None
    if l1:
        l1[-1]['printed_end'] = last_printed
    cur_end = None
    for n, e in enumerate(toc):
        if e['level'] == 1:
            cur_end = e['printed_end']
            continue
        nxt = next((f for f in toc[n + 1:] if f['level'] == 2 or f['level'] == 1), None)
        if nxt is None or nxt['level'] == 1:
            e['printed_end'] = cur_end
        else:
            e['printed_end'] = nxt['printed_page'] - 1 if nxt.get('printed_page') else None
    for e in toc:
        e['method'] = method
    if toc and toc[0]['level'] == 1 and str(year) not in toc[0]['title']:
        toc[0]['warning'] = f'chapter 1 title does not mention {year}'
    doc.close()
    return toc


def chapter_of(toc: list[dict], printed_page: int) -> dict | None:
    """Which 장 (level 1) and 절 (level 2) a printed page belongs to. None for front matter
    (before the first chapter) or pages past the end of the last entry."""
    if printed_page is None:
        return None
    l1 = [e for e in toc if e['level'] == 1 and e.get('printed_page') is not None]
    starts = [e['printed_page'] for e in l1]
    k = bisect_right(starts, printed_page) - 1
    if k < 0:
        return None
    ch = l1[k]
    if ch.get('printed_end') is not None and printed_page > ch['printed_end']:
        return None
    idx = toc.index(ch)
    kids = []
    for f in toc[idx + 1:]:
        if f['level'] == 1:
            break
        if f.get('printed_page') is not None:
            kids.append(f)
    sec = None
    for f in kids:
        if f['printed_page'] <= printed_page:
            sec = f
        else:
            break
    if sec is not None and sec.get('printed_end') is not None and printed_page > sec['printed_end']:
        sec = None
    return {'chapter': ch, 'section': sec}


if __name__ == '__main__':
    import glob
    import json
    import os
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    for y in [int(a) for a in sys.argv[1:]] or range(2020, 2026):
        f = glob.glob(os.path.join(r'C:\international_relations\data', str(y), '*.pdf'))[0]
        t = extract_toc(f, y)
        print('=====', y, t[0]['method'] if t else None, len(t))
        for e in t:
            print(('  ' if e['level'] == 2 else '') + f"{e['label']} {e['title']} | {e.get('printed_page')}-{e.get('printed_end')}"
                  + (f" toc={e.get('toc_page')}" if e.get('toc_page') is not None else '')
                  + (f" head='{e.get('heading_title')}'" if e.get('heading_title') and norm(e.get('heading_title')) != norm(e['title']) else '')
                  + (f" NOTE {e['note']}" if e.get('note') else ''))
