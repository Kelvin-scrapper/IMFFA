# IMF Financial Activities Data Extractor

Automated extraction system for IMF Weekly Financial Activities Index reports.
Achieves **98.2% accuracy** with robust universal (identifier-based) column mapping.

## Quick Start

```bash
pip install -r requirements.txt
python orchestrator.py
```

`orchestrator.py` runs the whole pipeline:

1. **Download** the latest report PDF → `Downloads/IMF_Report_<Month>_<Day>_<Year>.pdf`
2. **Extract & map** every PDF in `Downloads/` and `output/` → `output/IMFFA_DATA_OUTPUT.xlsx`

Run the steps individually if you prefer:

```bash
python main_requests.py     # download only (browserless)
python extract_final.py     # extract only (all PDFs found locally)
```

## Project Structure

```
imfaa/
├── orchestrator.py      Runs download → extract end to end
├── main_requests.py     PRIMARY downloader - browserless (requests only)
├── main.py              FALLBACK downloader - Playwright + real Chrome
├── extract_final.py     PDF parsing, universal column mapping, Excel output
├── config.json          Column-mapping definition (date_format + 385 columns)
├── requirements.txt     pandas, openpyxl, pdfplumber, requests, playwright
│
├── Downloads/           Downloaded report PDFs            (gitignored)
├── output/              IMFFA_DATA_OUTPUT.xlsx            (gitignored)
├── logs/                Timestamped run logs + debug HTML (gitignored)
└── IMFFA_DATA_.xlsx     Reference template, regenerated from config.json (gitignored)
```

## How the download works

IMF's site is behind Akamai bot protection. The SPROLLs listing page and a
cold PDF request both return **HTTP 403**. Two strategies are provided;
`orchestrator.py` tries them in order.

### 1. `main_requests.py` — browserless (primary)

No browser at all. Fast (~3-9 s), works unattended.

1. `GET https://www.imf.org/external/index.htm` — an open path that returns
   200 and sets the Akamai `ak_bmsc` cookie.
2. Walk **backwards day by day from today** (`DAYS_BACK = 21`), requesting
   `https://www.imf.org/-/media/files/publications/fa-index/{YYYY}/{MMDDYY}.pdf`
   with that cookie.
3. The first date that returns a real PDF is the latest report. A skipped
   week self-heals — the probe just keeps walking back.

Config knobs at the top of the file: `WARMUP_URLS` (tried in order),
`DAYS_BACK`, `USER_AGENT`.

### 2. `main.py` — Playwright (fallback)

Used only if `main_requests.py` fails (e.g. the media-URL scheme changes).
Drives real Google Chrome (`channel="chrome"` — uses the installed browser,
no `playwright install` needed) against the SPROLLs page, scrapes the
"Weekly Report" link from the rendered Coveo results, then downloads the PDF
with `requests` using the browser's cookies.

- **Headful by default** — a Chrome window opens. Headless is reliably
  blocked by Akamai (403), so leave it headful for real runs.
- Override for debugging only: `set HEADLESS=1` (env var).
- Do **not** reintroduce a persistent `userDataDir` / `.chrome_profile` — a
  stale profile accumulates Akamai flags and causes permanent 403s.

## Output Structure

`output/IMFFA_DATA_OUTPUT.xlsx`, one sheet, **386 columns**:

| Row | Contents |
|-----|----------|
| 1   | Technical column names — e.g. `IMFFA.CURFIN.AMCOM.ARG.W` |
| 2   | Human-readable descriptions — e.g. "Current Financial Arrangements: Amount Committed: Argentina" |
| 3+  | One data row per processed PDF. Column 1 = ISO year-week (`2026-35`); columns 2-386 = mapped values |

## Tables Extracted

### Table 1 — Current Financial Arrangements (GRA) — 357 columns
6 metrics × entity slots:

| Metric | Code | Entities |
|--------|------|----------|
| Amount Committed | `AMCOM` | 72 |
| Amount Undrawn | `AMUNDRAW` | 72 |
| Amount Drawn | `AMDRAW` | 72 |
| Credit Outstanding Amount | `CREDOUTAM` | 72 |
| Credit Outstanding % of Quota | `CREDOUTQUOT` | 67 |
| Memo Items | `MEMITEM` | 2 |

### Table 2 — Forward Commitment Capacity (FCC) — 28 columns
14 metrics, SDR + USD each: Usable Resources, Fund Quota Resources, Fund
Borrowed Resources, Undrawn Balance of Commitments, Precautionary,
Non-Precautionary, Uncommitted Usable Resources, Repurchases One Year
Forward, Repayments One Year Forward, Prudential Balance, Forward Commitment
Capacity, Quota Resources, NAB Resources, Bilateral Borrowing Resources.

## Universal Column Mapping ⭐

Data is mapped **by identifier, not by position**. The reference template
(`IMFFA_DATA_.xlsx`, built from `config.json`) defines output structure;
extraction places each value by its identifier (`IMFFA.CURFIN.AMCOM.ARG.W`).

```
PDF row:  "Argentina 3/ 15,267 4,578 10,689 41,789 1,311"
   ↓ parse         Country ARGENTINA → ARG ;  AMCOM 15,267 → 15267
   ↓ map by id     IMFFA.CURFIN.AMCOM.ARG.W
   ↓ place         column position taken from the reference template
```

Handled automatically: PDF columns reordered, countries in a different
order, new countries (pre-defined 72 slots), missing countries (empty cell
in the right column), tables on different pages (found by section name),
footnote changes (`3/` → `4/`), template reordered, varying number formats.
Missing values never cause misalignment.

### Robust parsing
- Footnote markers stripped via `\d+/` regex
- Values normalized: commas removed, `--` → null, decimals kept
- Arrangement-type aggregates computed
- Tables located by name, not page number

## Configuration

| What | Where |
|------|-------|
| Warm-up URLs, days to probe back, User-Agent | top of `main_requests.py` |
| Headful/headless (`HEADLESS` env var), browser channel | top of `main.py` |
| Column identifiers, order, display names, date format | `config.json` |
| Country name → ISO code | `country_map` in `extract_final.py` |
| FCC metric text → column code | `metric_map` in `extract_final.py` |

## Requirements

```bash
pip install -r requirements.txt
```

`pandas`, `openpyxl`, `pdfplumber`, `requests` (core) and `playwright` (only
for the `main.py` fallback). Playwright uses the system Google Chrome via
`channel="chrome"`, so no `playwright install` step is required.

## Maintenance

**Add a country:** add `'NEW COUNTRY': 'CODE'` to `country_map` in `extract_final.py`.

**Add / fix an FCC metric:** add `'Exact metric text from PDF': 'COLUMN_CODE'`
to `metric_map` in `extract_final.py`.

## Troubleshooting

| Issue | Cause / fix |
|-------|-------------|
| `main_requests.py`: "No report PDF found in the last 21 days" | Media-URL scheme changed, or a very long publication gap. Orchestrator falls back to `main.py`. Bump `DAYS_BACK` or check the URL pattern. |
| `main_requests.py`: warm-up not returning 200 | `external/index.htm` may be locked down. Add another open path to `WARMUP_URLS` (e.g. `robots.txt`). |
| `main.py`: HTTP 403 / "Access Denied" | Akamai bot block. Ensure it is running **headful** (unset `HEADLESS`) and that there is no `.chrome_profile` directory. |
| Missing countries in output | Country genuinely not in that week's PDF — historical entities don't appear in every report. |
| Column order looks different | Expected — output follows the reference template order, mapped by identifier. |

## License

Internal use only.
