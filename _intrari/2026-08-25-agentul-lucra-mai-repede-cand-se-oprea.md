---
title: Agentul lucra mai repede când se oprea
date: 2026-08-25
tip: incident
rezumat: Din 10.000 de fișiere scrise într-o rafală, 4.206 nu ajungeau în spool. Bănuiam watchdog; măsurătoarea a arătat că stratul de observare livrase toate cele 10.000. Hasher-ul aștepta 100 ms între toate trecerile și procesa un fișier per trecere — un plafon dur de zece fișiere pe secundă, indiferent de mărimea lor.
tags: [detectie, observabilitate, concurenta]
capitol: "3.1"
componente: agent
commits: [edr-agent@9a48e35, edr-agent@a1cfbd3]
teste: [tests/test_file_hasher.py::test_the_loop_does_not_wait_while_the_queue_has_work, tests/test_file_hasher.py::test_the_loop_still_rests_when_there_is_nothing_to_do]
status: rezolvat
---

## Context {#context}

Lanțul Etapei 0 era complet — observare, liniștire, hashing, spool — și avea un
harness cap-coadă care îl demonstra pe fire reale. Harness-ul fusese scris cu un
scop declarat: să transforme întrebarea din #13, dacă `watchdog` pierde
notificări în rafale, din ceva raționat în ceva măsurat. Testele lui scriu trei
fișiere, nu trei mii, dar instrumentul exista.

L-am extins cu un `observe()` instrumentat și i-am dat o rafală adevărată.

## Simptom {#simptom}

Zece mii de fișiere mici, scrise în 6,34 secunde:

```
scrise                      : 10000 in 6.34s (1577/s)
fisiere distincte observate : 10000
fisiere ajunse in spool     : 5794
pierdute INAINTE de tracker : 0
pierdute DUPA tracker       : 4206
```

Și, la oprire, două linii care nu apăruseră niciodată până atunci:

```
Shutdown hash budget expired with 4449 file(s) unhashed
File monitoring did not stop within its budget; still running
```

Peste patru mii de fișiere observate corect și dispărute pe drum.

## Ce am crezut {#ipoteza}

**Că `watchdog` pierde notificări sub rafală.** E chiar ipoteza scrisă în #13,
și era plauzibilă din trei motive: cozile interne ale lui `watchdog` au
dimensiune finită, 1.577 de scrieri pe secundă e mult peste orice regim normal,
iar pierderile la nivel de sistem de operare sunt un mod de eșec real și bine
documentat pentru genul ăsta de bibliotecă.

**Ipoteza secundară era că noi îl înfometăm.** Cu hasher-ul rulând la turație pe
firul lui, firul observer-ului ar fi putut să nu mai primească procesor, iar
`watchdog` ar fi început să piardă notificări din vina noastră indirectă.

Amândouă puneau problema în stratul de observare. Coloana `pierdute ÎNAINTE de
tracker` era acolo tocmai ca să le testeze, și amândouă au primit zero.
`watchdog` livrase toate cele 10.000, la 1.577 de scrieri pe secundă, cu
hasher-ul lucrând în paralel. **Pierderea era în întregime a noastră, în aval.**

## Cauza reală {#cauza}

`FileHasher.run()` aștepta `poll_seconds` între **toate** trecerile, iar
`process_once()` procesează deliberat **un singur fișier** per trecere.

Zece treceri pe secundă ori un fișier per trecere înseamnă un plafon dur de zece
fișiere pe secundă — indiferent dacă fișierul are 7 octeți sau 200 MB.

Intenția din docstring era corectă: un fișier mare nu trebuie să blocheze
reîncercările și degradările, care sunt ieftine. Dar implementarea lega *un
fișier per trecere* de *o trecere la 100 ms*, iar a doua parte nu decurge din
prima.

**Cauzalitatea, verificată prin variație:**

| `poll_seconds` | debit susținut |
|---|---|
| 0,1 | 9,1 fișiere/s |
| 0,001 | 83,2 fișiere/s |

De nouă ori, doar din pauză. Restul — circa 12 ms per fișier — e munca reală:
verificarea dublă de stabilitate plus commit-ul în spool.

**Cum devenea pierdere de date.** La nouă fișiere pe secundă, zece mii au nevoie
de peste optsprezece minute. În tot acest timp tracker-ul se apropia de plafonul
lui, iar bugetul de oprire arunca restul. Ambele mecanisme de siguranță s-au
declanșat exact cum fuseseră proiectate — pe o cauză care n-avea nicio legătură
cu ele.

**Asimetria care a scos problema la iveală:** `drain_for_shutdown()` buclează
fără nicio pauză. Oprirea agentului procesa de vreo douăsprezece ori mai repede
decât funcționarea lui normală. Un sistem care lucrează mai eficient când se
oprește decât când rulează are pauza în locul greșit.

## Soluția {#solutia}

Pauza se face doar când coada e goală. Un fișier per trecere rămâne — intenția
din docstring era corectă și e păstrată — dar trecerile nu mai sunt distanțate
artificial cât timp mai există de lucru.

## Cum știu că e rezolvat {#regresie}

Două gărzi în `tests/test_file_hasher.py`, deterministe, **fără ceas real**: se
numără apelurile de `wait()`, nu secundele.

Prima verifică faptul că zece intrări în coadă produc cel mult o pauză, cea de
după golire; cu implementarea veche ar fi apărut zece. A doua e contra-proba:
coada goală trebuie să producă o pauză de exact `poll_seconds`, altfel firul ar
consuma un nucleu întreg cât timp agentul nu are nimic de făcut — adică aproape
tot timpul.

**Garda a fost verificată în ambele sensuri: cu bucla veche pusă la loc, primul
test pică.**

Debitul susținut, în regim normal, fără să se atingă drenarea de oprire:

| fișiere | debit |
|---|---|
| 600 | 148,0/s |
| 2.000 | 173,5/s |
| 10.000 | 105,7/s |

De la 9,1 la 105–173, adică de douăsprezece până la nouăsprezece ori.

**Ce rămâne, declarat:** la zece mii de intrări debitul scade de la 173 la 106.
Tracker-ul ține intrările într-un dicționar peste care `due()` iterează la
fiecare trecere a releaser-ului, deci costul crește cu adâncimea cozii. E un
efect secundar, nu un plafon — măsurabil, și de tratat separat dacă ajunge să
conteze.

## Ce am învățat {#invatat}

**Regresia era invizibilă în orice test funcțional de până atunci.** Fiecare
fișier ajungea corect în coadă, fiecare hash era corect, fiecare eveniment avea
forma bună. Doar că zece pe secundă. Suita verifica *ce* se întâmplă și nu avea
niciun mijloc de a observa *cât de des* — iar la un agent care apără un endpoint,
debitul nu e o preocupare de performanță, e condiția ca mecanismul să existe.

**Înainte să acuzi stratul de dedesubt, măsoară-l.** #13 numea `watchdog`, iar
ipoteza era rezonabilă. Dacă aș fi pornit de la ea, aș fi ajuns să reglez cozi
de bibliotecă sau să caut un backend alternativ, pentru o pierdere care se
producea integral în codul meu, două etaje mai sus. Coloana care a decis totul
— `pierdute ÎNAINTE de tracker` — a costat câteva linii în harness.

**Când un sistem e mai rapid pe calea de excepție decât pe cea normală, calea
normală are un defect, nu excepția una virtuoasă.** Drenarea de oprire nu era
optimizată; era doar scrisă fără pauza pe care nimeni n-o pusese acolo cu un
motiv. Diferența de douăsprezece ori între cele două căi ale aceleiași funcții e
tipul de asimetrie care merită întotdeauna o întrebare.

**Un instrument construit pentru o întrebare răspunde și la altele.** Harness-ul
fusese scris ca să măsoare pierderile din `watchdog`. A găsit, la prima rulare
serioasă, un bug care n-avea nicio legătură cu întrebarea lui — pentru că
măsura lanțul întreg, nu doar capătul de care mă temeam.
