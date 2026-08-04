---
title: Agentul mort rămânea „active", pentru că nimeni nu scria contrariul
date: 2026-07-01
tip: incident
rezumat: Câmpul status era scris la înregistrare și la fiecare heartbeat, dar nimic nu-l scria înapoi când agentul murea — pentru că moartea unui proces nu produce nicio scriere. L-am scos din store și l-am mutat în calcul, derivat la citire din vechimea lui last_seen.
tags: [observabilitate]
componente: server
commits: [edr-server@f560c26]
teste: [app/tests/test_agent_routes_integration.py::test_stale_agent_becomes_offline_without_new_heartbeat, app/tests/test_agent_routes_integration.py::test_internal_store_status_is_not_overwritten_by_derived_view, app/tests/test_agent_routes_integration.py::test_heartbeat_revives_offline_agent, app/tests/test_agent_status_unit.py::test_long_dead_agent_is_offline, app/tests/test_agent_status_unit.py::test_at_stale_threshold_is_degraded]
status: rezolvat
---

## Context {#context}

Tocmai mutasem heartbeat-ul pe un endpoint propriu — `POST /api/agents/{id}/heartbeat`,
separat de fluxul de evenimente, cu un canal de directive în răspuns. Agenții
stăteau în `agents_store`, un dicționar în memorie, iar fiecare înregistrare avea
un câmp `status`.

Două locuri din cod îl scriau:

```python
# la înregistrare
agent_data["status"] = "registered"

# la fiecare heartbeat
agent["status"] = "active"
```

Iar `GET /api/agents` întorcea store-ul așa cum era:

```python
def get_agents() -> List[Dict[str, Any]]:
    return list(agents_store.values())
```

`status` e câmpul pe care atârnă singura întrebare pentru care există lista asta:
*care endpoint-uri sunt în regulă și care nu.*

## Simptom {#simptom}

Am oprit agentul de test — nu frumos, ci din task manager, ca să semene cu cazul
real. Am așteptat. Am interogat `GET /api/agents`:

```json
{
  "agent_id": "endpoint-01",
  "status": "active",
  "last_seen": "2026-07-01T11:42:18+00:00"
}
```

Ora din `last_seen` era de acum câteva minute bune. Peste jumătate de oră,
același răspuns, cu aceeași oră înghețată tot mai adânc în trecut. Aceeași
înregistrare conținea și adevărul, și minciuna, una lângă alta, iar câmpul care
se numea `status` era minciuna.

Mai era un simptom, pe care l-am înțeles abia după: un agent care se
înregistrase și nu apucase încă să trimită niciun heartbeat apărea `registered`,
iar unul care trimisese exact unul apărea `active` la nesfârșit. Valoarea nu-ți
spunea în ce stare e agentul. Îți spunea **ce ramură de cod a atins ultima oară
înregistrarea.**

Nimic în loguri. Nicio eroare. Serverul funcționa corect — asta e partea care
face din el un incident și nu o cădere: nu s-a stricat nimic.

## Ce am crezut {#ipoteza}

Că lipsește un mecanism care să *marcheze* agenții morți. Un sweeper: un fir de
fundal care baleiază periodic store-ul și trece pe `offline` tot ce are
`last_seen` vechi. Dacă nimeni nu scrie „offline", pun eu pe cineva să scrie.

Am și început să-l scriu — un thread, un interval, un lock peste store.

Părea evident pentru că modelul meu mental era „store-ul conține starea
sistemului". Într-un model în care depozitul e adevărul, un câmp greșit se
repară scriind în el valoarea corectă, iar singura întrebare deschisă e *cine
scrie și când*. E o întrebare bună. Era pusă la o problemă pe care n-o aveam.

M-a oprit alegerea perioadei. La 60 de secunde, starea e greșită până la 60 de
secunde. La o secundă, plătesc o baleiere completă a parcului în fiecare
secundă, ca să pot răspunde la o întrebare pe care poate n-o pune nimeni. Și în
ambele cazuri, între două rulări, `status` rămâne o afirmație veche. Sweeper-ul
nu elimina fereastra de minciună — o făcea doar mai scurtă și mai scumpă.

Când o soluție are un parametru pe care nu-l poți alege bine, de obicei nu e
parametrul de vină.

## Cauza reală {#cauza}

`status` nu era o stare. Era un jurnal cu un singur rând: ținea minte ultima
tranziție observată, nu situația curentă.

Ambele scrieri — `registered` și `active` — consemnau lucruri care *se
întâmplaseră*. Înregistrarea s-a întâmplat. Un heartbeat a sosit. Amândouă
adevărate, amândouă permanente. Iar tranziția care lipsea nu avea scriitor și nu
putea să aibă unul, pentru că **moartea agentului nu produce nicio scriere.** Un
proces ucis nu apucă să anunțe nimic, iar o rețea căzută nu trimite un mesaj de
rămas-bun. Evenimentul „agentul a murit" nu există nicăieri în sistem, deci nu
poate declanșa niciun `UPDATE`.

Asta e forma generală, și e mai largă decât câmpul ăsta: **o stare care se
schimbă prin trecerea timpului, nu printr-un eveniment, nu poate fi stocată
corect.** Poate fi doar calculată. Store-ul nu greșea fiindcă îi lipsea o
scriere; greșea fiindcă păstra răspunsul la o întrebare a cărei valoare de adevăr
expiră singură.

Iar informația corectă era deja acolo, în același obiect. `last_seen` conținea
răspunsul, exact, în orice moment, fără ca nimeni să scrie nimic. Nu-mi lipseau
datele. Îmi lipsea momentul în care să le citesc ca pe un verdict.

Momentul ăla nu e un tic de ceas. E citirea.

## Soluția {#solutia}

`status` nu se mai scrie niciodată pentru liveness. Se calculează la fiecare
citire, din vechimea lui `last_seen`:

```python
def _derive_status(agent: Dict[str, Any]) -> str:
    last_seen_raw = agent.get("last_seen")
    if not last_seen_raw:
        return "unknown"

    last_seen = datetime.fromisoformat(last_seen_raw)
    age_seconds = (datetime.now(timezone.utc) - last_seen).total_seconds()

    if age_seconds < STALE_AFTER_S:      # 30
        return "online"
    if age_seconds < OFFLINE_AFTER_S:    # 90
        return "degraded"
    return "offline"
```

Linia care a dispărut contează la fel de mult ca funcția care a apărut:

```diff
 agent["last_seen"] = _utc_now()
-agent["status"] = "active"
```

Heartbeat-ul nu mai *declară* nimic. Actualizează un fapt — când a fost văzut
ultima oară — și se oprește acolo. Concluzia o trage cititorul, în momentul în
care are nevoie de ea.

`get_agents()` compune vizualizarea peste store, fără să-l atingă:

```python
for agent in agents_store.values():
    agent_view = agent.copy()
    agent_view["status"] = _derive_status(agent_view)
    result.append(agent_view)
```

**`.copy()` nu e igienă, e miezul.** Fără el, atribuirea ar fi scris direct în
store — adică exact greșeala pe care o reparam, doar cu o valoare mai proaspătă.
În plus, ar fi șters tăcut `"registered"`, singura informație de stare care chiar
avea dreptul să stea acolo. O citire care mută store-ul nu e o citire.

Stările sunt trei, nu două. `degraded` există pentru că, la un interval de 10
secunde, o bătaie lipsă nu înseamnă nimic — jitter, un pachet întârziat, o
reîncercare — în timp ce nouă la rând înseamnă altceva. Banda din mijloc e locul
în care stă „încă nu știu", și există ca să pot avea încredere în celelalte două.

## Cum știu că e rezolvat {#regresie}

Două suite, 19 teste, verzi azi. Regresia care reproduce direct bug-ul original:

```python
def test_stale_agent_becomes_offline_without_new_heartbeat():
    _register()
    _backdate_last_seen("agent-1", seconds_ago=200)

    response = client.get("/api/agents")

    # regresie directa pentru bug-ul original: inainte de fix, aici ar fi aparut "active"
    assert response.json()["agents"][0]["status"] == "offline"
```

`_backdate_last_seen` e tot trucul: rescrie `last_seen` în trecut în loc să
aștepte. Pentru că starea e derivată, testul n-are nevoie de ceas, de `sleep`,
nici de un dublu peste timp — e suficient să falsifice intrarea. Cu o stare
stocată aș fi avut de așteptat un sweeper, adică fie un test lent, fie un mock
peste temporizator. Testabilitatea n-a fost un obiectiv, a venit pe gratis, și e
un semn destul de bun că forma soluției e corectă.

Și cea care păzește copia:

```python
def test_internal_store_status_is_not_overwritten_by_derived_view():
    _register()
    client.get("/api/agents")
    assert svc.agents_store["agent-1"]["status"] == "registered"
```

Un `GET` care mutează store-ul ar trece toate celelalte teste din fișier. Ăsta e
singurul care l-ar prinde.

Plus granițele, scrise explicit pentru că sunt puncte în care condiția `<` decide
singură pe ce parte cade egalitatea: 29,9 s → `online`, 30,0 s → `degraded`,
89,9 s → `degraded`, 90,0 s → `offline`. Un prag dedus din cod la fiecare citire
a lui e un prag pe care mai devreme sau mai târziu îl deduci greșit.

(O notă de onestitate: `test_missing_last_seen_is_unknown` acoperă o ramură la
care niciun drum prin API nu ajunge azi, fiindcă înregistrarea setează
întotdeauna `last_seen`. E o plasă, nu o verificare.)

## Ce am învățat {#invatat}

**O stare care se schimbă prin trecerea timpului nu se stochează, se derivă.** O
valoare scrisă e o afirmație făcută la momentul scrierii și rămâne adevărată doar
cât nu se schimbă nimic. Când ce o schimbă e ceasul, nu există moment de scriere,
deci nu există moment corect în care s-o scrii. Întrebarea „cine scrie că agentul
a murit" n-are răspuns — iar o întrebare fără răspuns e de obicei semn că
întrebarea e greșită, nu că lipsește cineva care să răspundă.

**Un câmp fără scriitor pentru fiecare tranziție nu e un câmp, e o capcană.**
`status` avea un scriitor pentru înregistrare și unul pentru heartbeat, adică
pentru fiecare tranziție *înspre* viață. Înspre moarte nu scria nimeni. O mașină
de stări în care unele săgeți n-au nicio cauză în spate nu-ți spune în ce stare
ești; îți spune pe ce săgeată ai trecut ultima dată.

**Un nume, două vocabulare.** `registered` e un fapt de ciclu de viață — s-a
înregistrat, rămâne adevărat pentru totdeauna. `active` e o afirmație despre
prezent, care expiră. Amestecate sub același nume, fiecare o strica pe cealaltă:
heartbeat-ul ștergea faptul de înregistrare, iar înregistrarea arăta ca o stare
de viață. Separarea lor — faptul în store, verdictul în vizualizare — e ce a
reparat bug-ul; pragurile sunt doar calibrare. Iar despărțirea nu e nici azi
completă: `POST /api/agents/register` întoarce înregistrarea din store, deci
răspunde `"status": "registered"`, în timp ce `GET /api/agents` răspunde
`"online"` pentru același agent, în aceeași secundă. Bug-ul e rezolvat, numele nu.

**Costul se mută pe citire, și e bine că se vede.** Derivarea nu e gratuită: se
calculează pentru fiecare agent la fiecare cerere, adică o parsare de dată per
agent per `GET`. E o formă mult mai bună de cost decât un sweeper — se plătește
doar când chiar întreabă cineva, și scalează cu interesul, nu cu timpul — dar nu
e zero. Dacă vreodată devine o problemă, răspunsul e un cache cu invalidare pe
timp, nu întoarcerea la scriere.

**Pragurile sunt constante, cadența e dictată, și cele două nu se vorbesc.**
`STALE_AFTER_S = 30` și `OFFLINE_AFTER_S = 90` sunt scrise de mână, în timp ce
serverul dictează cadența întregului parc prin `next_heartbeat_seconds` — azi 10
secunde. Faptul că pragurile înseamnă „3 bătăi" și „9 bătăi" e un accident al
valorilor curente, nu o relație exprimată undeva în cod. Dacă mut vreodată cadența
la 60 de secunde dintr-un singur loc, tot parcul devine `offline` fără să
pățească nimic. Două constante care descriu același lucru și nu se știu una pe
alta rămân corecte exact până la prima schimbare.

**Ce nu se scrie nicăieri, se pierde — și `last_seen` era deja jumătate din
problemă.** Câmpul ăsta a putut înlocui `status` pentru că răspunde la o
întrebare despre prezent. Două zile mai târziu am avut nevoie de una despre
trecut — *câte bătăi am pierdut* — și `last_seen` n-a mai putut ajuta, din același
motiv structural: se suprascrie la fiecare bătaie, deci nu ține minte nimic
despre intervalul sărit. Continuarea e în
[Cum numeri heartbeat-urile care n-au ajuns niciodată]({{ '/intrari/2026-07-03-cum-numeri-heartbeaturile-care-nu-au-ajuns/' | relative_url }}).
