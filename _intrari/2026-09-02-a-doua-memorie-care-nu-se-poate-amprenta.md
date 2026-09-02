---
title: A doua memorie, care nu se poate amprenta
date: 2026-09-02
tip: decizie
rezumat: Prevalența e prima cunoaștere care e a parcului, nu împrumutată dintr-o listă externă — și prima care se schimbă în timpul rulării. De aici decurge tot restul — nu se amprentează, ci se declară ca stare la început, ordinea sosirii devine parte din montaj, iar răspunsul stocat e ce știa serverul atunci, nu ce știe acum.
tags: [reputatie, pdp, contract]
capitol: "2.6"
componente: ambele
commits: []
teste: []
status: deschis
---

## Context {#context}

P2.3 a pus depozitul de reputație pe calea evenimentului: la fiecare fișier cu
hash, serverul spune ce știe la T0. Verificat pe montajul real, funcționează —
`known_malicious` cu proveniență, `known_software`, `unknown`.

Dar cunoașterea aceea e **împrumutată**. Vine din NSRL RDS și din inventarul
MalwareBazaar, adică din artă anterioară. Astăzi, dacă cinci endpoint-uri ating
același fișier necunoscut, toate cinci primesc `unknown` și toate cinci ar
escalada separat. Propoziția „un fișier escaladează o dată, parcul primește la
T0" e adevărată exact pentru fișierele pe care le știa deja altcineva.

Prevalența e prima bucată de cunoaștere care e a parcului. E și cea care dă
conținut brațului rece al ablației: fără ea, „rece" înseamnă doar „RDS fără
MalwareBazaar", adică o comparație între două liste externe.

Măsurat pe proba de la P2.3.6, golul e vizibil: trei instalatoare recente au
primit `unknown`, iar patru fișiere goale au primit `known_software` — fiindcă
amprenta șirului vid chiar e în RDS. Din 7 evenimente, 4 hash-uri distincte.
Deduplicarea există deja în date; ce lipsește e memoria care s-o folosească.

**Numerotarea deciziilor: M1–M11**, de la *memoria parcului*. `D*` e al
`METRICS.md` §9, `R*` al depozitului de reputație, `F*` al firului. A patra
etichetă distinctă, din același motiv ca la a treia.

## Forța {#forta}

**Prevalența e a doua memorie, dar nu seamănă cu prima în singurul fel care
contează.**

Instantaneul de reputație e un artefact sigilat: construit în afara rețelei,
livrat ca fișier, deschis `mode=ro&immutable=1`, schimbat prin înlocuire. O
rulare vede exact unul, iar amprenta lui de 64 de caractere răspunde definitiv la
„ce a citit serverul când a produs cifra asta".

Prevalența se schimbă **în timpul rulării**, prin construcție. Al cincilea
endpoint care raportează un fișier primește alt răspuns decât primul, și tocmai
asta e ce vrem să măsurăm. Trei consecințe, niciuna evitabilă:

1. **Nu se poate amprenta.** O amprentă peste ceva ce se schimbă în timpul
   rulării ar fi falsă înainte ca rularea să se termine. Ce se poate declara e
   *starea la început*, ca poziție de plecare — la fel ca brațul ablației.
2. **Răspunsul depinde de ordinea sosirii.** Aceleași evenimente, altă ordine,
   alte valori per eveniment. Constrângerea de montaj din §L2.12 — endpoint-uri
   adăugate eșalonat, cu ordinea fixată înainte — nu mai e doar despre atribuirea
   costului marginal; devine condiția în care prevalența înseamnă ceva.
3. **Valoarea de pe fir e perisabilă.** Ce a răspuns serverul la ora 10:03 nu mai
   e adevărat la 10:05. Deci ce se persistă lângă eveniment e o *fotografie*, nu
   o proprietate a fișierului.

**Iar codul nu lasă loc de deliberare la primul punct.** `sha256` nu e coloană în
depozitul de evenimente — stă în JSON-ul din `payload`, iar indecșii sunt pe
`run_id` și `agent_id`. Un răspuns derivat la citire ar cere scanare completă
plus parsare JSON **la fiecare eveniment**: O(n) per eveniment, O(n²) per rulare,
crescând cu experimentul. E aceeași formă cu amprentarea leneșă reparată la
P2.3.6, doar că acolo costul era constant, aici crește.

## Alternative {#alternative}

**Un contor per hash, incrementat la fiecare eveniment.** Respinsă. Nu se poate
reconstrui ca „agenți distincți" după aceea, iar a doua atingere a aceluiași
fișier pe aceeași mașină l-ar umfla — o mașină care rescrie un fișier de 500 de
ori ar arăta ca un parc. Greșeala nu produce nicio eroare, doar o cifră mai mare
în direcția favorabilă.

**Prevalență per rulare, nu globală.** Respinsă. Memoria unui parc nu se golește
când operatorul redenumește experimentul. Ar face și ablația imposibil de
exprimat: „prevalență rece" ar deveni un comutator, adică un parametru care
schimbă tăcut înțelesul cifrei, în loc de un montaj vizibil.

**Amprentarea registrului, ca la instantaneu.** Respinsă — vezi mai sus. Ar fi o
cifră care pare să ofere aceeași garanție ca amprenta instantaneului și nu o
oferă. Un mecanism de verificare care minte e mai rău decât absența lui.

**Prevalența în blocul `reputation`, lângă dispoziție.** Respinsă. Sursele sunt
diferite — una externă și sigilată, una internă și vie — iar `disposition` e
definită ca bijecție cu 2×2-ul instantaneului. Un câmp de altă proveniență
înăuntru ar face vocabularul acela să nu mai descrie ce pretinde.

**Prevalența ca scor, chiar și simplu.** Respinsă, și e aceeași linie ca la R1:
momentul în care aici apare un prag e momentul în care §L2.7 rămâne fără obiect,
iar sistemul are două mecanisme de decizie care se contrazic pe tăcute. Se
transmite dovadă; agregarea e a benzii, cu ponderi înghețate.

**Amânarea prevalenței pe fir până la bandă.** Respinsă *de operator*, și
argumentul lui e mai bun decât al meu: fără prevalență în răspuns, efectul de
parc rămâne invizibil pe fir, iar mecanismul care poartă afirmația centrală n-ar
avea nicio urmă observabilă până la un pas care încă nu are dată. Costul e
declarat mai jos.

## Alegerea {#alegerea}

**M1. Registru întreținut la ingestie, nu derivat la citire.** Constrângerea de
mai sus, transformată în structură.

**M2. Se stochează perechi `(sha256, agent_id)`, nu contoare.** `UNIQUE` pe
pereche și `INSERT ... ON CONFLICT DO NOTHING`, iar prevalența e un `COUNT(*)`.
Numărul devine corect prin construcție, nu prin grija apelantului — aceeași
apărare ca deduplicarea pe `client_event_id`. La montajul fixat sunt 5784 de
rânduri în total, deci costul e neglijabil.

**M3. `first_seen` și `last_seen` de la început**, deși niciun scor nu le
folosește azi. Vechimea intră în scor împreună cu prevalența: prezent pe 400 de
mașini de trei luni ≠ apărut pe 50 de mașini în 10 minute. Asimetria decide
singură, ca la R2 — costul unei coloane nefolosite e spațiu, al uneia lipsă e
reconstruirea registrului, adică pierderea istoricului care nu se poate reface.

**M4. Global peste rulări.** Registrul e memoria parcului, nu a experimentului.

**M5. Nu se amprentează; se declară STAREA LA ÎNCEPUTUL RULĂRII.** Hash-uri
distincte și agenți distincți, consemnate la deschiderea rulării, lângă
identitatea instantaneului din `run_reputation`. Fără ele, două rulări cu aceleași
evenimente și memorii de plecare diferite ar publica cifre incomparabile fără ca
nimic să spună de ce.

**M6. Se înregistrează întâi, se citește după.** Endpoint-ul care raportează se
numără pe sine, deci primul primește `1`, niciodată `0`. Un zero n-ar putea fi
deosebit de „n-a fost numărat", iar numărul înseamnă *pe câte mașini se știe că
există conținutul ăsta acum*, iar mașina care tocmai a raportat e una dintre ele.

**M7. Prevalența circulă pe fir, în bloc PROPRIU.** `prevalence`, frate cu
`reputation` în evenimentul stocat, nu câmp înăuntrul lui. Două surse, două
cicluri de viață, două blocuri.

**M8. Ce circulă e dovadă, nu scor:** `agents` (pe câte mașini distincte se știe
conținutul, inclusiv aceasta), `park_agents` (câte mașini au raportat vreodată un
fișier cu hash) și `first_seen` (când l-a văzut parcul prima oară).

`park_agents` nu e decor: „3 mașini" înseamnă altceva într-un parc de 5 decât în
unul de 500, iar un numărător fără numitor e exact tiparul refuzat la §3.4. Se
derivă din registru, nu din inventarul de agenți — acela trăiește în memoria
procesului și s-ar goli la repornire, deci numitorul ar scădea fără ca parcul să
se micșoreze.

**M9. Valoarea stocată e cea de la PRIMA sosire.** Ca la F9: dispoziția și
prevalența intră în payload înainte de inserare, iar retransmisia întoarce rândul
existent. Ce se persistă e ce știa serverul când a răspuns, nu ce știe acum.
Prevalența curentă a unui hash e o interogare separată; confundate, aceleași date
ar da două cifre și niciuna n-ar fi reconstruibilă.

**M10. `prevalence` e INTERZIS pe cerere.** Un endpoint care și-ar declara
singur prevalența și-ar putea fabrica propria închidere la T0 — memoria partajată
ar depinde de ce afirmă mașina observată. Aceeași interdicție ca la `reputation`,
din același motiv.

**M11. Ordinea de adăugare a endpoint-urilor devine parte din montaj**, nu doar
recomandare de măsurătoare. Se consemnează în intrarea de tip măsurătoare, iar
fără ea cifrele per eveniment nu sunt reproductibile nici măcar pe aceleași date.

## Predicția, scrisă înainte de măsurătoare {#predictie}

Corpusul e deja fixat, deci histograma prevalenței se poate pre-înregistra. Din
intrarea de corpus: 1046 de fișiere (70,0%) pe toate cele cinci mașini, 448
(30,0%) unice, gradate pe 1–3 mașini, 5784 de plasări, media 3,87 mașini per
fișier.

| prevalență finală | fișiere așteptate |
|---|---|
| 5 mașini | 1046 |
| 1–3 mașini | 448 |
| **total hash-uri distincte** | **1494** |

Dacă la măsurătoare iese altceva, defectul e în conductă — hashing, spool,
deduplicare — nu în parc. E singura cifră a pasului care se poate verifica fără
să se compare cu ea însăși.

## Costul acceptat {#cost}

**Al doilea bloc pe legătura descendentă, tot nemăsurat.** `wire_accounting`
numără doar octeți primiți; `prevalence` adaugă câteva zeci de octeți la fiecare
eveniment de fișier, invizibili pentru registru. Golul era declarat de la P2.3;
acum se dublează, iar formularea „zero octeți ascendenți suplimentari" acoperă o
direcție tot mai scumpă. Nu se repară aici, dar de la pasul ăsta contabilizarea
descendentă încetează să fie o curățenie și devine o datorie.

**Răspunsul per eveniment nu e reproductibil fără ordinea sosirii.** Agregatul
e — histograma finală nu depinde de ordine — dar valoarea primită de un anumit
fișier pe o anumită mașină, da. Cine compară două rulări eveniment cu eveniment
trebuie să compare și ordinea.

**Registrul global se murdărește ușor.** O sesiune de depanare cu evenimente de
probă intră în memoria parcului și schimbă poziția de plecare a următoarei
măsurători. De aceea M5 cere declararea stării la început: nu previne
murdărirea, o face vizibilă. Curățarea reală e o bază de evenimente nouă.

**Un rând per (fișier, mașină).** 5784 la montajul de acum. Crește cu produsul
dintre dimensiunea parcului și cea a corpusului, nu cu numărul de evenimente —
dar crește, iar un parc real l-ar simți acolo unde 5784 nu se simte deloc.

**Prevalența nu e prevalență reală, e prevalență observată.** Numără mașinile
care au *raportat* fișierul, nu pe cele care îl au. Un endpoint oprit, unul cu
coada plină, sau unul care n-a atins încă directorul monitorizat lipsesc din
număr. Limitare declarată, nu rezolvabilă la acest strat.

## Ce am învățat {#invatat}

**Două lucruri numite la fel — „memorie" — cer garanții opuse.** Prima memorie
are nevoie să fie neschimbătoare ca să poată fi amprentată; a doua are nevoie să
se schimbe, altfel n-ar măsura nimic. Reflexul de a le trata la fel ar fi produs
o amprentă peste registrul de prevalență, adică o cifră care promite
reproductibilitate și n-o poate ține. Numele comun era tot ce aveau în comun.

**O constrângere de montaj poate deveni o condiție de corectitudine fără ca
cineva s-o mute.** Eșalonarea endpoint-urilor era, la §L2.12, o măsură pentru
atribuirea costului marginal. Din clipa în care răspunsul serverului depinde de
ordinea sosirii, aceeași propoziție apără altceva: reproductibilitatea per
eveniment. N-a fost rescrisă nicio regulă; s-a schimbat ce se sprijină pe ea.
