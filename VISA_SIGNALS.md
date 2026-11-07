# E2 / L-1 visa signals

**Goal:** find companies that are getting an E-2 visa or filing for an L-1, so Gershon can offer US sales pipeline before they hire a US sales team.

## Why there is no direct list
- E-2 visa records are confidential by law (INA 222(f)) and can't be released under FOIA, including the consulates' E-2 company registrations.
- USCIS published L-1 approvals by employer only for FY2015–FY2017. Current data is aggregate totals only.

## What we use instead: the US set-up that both visas require
Both visas need a foreign company to open a US business first (E-2: the investment enterprise; L-1 "new office": the US affiliate). We catch those set-ups in public filings every weekday:

| Source | What it shows | Why it matters |
|---|---|---|
| SEC Form D | A company based in a treaty country files for its US entity (often a Delaware corp) to raise from US investors. Shows the CEO and other officers, HQ city, industry, size band and amount raised. | A new US entity with a foreign HQ is the classic E-2 / L-1 profile. |
| Florida Sunbiz daily filings | New Florida companies whose address or home jurisdiction is in a treaty country, with their officers. | Florida is a top E-2 destination. |
| Colorado registry (open data) | Companies formed abroad registering to do business in Colorado. | Same signal, smaller volume. |

Filtered out: investment funds, Canadian junior miners and resource companies, and the countries Gershon excludes (China, India, Russia, Brazil, Vietnam, South Africa, Saudi Arabia, UAE, Hong Kong).

The sample of Oct 19–30, 2026 gave about 2 usable companies per business day. The daily news research in task #08 fills the rest of the 10/day target.

## How it runs
- `.github/workflows/visa-signals.yml` runs `visa_signals/signals.py` Mon–Fri at 06:17 New York time and commits `data/candidates/latest.json` plus a log.
- Claude's daily task #08 reads `latest.json` first, qualifies each company (size, no US sales lead, reachable CEO), finds and verifies the CEO email, sends the intro email (cc sales@gershonconsulting.com) and queues the CEO plus 2 key people for Sales Navigator.

`florida_pipeline.py`, `field_spec.py`, `scoring.py` and `mailer.py` are the earlier VPS version (June 2026). They have broken indentation and unverified offsets. `visa_signals/signals.py` replaces them.
