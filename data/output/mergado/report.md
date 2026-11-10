# Demo: Mergado / XML feed

- Vstup: 1 000 produktov
- Spracované: 987
- Na kontrolu: 13
- Ticho prejdené chyby: 0
- Čas: 7 s (simulovaný demo čas)

## Na kontrolu

- `A-0001` — chýba kategória — Produkt nemá kategóriu
- `A-0002` — chýba kategória — Produkt nemá kategóriu
- `A-0003` — chýba kategória — Produkt nemá kategóriu
- `A-0004` — chýba kategória — Produkt nemá kategóriu
- `A-0005` — chýba kategória — Produkt nemá kategóriu
- `A-0006` — chýba kategória — Produkt nemá kategóriu
- `A-0007` — chýba kategória — Produkt nemá kategóriu
- `A-0008` — chýba kategória — Produkt nemá kategóriu
- `A-0009` — chýba kategória — Produkt nemá kategóriu
- `B-0100` — duplicitný EAN — EAN 2000000030500 už je v A-0050
- `B-0200` — iná mena ako CZK — Mena EUR bez kurzového lístka
- `C-0200` — iná mena ako CZK — Mena USD bez kurzového lístka
- `C-0250` — neplatná cena — Neplatná cena: 'N/A'

## Upozornenia

- `A-0010` — kategória odvodená z názvu — Kategória odvodená z názvu: Príslušenstvo
- `C-0001` — nulový sklad – produkt zostal v master feede — Produkt zostáva v master feede s nulovým skladom
- `C-0002` — nulový sklad – produkt zostal v master feede — Produkt zostáva v master feede s nulovým skladom
- `C-0003` — nulový sklad – produkt zostal v master feede — Produkt zostáva v master feede s nulovým skladom
- `C-0004` — nulový sklad – produkt zostal v master feede — Produkt zostáva v master feede s nulovým skladom
- `C-0005` — nulový sklad – produkt zostal v master feede — Produkt zostáva v master feede s nulovým skladom

## Kontroly

- OK `master_xml_well_formed` — lxml parse
- OK `master_count` — XML=987, CSV=987, expected 987
- OK `mapping_complete` — 1000/1000
- OK `unique_ean_in_master` — no duplicate EAN in master
- OK `category_rule_reported` — 1 inferred category is a warning, 9 missing categories are flagged
- OK `silent_errors_zero` — every warning/flag is present in report.json

## Výstupy

- `mergado/master_feed.xml`
- `mergado/master_feed.csv`
- `mergado/mapping.json`
- `mergado/report.json`
- `mergado/report.md`
- `mergado/run.log`

## Limity

- Syntetické dáta, všetky firmy a osoby sú vymyslené.
- Nie je to reálny klient ani klientsky prípad.
- Žiadne reálne pripojenie k Shoptetu, Pohode alebo Mergadu.
- Demo beží lokálne, bez siete, databázy a Dockeru.
