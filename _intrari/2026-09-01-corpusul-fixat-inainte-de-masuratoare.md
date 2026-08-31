---
title: Corpusul, fixat înainte de măsurătoare
date: 2026-09-01
tip: masuratoare
rezumat: Compoziția celor 1494 de fișiere pe care se va rula evaluarea, pre-înregistrată cu tot cu abaterile de la specificație, înainte să existe vreo cifră.
tags: [pdp, observabilitate]
capitol: "2.11"
componente: ambele
commits: []
teste: []
status: partial
---

## Context {#context}

`CORPUS.md` §1.1 interzice o singură mișcare, și e cea mai ieftină de făcut fără
să-ți dai seama: ajustarea proporțiilor după ce se văd rezultatele. Un strat de
stres mărit fiindcă „banda nu se declanșează destul" ar fi un corpus ales ca să
iasă cifra, iar rezultatul ar descrie alegerea, nu sistemul.

Apărarea nu poate fi buna-credință. Singura apărare verificabilă e ca
proporțiile să existe scrise, cu dată, înaintea primei măsurători. Intrarea asta
e acel document. Corpusul s-a terminat de construit ieri; nicio treaptă de
divulgare n-a rulat încă peste el.

Ce se pre-înregistrează nu e o intenție, ci o stare a discului: manifestul
există deja, cu hash-urile celor 1494 de fișiere.

## Compoziția fixată {#alegerea}

| Sursă | Fișiere | Etichetă vine din |
|---|---|---|
| binare dintr-o instalare curată de Windows | 700 | proveniență |
| instalatoare descărcate oficial (winget) | 300 | proveniență |
| artefacte compilate local | 164 | proveniență |
| mostre MalwareBazaar | 330 | sursă |
| **total** | **1494** | |

**Straturi (§2):** realist 1164 (77,9%), stres 330 (22,1%).

**Paliere de dimensiune (§4):** sub 2 KB — 50 (3,3%); 2 KB–100 KB — 544 (36,4%);
peste 100 KB — 900 (60,2%).

**Suprapunere între endpoint-uri (§6):** 1046 comune (70,0%), 448 unice (30,0%),
pe 5 endpoint-uri. Cotul unic e gradat pe 1-3 mașini, conform §6.4:

| Apare pe | Fișiere | din care malițioase |
|---|---|---|
| 1 mașină | 363 (24,3%) | 280 |
| 2 mașini | 64 (4,3%) | 40 |
| 3 mașini | 21 (1,4%) | 10 |
| toate 5 | 1046 (70,0%) | 0 |

5784 de plasări în parc, adică 3,87 mașini în medie per fișier. Fiecare endpoint
primește 110-111 fișiere din cotul unic, dintre care 78 malițioase.

**Sămânța repartiției:** `20260831`. Aceeași sămânță și aceleași jurnale produc
aceeași repartiție; e scrisă în `manifest.json` alături de praguri și cote.

**Amprenta compoziției:**
`37fbf57dc9dfda667fa93ff8ab6a8c67dd064e53a6ce382a3f6697fee689afe5`.

Nu e hash-ul fișierului `manifest.csv`, și distincția contează. Fișierul acela se
rescrie la fiecare rulare de verificare, fiindcă i se completează coloanele
`vt_checked`, `vt_detections` și `vs_md5_present` — un hash al lui ar expira în
câteva ore și n-ar ancora nimic. Amprenta de mai sus acoperă numai coloanele care
descriu compoziția: ce fișiere sunt în corpus, cât de mari sunt, cum sunt
etichetate, în ce strat și pe ce mașini apar. Se calculează la fiecare rulare a
manifestului și se scrie în `manifest.json`.

Cât timp amprenta rămâne aceeași, corpusul e cel pre-înregistrat aici. Dacă se
schimbă după prima măsurătoare, s-a rescris montajul — exact ce interzice §1.1.

## Amendament, în aceeași zi {#schimbat}

Prima variantă a repartiției punea fiecare fișier unic pe exact o mașină. Era
mai strictă decât §6.3, care spune „pe **una sau două** mașini", și avea o
consecință pe care n-am văzut-o până n-am numărat: **prevalența lua exact două
valori**, 1 și 5. Nimic la mijloc.

Asta desființa tăcut jumătate din ce pretinde lucrarea. Deduplicarea și
escaladarea conștientă de prevalență sunt afirmații despre o relație — cu cât un
fișier e mai răspândit, cu atât costul lui marginal e mai mic — iar o relație
măsurată în două puncte nu se poate distinge de nicio altă formă care trece prin
ele. Cazul în care mecanismul chiar decide ceva, fișierul văzut pe două-trei
mașini, lipsea cu totul din corpus, prin construcție.

`CORPUS.md` a căpătat deci o secțiune nouă, §6.4, cu forma gradată a cotului
unic — 70/20/10 pentru benigne, 85/12/3 pentru malițioase — iar manifestul a fost
regenerat. Amprenta anterioară a compoziției, acum înlocuită, corespundea unui
`manifest.csv` de 310.379 de octeți cu SHA-256
`756489962467b6694c6c1b97dee59481c81f216a202062a666c3a135fcbebbb0`.

Modificarea e legitimă acum și ar fi fost imposibil de justificat peste o zi:
**nicio treaptă de divulgare n-a rulat încă peste corpus.** Nu s-a schimbat nimic
ca reacție la un rezultat, fiindcă nu există niciun rezultat. Rămâne totuși o
revizuire a unui document de pre-înregistrare, deci se scrie aici, cu ora și cu
motivul, nu se rescrie tăcut secțiunea de mai sus.

## Cum a fost obținut {#provenienta}

Uneltele sunt în repo-ul `Malware_Lab`, separat de `edr-agent` și `edr-server`:
construirea corpusului nu e cod de produs și nu rulează pe niciun endpoint
monitorizat.

Partea malițioasă a venit în trei faze deliberat separate — inventar de
metadate, selecție offline, descărcare. Separarea nu e organizatorică: palierul
de sub 2 KB nu se obține descărcând mai mult, ci filtrând pe tipuri de fișier
înainte de descărcare, iar asta e posibil doar fiindcă API-ul întoarce
`file_size` fără să livreze mostra. Inventarul a ajuns la 14.251 de intrări; s-au
descărcat 330.

Partea benignă a venit din trei surse cu proveniență controlată. Binarele de
sistem au fost copiate de pe o instalare curată de Windows, dintr-o mașină
virtuală care nu avusese niciodată altceva instalat pe ea — colectarea s-a făcut
cu un script PowerShell tocmai ca instalarea unui interpretor Python să nu scrie
runtime-ul Visual C++ în `System32` și să contamineze sursa. Instalatoarele au
fost luate prin `winget download`, fără executare. Artefactele compilate sunt
șase programe mici în opt combinații de optimizare, simboluri și arhitectură.

Mostrele stau arhivate cu parolă, pe o mașină virtuală dedicată, cu instantaneu
curat făcut înainte de prima descărcare. Nimic nu s-a executat.

## Abaterile, declarate {#cost}

Șase diferențe față de `CORPUS.md`. Toate sunt cunoscute înainte de măsurătoare,
și niciuna nu se corectează retroactiv.

**Fracțiunea malițioasă e 22,1%, nu 20%.** Selecția a cerut 330 de mostre în loc
de 300, ca surplus pentru descărcări eșuate; n-a eșuat niciuna. Mai mult stres
decât s-a planificat înseamnă condiții mai grele pentru protocol, nu mai ușoare.

**Palierul mijlociu e la 544, nu la ~300.** Cele 144 de binare compilate ies
între 3 și 8 KB și se adaugă peste cele 250 de binare de sistem din același
palier. Consecința e că palierul superior are 900 în loc de ~1150. Palierul
mijlociu e zona neutră a predicției din §4.1 — nici acolo unde protocolul
câștiga detașat, nici unde pierde.

**`System32` n-a avut niciun fișier sub 2 KB.** Zero din 6309 candidați. Palierul
critic — singurul care poate infirma predicția despre pragul de dimensiune — e
acoperit integral din alte două surse: 30 de droppere scriptate malițioase și 20
de fișiere de configurare produse la compilare. Numărul acestora din urmă a fost
coborât de la 60 la 20 tocmai ca palierul să nu depășească proporția fixată; §4.2
avertizează explicit că umplerea corpusului cu fișiere minuscule ar fi trucare.

**Instalatoarele: 300 de fișiere din 79 de pachete, cu 11 pachete eșuate.** Unele
nu expun versiuni prin winget, altele nu livrează instalatorul pentru descărcare.
Volumul de 27,4 GB provine din mai multe versiuni ale acelorași aplicații — ceea
ce e și intenția §3.2, nu doar o soluție de volum.

**Prevalența n-are valoarea 4.** Cotul unic urcă până la 3 mașini, cel comun stă
la 5; între ele nu există nimic. Cu 5 endpoint-uri, un fișier pe 4 mașini ar fi
practic comun, iar granița dintre cele două categorii ar deveni arbitrară. Curba
prevalenței are deci patru puncte — 1, 2, 3 și 5 — dintre care cel de la 3 se
sprijină pe 21 de fișiere, iar cel de la 2 pe 64. Se raportează cu numărul de
fișiere sub fiecare punct, nu ca o curbă netedă.

**VirusShare n-a confirmat nimic.** 262.144 de MD5 din listele 00496-00499, zero
potriviri pe cele 330 de mostre malițioase. Explicația nu e că mostrele n-ar fi
malware, ci că listele publice sunt în urma colecției MalwareBazaar: ultima
publicată e mai veche decât mostrele colectate acum. A treia opinie din §5.1 nu
e disponibilă pentru acest corpus și se raportează ca atare. Partea utilă a
rezultatului rămâne: niciunul dintre cele 1164 de fișiere benigne nu apare
într-o colecție de malware.

## Ce nu apără intrarea asta {#forta}

Pre-înregistrarea fixează compoziția, nu corectitudinea etichetelor.

Eticheta „malițios" aparține MalwareBazaar, care acceptă contribuții din
comunitate; un fals pozitiv de acolo devine fals pozitiv aici. Eticheta „curat"
înseamnă „provenit dintr-o sursă de încredere și necunoscut ca malițios", nu
„dovedit curat" — un binar de sistem compromis n-ar fi prins de metoda asta.

Consecința e mărginită și merită repetată, fiindcă e motivul pentru care
investiția în consens complet ar fi fost greșit plasată: afirmația centrală
compară protocolul cu always-upload, iar ambele folosesc același oracol
alimentat cu fișierele integrale. O etichetă greșită afectează identic cele două
părți și se anulează. Etichetele contează pentru `METRICS.md` §5, care e context,
nu afirmație.

## Ce urmează {#urmeaza}

Verificarea la VirusTotal e pornită și rămâne parțială prin construcție: ~4
cereri pe minut înseamnă patru zile pentru 1494 de fișiere. Fracțiunea acoperită
și numărul divergențelor se declară la final, alături de cifrele de mai sus.

Repartiția fixează 5 endpoint-uri. Există două mașini virtuale, dintre care una
contaminată cu mostre; celelalte trei se clonează din instantaneul curat.
`METRICS.md` §3.1 cere ca ordinea de adăugare să fie fixată înainte de
măsurătoare — e o cerință de montaj, nu de corpus, și tocmai de aceea e ușor de
uitat.
