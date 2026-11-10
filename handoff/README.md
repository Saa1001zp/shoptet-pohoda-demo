# Handoff pre dizajnéra

Demo pack pre **perepolkin.sk**. Všetko je syntetické, bez reálneho klienta,
bez IČO/DIČ a bez live pripojenia na Shoptet/Pohoda/Mergado.

Vizuál v2 používa tokeny webu: cream `#F7F4EE`, karty `#FDFBF7`,
text `#1F1B16`, akcent `#A8382A`, OK `#2F6B4B`; Newsreader + Inter +
JetBrains Mono. Terminál je tmavý `#1F1B16`, warning je akcentná červená.

## Kam čo patrí

| Súbor | Použitie |
|---|---|
| `handoff/shoptet/input.png` | Karta „Vstup“ — 50 objednávok, súbory, ukážka objednávky |
| `handoff/shoptet/run.png` | Karta „Beh“ — terminál s reálnym logom |
| `handoff/shoptet/output.png` | Karta „Výstup“ — 46 XML faktúr + výdajky |
| `handoff/shoptet/report.png` | Karta „Report“ — 46 / 4 / 0 |
| `handoff/invoices/...` | To isté pre dodávateľské faktúry (8 / 2 / 0, 48/48 riadkov) |
| `handoff/mergado/...` | To isté pre Mergado feed (987 / 13 / 0) |
| `handoff/{scenario}/metrics.md` | Presné čísla a texty pre kartu |
| `handoff/{scenario}/video.mp4` | 90 s video pre daný scenár, 1440×900, ticho |
| `handoff/raw/run-all.mp4` | Surová 59,5 s nahrávka reálneho `run-all`, bez strihu |
| `handoff/raw/poster.png` | Poster pre raw video |
| `handoff/raw/README.md` | Čo presne raw nahrávka ukazuje |
| `handoff/manifest.json` | Strojový manifest všetkých troch scenárov |
| `handoff/README.md` | Tento súbor |
| `handoff/perepolkin-demo-pack.zip` | ZIP so vstupmi, výstupmi, reportmi, screenshotmi a videom |

## Presné čísla na stránku

| Scenár | Vstup | Automaticky | Na kontrolu | Ticho prejdené |
|---|---|---:|---:|---:|
| Shoptet → Pohoda | 50 | 46 | 4 | 0 |
| Dodávateľské faktúry → Pohoda | 10 | 8 | 2 | 0 |
| Mergado / XML feed | 1 000 | 987 | 13 | 0 |

**Nepíšte „nulový počet chýb“.** Správna formulácia je
**„0 ticho prejdených chýb“** a k tomu počet položiek na ručnú kontrolu.
Demo má zámerne flagged prípady.

## Odporúčané texty

### Shoptet → Pohoda

- Nadpis: **Shoptet → Pohoda**
- Podnadpis: *50 syntetických objednávok. 46 automaticky, 4 na kontrolu.*
- Pod čísla: *0 ticho prejdených chýb. Každé upozornenie je v reporte.*
- CTA: **Chcem test na svojich dátach**

### Dodávateľské faktúry → Pohoda

- Nadpis: **Dodávateľské faktúry → Pohoda**
- Podnadpis: *10 PDF faktúr. 8 automaticky, 2 na kontrolu. 48/48 riadkov.*
- Pod čísla: *Sken bez OCR ide na manuálnu kontrolu, nič sa nehádá.*
- CTA: **Chcem test na svojich dátach**

### Mergado / XML feed

- Nadpis: **Mergado / XML feed**
- Podnadpis: *3 feedy, 1 000 produktov. 987 v master feede, 13 na kontrolu.*
- Pod čísla: *Duplicity, meny a ceny sú viditeľné v reporte.*
- CTA: **Chcem test na svojich dátach**

## Kam dať DEMO / syntetické dáta

- Na každom screenshote je vpravo dole **DEMO** a vľavo dole veta
  *Syntetické dáta · všetky firmy a doklady sú vymyslené · bez reálneho IČO/DIČ*.
- Pri vkladaní na web neodstraňujte watermark ani tento text.
- Do alt textu pridajte: `Syntetické demo dáta, nie reálny klient`.
- Video má ticho; netreba pridávať hudbu. Ak ju pridáte, použite vlastnú
  alebo bezlicenčnú a ponechajte DEMO.
- Nikde nepíšte „klientsky prípad“, „referencia“ ani reálne IČO/DIČ.

## Video

- Tri verzie: `handoff/shoptet/video.mp4`, `handoff/invoices/video.mp4`,
  `handoff/mergado/video.mp4`.
- 90 sekúnd, 1440×900, 30 fps, bez zvuku, bez browser chrome, veľký font.
- Osnova: titul → terminál → výstup → report → CTA „Pošlite 2 vzorky“.
- Samostatná surová nahrávka: `handoff/raw/run-all.mp4` (59,5 s, 1440×900,
  30 fps, bez zvuku, reálny `python -m demo run-all`, bez strihu a bez hudby).
  Poster je `handoff/raw/poster.png`, popis `handoff/raw/README.md`.
  Na stránke ju použite ako samostatný odkaz „Pozrieť surový beh“.

## Odkazy

- GitHub: https://github.com/Saa1001zp/shoptet-pohoda-demo
- Branch: `feat/demo-assets-v2`
- Commit: `5462487`
- Remote: `https://github.com/Saa1001zp/shoptet-pohoda-demo.git`
- ZIP: `handoff/perepolkin-demo-pack.zip`
- Web: https://perepolkin.sk

## Ako vložiť kartu

1. Vezmite `report.png` ako hlavný obrázok karty.
2. Pod neho dajte čísla z `metrics.md` (nie z tohto README).
3. CTA odkazujte na kontakt alebo `perepolkin.sk`.
4. Ak používate video, nastavte `poster` na `run.png` a `preload="metadata"`.
5. Pri mobilnom zobrazení zachovajte pomer 16:10; text nesmie zmiznúť.

## Kontrola pred publikovaním

- [ ] Na karte sú presné čísla z `metrics.md`.
- [ ] Je viditeľné DEMO / syntetické dáta.
- [ ] Nie je tam „nulový počet chýb“.
- [ ] Nie je tam reálne IČO/DIČ ani reálne meno.
- [ ] CTA je „Chcem test na svojich dátach“.
