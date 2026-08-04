---
title: Al doilea mecanism, nu încă o clauză
date: 2026-08-04
tip: decizie
rezumat: Garda de curățare a debouncer-ului rulează cel mult o dată la 60 de secunde, deci nu se poate declanșa în interiorul unei rafale mai scurte de atât. Dimensiunea se întoarce ca plafon dur cu evacuare LRU — mecanism separat, O(1), nu o a treia variantă de operator boolean.
tags: [concurenta, detectie]
componente: agent
commits: [edr-agent@61a5bb5]
teste: [tests/test_event_debouncer.py::test_dictionary_never_exceeds_the_cap_during_a_burst, tests/test_event_debouncer.py::test_reseeing_a_key_protects_it_from_eviction, tests/test_event_debouncer.py::test_ordering_survives_a_cleanup_pass]
status: rezolvat
---

## Context {#context}

Intrarea din 25 iunie despre
[garda care nu pornea niciodată]({{ '/intrari/2026-06-25-curatarea-care-nu-pornea-niciodata/' | relative_url }})
s-a închis cu o datorie scrisă explicit, în două propoziții:

> Varianta de azi curăță cel mult o dată la 60 de secunde, deci o rafală mai
> scurtă de un minut nu e tăiată deloc pe parcurs. [...] Dacă se întoarce,
> trebuie să se întoarcă drept al doilea mecanism, separat — un plafon dur pe
> dicționar, cu evacuare — nu ca încă o clauză în același `if`.

Șase săptămâni mai târziu, `EventDebouncer` și-a primit primele teste. Ordinea
n-a fost întâmplătoare: clasa avea nouă linii de gardă care purtaseră deja două
bug-uri opuse și zero teste, deci orice mecanism nou s-ar fi adăugat peste un
comportament pe care nimic nu-l fixa. Testele au cerut, la rândul lor, o
singură schimbare de producție — un ceas injectabil, în locul apelului direct la
`time.monotonic()` — pentru că altfel un test care verifică ce se întâmplă după
un minut ar trebui să aștepte un minut, iar unul care verifică zece minute de
funcționare ar dura zece minute.

Cu comportamentul fixat, datoria din iunie a devenit sigur de plătit.

## Forța {#forta}

**Curățarea trebuie să fie rară, dar mărginirea trebuie să fie deasă.**

Curățarea periodică reconstruiește dicționarul: e O(n), rulează sub lock și pe
firul observatorului `watchdog` — singurul fir care vede evenimente de fișiere.
Costul ăsta e acceptabil o dată pe minut și inacceptabil o dată pe eveniment;
varianta cu OR a demonstrat asta cu 19.501 reconstrucții într-o rafală de 20 de
secunde.

Dar tocmai *raritatea* care o face ieftină o face oarbă. O limită de frecvență
de 60 de secunde **nu se poate declanșa înăuntrul unei rafale de 15 secunde**.
Nu e o problemă de reglaj — e o proprietate structurală: un mecanism care rulează
cel mult o dată la un minut nu are cum să mărginească ceva ce începe și se
termină în interiorul acelui minut.

Deci ai două cerințe care nu încap în același mecanism:

- una rară și scumpă, care decide *ce* a devenit irelevant (vechimea);
- una deasă și ieftină, care decide *câte* intrări au voie să coexiste (numărul).

**Iar rafala nu e ipotetică.** Mii de fișiere distincte atinse în câteva secunde
e profilul unei dezarhivări, al unui build — și al unui ransomware. Adică
momentul în care agentul e cel mai solicitat coincidea cu momentul în care
consuma cel mai mult, ceea ce e exact pe dos față de ce vrei de la un mecanism
de apărare.

## Alternative {#alternative}

**Încă o clauză în aceeași gardă.** Respinsă înainte să fie încercată: intrarea
din iunie e dovada. O limită de frecvență și un declanșator nu se combină cu un
operator boolean, pentru că una vorbește despre permisiune și celălalt despre
nevoie. Ambele variante ale alegerii binare produseseră deja comportamente
greșite — semn că întrebarea era prost pusă, nu răspunsul.

**Interval de curățare mai mic — 60 de secunde devin 5.** Nu mărginește nimic:
o rafală de patru secunde scapă în continuare întreagă. În schimb înmulțește cu
doisprezece reconstrucțiile O(n) sub lock, în funcționare normală, unde nu era
nicio problemă de rezolvat. E fix greșeala variantei OR, doar mai politicoasă:
mută costul din memorie în procesor și îl plătește tot timpul, nu doar când
trebuie.

**Curățare la fiecare eveniment, fără gardă.** Mărginește corect, dar e O(n) per
eveniment — adică exact thrashing-ul din iunie, de data asta prin construcție,
nu din accident.

**Nimic — accepți vârful.** Respins pentru că „nemărginit" nu e o valoare. Un
agent de securitate care crește necontrolat în memorie ajunge să fie oprit de
sistem sau dezinstalat de administrator, iar atunci endpoint-ul rămâne exact
nemonitorizat — se pierde fix lucrul pe care mecanismul îl apăra.

## Alegerea {#alegerea}

Un plafon dur pe numărul de intrări, cu evacuarea celei mai vechi, independent
de ceas:

```python
_DEBOUNCE_MAX_TRACKED_EVENTS = 10_000

def _evict_over_capacity(self) -> None:
    while len(self._last_seen) > self.max_tracked_events:
        self._last_seen.popitem(last=False)
```

Cele două mecanisme coexistă acum fără să se subordoneze:

| | curățarea periodică | plafonul de capacitate |
|---|---|---|
| întrebarea | *ce* a devenit irelevant? | *câte* încap simultan? |
| criteriul | vechime > `2 × interval` | număr > 10.000 |
| frecvența | cel mult o dată la 60 s | la fiecare eveniment |
| costul | O(n) | O(1) |

Costul O(1) e ce face plafonul rulabil la fiecare eveniment sub lock, și el vine
din structura de date: `_last_seen` devine `OrderedDict`, iar
`popitem(last=False)` scoate din capătul cel mai vechi fără să parcurgă nimic.
Cu un dicționar obișnuit, „care e cea mai veche intrare?" ar fi cerut o parcurgere
completă — adică O(n), adică plafonul ar fi devenit a doua curățare, nu un
mecanism diferit.

**Capcana e într-o singură linie.** În `OrderedDict`, scrierea peste o cheie
existentă actualizează valoarea, dar **nu îi schimbă poziția**. Fără mutarea
explicită la capăt, ordinea ar însemna „prima apariție" în loc de „ultima
apariție":

```python
self._last_seen[event_key] = current_time
self._last_seen.move_to_end(event_key)
```

Pe un plafon de 3, cu `a` revăzut la pasul 4:

| pas | fără `move_to_end` | cu `move_to_end` |
|---|---|---|
| 1-3: `a`, `b`, `c` | `a, b, c` | `a, b, c` |
| 4: `a` din nou | `a, b, c` | `b, c, a` |
| 5: intră `d` | evacuat **`a`** | evacuat `b` |

Fără linia aceea, evacuarea aruncă exact fișierul văzut cel mai des — adică fix
acela pentru care debouncing-ul există. Mecanismul ar fi funcționat pe dos, dar
tăcut: memoria ar fi rămas corect mărginită, doar deduplicarea ar fi eșuat, și
numai pe cazurile care contează. De-asta linia are un test doar al ei, verificat
prin ștergerea ei.

**Cuplajul tăcut.** Curățarea periodică reconstruiește dicționarul, deci trebuie
să producă tot un `OrderedDict`, cu ordinea păstrată. Dacă reconstrucția ar
amesteca ordinea, plafonul ar începe să evacueze intrarea greșită și nimic nu
s-ar plânge. Cele două mecanisme sunt independente ca scop, dar legate printr-un
invariant pe care doar un test îl impune.

## Costul acceptat {#cost}

**Se pot raporta duplicate.** O cheie evacuată de plafon înainte să-i expire
fereastra de două secunde va fi văzută ca eveniment nou la următoarea apariție.
Sub presiune extremă, calitatea deduplicării scade — dar serviciul nu cade.
Compromisul e ales în direcția asta deliberat: un duplicat ocazional e
recuperabil pe server, un agent oprit de sistem nu.

**Un al doilea parametru de reglat, ales fără măsurători.** 10.000 de intrări
înseamnă câțiva MB și nu se atinge niciodată în trafic normal — e o plasă de
siguranță, nu un regim de lucru. Dar cifra e o estimare, nu un rezultat: n-am
măsurat consumul real pe o stație sub rafală. Dacă vreodată plafonul se atinge
în funcționare obișnuită, valoarea e greșită, nu mecanismul.

**`_last_seen` nu mai e un dicționar oarecare.** Oricine atinge curățarea pe
viitor trebuie să știe că ordinea e semnificativă. Asta e o obligație nouă, iar
singurul lucru care o apără e un test.

## Ce am învățat {#invatat}

**Un mecanism care nu se poate declanșa în fereastra care contează nu e o
protecție slabă — e absența protecției.** Garda de 60 de secunde funcționa
perfect pe intervalul pentru care fusese scrisă, și era complet inertă exact în
scenariul în care memoria explodează. „Rulează rar" și „rulează când trebuie" nu
sunt același lucru, iar diferența nu se vede din cod, ci din suprapunerea dintre
perioada mecanismului și durata evenimentului pe care ar trebui să-l prindă.

**Structura de date corectă cu operația greșită eșuează la fel de tăcut ca
structura greșită.** `OrderedDict` fără `move_to_end` mărginește memoria
impecabil și ruinează scopul clasei, fără nicio eroare, fără nicio linie de log,
și numai pe fișierele active — adică pe cele pentru care ai scris codul.

**Testele n-au fost consecința schimbării, ci precondiția ei.** În iunie am
lăsat intrarea la `partial` tocmai pentru că nimic nu împiedica bug-ul să se
întoarcă. Adăugarea unui mecanism nou peste o clasă nefixată ar fi însemnat două
comportamente netestate în loc de unul. Ordinea corectă a fost: ceas injectabil,
teste peste comportamentul existent, abia apoi mecanismul nou.

**Datoria scrisă în jurnal se plătește; cea nescrisă se uită.** Fraza din iunie
— „dacă se întoarce, trebuie să se întoarcă drept al doilea mecanism" — a fost,
șase săptămâni mai târziu, specificația completă a acestei intrări. Nu mi-am
amintit raționamentul; l-am citit.
