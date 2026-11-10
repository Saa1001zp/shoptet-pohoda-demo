# Demo: Shoptet → Pohoda

- Vstup: 50 objednávok
- Spracované: 46
- Na kontrolu: 4
- Ticho prejdené chyby: 0
- Čas: 12 s (simulovaný demo čas)

## Na kontrolu

- `DEMO-2026-0033` — storno – vyžaduje ručné spracovanie — Storno objednávky – vyžaduje ručné spracovanie.
- `DEMO-2026-0041` — chýba EAN a SKU nie je v katalógu — SKU SKU-999 nie je v katalógu
- `DEMO-2026-0044` — doklad patrí do uzavretého obdobia — Doklad patrí do uzavretého účtovného obdobia.
- `DEMO-2026-0007` — duplicitná objednávka — Druhý výskyt rovnakého order_id

## Upozornenia

- `DEMO-2026-0012` — EAN chýbal, doplnené z katalógu podľa SKU — SKU SKU-001: EAN 2000000010014 doplnené z katalógu
- `DEMO-2026-0027` — EAN chýbal, doplnené z katalógu podľa SKU — SKU SKU-004: EAN 2000000010045 doplnené z katalógu
- `DEMO-2026-0031` — zaokrúhlenie DPH 0,01 CZK – pridaný rounding line — Rozdiel 0.01 CZK vyriešený rounding line

## Kontroly

- OK `xml_well_formed` — 46 invoice files + pack + stock pack
- OK `totals_reconcile` — sum(lines) == invoice total for every invoice
- OK `decimal_money` — Decimal + ROUND_HALF_UP, no float
- OK `catalog_match` — every processed line matched by SKU/EAN
- OK `duplicate_orders_reported` — duplicate order sent to manual review
- OK `silent_errors_zero` — every warning/flag is present in report.json

## Výstupy

- `shoptet/pohoda_invoices.xml`
- `shoptet/stock_issues.xml`
- `shoptet/invoices/`
- `shoptet/report.json`
- `shoptet/report.md`
- `shoptet/run.log`

## Limity

- Syntetické dáta, všetky firmy a osoby sú vymyslené.
- Nie je to reálny klient ani klientsky prípad.
- Žiadne reálne pripojenie k Shoptetu, Pohode alebo Mergadu.
- Demo beží lokálne, bez siete, databázy a Dockeru.
