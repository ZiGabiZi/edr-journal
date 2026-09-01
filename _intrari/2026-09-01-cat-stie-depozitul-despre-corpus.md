---
title: Cât știe depozitul despre corpus
date: 2026-09-01
tip: masuratoare
rezumat: Acoperirea instantaneului de reputație peste cele 1494 de fișiere ale corpusului, pre-înregistrată cu amprentă și cu ambele brațuri ale ablației, înainte să existe vreo cifră de divulgare.
tags: [reputatie, pdp]
capitol: "2.6"
componente: server
commits: []
teste: []
status: partial
---

## Context {#context}

Ce știe sistemul înainte de orice analiză decide direct cât se poate închide la
T0, deci decide cifra din titlul lucrării. `METRICS.md` §8.1 cere ca acoperirea
să fie declarată lângă orice cifră, iar
[intrarea de decizie]({{ '/intrari/2026-09-01-doua-axe-de-cunoastere-nu-trei-stari/' | relative_url }})
a fixat forma depozitului înainte de prima descărcare.

Intrarea asta consemnează ce a ieșit, **înainte** de primul experiment de
divulgare. Ordinea contează la fel ca la
[corpus]({{ '/intrari/2026-09-01-corpusul-fixat-inainte-de-masuratoare/' | relative_url }}):
o acoperire raportată după ce se vede raportul de divulgare n-ar mai putea fi
deosebită de una aleasă ca să-l explice.

## Instantaneul {#alegerea}

```
amprenta fișierului : 6567fc31a629b9b8c7b799c2d53b3172fcc1f2a0f4b9e364d8ff0e75acddfd4d
amprenta de conținut: d4dc221f936a6acaa3087b94353fa59c54b3a7f00d62b3022aa73bde64d53783
schema              : versiunea 1
rânduri             : 72.029.536
dimensiune          : 3,06 GB
```

Două surse, amândouă declarate cu versiunea lor:

| sursă | axă | versiune | rânduri |
|---|---|---|---|
| NSRL RDS | software | 2026.03.1 | 72.015.285 |
| MalwareBazaar | threat | 2026-08-31T11:12:26.947821+00:00 | 14.251 |

Suma dă exact 72.029.536, deci **suprapunerea dintre surse e zero**: niciun hash
din inventarul de amenințări nu apare în RDS.

Numărul de rânduri RDS coincide la unitate cu cifra publicată de NIST în
`hash_counts.txt` pentru ediția 2026.03.1 — 72.015.285 de valori SHA-256
distincte. Nu e o confirmare a corectitudinii importului, dar ar fi fost o
infirmare imediată dacă nu se potrivea.

## Acoperirea peste corpus {#provenienta}

Cele 1494 de fișiere din manifest, interogate offline din instantaneul de mai sus:

| origine | fișiere | în RDS | % | amenințare | ambele | necunoscut |
|---|---|---|---|---|---|---|
| compilat | 164 | 0 | 0,0% | 0 | 0 | 164 |
| instalator | 300 | 10 | 3,3% | 0 | 0 | 290 |
| malware | 330 | 0 | 0,0% | 330 | 0 | 0 |
| sistem | 700 | 565 | 80,7% | 0 | 0 | 135 |
| **TOTAL** | **1494** | **575** | **38,5%** | **330** | **0** | **589** |

Ambele verificări de sănătate, enunțate în cod înainte de prima rulare pe date
reale, trec:

- **artefactele compilate lipsesc din RDS** — 0 din 164. Dacă ar fi apărut,
  categoria pe care `CORPUS.md` §3.1 o cere — benign ȘI necunoscut în același
  timp — n-ar exista, iar banda ar învăța că tot ce e necunoscut e malițios.
- **binarele de sistem apar în RDS** — 565 din 700, adică 80,7%, față de pragul
  de 50% fixat dinainte.

## Cele două brațuri {#invariant}

`METRICS.md` §8.1 cere ca orice cifră de divulgare să spună care braț a fost
rulat. Amândouă se citesc din tabelul de mai sus:

| braț | se închide la T0 | |
|---|---|---|
| **semiînzestrat** — ambele surse consultate | 905 / 1494 | **60,6%** |
| **rece** — fără MalwareBazaar | 575 / 1494 | **38,5%** |
| diferența | | **22,1 puncte** |

Cele 22,1 puncte sunt exact contribuția reputației externe de amenințări, și
provin în întregime din faptul că selecția corpusului a fost făcută DIN
inventarul MalwareBazaar. Toate cele 330 de mostre malițioase sunt în acea
sursă, deci brațul semiînzestrat închide stratul de stres integral, fără ca
protocolul să facă ceva.

Brațul rece e cel pe care se sprijină lucrarea: **61,5% din corpus rămâne
necunoscut**, deci banda de incertitudine chiar are ce decide. Un corpus care
s-ar închide integral la T0 ar fi făcut experimentul imposibil de eșuat, adică
exact ce interzice `CORPUS.md` §1.

## Decalajul de cinci luni, declarat {#cost}

Cele două goluri din tabel — 290 de instalatoare și 135 de binare de sistem —
au aceeași cauză, iar ea nu e o deficiență a listei NIST.

**RDS 2026.03.1 e un instantaneu din martie 2026. Corpusul a fost construit în
august.**

Cele 10 instalatoare găsite sunt software stabil, cu versiuni vechi: 7zip,
WinRAR, VLC, Python 3.12, Nmap, Inkscape, SumatraPDF. Cele 290 lipsă sunt
software care se actualizează des — Firefox, Telegram, OBS, Git, JetBrains,
Kodi — descărcat prin `winget` în august, deci în versiuni pe care NSRL nu le-a
colecționat încă.

Binarele de sistem lipsă poartă aceeași semnătură: `twinui.pcshell.dll`,
`win32appinventorycsp.dll`, `LicenseManagerSvc.dll` — componente care se schimbă
la fiecare actualizare cumulativă, într-o instalare peticită mai recent decât
ediția din martie.

**Acoperirea RDS e o funcție a decalajului de timp dintre ediția importată și
corpus.** Se declară ca atare, nu se prezintă ca proprietate a listei.

Consecința e favorabilă montajului, dar tocmai de aceea trebuie spusă: un corpus
mai puțin cunoscut e un corpus pe care protocolul are mai mult de lucru.

## Ce NU s-a făcut, deși ar fi urcat cifra {#forta}

Există `RDS_2026.09.1_modern_minimal_delta.zip`, ediția din septembrie.
Importarea ei ar închide o parte din decalajul de mai sus.

Nu s-a făcut. Intrarea de decizie a declarat în avans că verificarea de sănătate
poate declanșa **un** reimport — pentru cazul în care binarele de sistem
*lipsesc*. Verificarea a trecut, cu 80,7% față de un prag de 50%. Un reimport
acum n-ar fi reparație, ci alegerea importului care maximizează acoperirea după
ce cifra a fost văzută — exact definiția pescuitului din `CORPUS.md` §1.1.

Decalajul se declară. Nu se vânează.

## O predicție confirmată și un argument neconfirmat {#invatat}

**Confirmată.** Înainte de descărcare, dimensiunea instantaneului a fost
proiectată dintr-un fișier de 751 de octeți publicat de NIST și dintr-o
măsurătoare pe 500.000 de rânduri false: 45,60 octeți pe rând, 3,06 GB la
72.015.285 de rânduri. Rezultatul real: 45,6 octeți pe rând, 3,06 GB. Pragul R1
era 20 GB, deci decizia „integral, nu subset" a fost luată corect pe o proiecție,
fără să descarce nimic.

**Neconfirmat.** Alegerea celor două axe în locul unui enum de trei valori a fost
argumentată, printre altele, cu faptul că celula de suprapunere — fișierul
prezent și în RDS, și într-o sursă de amenințări — e cea interesantă și că un
enum ar face-o imposibil de reconstruit. În datele astea celula e **goală**.

Decizia rămâne corectă, dar din celălalt motiv, cel structural: `CORPUS.md` §5.4
interzice ca RDS să producă verdictul curat, iar un enum n-ar fi avut unde să
pună adevărul. Celula goală nu confirmă argumentul; doar nu-l infirmă. Merită
consemnat, fiindcă un argument care s-a dovedit inutil e mai ușor de recunoscut
acum decât la susținere.

## Ce urmează {#urmeaza}

Eticheta rulărilor de măsurătoare care folosesc instantaneul acesta e numele
intrării de față, conform `METRICS.md` §9.2. Orice cifră de divulgare produsă cu
el declară amprenta `6567fc31…` și brațul rulat.

Registrul de prevalență, care la P2.3 va adăuga a treia componentă a scorului,
nu se amprentează: se declară ca stare la începutul rulării.
