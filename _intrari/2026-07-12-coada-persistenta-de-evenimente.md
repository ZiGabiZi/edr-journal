---
title: De ce agentul scrie evenimentele pe disc înainte să le trimită
date: 2026-07-12
tip: decizie
rezumat: Detecția și livrarea erau același lucru, așa că orice server picat însemna evenimente pierdute definitiv. Le-am separat printr-o coadă SQLite, cu tot ce atrage după sine semantica at-least-once.
tags: [persistenta, retea, concurenta, identitate]
componente: ambele
commits: [edr-agent@ed3cee6, edr-agent@bab4817, edr-agent@0eab4d9, edr-agent@f40ff46, edr-agent@457d17d, edr-server@382cd49]
teste: [app/tests/test_duplicate_client_event_id_is_idempotent.py::test_duplicate_client_event_id_is_idempotent, app/tests/test_duplicate_client_event_id_is_idempotent.py::test_event_without_client_id_still_accepted]
status: partial
---

## Context {#context}

Agentul supraveghează câteva directoare cu `watchdog`. Când apare un fișier nou
sau se modifică unul existent, biblioteca îmi apelează un handler pe firul ei de
observație. În prima versiune, handler-ul construia payload-ul evenimentului și
îl trimitea imediat la server:

```
watchdog (thread observer) ──▶ POST /api/events ──▶ server
```

Nu exista niciun pas între detecție și rețea. Dacă `POST`-ul eșua, funcția
loga un warning și se termina. Payload-ul existase doar ca dicționar în memoria
firului respectiv, deci în acel moment dispărea definitiv.

Erau trei feluri de a pierde un eveniment, și niciunul nu era exotic:

- serverul oprit sau repornit;
- rețeaua căzută între endpoint și server;
- serverul pornit și sănătos, dar fără să mai știe de agent — store-ul lui de
  agenți e în memorie, deci după repornire răspundea `404` la orice eveniment
  venit de la un agent înregistrat înainte.

Al treilea caz e cel care m-a deranjat cel mai tare: totul funcționa, ambele
procese rulau, și evenimentele se pierdeau oricum.

Mai era un cost pe care nu-l vedeam în loguri. Timeout-ul HTTP e de 5 secunde
(`DEFAULT_TIMEOUT_SECONDS` din `transport.py`), iar handler-ul rula pe firul
observer-ului. Cu serverul indisponibil, fiecare eveniment bloca detecția
până la 5 secunde — exact în momentele în care se întâmplă ceva pe disc.

## Forța {#forta}

Constrângerile care se băteau cap în cap:

**Detecția nu are voie să aștepte.** Firul observer-ului e singurul care vede
evenimentele de sistem de fișiere. Orice secundă petrecută acolo într-un timeout
e o secundă în care nu observ nimic altceva.

**Livrarea e nesigură prin natura ei.** Rețeaua pică, serverul se repornește,
agentul devine necunoscut. Astea nu sunt erori — sunt starea normală a unui
sistem distribuit, și trebuie tratate ca atare, nu ca excepții.

**Un EDR care pierde evenimente nu e un EDR.** Evenimentul pierdut e, statistic,
exact cel care contează: un atacator care oprește serverul sau taie rețeaua
înainte să scrie pe disc obține exact ce vrea. Pierderea tăcută e mai rea decât
o alertă ratată, fiindcă nu lasă urmă.

**Memoria e mărginită și procesele mor.** Orice soluție care ține evenimentele
doar în RAM le pierde la repornirea agentului sau a mașinii — adică fix în
scenariul de care mă apăr.

**Nu am coordonare centrală.** Sistemul e gândit să funcționeze și izolat, deci
nu pot presupune un broker sau un serviciu extern care să preia responsabilitatea.

## Alternative {#alternative}

**Retry pe loc, în handler.** Cea mai mică schimbare: bucla de reîncercare
direct în callback. Am respins-o pentru că mută problema în locul cel mai
prost — cu backoff exponențial, firul observer-ului ar fi stat blocat minute
întregi. Rezolvam pierderea evenimentului curent sacrificând detecția tuturor
celorlalte.

**Coadă în memorie (`queue.Queue`) plus un fir de trimitere.** Deblochează
observer-ul și e câteva linii de cod. Am respins-o pentru că nu rezolvă decât
jumătate din problemă: la repornirea agentului sau la reboot, coada dispare.
Or, tocmai repornirile sunt momentul în care vreau garanția.

**Fișier append-only cu câte un JSON pe linie.** Durabil și foarte simplu de
scris. Am respins-o din cauza ștergerii: după confirmarea unui eveniment
trebuie scos din mijlocul fișierului, ceea ce înseamnă rescrierea lui, plus
sincronizare manuală între firul care scrie și cel care citește. SQLite îmi dă
tranzacții, `DELETE ... WHERE id = ?` și acces concurent — lucruri pe care
altfel le-aș fi reimplementat prost.

**Un broker real (Redis, RabbitMQ, Kafka).** Corect ca semantică, dar
disproporționat: ar însemna un serviciu de instalat și întreținut pe fiecare
mașină monitorizată. Agentul trebuie să fie un singur proces care nu cere nimic
de la endpoint.

## Alegerea {#alegerea}

Detecția și livrarea devin două etape separate, legate printr-o coadă durabilă
pe disc:

```
watchdog (producător) ──▶ EventSpool (SQLite) ──▶ EventDispatcher ──▶ server
```

Callback-ul de fișier nu mai atinge rețeaua. Face două lucruri, ambele locale:

```python
def file_event_callback(event_payload: Dict[str, Any]) -> None:
    spool.enqueue(event_payload)
    dispatcher.wake()
```

`EventSpool` e o coadă FIFO peste SQLite, cu `journal_mode=WAL` pentru acces
concurent între firul care scrie și cel care citește, și o singură conexiune
partajată serializată cu un `threading.Lock` propriu.

Piesa centrală nu e coada în sine, ci **separarea citirii de ștergere**.
`peek_batch()` returnează cele mai vechi evenimente fără să le șteargă, iar
`mark_sent()` le șterge abia după răspunsul de succes al serverului. Dacă
agentul moare între trimitere și confirmare, evenimentul e încă acolo la
următoarea pornire. Asta e, în esență, semantica **at-least-once**.

`EventDispatcher` rulează pe firul lui și golește coada. Toată valoarea lui stă
în ce face la eroare, pentru că fiecare tip de eșec cere alt răspuns:

| Eșec | Interpretare | Ce face |
|---|---|---|
| `AgentNotRegisteredError` (404) | temporar — serverul și-a pierdut agenții | păstrează tot în coadă, backoff; heartbeat-ul re-înregistrează agentul, apoi coada se golește singură |
| `TransportError` (timeout, 5xx, rețea) | temporar | identic: nimic nu se pierde, se reîncearcă |
| `FatalTransportError` (4xx, mai puțin 408 și 429) | definitiv, dar doar pentru evenimentul ăsta | îl șterge individual și îl loghează ca eroare |

Ultima linie e problema **poison message**: un payload pe care serverul îl va
refuza mereu (un `422`, de exemplu) stă primul în coadă și, dacă îl tot
reîncerc, blochează la nesfârșit tot ce vine după el. Un singur eveniment
invalid ar opri livrarea întregii cozi. De-asta e aruncat individual, cu urmă în
log. Același tratament îl primesc și rândurile cu JSON corupt, detectate la
`peek_batch()`.

Tratarea lui `404` ca eroare recuperabilă, nu fatală, a fost o schimbare
separată în `transport.py` — înainte, un server repornit oprea agentul de tot.

Un detaliu de concurență care m-a costat un bug: `wake()`, apelat de producător
după fiecare `enqueue`, tăia scurt și așteptarea de backoff. Efectul e că un
fișier nou anula protecția anti-retry-storm, deși apariția lui nu spune absolut
nimic despre disponibilitatea serverului. Acum așteptarea de backoff
(`_sleep_backoff`) ascultă doar de `stop_event`, nu de `wake()`
([9bb131f](https://github.com/ZiGabiZi/edr-agent/commit/9bb131f)).

**Partea de server.** At-least-once înseamnă că serverul va primi uneori același
eveniment de două ori — dacă răspunsul se pierde după ce l-a procesat, agentul
îl retrimite pe bună dreptate. Deci fiecare eveniment poartă un
`client_event_id` (un UUID4), iar serverul deduplică pe el și întoarce
evenimentul deja înregistrat în loc să creeze unul nou.

Detaliul care face mecanismul să funcționeze e **unde** se generează cheia: în
`build_file_event_payload()`, adică în momentul detecției, înainte de a intra în
coadă. Dacă aș fi generat-o la trimitere, fiecare reîncercare ar fi produs alt
UUID și deduplicarea n-ar fi prins nimic. Identitatea trebuie să se nască odată
cu evenimentul, nu cu cererea HTTP.

## Costul acceptat {#cost}

**Duplicatele sunt prin proiectare, nu un accident.** At-least-once nu e o
variantă slabă de exactly-once, e un contract care mută sarcina: expeditorul
garantează că nu pierde, destinatarul garantează că nu dublează. Fără partea a
doua, prima e inutilă.

**Deduplicarea ține doar cât trăiește procesul serverului.** Indexul
`_events_by_client_id` și `events_store` sunt structuri în memorie. După o
repornire a serverului, memoria deduplicării dispare, iar evenimentele
retrimise de agent după acel moment vor fi acceptate ca noi. Garanția de
idempotență e reală, dar mărginită la durata de viață a procesului — asta
rămâne de rezolvat odată cu persistența pe server.

**Coada plafonată aruncă cele mai vechi evenimente.** Limita e 10.000; la
depășire se elimină cele mai vechi (FIFO), cu warning în log. Alegerea are o
logică — pentru răspuns activ, evenimentele recente valorează mai mult — dar
consecința e că o indisponibilitate lungă taie *începutul* poveștii, adică exact
partea în care s-ar vedea cum a intrat atacatorul.

**Ordinea se păstrează cu prețul debitului.** La prima eroare temporară,
dispatcher-ul oprește tot lotul în loc să sară peste evenimentul problematic.
E deliberat, dar înseamnă că un eveniment lent ține pe loc coada din spate.

**Un fișier de bază de date în plus pe fiecare endpoint**, plus o scriere pe
disc per eveniment.

**Nu am încă test de regresie pe partea de agent.** Testele care există acoperă
idempotența pe server: retransmisia aceluiași `client_event_id` nu creează
un al doilea eveniment, iar evenimentele vechi fără `client_event_id` sunt în
continuare acceptate. Garanția care contează cel mai mult — coada supraviețuiește
repornirii agentului — e verificată deocamdată doar manual. De-asta intrarea e
marcată `partial`, nu `rezolvat`.

## Ce am învățat {#invatat}

**Detecția și livrarea sunt două domenii de fiabilitate diferite.** Cât timp
sunt în același apel de funcție, cel slab (rețeaua) dictează comportamentul
celui puternic (observația locală, care nu poate eșua). Coada nu e o
optimizare de performanță — e granița dintre ce controlez și ce nu.

**Identitatea unui mesaj trebuie să se nască odată cu mesajul.** Cheia de
idempotență generată la trimitere e inutilă, pentru că se schimbă exact la
retransmisie, adică singurul moment în care ar folosi la ceva.

**Taxonomia erorilor e o decizie de arhitectură, nu tratare de excepții.**
Întrebarea „e temporar, e fatal pentru mesajul ăsta, sau e fatal pentru agent?"
decide dacă coada se golește, se blochează la nesfârșit sau își pierde
conținutul. Trei ramuri de `except` care arată banal în cod sunt, de fapt,
contractul de livrare al întregului sistem.
