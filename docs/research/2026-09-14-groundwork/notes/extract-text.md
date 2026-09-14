# Text extraction for the six 2020-2025 volumes: decision and proof

Environment: PyMuPDF 1.26.7, Python 3.12, Windows 11. All numbers below come from scripts in this folder, run on every page of the six PDFs.
Terms: "half" = the left (L) or right (R) half of a PDF spread = one printed page. There are 2,138 halves (1,069 PDF pages x 2).

## 0. Decision

| Step | Decision |
|---|---|
| Engine | PyMuPDF `page.get_text("rawdict", clip=half, flags=TEXTFLAGS_TEXT)`, rebuilt into lines. No fallback engine needed: no half fails the spacing metric. |
| Split | Clip at the page midline (`page.rect` width / 2). The gutter is empty on every body spread. Pages narrower than 1.2 x height (2023 p199, 2024 p194) are single pages: L = whole page, R = "". |
| Order | MuPDF content-stream order. `sort=True` is not used. Two targeted fixes: display titles move up, footnotes move to the end. |
| Running blocks | Header and footer y-bands are learned per volume from repeated lines. The side tab is the 50 pt outer margin of R halves. `extract_half_text` puts these blocks first and last; `clean_text` strips them using `running_strings.json`. |
| Paragraphs | Lines are joined by the trailing-space rule plus a geometric continuation test. The output has one paragraph, table cell or heading per line. |
| Image-only | `find_image_only`: at most 20 body characters, with an image covering at least 30 % of the half or at least 200 vector items, and visible ink. |

Deliverables: `extract.py` (keep `running_strings.json` next to it), `quality.csv` (one row per half), this file.
Evidence: `run_eval.py`, `order_check.py`, `join_check.py`, `glue_check.py`, `timing.py`, `final_summary.json`, `texts/<year>_clean.txt` (all cleaned text), `samples/`.

## 1. Spacing quality (PyMuPDF keeps Korean spacing)

Metrics, computed per half in `quality.csv`:
- **long13 share** = Hangul runs (`[가-힣]+`) with at least 13 syllables / all Hangul runs. If spaces had been lost, this would jump to above 10 %.
- **1-syllable share** = whitespace tokens that are one Hangul syllable plus punctuation / tokens containing Hangul. If text were over-split, this would exceed 30 %.
- A half is flagged when long13 share > 3 % (with at least 20 runs) or 1-syllable share > 30 % (with at least 30 tokens).

| Year | PDF pages | Halves | Chars (no whitespace, cleaned) | raw long13 share | clean long13 share | raw 1-syl share | clean 1-syl share | Longest run | Halves failing |
|---|---|---|---|---|---|---|---|---|---|
| 2020 | 190 | 380 | 247,657 | 0.013 % (9/71,129) | 0.015 % | 9.6 % | 5.7 % | 15 | 0 |
| 2021 | 142 | 284 | 195,171 | 0.018 % | 0.030 % | 8.8 % | 4.7 % | 16 | 0 |
| 2022 | 173 | 346 | 227,920 | 0.022 % | 0.026 % | 9.2 % | 5.4 % | 18 | 0 |
| 2023 | 199 | 398 | 268,800 | 0.023 % | 0.026 % | 9.0 % | 5.2 % | 16 | 1 (p165 R) |
| 2024 | 194 | 388 | 257,370 | 0.022 % | 0.024 % | 9.3 % | 5.5 % | 20 | 1 (p161 R) |
| 2025 | 171 | 342 | 218,347 | 0.015 % | 0.016 % | 6.4 % | 5.5 % | 13 | 0 |

- "raw" means `page.get_text("text", clip=half)`. "clean" means `clean_text(extract_half_text(...))`. The total is 1,415,265 non-whitespace characters, which matches the spec's "about 1.46 million" before header removal.
- **The 2 flagged halves are false alarms.** Every run of 13 or more syllables in all six volumes is a real compound name, for example 남극해양생물자원보존위원회 or 주상트페테르부르크총영사관에서는 (full list in `glue_check.py` output and `texts/`). The 2023 p165 R and 2024 p161 R halves are tables of international organisations.
- Raw 1-syllable share is about 9 % in the InDesign volumes (2020-2024) because Korean justified text breaks words at line ends (`동력` / `을`). Line joining brings it down to about 5 %.
- The worst raw halves are the org charts (97 % single-syllable tokens: one vertical glyph per line). They are fixed by merging vertical glyphs.
- **Fallback test (pdfminer / glyph gaps): not needed.** No half fails. Glyph gaps are still used in one place (section 3).

## 2. Split and reading order

**Midline split (verified).**
- On all body spreads, no word crosses the midline and the text-free gutter is at least 113 pt wide: the L text ends at x ≤ 459 and the R text starts at x ≥ 572 on a 1020-wide page, so text stays at least 51 pt from the midline (2025: ≤ 448 and ≥ 607 on 1054).
- Non-whitespace characters of the L clip + R clip equal those of the whole page on every page except the two covers:
  - 2020 p1: the spine text "2021" straddles the midline.
  - 2021 p1: the spine title straddles the midline (its cropbox is offset: cropbox 283-1340 of mediabox 1623).
  - In both cases the straddling glyphs appear in **both** halves (4 and 15 characters).
- The docs say "Any content ... not fully contained in clip will be completely omitted" (https://pymupdf.readthedocs.io/en/latest/_sources/page.rst). Observed behaviour differs, but only for these glyphs.
- `extract_half_text` is lossless: its non-whitespace character multiset equals the raw clip text on all 2,138 halves (flag `ext_not_lossless` = 0).

**Why not `sort=True`.**
- Docs: for "text", the lines "are completely re-synthesized ... which even establishes the original layout to some extent"; for "dict", sorting is by block `(y1, x0)` (https://pymupdf.readthedocs.io/en/latest/_sources/page.rst).
- In 1.26.7, `utils.get_sorted_text` rebuilds lines from words and pads gaps with spaces. On 2020 p76 L this interleaved the table cells of neighbouring columns.
- Default order keeps each table cell's lines together, row by row, and keeps paragraphs unbroken by captions.

**Findings (`order_check.json`, `block_order.txt`).**
- Prose lines (at least 25 characters and wider than 250 pt) going upward after the fixes:
  - 2020: 3 halves (p31 L, p77 L, p126 L: a table or chart placed above body text but written after it).
  - 2022: 1 half (p147 R).
  - 2021, 2023, 2024, 2025: 0.
- Halves with any upward jump (all lines): 103, 50, 88, 105, 125, 81. These are nearly all tables with vertically centred cells, or photo captions emitted after the paragraph that surrounds the photo. Both are harmless.
- `table_or_columns` flag (at least 8 side-by-side lines): 85, 75, 92, 103, 98, 80 halves.

**Fixes applied (halves changed: 50, 47, 49, 55, 51, 6).**
- **Display titles.** Lines at least 2 pt larger than the body text and above the first body line are moved up to just before the first line below them. Example: the section-start pages were `1. 개관 … 국제정세 개관 제1절` and now read `제1절 / 국제정세 개관 / 1. 개관`.
- **Footnotes.** The small-type zone from the first `1)` marker down, with no body text below it, goes to the end. This fixes 2020 p23 R and p80 L, where footnotes came before the body.
- **Org charts** (2020 p163, 2021 p116, 2022 p137, 2023 p160, 2024 p156). Vertical one-glyph lines are merged: `장/관/정/책/보/좌/관` becomes `장관정책보좌관`.

**Paragraph joining (`join_check.json`).**
- Verified signal: InDesign and HWP write a trailing space at a line end exactly when a word boundary falls there. Every comma-final line has one, and no mid-word break has one.
- Continuation test: same font and size; next baseline 0.9-2.4 em lower; horizontal overlap; the next line does not start with a list marker (`• - ※ ① 1) 1. [ < 제N장/절`); the line fills its column (at least 8 em wide and at the column's right edge, or aligned with its neighbour, which covers text wrapped beside photos).

| Year | Mid-word pairs joined | Pairs after a sentence end without trailing space joined |
|---|---|---|
| 2020 | 2,365 / 2,372 | 0 / 259 |
| 2021 | 1,634 / 1,650 | 0 / 270 |
| 2022 | 1,998 / 1,999 | 0 / 239 |
| 2023 | 2,429 / 2,432 | 0 / 355 |
| 2024 | 2,259 / 2,261 | 0 / 449 |
| 2025 | 3 / 3 | 0 / 277 |

- A mid-word pair is a line without trailing space that ends in Hangul, followed by a line starting with Hangul. The pairs left unjoined are TOC entries, which must stay separate.
- A sentence end without trailing space is a paragraph end, so 0 joined is correct.
- 2025 (HWP) breaks lines only at spaces.
- Glue check on the cleaned text: 0 new `다.가` glues (the one in 2023 is in the source line) and 0 headings glued to body text.

## 3. Normalization (`clean_text`)

**Header, footer and side-tab rules.** The bands are learned per volume by `_profile`: the most common y0 on at least 25 % of spreads, ±3.5 pt.

| Year | Running header (y0) | Page number | Footer (y0) | Side tab (R outer 50 pt) |
|---|---|---|---|---|
| 2020 | 43: L `제N장 <장>`, R `제N절 \| <절>`, appendix names | footer | 639: `096` | vertical `외교지평 확대` |
| 2021 | 46: L `096 제4장 지역 외교`, R `제4절 … 097` | in header | none | horizontal small `제4장.` / `지역 외교` |
| 2022 | 27 | in header | none | vertical `제N장` + title |
| 2023 | 31 (page-number glyph 31) | in header | none | vertical |
| 2024 | 31 (page-number glyph y0 29) | in header | none | vertical `제N장  title` |
| 2025 | 49: L `제N장_<장>`, R `제N절 <절>` / appendix names | footer | 654: `98` | none as text (vector) |

How `clean_text` strips:
- It removes the first block only if every line (digits masked to `#`) is a learned header string (49/49/48/44/46/45 strings in `running_strings.json`).
- Co-occurrence rules, verified on all halves:
  - Footer and side tab never occur without a header.
  - In 2020 and 2025, header and footer always occur together.
  - In 2021-2024, every header row contains a page number.
- Result: the text-only rule agrees with the geometric roles on **2,138 / 2,138 halves** (flag `running_strip_mismatch` = 0). Chapter-opener titles such as `부록`, `지역 외교` and the TOC page numbers on 2020 openers are kept.

Other normalization:
- Middle-dot variants become `·`: U+318D `ㆍ` (2021: 440), U+FF65 `･` (2025: 1,058), U+2027 `‧` (2023: 42), U+F09E private-use Wingdings glyph (2025 p43, rendered and checked as `외교·산업`).
- `｢｣` becomes `「」`.
- U+2219 `∙` becomes `• ` at line start (a 2025 bullet) and `·` elsewhere.
- Removed: `\x07` (InDesign indent-to-here: 102/28/0/164/111/0), `\x08`, ZWNJ.
- Tab and NBSP become a space. Space runs collapse. Letter-spaced labels such as `양 자 관 계` become `양자관계` (whole line of 2-5 single syllables).
- **Soft hyphen U+00AD** (auto-hyphenation, 2023: 78, 2024: 69) is removed and the word re-joined (`NA\xad`+`TO` becomes `NATO`).
- **A hard `-` at line end is always a real hyphen** in all six volumes (`Al-`/`Safadi`, `Chan-`/`o-cha`, `Asia-`/`Pacific`: 14 cases). It is kept and joined without a space.
- **Glyph gaps.** A gap wider than 0.5 em between two non-space glyphs becomes a space. This happens in 9, 1, 0, 5, 13 and 4 lines (`gaps.py`), never in body prose:
  - 2025 p50 `면담한-CARICOM` becomes `면담 한-CARICOM`;
  - 2023/2024 openers `제1절북한` become `제1절 북한`;
  - side effect: the 2020 opener's letter-spaced `외교백서` becomes `외 교 백 서` (decorative text only).
- Kept as they are: `〃` and `″` (ditto marks in tables), `▴` inline bullets, Hanja, superscript footnote references inline (`있다.1) 특히`).

## 4. Image-only and textless halves

`find_image_only` (manually checked by rendering):

| Kind | Halves |
|---|---|
| **Content as image** (not in text; register as "자료에 없음" / OCR later) | 2025 p2 L+R (인사말), p3 L+R (목차, the whole spread), p138 L+R (부록 1. 외교부 조직도; L keeps only the title text) |
| Decorative chapter dividers, image (chapter number, title, section list duplicated by headings) | 2025 p4, 16, 30, 67, 88, 119, 132, 137 (L+R); 2020 p5, 15, 29, 49, 97, 113, 132, 156, 162 L; 2021 p4, 12, 18, 31, 58, 74, 91, 110 R |
| Covers and title pages (vector art) | 2020 p1 L, p2 R; 2021 p1 R, p2 R |

- The spec's "2025 인사말·목차 = PDF 2-4" is slightly off: p4 is the Chapter 1 divider, and p138 (org chart) is also an image.
- Every 2025 half has a full-page background image, so image coverage alone cannot tell content apart; the ink ratio is used as well.
- `classify_half` also returns:
  - **blank** (35 halves, for example 2020 p96 R, 2025 p15 R, p29 R, p118 R, p136 R);
  - **little_text** (24 chapter-title-only halves in 2022-2024, text present).
- All lists are in `final_summary.json`.

## 5. Runtime (`timing.json`, fresh process, 24-thread Intel CPU)

| Year | Profile | extract + clean (all halves) | find_image_only |
|---|---|---|---|
| 2020 | 0.34 s | 0.72 s | 1.90 s |
| 2021 | 0.26 s | 0.56 s | 0.56 s |
| 2022 | 0.29 s | 0.64 s | 0.52 s |
| 2023 | 0.50 s | 0.94 s | 0.80 s |
| 2024 | 0.41 s | 0.80 s | 0.68 s |
| 2025 | 0.19 s | 0.59 s | 0.81 s |

- `build_running_strings` (one-off) takes 3.5 s. The whole pipeline for all six volumes takes **15.0 s**.
- The full evaluation (`run_eval.py`, with all metrics) takes about 35 s.

## 6. Residual problems

1. **TOC pages** (2020 p4, 2021 p3, 2022 p3 L, 2023 p3 L, 2024 p4 L; 2025 p3 is an image): the stream groups text by style, so page numbers are separated from their entries (2021 p3). Build `toc.json` from section-start headings or running headers, not from TOC text.
2. **Tables are one cell per line**, row by row. Row structure is implicit; a multi-line cell stays together but the column labels are not repeated. `page.find_tables()` was not evaluated.
3. **Display-title glyph order**: 2022 openers read `1 / 국제정세 개관 / 제 / 절` because "제 1 절" is drawn as three glyph lines.
4. **Covers**: spine text is duplicated in both halves (2020 p1, 2021 p1).
5. **Captions and photo notes** stay in content-stream order (after the paragraph). Charts (for example 2021 p20 L) give bare numbers.
6. **Page numbers (for the page-map task).** The header and footer numbers give k in printed page = 2N + k (L), 2N + k + 1 (R):
   - 2020: −4 on all 352 numbered halves.
   - 2021: **−3 on p5-p11** (007-020), then −4 from p13 (022-) to the end. The p12 chapter-2 opener spread holds only printed page 021.
   - 2022-2025: −2 throughout.
7. `clean_text` depends on `running_strings.json`, which is built from these six PDFs. Without it, a regex fallback strips only obvious headers and page numbers.
8. `lines_all.json` (17 MB) in this folder is exploration data, not a deliverable.
