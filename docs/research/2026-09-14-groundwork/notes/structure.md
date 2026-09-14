# Structure of the six phase-1 volumes (data folders 2020-2025)

Date: 2026-09-14. Read-only on `C:\international_relations`. PyMuPDF 1.26.7, Python 3.12.

Files in this folder
- `structure.json` - volumes (title, evidence, toc with printed start/end pages), missing registry, corpus_years.
- `toc.py` - `extract_toc(pdf_path, year, prefer=None)`, `chapter_of(toc, printed_page)`, helpers `page_labels`, `parse_toc_page`, `detect_headings`.
- `build_structure.py` - builds structure.json and the check files; `test_toc.py` - 20 chapter_of cases + ordering check (all pass, `out/test_toc.log`).
- `out/accuracy.json` - per volume: outline content, 목차-vs-heading comparison, running-header check of chapter_of, page-label stats.
- `out/chapter_lookup.json` - printed-page ranges -> (장, 절) for every printed page 1..last numbered page.
- `out/manual_toc_2025.json` - my visual transcription of the image 목차 (ground truth for 2025 only).
- `out/img/*.png` - renders I looked at (2025 인사말/목차/간지/조직도, 2021 inner title/목차/간지, 2022 인사말).

## 1. Verified results per volume

| folder | file | PDF pp | edition title (display) | printed pages numbered | 장 / 절 / 부록 items | toc method |
|---|---|---|---|---|---|---|
| 2020 | 2021 외교백서(국문).pdf | 190 | 「2021 외교백서」 | 8-375 | 8 / 31 / 12 | 목차 text |
| 2021 | 2021년도 국제정세와 외교활동(외교백서)_홈페이지 게시.pdf | 142 | 「2021년도 국제정세와 외교활동」 | 7-279 | 8 / 27 / 12 | 목차 text |
| 2022 | 2022년도 국제정세와 외교활동(외교백서).pdf | 173 | 「2022년도 국제정세와 외교활동」 | 8-343 | 7 / 28 / 12 | 목차 text |
| 2023 | 2023년도 국제정세와 외교활동.pdf | 199 | 「2023년도 국제정세와 외교활동」 | 8-395 | 7 / 27 / 11 | 목차 text |
| 2024 | 2024년도 국제정세와 외교활동.pdf | 194 | 「2024년도 국제정세와 외교활동」 | 10-383 | 7 / 28 / 11 | 목차 text |
| 2025 | 2025년도 국제정세와 외교활동.pdf | 171 | 「2025년도 국제정세와 외교활동」 | 8-339 | 7 / 27 / 11 | body headings (목차 is an image) |

Last numbered printed page matches the survey (375, 279, 343, 395, 383, 339).

### Title evidence (quoted from extracted text; PDF page numbers are 1-based)
- 2020: cover p1 `Diplomatic White Paper / 2021`; 목차 p4 line `2021 외교백서` (12pt); every 장 간지 `2 0 2 1  외교백서` (p5, p15, ...); 인사말 p3 signed `2021년 12월` / `외교부 장관`; colophon p190 `발행일` `2021년 12월`. The Korean words "2021 외교백서" appear as one text line only on the 목차 page; the cover has only the English + year.
- 2021: cover p1 `발간등록번호 / 11-1260000-000062-10 / 2021년도 국제정세와 외교활동 / 외교백서`; colophon p142 `발행일  2022년 12월`. (Inner title p2 draws the title as vector outlines: no text.)
- 2022: cover p1 `외교백서 / 2022년도 / 국제정세와 / 외교활동`; 인사말 p2 `2023년 12월`, `외교부 장관 박 진`; colophon p173 `발행일  2023년 12월`.
- 2023: cover p1 `외교백서 / 2023년도 / 국제정세와 / 외교활동`; 인사말 p2 `2024년 12월`, `외교부 장관 조 태 열`; colophon p199 `발행일  2024년 12월`. Caution: this 인사말 itself calls the book `2024년 외교백서가 2023년 한 해 동안 ...` - use the cover title, not the 인사말 wording.
- 2024: cover p1 `외교백서 / 2024년도 / 국제정세와 / 외교활동`; 인사말 p3 `2025년 5월`, `외교부 장관 조 태 열`; colophon p193 `발행일  2025년 05월`.
- 2025: cover p1 `외교백서 / 2025년도 / 국제정세와 / 외교활동` (joined lines `2025년도`, `국제정세와`, `외교활동`, `외교백서`); colophon p171 `2025년도 국제정세와 외교활동`, `2026년 07월`. 인사말 p2 is an image (viewed: signed 2026년 6월, 외교부 장관 조 현).

## 2. TOC methods and accuracy

| volume | (a) PDF outline `doc.get_toc()` | (b) 목차 page text | (c) body headings | used |
|---|---|---|---|---|
| 2020 | 2 entries, file-merge bookmarks only (`(국문)외교백서_표지 1130`, `(국문)외교백서_내지 최종.pdf`) - unusable | PDF p4, grid layout (labels, titles, numbers in separate lines) - parsed 8 장, 31 절, 12 부록 | 43/43 절+부록 found, 43/43 pages = 목차, 43/43 titles; 장 titles from running headers 8/8 | b, pages re-anchored by c |
| 2021 | empty | PDF p3, page numbers left of labels - 8 / 27 / 12 | 39/39 found, **38/39 pages** (제1장 제1절: 목차 006, heading on page labelled 007), 39/39 titles; 장 titles 8/8 | b + c |
| 2022 | empty | PDF p3 - 7 / 28 / 12 | 40/40, 40/40, 40/40; 장 titles 6/7 (running header of 제2장 reads `한반도 자유·평화·번영과 역내 협력`, 목차 `한반도의 ...`) | b + c |
| 2023 | empty | PDF p3 - 7 / 27 / 11 | 38/38, 38/38, 38/38; 장 titles 7/7 | b + c |
| 2024 | empty | PDF p4 - 7 / 28 / 11 | 39/39, 39/39, 39/39; 장 titles 6/7 (header of 제3장 `인도-태평양 전략과 ...`, 목차 `전략 및 ...`) | b + c |
| 2025 | empty | none - PDF p3 is an image | vs my visual transcription of the image 목차: 38/38 found, 38/38 pages, 38/38 titles (normalized); 장 titles 7/7 | c |

"Titles equal" = equal after NFKC, middle-dot unification and removing spaces/punctuation (e.g. 2025 heading `수출통제·제재외교` vs 목차 `수출통제·제재 외교`). Displayed titles come from the 목차 (2020-2024) or the headings/running headers (2025), with `･`/`ㆍ` mapped to `·`.

Heading detection rules (toc.py `detect_headings`): in the top third of each half, a `제N절` line of >=12pt (2020 16pt, 2021 16/19.2pt, 2023-24 46pt `제 1 절`, 2025 44pt `제1 절`) or, for 2022, separate `제` + `절` (13pt) with a >=30pt digit between them (`1` 87pt); title = largest other line >=19pt (joined when wrapped). 절 numbering restarts at 1 -> new 장. 부록 items: rows >=13pt with y0<120 in halves after the last 절 heading and after the first header containing `부록` (`1 외교부 조직도`, `1. 외교부 조직도`, or unnumbered `외교부 조직도` in 2021).

Independent check of `chapter_of` against the running headers of every numbered half (`out/accuracy.json` -> running_header_check_of_chapter_of): chapter agreement 352/352 (2020), 258/258 (2021), 322/322, 374/374, 360/360, 314/314 (2025); section agreement on halves whose header names 제N절: 176, 129, 161, 187, 178, 155 - zero mismatches. Only 2 부록 notes in 2024: printed 335 header says `운전면허 상호인정 현황` but the `9 운전면허 상호인정 현황` heading is on 336 (= 목차 336); printed 339 header `여권 발급 및 해외여행자 현황` vs 목차 `여권 발급 및 우리국민 해외관광객 현황` (wording only).

### Chapter start pages
장 `printed_page` = first page of its 간지 (divider), inferred because 간지 are unnumbered; `divider_pages` lists them. 절 `printed_page` = label of the page carrying the body heading. `printed_end` = next start - 1; the last entry ends at the last numbered page. chapter_of returns None for front matter (before 제1장's 간지) and for pages beyond the last numbered page.

## 3. Page labels (needed for (b)/(c); a separate page-map task may own this)
Printed numbers were detected in the header/footer band at the outer edge of each half (`toc.page_labels`).
- 2020: all 352 numbered halves fit PDF N -> printed 2N-4 | 2N-3.
- 2022, 2023, 2024, 2025: all numbered halves fit 2N-2 | 2N-1 (322, 374, 360, 314 halves). 2023 p199 and 2024 p194 are single-width back covers.
- **2021 is not one offset**: PDF p5-p11 (printed 7-20, 14 halves) fit 2N-3 | 2N-2 (odd numbers on the LEFT half, e.g. p5 = `007` left, `008` right); p12 is the full-bleed 제2장 간지 between 020 and 022, so both halves can only be printed 21; p13-p141 fit 2N-4 | 2N-3 (244 halves). The survey's "k = -4 for 2021" is right for 94% only; a single-k page map would mis-cite all of 제1장 (printed 7-20) by one page.
- No gaps or duplicates among detected numbers in any volume -> no missing printed ranges inside the numbered body.
- PDF p1 is the cover in all six volumes (gets no label). Halves after the last numbered page (colophon/back cover) get extrapolated labels with status `inferred_after_last` in `page_labels`; treat them as unnumbered.

## 4. Missing registry (structure.json `missing`)
Verified (0 extractable characters, rendered and viewed):
- 2025 인사말 = PDF p2 (printed 2-3), 목차 = PDF p3 (printed 4-5), 제1장 간지 = PDF p4 (printed 6-7). The spec's "2025 인사말·목차 (PDF 2~4쪽)" should read "인사말 p2, 목차 p3, 제1장 간지 p4".
- 2025 all other 간지 are images too: PDF p16, 30, 67, 88, 119, 132 (장 2-7) and p137 (부록) = printed 30-31, 58-59, 132-133, 174-175, 236-237, 262-263, 272-273. They carry only the chapter title and 절/item list with pages (the same information is in the toc).
- 2025 부록 1 외교부 조직도 = PDF p138 (printed 274-275): the chart is an image; only `부록`, `외교부 조직도`, `1. 외교부 조직도` and page numbers are text.
- 2021 has no 인사말/발간사 in the posted PDF (p1 cover, p2 inner title, p3 목차, p4 제1장 간지); registered with null printed range.
- Not registered (no content): 2025 decorative blank colour pages printed 29, 57, 235, 271 (image only, before a 간지); 2020 p2 left half blank; back covers. They are listed per volume in `zero_text_halves`.
- 2020-2024: no image-only content pages found (halves with <150 characters are 간지, chapter-end short pages, covers, colophons).
- Out of range: `corpus_years` = [2020..2025]; anything 2019 or earlier / 2026 or later -> not_in_corpus.

## 5. Inferred / not verified
- That the printed book of 2021 has page 006 as the start of 제1절 (목차) - the posted PDF labels that page 007; I store 7 and keep `toc_page: 6`.
- Whether the 2021 printed book has an 인사말.
- 2025 image 목차 transcription is my visual reading of a 2.2x render; all 38 page numbers agree with the headings found independently, so errors are unlikely.

## 6. Things other tasks should know
- Middle dots differ by volume (counted over all text): 2025 uses U+FF65 `･` 1,058 times vs U+00B7 `·` 104 times (plus U+2219 167); 2021 uses U+318D `ㆍ` 440 times. Search normalisation must unify them or `한·미` will not match 2025 text (`out/dots.log`).
- Running-header wording is not always identical to the 목차 (2022 제2장, 2024 제3장, 2024 부록 10); use 목차 titles for display.
- `extract_toc` scans the whole PDF 2-3 times (~20-40 s per volume on this PC); run it once in prep and store `corpus/toc.json`.
