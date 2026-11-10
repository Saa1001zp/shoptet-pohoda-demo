# Limity demo packu

Toto je demo, nie produkčná integrácia a nie klientsky prípad.

## Dáta

- Všetky firmy, osoby, adresy, e-maily, objednávky, faktúry a produkty sú
  syntetické. Žiadne reálne IČO, DIČ, rodné čísla ani klientske dáta.
- DemoShop s.r.o. a Demo Dodávateľ Alfa/Beta/Gama s.r.o. sú vymyslené názvy.
- PDF faktúry sú vygenerované pre demo, nie sú to reálne doklady.

## Integrácie

- Žiadne pripojenie k Shoptetu, Pohode, Mergadu ani inému externému systému.
- Žiadny backend, databáza, Docker ani sieťové volania.
- Pohoda XML je zdokumentovaný subset, nie garantovaná XSD validita voči
  konkrétnej verzii Pohody. Import do reálnej Pohody nebol testovaný.
- Shoptet vstup je JSON/CSV export, nie live API.
- Mergado feed je lokálny XML/CSV súbor, nie live Mergado.

## Spracovanie

- OCR nie je implementované. Naskenovaná faktúra bez textovej vrstvy ide na
  manuálnu kontrolu; demo to nikdy nehádže.
- Duplicitná faktúra ide na manuálnu kontrolu, nie je automaticky zahodená.
- Pri chýbajúcom SKU sa použije EAN. Ak EAN chýba alebo nie je v katalógu,
  doklad ide na manuálnu kontrolu.
- Pri rozdiele ceny dodávateľskej faktúry a katalógu sa použije cena z faktúry
  a zapíše sa warning. Demo netvrdí, že katalóg je vždy správny.
- 0,01 CZK rozdiel v celkovej sume sa rieši viditeľným rounding line.
  Pôvodné vstupné hodnoty sa nemení.
- Mergado: 1 produkt bez kategórie sa odvodí z názvu, 9 zostáva na kontrolu.
  Nulový sklad nie je chyba, produkt zostáva v master feede s warningom.
  Cudzie meny sa nekonvertujú bez kurzového lístka.

## Reporty

- `duration_ms` je simulovaný pevný čas, aby boli reporty deterministické.
  Reálny čas behu sa zobrazuje len v termináli.
- `silent_errors = 0` znamená, že každý warning/flag je v reporte. Neznamená
  to „0 chýb“: demo má zámerne N flagged položiek na manuálnu kontrolu.
- Čísla v reportoch sa počítajú z aktuálneho behu. Ak sa zmenia vstupy,
  zmenia sa aj čísla.

## Video a screenshoty

- Sú vygenerované z demo výstupov, s watermarkom DEMO.
- Video má 1440×900, bez browser chrome, so syntetickými dátami.
- Hudba je voliteľná; finálne video má ticho, aby neboli licenčné problémy.
- Screenshoty nie sú marketingový dôkaz reálneho klienta.

## Čo demo nie je

- Nie je to live aplikácia pre web.
- Nie je to klientsky case study.
- Nie je to náhrada za reálnu implementáciu a testovanie na vzorkách.
