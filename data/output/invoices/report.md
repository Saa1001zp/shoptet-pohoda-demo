# Demo: Dodávateľské faktúry → Pohoda

- Vstup: 10 faktúr
- Spracované: 8
- Na kontrolu: 2
- Riadky: 48/48
- Ticho prejdené chyby: 0
- Čas: 9 s (simulovaný demo čas)

## Na kontrolu

- `invoice_09_scan.pdf` — sken bez textovej vrstvy – potrebné OCR / ručné zadanie — Dokument vyžaduje ručné zadanie
- `invoice_10.pdf` — duplicitná faktúra — Rovnaké číslo ako invoice_03.pdf

## Upozornenia

- `invoice_05.pdf` — SKU chýbalo, položka spárovaná cez EAN — Riadok 2: SUP-999 -> SUP-002
- `invoice_06.pdf` — cena sa líši od katalógu – použité cena z faktúry — Riadok 1: faktúra 134.90, katalóg 129.90, rozdiel 5.00
- `invoice_07.pdf` — faktúra kombinuje 0 % a 23 % DPH — Faktúra obsahuje 0 % aj 23 % DPH

## Kontroly

- OK `xml_well_formed` — 8 received invoices + stock receipts
- OK `totals_reconcile` — sum(lines) == invoice total
- OK `line_coverage` — 48/48 posted lines
- OK `vat_rates_supported` — 0 % and 23 % only
- OK `scan_not_guessed` — image-only scan sent to manual review
- OK `duplicate_reported` — duplicate invoice sent to manual review
- OK `silent_errors_zero` — every warning/flag is present in report.json

## Výstupy

- `invoices/pohoda_received_invoices.xml`
- `invoices/stock_receipts.xml`
- `invoices/invoices/`
- `invoices/parsed/`
- `invoices/parsed.json`
- `invoices/report.json`
- `invoices/report.md`
- `invoices/run.log`

## Limity

- Syntetické dáta, všetky firmy a osoby sú vymyslené.
- Nie je to reálny klient ani klientsky prípad.
- Žiadne reálne pripojenie k Shoptetu, Pohode alebo Mergadu.
- Demo beží lokálne, bez siete, databázy a Dockeru.
