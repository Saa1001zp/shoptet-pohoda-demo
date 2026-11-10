# Handoff: Shoptet → Pohoda demo pre perepolkin.sk

Tento dokument stačí dizajnérovi na vloženie demo bloku do webu. Všetky čísla
sú z reálneho behu demo packu, nie ručne prepísané. Všetko je syntetické.

## 1. Čo prevziať

| Čo | Kde | Na čo |
|---|---|---|
| Screenshoty v2 | `handoff/{shoptet,invoices,mergado}/` | 4 karty na scenár: vstup, beh, výstup, report |
| Metriky a texty | `handoff/{scenario}/metrics.md` | presné čísla a CTA pre kartu |
| 90 s videá | `handoff/{scenario}/video.mp4` | 90 s, 1440×900, 30 fps, ticho |
| Raw beh | `handoff/raw/run-all.mp4` | 59,5 s reálneho `run-all`, bez strihu |
| Raw poster | `handoff/raw/poster.png` | poster pre odkaz „Pozrieť surový beh“ |
| Manifest | `handoff/manifest.json` | strojové metriky, cesty, alt a caption |
| ZIP | `handoff/perepolkin-demo-pack.zip` | všetko vyššie + vstupy, XML/JSON, reporty |
| Detailný handoff | `handoff/README.md` | rovnaké pokyny v rozšírenej verzii |

Všetky screenshoty sú PNG 1440×900. Vpravo dole je **DEMO**, vľavo dole
*Syntetické dáta · všetky firmy a doklady sú vymyslené · bez reálneho IČO/DIČ*.
Tento vodoznak neodstraňujte.

## 2. Presné čísla

| Scenár | Vstup | Automaticky | Na kontrolu | Ticho prejdené |
|---|---:|---:|---:|---:|
| Shoptet → Pohoda | 50 objednávok | 46 | 4 | 0 |
| Dodávateľské faktúry → Pohoda | 10 PDF | 8 | 2 | 0 |
| Mergado / XML feed | 1 000 produktov | 987 | 13 | 0 |

Dodávateľské faktúry majú navyše **48/48 riadkov** a **0 unmatched**.
Mergado má **5 nulových skladov** a **1 odvodenú kategóriu**.

Čas neuvádzajte ako benchmark. Report používa simulovaný čas; reálny
`run-all` je rádovo sekundy. V `metrics.md` preto čas nie je.

**Nikdy nepíšte „nulový počet chýb“.** Správne je **„0 ticho prejdených chýb“**
a k tomu počet položiek na ručnú kontrolu. Demo má zámerne flagged prípady.

## 3. Karty a texty

### 3.1 Shoptet → Pohoda

- Obrázky: `handoff/shoptet/input.png`, `run.png`, `output.png`, `report.png`
- Video: `handoff/shoptet/video.mp4` · raw: `handoff/raw/run-all.mp4`
- Nadpis: **Shoptet → Pohoda**
- Podnadpis: *50 syntetických objednávok. 46 automaticky, 4 na kontrolu.*
- Čísla: **46** automaticky · **4** na kontrolu · **0** ticho prejdených
- Detail: *46 XML faktúr + 46 výdajok skladu. 1 rounding line 0,01 CZK.*
- CTA: **Chcem test na svojich dátach**
- Alt text: `Syntetické demo dáta, 50 objednávok, 46 automaticky spracovaných, 4 na kontrolu`

Na kontrolu: storno, chýbajúci EAN s neznámym SKU, uzavreté obdobie, duplicita.
Upozornenia: 2× doplnený EAN, 1× zaokrúhlenie DPH.

### 3.2 Dodávateľské faktúry → Pohoda

- Obrázky: `handoff/invoices/input.png`, `run.png`, `output.png`, `report.png`
- Video: `handoff/invoices/video.mp4` · raw: `handoff/raw/run-all.mp4`
- Nadpis: **Dodávateľské faktúry → Pohoda**
- Podnadpis: *10 PDF faktúr. 8 automaticky, 2 na kontrolu. 48/48 riadkov.*
- Čísla: **8** automaticky · **2** na kontrolu · **0** ticho prejdených
- Detail: *48/48 riadkov spárovaných. Sken bez OCR ide na manuálnu kontrolu.*
- CTA: **Chcem test na svojich dátach**
- Alt text: `Syntetické demo dáta, 10 PDF faktúr, 8 automaticky, 2 na kontrolu, 48/48 riadkov`

Na kontrolu: sken bez textovej vrstvy (OCR sa nerobí), duplicitná faktúra.
Upozornenia: SKU spárované cez EAN, cena z faktúry sa líši od katalógu,
faktúra s 0 % a 23 % DPH.

### 3.3 Mergado / XML feed

- Obrázky: `handoff/mergado/input.png`, `run.png`, `output.png`, `report.png`
- Video: `handoff/mergado/video.mp4` · raw: `handoff/raw/run-all.mp4`
- Nadpis: **Mergado / XML feed**
- Podnadpis: *3 feedy, 1 000 produktov. 987 v master feede, 13 na kontrolu.*
- Čísla: **987** automaticky · **13** na kontrolu · **0** ticho prejdených
- Detail: *3 dodávatelia, 2 XML + 1 CSV. Duplicity, meny a ceny sú v reporte.*
- CTA: **Chcem test na svojich dátach**
- Alt text: `Syntetické demo dáta, 3 feedy, 1 000 produktov, 987 v master feede, 13 na kontrolu`

Na kontrolu: 9× chýbajúca kategória, 1× duplicitný EAN, 2× cudzia mena,
1× neplatná cena. Upozornenia: 1× kategória odvodená z názvu, 5× nulový sklad.

## 4. Video

- Tri verzie, každá 90 s, 1440×900, 30 fps, ticho, bez browser chrome.
- Bez reálnych mien, log alebo IČO/DIČ.
- Osnova:
  1. 0–10 s: titul a počet vstupov.
  2. 10–30 s: `python -m demo run --scenario ...`, log.
  3. 30–50 s: výstup — XML / master feed.
  4. 50–70 s: report — automaticky / na kontrolu / 0 ticho prejdených.
  5. 70–90 s: „Chcete test na vašich dátach? Pošlite 2 vzorky.“
- Ak video vkladáte cez `<video>`, nastavte `poster="run.png"` a
  `preload="metadata"`. Zvuk netreba; ak pridáte hudbu, použite bezlicenčnú.

### Raw video

- `handoff/raw/run-all.mp4` — 59,5 s, 1440×900, 30 fps, bez zvuku.
- Je to jedna súvislá nahrávka reálneho `python -m demo run-all`, bez strihu.
- Ukazuje príkaz, reálny log, tri výsledky, počty XML a vznik 86 súborov.
- Na stránke použite samostatný odkaz **„Pozrieť surový beh“**.
- Popis je v `handoff/raw/README.md`, poster v `handoff/raw/poster.png`.

## 5. Kam čo vložiť

Odporúčaná štruktúra sekcie:

```text
[ malý label: DEMO / SYNTETICKÉ DÁTA ]
[ H2: Shoptet → Pohoda ]
[ podnadpis: 50 objednávok. 46 automaticky, 4 na kontrolu. ]
[ 4 obrázky: input → run → output → report ]
[ čísla: 46 / 4 / 0 ]
[ CTA: Chcem test na svojich dátach ]
[ odkaz: Pozrieť surový beh ]
```

- `input.png` je vstupná karta, `run.png` terminál, `output.png` výsledok,
  `report.png` čísla. Na mobile zobrazte aspoň `report.png` a čísla.
- Pomer 1440×900 = 16:10. Pri mobilnom reze zachovajte celý text, neorezávajte
  vodoznak DEMO.
- CTA odkazujte na kontakt alebo `https://perepolkin.sk`.
- Do alt textu vždy pridajte „Syntetické demo dáta, nie reálny klient“.
- Presné cesty a texty berte z `handoff/manifest.json`.

## 6. Čo nesmieme tvrdiť

- Nie je to klientsky prípad, referencia ani reálna implementácia.
- Nie je to live napojenie na Shoptet, Pohodu alebo Mergado.
- Nie sú tam reálne IČO, DIČ, mená, adresy ani faktúry.
- Nevypisujte nulový počet chýb. Demo má flagged položky; správne je
  „0 ticho prejdených chýb“ + počet na kontrolu.
- Nekonvertujte cudzie meny bez kurzového lístka; demo to nerobí.

## 7. Repozitár a odkazy

- GitHub: https://github.com/Saa1001zp/shoptet-pohoda-demo
- Stav: verejný repozitár, vetva `feat/demo-assets-v2`.
- Remote:
  ```text
  $ git remote -v
  origin  https://github.com/Saa1001zp/shoptet-pohoda-demo.git (fetch)
  origin  https://github.com/Saa1001zp/shoptet-pohoda-demo.git (push)
  ```
- Commit s v2 assetmi: `5462487`
- ZIP: `handoff/perepolkin-demo-pack.zip`
- Web: https://perepolkin.sk

## 8. Kontrola pred publikovaním

- [ ] Čísla sedia s `metrics.md` (46/4/0, 8/2/0 + 48/48, 987/13/0).
- [ ] Na karte je DEMO alebo „Syntetické dáta“.
- [ ] Nie je tam nulový počet chýb.
- [ ] Nie je tam reálne IČO/DIČ ani reálne meno.
- [ ] CTA je „Chcem test na svojich dátach“.
- [ ] Video má poster `run.png` a je ticho alebo s bezlicenčnou hudbou.
- [ ] Raw odkaz smeruje na `handoff/raw/run-all.mp4`.
- [ ] Manifest a ZIP sú z rovnakého behu.
