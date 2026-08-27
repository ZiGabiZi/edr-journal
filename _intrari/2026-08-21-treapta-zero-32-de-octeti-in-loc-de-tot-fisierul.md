---
title: Treapta zero — 32 de octeți în loc de tot fișierul
date: 2026-08-21
tip: decizie
rezumat: Agentul raporta până acum că a apărut un fișier; de acum raportează ce a apărut. Hashing-ul primește fir propriu, pentru că o citire de zeci de secunde pe firul de dinainte ar transforma un fișier mare în orbire temporară a monitorizării — iar rezultatul se verifică de două ori, pentru că tracker-ul produce un candidat, nu un adevăr.
tags: [pdp, detectie, concurenta]
capitol: "2.5"
componente: agent
commits: [edr-agent@062df7d, edr-agent@fe99154]
teste: [tests/test_file_hasher.py::test_a_file_changed_during_the_read_is_reintroduced_not_reported, tests/test_file_hasher.py::test_a_file_changed_before_the_read_is_caught_too, tests/test_file_hasher.py::test_reintroduction_preserves_the_original_occurred_at, tests/test_file_hasher.py::test_the_entry_that_waited_longest_keeps_its_place_in_line, tests/test_file_hasher.py::test_pressure_never_turns_into_silence, tests/test_file_hasher.py::test_a_read_already_in_progress_is_abandoned_at_the_deadline, tests/test_file_hasher.py::test_the_deadline_comes_from_the_caller_not_from_drain_entry, tests/test_file_hasher.py::test_what_the_budget_does_not_cover_is_reported_without_a_hash, tests/test_settle_tracker.py::test_a_reintroduced_file_gets_a_fresh_quiet_period, tests/test_settle_tracker.py::test_the_cost_anchor_survives_every_reintroduction]
status: rezolvat
---

## Context {#context}

Cu [SettleTracker]({{ '/intrari/2026-08-20-fisierul-scris-continuu-nu-iesea-niciodata/' | relative_url }})
în flux, agentul știe în sfârșit *când* un fișier a încetat să se schimbe. Ceea
ce face posibilă întrebarea următoare, care e chiar prima treaptă a protocolului:
ce anume a apărut?

Până acum, un eveniment spunea *că* a apărut un fișier — cale, tip, moment,
dimensiune. Treapta T0 spune *ce* a apărut: SHA-256, 32 de octeți, în locul
fișierului întreg. E prima instanță concretă a invariantei pe care se sprijină
toată lucrarea — analiza merge la fișier, nu fișierul la analiză — și e locul
unde tot ce urmează, banda de incertitudine și treptele T1–T3, are ce escalada.

## Forța {#forta}

Patru tensiuni, dintre care trei se rezolvă prin aceeași mișcare și una nu se
rezolvă deloc.

**Timpul de citire împotriva garanției de dinainte.** Tracker-ul promite că
orice intrare iese în cel mult `max_wait_seconds`. Promisiunea e adevărată doar
cât timp cineva apelează `due()`. Citirea integrală a unui fișier poate dura
zeci de secunde, iar un hash calculat pe firul releaser-ului ar fi însemnat că,
în tot acel timp, nimic nu mai iese din tracker. Un fișier mare ar fi devenit
orbire temporară a monitorizării — și cu cât fișierul e mai interesant, cu atât
orbirea e mai lungă.

**Candidatul împotriva adevărului.** Tracker-ul raportează liniște, iar liniștea
lui înseamnă *nu am primit observații de o secundă*. `watchdog` nu garantează un
eveniment pentru fiecare scriere. Deci absența observațiilor nu înseamnă „nimeni
n-a scris", ci „nu mi s-a spus că cineva a scris". Diferența e exact spațiul în
care se calculează un hash pe un fișier care încă se schimbă.

**Oprirea mărginită împotriva citirii nemărginite.** Agentul trebuie să se
oprească într-un buget dat de apelant. Un fișier de 200 MB pornit cu o
milisecundă înainte de expirarea bugetului nu se citește într-o milisecundă.

**Presiunea trebuie să degradeze pe cineva.** Când coada de hashing se umple,
ceva trebuie să cedeze. Alegerea *cui* îi cere sacrificiul e o decizie, nu un
detaliu.

## Alternative {#alternative}

**Hashing pe firul releaser-ului.** Respins: e chiar prima tensiune, netratată.
Ar fi funcționat impecabil în teste, unde fișierele au zeci de octeți, și ar fi
orbit monitorizarea la primul ISO copiat pe endpoint.

**Încredere în tracker, fără verificare la citire.** Respins pentru că
transformă o limitare cunoscută a lui `watchdog` într-o afirmație pe care
agentul o face despre conținut. Un hash raportat e o afirmație tare — *acesta e
fișierul* — și n-are voie să se sprijine pe absența unei notificări.

**Închiderea completă a ferestrei de citire.** Respinsă ca imposibilă, nu ca
scumpă: fără suport de kernel, nu există nicio combinație de verificări în
spațiul utilizator care să garanteze că fișierul nu s-a schimbat între prima și
ultima citire. Alternativa onestă nu e o garanție mai bună, ci o garanție mai
mică, declarată ca atare.

**Termen de oprire per etaj.** Respins după ce a fost scris: cu trei etaje,
același `timeout` dat fiecărei așteptări făcea ca `join(timeout=5)` să dureze
15 secunde. Semnătura promitea o limită și livra un multiplu al ei, iar minciuna
creștea tăcut cu fiecare etaj adăugat.

**Termen verificat doar înainte de fișier.** Respins: mărginește momentul
ultimei *porniri*, nu durata muncii. Fișierul de 200 MB pornit cu o milisecundă
înainte de expirare se citea integral.

**Degradarea capului cozii sub presiune.** Respinsă pentru că `_take_next()` ia
din cap, deci capul e simultan intrarea care a așteptat cel mai mult și
următoarea la rând. A o degrada ar fi însemnat să aruncăm exact așteptarea pe
care tocmai a plătit-o.

## Alegerea {#alegerea}

**Al treilea etaj de fire.** Fiecare etaj revine în timp constant către cel de
dinaintea lui:

```
watchdog  -> tracker.observe()             (fir observer, timp constant)
releaser  -> tracker.due() -> hasher       (fir propriu, timp constant)
hasher    -> stat / hash / re-stat -> spool  (fir propriu, poate dura)
```

Separarea nu e ornamentală: **fiecare etaj protejează garanția etajului dinainte
de latența etajului de după.**

**Verificarea dublă:** `stat` înainte, hash, `stat` după. Dacă dimensiunea sau
`mtime` s-au schimbat, rezultatul se aruncă și fișierul se reintroduce în
așteptare.

**Reintroducerea repornește fereastra de stabilizare**, pe o singură cale, nu
două. Ramura în care intrarea există deja în așteptare e cazul *obișnuit*, nu
excepția: aceeași scriere fizică e și motivul pentru care verificarea dublă a
picat, și motivul pentru care intrarea nouă există. Două ramuri cu comportamente
diferite ar fi făcut rezultatul să depindă de un detaliu nedeterminist — dacă
`watchdog` a apucat sau nu să livreze evenimentul.

**`first_seen` se desparte în două câmpuri**, pentru că avea două slujbe cu
același răspuns doar din accident:

| câmp | ce ancorează | la reintroducere |
|---|---|---|
| ancora costului | `settle_wait_ms`, care trebuie să acopere tot | se cumulează |
| `settling_since` | de cât timp suprim raportarea acestui fișier | reîncepe |

Ținute pe același câmp, un fișier reintrodus ar fi depășit plafonul din prima
clipă și ar fi fost reeliberat instantaneu, fără nicio secundă de liniște — deși
agentul tocmai constatase că se schimbă.

**Sub presiune se degradează sosirea, nu capul cozii.** Numărul de fișiere care
primesc hash nu se schimbă — el e dat de viteza hasher-ului. Se schimbă doar
*care* fișiere și cât se așteaptă degeaba. Analogia cu tracker-ul se inversează
aici: acolo „cel mai vechi" înseamnă „cel mai probabil deja stabilizat", deci
alegerea cea mai puțin dăunătoare; aici înseamnă „cel mai aproape de a fi citit",
deci cea mai dăunătoare.

**Termenul de oprire vine de la apelant, ca moment absolut, și se verifică între
blocurile de citire.** Nu ca durată numărată de la intrarea în drenare:
întârzierea până acolo e nemărginită, pentru că semnalul de oprire nu se observă
cât timp firul e blocat într-o citire.

Iar termenul mărginește **hashing-ul, nu raportarea**. Un fișier nehash-uit
pierde doar identitatea lui de conținut; unul neraportat dispare cu totul.

## Costul acceptat {#cost}

**Garanția e mai modestă decât pare, și trebuie spusă limpede.** Un fișier care
revine exact la aceeași dimensiune, cu `mtime` intact, între cele două `stat`-uri
trece nedetectat. Ce se poate afirma onest e: *dacă un hash e raportat, fișierul
nu s-a schimbat **observabil** în timpul citirii.* Nu „nu s-a schimbat".

**Trei etaje de fire în loc de unul.** Fiecare cu bucla lui, garda lui de
excepții și ordinea lui la oprire. `FileMonitor.join()` a devenit un buget
*total*, cu o rezervă tăiată pentru raportare — complexitate care nu exista cât
timp totul rula pe firul `watchdog` și care va trebui recitită de oricine adaugă
un al patrulea etaj.

**Un fișier poate ajunge la server fără hash.** Peste plafonul de dimensiune, la
expirarea bugetului de oprire, sau după plafonul de reintroduceri. Vocabularul
de stare (`ok`, `unstable`, `vanished`, `unreadable`) există tocmai ca absența să
fie numită, nu tăcută — dar rămâne o fracțiune din corpus pentru care treapta T0
nu produce artefactul ei, și fracțiunea aia va trebui numărată la evaluare.

**Raportarea se mărginește structural**, prin adâncimea cozii de hashing. E o
limită reală, nu una teoretică — și, cum s-a văzut patru zile mai târziu, e
limita pe care o atinge prima un debit prost reglat.

## Ce am învățat {#invatat}

**O garanție care e adevărată doar cât timp cineva apelează o metodă nu e o
garanție a mecanismului, e una despre apelant.** Tracker-ul promite eliberarea în
`max_wait_seconds` și chiar o respectă — dar promisiunea trăiește în firul care
îl consumă, nu în el. Orice muncă adăugată în acel fir scurtcircuitează tăcut o
proprietate demonstrată prin teste, fără ca vreun test al tracker-ului să pice.

**Absența unei notificări nu e o observație.** `watchdog` nu promite un eveniment
per scriere, deci liniștea lui e o ipoteză, nu un fapt. Un mecanism care
construiește o afirmație tare — *acesta e conținutul fișierului* — pe o ipoteză
slabă trebuie să verifice ipoteza la momentul folosirii, nu să o moștenească.

**Când un câmp are două slujbe și dai peste un caz în care răspunsurile diferă,
n-ai găsit un bug — ai găsit că erau două câmpuri de la început.** `first_seen`
funcționa perfect atât timp cât nimic nu se reintroducea. Reintroducerea n-a
stricat câmpul, doar a arătat că a fost mereu o coincidență.
