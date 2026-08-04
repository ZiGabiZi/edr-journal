---
title: Serverul era concurent fără să fi cerut nimeni asta
date: 2026-07-02
tip: incident
rezumat: Rutele scrise ca `def` simplu rulează pe fire diferite, deci store-urile din memorie erau citite și scrise concurent. Un `RuntimeError` zgomotos m-a trimis după o clasă întreagă de curse tăcute, inclusiv ID-uri de evenimente duplicate derivate din lungimea listei.
tags: [concurenta, identitate]
capitol: "3.6"
componente: server
commits: [edr-server@c49cef8, edr-server@cf19587]
teste: [app/tests/test_agent_service_concurrency.py::test_concurrent_register_and_read_does_not_corrupt_store, app/tests/test_agent_service_concurrency.py::test_concurrent_heartbeats_are_atomic]
status: partial
---

## Context {#context}

Serverul ține totul în memorie: `agents_store` e un dicționar de la `agent_id` la
înregistrarea agentului, `events_store` e o listă de evenimente. Nu e o scăpare, e
o etapă — persistența urmează, iar până atunci structurile astea sunt sursa de
adevăr.

Rutele arată așa:

```python
@router.get("")
def list_agents() -> dict:
    agents = get_agents()
    ...
```

`def`, nu `async def`. Serviciile din spate citesc și scriu direct în cele două
structuri, fără nicio sincronizare. Modelul meu mental era că un proces Python cu
un server ASGI procesează cererile una după alta, deci nu am de ce să mă apăr de
mine însumi.

## Simptom {#simptom}

Sub o singură cerere pe rând, nimic. Totul se comportă exact cum arată în cod.

Sub cereri simultane, două lucruri diferite ca zgomot. Primul, un `RuntimeError:
dictionary changed size during iteration` ieșit din `GET /api/agents`, adică un
`500` la o rută care nu face nimic altceva decât să citească. Reproductibil în
câteva sutimi de secundă cu patru fire care înregistrează agenți și șase care
citesc lista.

Al doilea nu ieșea nicăieri: două evenimente sosite în același moment primeau
același `event_id`. Fără eroare, fără avertisment, fără log. Două rânduri distincte
în `events_store`, cu aceeași identitate.

Diferența dintre ele contează mai mult decât fiecare în parte. Primul e o excepție
care oprește o cerere și nu strică nimic — starea rămâne coerentă, clientul
reîncearcă. Al doilea nu se vede niciodată și coruptează exact lucrul pe care se
sprijină toată corelarea de mai târziu. Cel zgomotos e cel care m-a făcut să mă
uit; cel tăcut era motivul pentru care trebuia să mă uit.

## Ce am crezut {#ipoteza}

Că serverul e mono-fir. Nu am formulat-o niciodată explicit, ceea ce e chiar
problema — era o presupunere moștenită, nu o decizie.

Presupunerea are și o versiune în care e adevărată, și de-aia se ține atât de bine:
dacă rutele ar fi fost `async def`, ar fi rulat toate pe același fir al buclei de
evenimente, iar orice secvență fără `await` între citire și scriere ar fi fost
atomică. Într-un server complet asincron, `event_id = len(events_store) + 1` urmat
de `append` chiar nu poate fi întrerupt.

Dar rutele sunt `def` simplu. Starlette nu poate rula cod sincron pe bucla de
evenimente fără s-o blocheze, deci îl trimite într-un threadpool. Fiecare cerere
sincronă ajunge pe un fir de lucru, iar mai multe cereri rulează efectiv în
paralel, pe fire diferite, peste aceleași structuri globale. Concurența nu a fost
aleasă. A fost moștenită dintr-un cuvânt-cheie pe care nu l-am scris.

A doua jumătate a ipotezei era GIL-ul: Python are un lock global, deci accesul la
un dicționar e sigur. E adevărat și irelevant. GIL-ul garantează că o operație
individuală pe un dicționar nu lasă structura într-o stare invalidă. Nu garantează
nimic despre două operații consecutive scrise de mine, iar toate bug-urile de aici
sunt exact asta: două operații între care încape altcineva.

## Cauza reală {#cauza}

Toate cursele au aceeași formă — citește, decide, scrie — și un interval între
citire și scriere în care starea se poate schimba.

**ID-ul de eveniment.** Cea mai curată:

```python
event_id = len(events_store) + 1
new_event = {"event_id": event_id, ...}
events_store.append(new_event)
```

Două fire citesc `len` = N, amândouă construiesc evenimentul N+1, amândouă adaugă.
Dincolo de cursă, e o greșeală de proiectare mai adâncă: identitatea evenimentului
era derivată dintr-o proprietate a *containerului*, nu a evenimentului. Lungimea
unei liste nu e un identificator, e o coincidență care ține cât timp nimeni nu
adaugă în paralel și nimeni nu șterge vreodată.

**Înregistrarea agentului.** `register_agent` citește `agents_store.get(agent_id)`,
decide pe ce ramură merge, apoi mută. Două înregistrări simultane ale aceluiași
agent pot citi amândouă „nu există" și pot scrie amândouă, ultima câștigând tăcut.

**Iterarea în timpul inserției.** `get_agents()` parcurgea `agents_store.values()`
în timp ce alt fir insera o cheie nouă. Ăsta e `RuntimeError`-ul, și e singurul
dintre toate care are decența să se plângă.

## Soluția {#solutia}

Câte un lock per structură, și fiecare secvență citește-decide-scrie mutată
înăuntru:

```python
agents_store: Dict[str, Dict[str, Any]] = {}
agents_lock = Lock()
```

Pentru evenimente, identitatea nu mai vine din container:

```python
_event_id_counter = count(1)

with events_lock:
    new_event["event_id"] = next(_event_id_counter)
    events_store.append(new_event)
```

`itertools.count` e un contor propriu, care nu mai are nimic de-a face cu câte
elemente sunt în listă. Chiar și fără lock, `next()` pe el ar fi fost atomic; cu
lock, atribuirea și adăugarea sunt și ele o singură unitate.

Două detalii care par cosmetice și nu sunt. `record_heartbeat` returnează acum
`agent.copy()`, iar `get_all_events()` returnează `list(events_store)` — înainte
întorceau referința vie, adică orice apelant putea modifica store-ul din afara
lock-ului, fără să știe că o face. Un lock care apără doar scrierile din interiorul
modulului nu apără nimic dacă modulul dă mai departe referințe către structura pe
care o apără.

Al treilea detaliu e cel care a costat. `find_agent_by_machine_id_hash` era o
funcție separată; ca s-o pot apela din interiorul lock-ului fără să-l reintru, am
mutat bucla direct în corpul lui `register_agent`. Mutarea a fost mecanică, și
odată cu ea a dispărut prima linie a funcției:

```python
def find_agent_by_machine_id_hash(machine_id_hash):
    if not machine_id_hash:
        return None
    ...
```

Garda aia n-avea nicio legătură cu concurența. Ce a devenit după ce a dispărut e
[povestea din 12 iulie]({{ '/intrari/2026-07-12-doi-agenti-care-nu-stiu-cine-sunt/' | relative_url }}).

## Cum știu că e rezolvat {#regresie}

`test_agent_service_concurrency.py` pune patru fire să înregistreze câte 400 de
agenți în timp ce șase fire apelează `get_agents()` de câte 150 de ori, și cere ca
lista de excepții să rămână goală și store-ul să conțină exact câți agenți au fost
înregistrați. Pe codul dinainte de lock, testul pica în câteva sutimi de secundă —
ceea ce e util de scris aici, pentru că înseamnă că bug-ul era ușor de reprodus și
totuși a stat acolo până când s-a nimerit să-l caute cineva.

Al doilea test verifică atomicitatea heartbeat-urilor concurente pe același agent.

Partea de evenimente n-are test, și de-asta intrarea e `partial`. Cursa pe
`event_id` a fost reparată în același sfert de oră cu cealaltă, dar fără regresie —
iar ea e cea tăcută, adică exact aceea pentru care un test contează cel mai mult.

## Ce am învățat {#invatat}

**`def` și `async def` sunt o declarație despre concurență.** Un cuvânt-cheie
decide dacă handler-ele rulează serializat pe o buclă de evenimente sau în paralel
pe un threadpool, deci decide dacă starea globală are nevoie de protecție. Eu
alesesem `def` pentru că e mai simplu de scris, adică luasem decizia fără să știu
că o iau.

**GIL-ul apără structura, nu intenția.** Faptul că un dicționar nu se corupe la o
operație individuală nu spune nimic despre secvențele pe care le scriu eu între
două operații. Aproape toate cursele reale trăiesc între instrucțiuni, nu în ele.

**Identitatea derivată din numărare nu e identitate.** `len(lista) + 1` produce un
număr care depinde de câți alții au fost înainte, nu de ce e obiectul ăsta. E
aceeași lecție pe care o scrisesem despre cheia de idempotență a evenimentelor, din
partea cealaltă a firului: identitatea trebuie să fie o proprietate a lucrului
identificat.

**Un bug zgomotos e un noroc.** `RuntimeError`-ul din iterare nu strica nimic — o
cerere pica, atât. Dar era singurul simptom vizibil al unei clase de probleme din
care restul erau invizibile. Dacă `get_agents()` s-ar fi întâmplat să nu itereze
niciodată în timpul unei inserții, aș fi rămas cu ID-uri duplicate și actualizări
pierdute, fără nimic care să mă trimită acolo.

**Refactorizarea într-o dimensiune poate șterge o garanție din alta.** Mutarea
buclei înăuntrul lock-ului a fost corectă pentru concurență și a aruncat, în
trecere, o gardă care ținea de identitate. N-am recitit ce mut; am mutat. Un
`if` de două rânduri șters dintr-o funcție pe care o inlinez arată, în diff, exact
ca restul mutării.
