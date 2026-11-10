# Shoptet → Pohoda demo pack

Syntetické demo pre [perepolkin.sk](https://perepolkin.sk). Ukazuje tri lokálne
scenáre: Shoptet → Pohoda, dodávateľské faktúry → Pohoda a Mergado/XML feed.

> **Demo, nie klientsky prípad.** Všetky firmy, osoby, doklady a čísla sú
> vymyslené. Demo sa nepripája k Shoptetu, Pohode ani Mergadu a nepoužíva
> žiadne reálne dáta, IČO, DIČ ani sieťové volania.

## Rýchly štart

```bash
git clone https://github.com/perepolkin/shoptet-pohoda-demo.git
cd shoptet-pohoda-demo
uv sync --extra dev
make demo          # vygeneruje vstupy, spustí 3 scenáre, zapíše reporty
make test          # pytest
make assets        # screenshoty + 3 videá (vyžaduje ffmpeg)
make pack          # perepolkin-demo-pack.zip
```

`make demo` je ekvivalent `python -m demo run-all`. Beží pod 2 minúty.
Ak nemáte `uv`, stačí Python 3.11+ a `pip install -e ".[dev]"`.

## CLI

```bash
python -m demo generate
python -m demo run --scenario shoptet
python -m demo run --scenario invoices
python -m demo run --scenario mergado
python -m demo run-all
python -m demo assets
python -m demo pack
pytest
```

`run-all` vyčistí `data/output/`, vygeneruje vstupy, spustí všetky scenáre,
zapíše reporty a vráti exit code 0. Každý scenár má vlastný `run.log`,
`report.json` a `report.md`.

## Scenáre a výsledky

| Scenár | Vstup | Spracované | Na kontrolu | Ticho prejdené |
|---|---|---:|---:|---:|
| Shoptet → Pohoda | 50 objednávok | 46 | 4 | 0 |
| Dodávateľské faktúry → Pohoda | 10 PDF | 8 | 2 | 0 |
| Mergado / XML feed | 1 000 produktov | 987 | 13 | 0 |

Čísla nie sú ručne prepísané: generátor ich vytvorí a report ich vypočíta.
Ak sa vstupy zmenia, report ukáže nové čísla. `silent_errors = 0` znamená,
že každé upozornenie je v reporte — nie že demo nemá flagged položky.

### Shoptet → Pohoda

- 3 objednávky bez EAN: 2 doplnené z katalógu podľa SKU, 1 neznáme SKU na kontrolu.
- 1 duplicitná objednávka, 1 storno a 1 doklad v uzavretom období na kontrolu.
- 1 objednávka s rozdielom 0,01 CZK: pridaný viditeľný rounding line, nie tichá oprava.
- Výstup: 46 XML faktúr + `pohoda_invoices.xml`, 46 výdajok, reporty.

### Dodávateľské faktúry → Pohoda

- 8 čitateľných PDF = 48 riadkov, všetky spárované.
- 1 naskenovaná faktúra bez textovej vrstvy → manuálna kontrola (OCR sa nerobí).
- 1 duplicitná faktúra → manuálna kontrola.
- Chýbajúce SKU sa páruje cez EAN; rozdiel ceny sa berie z faktúry a je vo warnings.
- Faktúra s 0 % a 23 % DPH je spracovaná korektne.

### Mergado / XML feed

- 3 feedy (2 XML + 1 CSV), 1 000 produktov.
- 10 bez kategórie: 1 odvodená z názvu, 9 na kontrolu.
- 1 duplicitný EAN, 2 cudzie meny, 1 neplatná cena na kontrolu.
- 5 nulových skladov zostáva v master feede s warningom.
- Výstup: `master_feed.xml`, `master_feed.csv`, `mapping.json`, reporty.

## Štruktúra

```text
shoptet-pohoda-demo/
  README.md
  LIMITATIONS.md
  handoff.md
  pyproject.toml
  Makefile
  demo/
    cli.py, models.py, artifacts.py
    generators/      syntetické vstupy
    scenarios/       tri scenáre
    parsers/         JSON/CSV, PDF, Mergado XML/CSV
    exporters/       Pohoda XML, master feed
    validation/      DPH, matching, totals
    reports/         report.json + report.md
    tests/
  data/input/        vygenerované vstupy
  data/output/       výsledky a reporty
  assets/
    screenshots/     12 × PNG 1440×900
    video/           3 × MP4 1440×900, 90 s
  handoff/
    shoptet/         input/run/output/report.png, metrics.md, video.mp4
    invoices/
    mergado/
    README.md
    perepolkin-demo-pack.zip
```

## Použité Pohoda XML polia

Demo používa zámerne malý subset:

- `dat:dataPack` → `dat:dataPackItem`
- `inv:invoice` → `invoiceHeader` (`invoiceType`, `number`, `symVar`, `date`,
  `dateDue`, `text`, `partnerIdentity`, `paymentType`, `note`)
- `invoiceDetail` → `invoiceItem` (`quantity`, `unit`, `text`, `code`,
  `homeCurrency` s `unitPrice`, `price`, `priceVAT`, `rateVAT`, `percentVAT`,
  `stockItem`)
- `invoiceSummary` → `homeCurrency` (`priceNone`, `priceHigh`, `priceHighVAT`,
  `round/priceRound`)
- `stk:stock` → `stockHeader` (`stockType`, `number`, `date`, `text`, `store`)
  a `stockDetail` (`stockItem/quantity`, `stockItem/stockItem/ids`)

XML je well-formed a testy kontrolujú povinné polia a súčty. Nie je to tvrdenie
o XSD validite voči konkrétnej verzii Pohody — pozri `LIMITATIONS.md`.

## Determinizmus

- Pevný seed `20261110`.
- Pevné demo hodiny `2026-11-10T10:00:00Z`.
- `duration_ms` v reporte je simulovaný, aby reporty boli zhodné medzi behmi.
- `data/output/` sa pred `run-all` maže.
- PDF sa generujú v reportlab invariant režime.
- Testy overujú zhodu vstupov aj výstupov medzi dvoma behmi.

## Bezpečnosť

- Žiadne sieťové volania v aplikácii.
- Žiadne reálne dáta, mená, adresy, IČO, DIČ alebo heslá.
- Všetky firmy sú `Demo ... s.r.o.` a všetky e-maily sú `@example.com`.
- Screenshoty a video majú watermark `DEMO` / `SYNTETICKÉ DÁTA`.
- Testy kontrolujú neprítomnosť IČO/DIČ v XML a JSON.

## Screenshoty a video

```bash
make assets
```

Vytvorí 12 screenshotov (4 na scenár) a 3 videá. Screenshoty sú 1440×900,
PNG, s vodoznakom DEMO. Videá sú 1440×900, 90 s, ticho, bez browser chrome.
Výstup je v `assets/` a v `handoff/{scenario}/`.

## ZIP a handoff

```bash
make pack
```

Vytvorí `perepolkin-demo-pack.zip` a jeho kópiu v `handoff/`. ZIP obsahuje
vstupy, výstupy, reporty, README, handoff screenshoty a videá.

Pre dizajnéra: [`handoff.md`](handoff.md), [`handoff/README.md`](handoff/README.md).

## Limity

Pozri [`LIMITATIONS.md`](LIMITATIONS.md). Krátko: syntetické dáta, žiadna live
integrácia, žiadny backend, žiadny Docker, žiadna databáza, žiadne OCR.
