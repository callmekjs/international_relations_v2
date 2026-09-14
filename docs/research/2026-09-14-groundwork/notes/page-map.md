# Printed-page mapping — six spread PDFs (data 2020–2025)

Run 2026-09-14, PyMuPDF 1.26.7, Python 3.12. Source PDFs read-only. Re-run: `python run_all.py` then `python toc_check.py` (this folder).

## 1. Result

`pdf_page` N is **1-based** (PyMuPDF index = N−1). Left half = printed **2N+k**, right half = **2N+k+1**.
0-based form (i = N−1): left = 2i + (k+2).

| folder | file | PDF pages | slots | k (1-based) | k+2 (0-based) | folio position | slots with folio | agree with k | printed range (k) | folio range |
|---|---|---|---|---|---|---|---|---|---|---|
| 2020 | 2021 외교백서(국문).pdf | 190 | 380 | **−4** | −2 | bottom outer corner, "096" | 352 | 352 (100 %) | 1–377 | 8–375 |
| 2021 | 2021년도 …_홈페이지 게시.pdf | 142 | 284 | **−4** | −2 | top outer corner, "096" | 258 | 244 (94.6 %) | 1–281 | 7–279 |
| 2022 | 2022년도 …(외교백서).pdf | 173 | 346 | **−2** | 0 | top outer corner, "098" | 322 | 322 (100 %) | 1–345 | 8–343 |
| 2023 | 2023년도 국제정세와 외교활동.pdf | 199 | 397 | **−2** | 0 | top outer corner, "098" | 374 | 374 (100 %) | 1–396 | 8–395 |
| 2024 | 2024년도 국제정세와 외교활동.pdf | 194 | 387 | **−2** | 0 | top outer corner, "098" | 360 | 360 (100 %) | 1–386 | 10–383 |
| 2025 | 2025년도 국제정세와 외교활동.pdf | 171 | 342 | **−2** | 0 | bottom outer corner, "98" (no zero pad) | 314 | 314 (100 %) | 1–341 | 8–339 |

- All six: 1,966 of 1,980 detected folios agree with k (99.3 %). The 14 that do not are one run in 2021 (section 3).
- Vote (pass 1): unanimous in 2020, 2022–2025; 2021 = 244 votes for −4, 14 for −3.
- Survey hypotheses confirmed: PDF 50 = 98·99 in 2023 and 2025; k = −4 holds for **both** folder 2020 and folder 2021; last folios 375/279/343/395/383/339 equal the survey's page counts.
- No roman numerals anywhere in the top/bottom 15 % bands of any page (scan: 0 hits).
- Numbering never restarts or jumps: under k every volume is one consecutive, unique sequence; chapter dividers, 부록 divider, text-less and image-only pages are counted in the pagination.

## 2. Method

**Split.** A page is a spread when width/height ≥ 1.2. Cut at W/2 unless a word crosses it; then cut at the nearest word-free x (only the two wrap covers needed this: 2020 p1 cut 515.0 — spine "2021" goes right; 2021 p1 cut 537.67 — spine title goes left). Clips are in `page.rect` coordinates (2021 p1 has CropBox x 283.5–1339.7 inside a 1623-wide MediaBox; the check below passed on it). Single-width pages (2023 p199, 2024 p194, both the last page) are one slot, side 'L' (= 2N+k; no folio on either).

**Split check** (every spread page, 1,067 pages, 404,416 words, 1,459,955 non-space characters):

| check | result |
|---|---|
| words whose bbox crosses the cut | 0 in all six |
| text lines (full-page `dict`) crossing the cut | 0 in all six |
| **line method** — `slot_text()`: full-page lines assigned to the half holding their centre; word + char multisets vs full page | **0 mismatches** in all six |
| **clip method** — `get_text("words"/"text", clip=…)` per half; char multiset vs full page | 0 mismatches in all six |
| clip method, word multiset | 3 pages differ, all 2023 chapter dividers (p4, p141, p154): MuPDF glues the giant chapter numeral to the previous line inside the clip (`기조`+`1` → `기조1`, `증진6`, `활동7`). No character lost or duplicated |
| text **blocks** crossing the cut | 140–218 per volume in 2020–2024 (0 in 2025) → never assign by block |

**Folio detection** (`pagemap._scan`). Pass 1: 1–3-digit words with centre within 8.5 % of the page height from the top/bottom edge and in the outer quarter of their half vote k = value − 2N − (R?1:0). Pass 2: folio positions are learned from the agreeing votes (side, band, distance of the word's outer edge from the half's outer edge, y); a slot's folio is a numeric word within 8 pt / 5 pt of a position backed by ≥ 3 votes. So a misprinted folio in the usual spot is still read (that is how the 2021 run was found).

**Independent check against the books' own tables of contents** (`toc_check.py` → `toc_check.txt`). Section-start pages were found by large "제N절" headings (≥ 16 pt; 2022 uses 13 pt 제 + 87 pt numeral + 13 pt 절). Their k-page must appear among the numbers printed on the ToC/divider pages:

| folder | section starts | k-page listed in ToC | control: page−1 / page+1 listed | detected folio listed |
|---|---|---|---|---|
| 2020 | 31 | 31 | 1 / 0 | 31 of 31 |
| 2021 | 27 | 27 | 0 / 0 | **26 of 27** (p5L: ToC 006, folio 007) |
| 2022 | 28 | 28 | 1 / 0 | 28 of 28 |
| 2023 | 27 | 27 | 1 / 0 | 27 of 27 |
| 2024 | 28 | 28 | 0 / 0 | 28 of 28 |
| 2025 | 27 | not checkable: ToC and dividers have no text layer | – | – |

## 3. Exceptions and inconsistencies

1. **2021, PDF pages 5–11: folios are one too high.** Printed folios read 007…020 where k gives 6…19 (both halves of all 7 spreads, 14 slots). Evidence that the folios, not k, are wrong: the 목차 (p3) and the chapter-1 divider (p4) both give 제1절 국제정세 개관 = **006**, and that section starts on p5L; the folios would put odd numbers on left pages; after the unnumbered chapter-2 divider (p12) folios resume at 022 on p13L, exactly k (so 020 → 022 across a two-page spread). Rendered check: p5 shows "007" top-left and "008" top-right. Consequence per policy:
   - `policy="k"` (default): 6…19, gap-free; `label_source='k'`, `detected_number` holds 7…20, `agrees=False`.
   - `policy="detected"`: 7…20; printed 6 is missing and p12L (k=20, collides with p11R folio 20) becomes None.
2. **Front matter has no printed numbers**; its numbers come from k (`label_source='k'`). Slots with 2N+k < 1 get `printed_page=None`, `label_source='none'`, `page_label='PDF<N><side>'`.

   | folder | none | implied (k) front matter | first folio |
   |---|---|---|---|
   | 2020 | p1 wrap cover (both halves, spine), p2L (no text) | 1 inner title "Diplomatic White Paper" (p2R) · 2–3 인사말 (p3) · 4–5 목차 (p4) · 6–7 ch.1 divider (p5) | 8 (p6L) |
   | 2021 | p1 wrap cover, p2L (no text) | 1 title (p2R) · 2–3 목차 (p3) · 4–5 ch.1 divider (p4); no 인사말 text in p1–p4 | 7 printed / 6 by k (p5L) |
   | 2022 | p1L (no text) | 1 title (p1R) · 2–3 인사말 (p2) · 4–5 목차 (p3) · 6–7 divider (p4) | 8 (p5L) |
   | 2023 | p1L (no text) | same layout as 2022 | 8 (p5L) |
   | 2024 | p1L (no text) | 1 title · 2–5 인사말 (p2–p3) · 6–7 목차 (p4) · 8–9 divider (p5) | 10 (p6L) |
   | 2025 | p1L (no text) | 1 title (p1R) · 2–7 **image-only** (p2–p4; half-page images at x 0–527 / 527–1055, 0 words) | 8 (p5L) |

3. **Unnumbered slots inside the book** (all agree with the surrounding sequence, none shifts it):
   - chapter/부록 divider spreads — 2020 p15 29 49 97 113 132 156 162; 2021 p12 18 31 58 74 91 110 115; 2022 p16 33 71 90 117 131 136; 2023 p17 34 89 111 141 154 159; 2024 p16 32 84 105 136 149 155.
   - 2025 image-only slots (0 words, image(s) covering the whole half; 18 in the body + 6 front-matter slots 2–7): 29, 30–31, 57, 58–59, 132–133, 174–175, 235, 236–237, 262–263, 271, 272–273 (PDF 15R, 16, 29R, 30, 67, 88, 118R, 119, 132, 136R, 137).
   - back matter: colophon + a no-text half — 2020 376/377 (p190), 2021 280/281 (p142), 2022 344/345 (p173), 2023 396 (single-width p199, colophon only), 2024 384/385 (p193) + 386 no-text single-width p194, 2025 340/341 (p171).
4. **Page geometry outliers**: wrap covers wider than the spreads (2020 p1 1065.8 pt vs 1020.5; 2021 p1 1056.2 pt with offset CropBox); 2025 p1 1037.5×711.5 vs 1054×711; single-width last pages in 2023 and 2024. No single page and no inserted separator page in the middle of any volume.

## 4. Verified vs inferred

Verified (ran / quoted): every number in sections 1–3; 2021 p2, p3, p4, p5, p11, p12 rendered and viewed; all 24 zero-word 2025 slots listed above carry an image covering the whole half (`get_image_info`); the other zero-word slots (all volumes) have no image covering more than 1 % of the half; contract check (types, clips tile each spread exactly, printed pages consecutive and unique per volume) in `work/contract_check.txt`. PyMuPDF 1.26.7 source, `site-packages/pymupdf/utils.py`, `get_text` docstring: "textpage: reuse this pymupdf.TextPage and make no new one. If specified, 'flags' and 'clip' are ignored." (`get_text_words` is the exception: with a textpage it keeps words at least half inside the clip). So pass `clip` without a shared textpage (what `map_pages` and `verify_split` do), or use `slot_text()`.

Inferred (not proven): that 2021's chapter-1 folios are a typesetting error rather than a different print layout; that the title page counts as printed page 1 in 2022–2025 (it follows from k and the first folio, but no number is printed); why MuPDF glues the numeral inside a clip (the Python fallback in `pymupdf/__init__.py` `extractWORDS` includes a character when its bbox overlaps the text-page rect, but the C++ path actually used was not read); that the thresholds (8.5 %/15 % bands, 8/5 pt tolerance) carry over to the second-phase volumes.

## 5. Suggestions for the plan

- Use `map_pages(path)` (policy "k"). Keep `detected_number` in `pages.jsonl` or a side file so the UI can say "인쇄 표기 7쪽" for the 14 slots of 2021 if wanted.
- Build slot text with `slot_text(page, clip, page.get_text("dict"))`; if `get_text(clip=…)` is used instead, expect the 3 glued words on 2023 dividers. Never split by text blocks.
- Mark `label_source='k'` front-matter numbers as "쪽 번호 인쇄 없음" in citations; drop or flag `none` slots; route the 24 image-only 2025 slots (and the other `n_words==0` slots) to `missing.json` / later OCR.
- Test fixtures for spec 8.1 (LLM-free): (2020,50,L)=96, (2021,50,R)=97, (2021,5,L)=6 with folio 7, (2021,13,L)=22, (2022,5,L)=8, (2023,50,L)=98, (2023,199,L)=396, (2024,6,L)=10, (2025,50,R)=99, (2020,1,R)=None; and `verify_split()["lines_mismatches"] == []` for all six.
- `get_toc` for 2020–2024 can trust ToC page numbers as printed_page (checked). 2025 ToC is an image: use running headers ("제1장_…") and the 27 large section headings.

## Files

| file | content |
|---|---|
| pagemap.py | `map_pages`, `slot_text`, `verify_split`, `analyze` |
| pagemap.csv | year, pdf_page, side, printed_page, detected_number, agrees (yes/no/blank) — 2,136 rows, UTF-8 BOM |
| pagemap_detail.csv | + clip, page_label, label_source, k_page, n_words, printed page under policy "detected" |
| results.json | per-volume `analyze()` + `verify_split()` output |
| toc_check.py / toc_check.txt | ToC cross-check |
| run_all.py | regenerates the CSVs and results.json |
| work/ | exploration scripts, logs, rendered PNGs, nofolio.txt (every slot without a folio with its first text) |
