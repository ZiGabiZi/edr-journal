---
title: Redenumirea pică în repo-ul care a făcut-o
date: 2026-08-06
tip: decizie
rezumat: Testele care apărau granița dintre agent și server comparau payload-urile emise cu nume de câmpuri copiate de mână din celălalt repo. Copia nu era impusă de nimic. Numele se mută într-un contract comis identic în ambele părți, iar fiecare parte își validează propriul cod față de exemplarul ei.
tags: [contract, observabilitate]
capitol: "3.8"
componente: ambele
commits: [edr-agent@317097e, edr-server@dc62093, edr-server@fb7774f]
teste: [app/tests/test_wire_contract.py::test_schema_declares_exactly_the_fields_the_contract_lists, app/tests/test_wire_contract.py::test_schema_agrees_with_the_contract_on_what_is_mandatory, app/tests/test_wire_contract.py::test_schema_does_not_declare_a_field_the_contract_forbids, app/tests/test_wire_contract.py::test_every_contract_model_is_bound_to_a_schema, tests/test_payload_contracts.py::test_no_builder_emits_a_field_the_contract_forbids, tests/test_payload_contracts.py::test_the_contract_still_forbids_the_incarnation_at_registration, tests/test_payload_contracts.py::test_the_peer_repository_carries_the_same_contract, app/tests/test_undeclared_fields.py::test_an_undeclared_key_is_reported_with_its_name, app/tests/test_undeclared_fields.py::test_an_undeclared_key_does_not_reject_the_request]
status: rezolvat
---

## Context {#context}

Pe 3 august am reparat un câmp. Agentul trimitea `agents_instance_id`, serverul
citea `agent_instance_id`, Pydantic arunca diferența tăcut, iar detecția de
repornire nu se declanșase niciodată în producție —
[povestea e scrisă]({{ '/intrari/2026-08-03-un-test-verde-peste-un-camp-care-nu-ajungea/' | relative_url }}),
împreună cu testul care o păzește.

Pe 5 august, `be78e8c` a generalizat verificarea de la un builder la toți cinci.
Testul nou compara cheile emise de fiecare builder cu setul de câmpuri declarate
de schema corespunzătoare de pe server. Repo-urile fiind separate, agentul nu
poate importa modulele serverului, deci seturile acelea erau scrise de mână, în
`tests/test_payload_contracts.py`, cu un comentariu deasupra care cerea explicit
actualizarea lor odată cu schema.

Douăzeci și două de ore mai târziu am scris commit-ul care le șterge. Intrarea asta e
despre ce era greșit la ele și cu ce au fost înlocuite.

`be78e8c` a mai purtat o schimbare, lăsată deliberat în afara acestei intrări:
ștergerea incarnării din payload-ul de înregistrare — acolo aruncarea tăcută a
cheii era *accidental load-bearing* — plus mutarea momentului producerii pe
evenimente. Aia e o poveste despre identitate și timp, nu despre granița dintre
repo-uri, și își așteaptă intrarea ei, împreună cu partea de server. Aici apare o
singură dată, ca invarianta pe care contractul o declară interzisă. O menționez ca
să se vadă că e alegere, nu scăpare: cine compară commit-ul cu intrarea găsește
jumătate din el nescrisă.

## Forța {#forta}

**Niciun commit nu poate atinge ambele părți.** `edr-agent` și `edr-server` sunt
repo-uri separate, iar separarea e deliberată: două unități de livrare, dintre
care una se instalează pe endpoint și cealaltă nu. Consecința e că orice schimbare
de schemă e, structural, jumătate de schimbare, iar a doua jumătate depinde de
memoria cuiva. Partea care agravează: **niciunul dintre repo-uri nu rulează CI**,
deci nici măcar suita nu e o plasă automată — e ceva ce cineva alege să ruleze.

**Eșecul nu are formă de eroare.** Schemele rulează cu `extra="ignore"`. O cheie
pe care modelul nu o declară e aruncată la validare: fără 422, fără log, agentul
primește 200 OK, câmpul rămâne `None`. Defectul nu se manifestă când e comis, ci
luni mai târziu, când cineva caută datele și nu sunt acolo.

**Copia nu verifica serverul.** Verifica ce scrisese cineva despre server, la un
moment dat. O redenumire dincolo — `agent_instance_id` devenit `instance_id` — ar
fi lăsat agentul să trimită numele vechi, iar suita ar fi rămas verde. Adică fix
eșecul tăcut pentru care fuseseră scrise testele acelea, reintrodus pe canalul pe
care nu-l acopereau.

**Iar unul dintre teste nu verifica nimic.**
`test_every_field_the_agent_sends_is_known_to_the_server` nu apela nicio funcție
din agent. Compara două `frozenset`-uri definite la cincizeci de linii distanță,
în același fișier. Trecea pentru că le scrisesem pe amândouă.

**Direcția server → agent nu era acoperită deloc.** Agentul citește răspunsul cu
`response.get(...)`, deci o redenumire a lui `next_heartbeat_seconds` nu i-ar
produce nicio eroare — l-ar lăsa pe intervalul local pentru totdeauna, iar cadența
dictată central ar înceta să funcționeze fără ca cineva să observe.

## Alternative {#alternative}

**Oglinda scrisă de mână.** Nu e o alternativă ipotetică: e ce livrasem cu
douăzeci și două de ore înainte. Ce o descalifică e scris în chiar mesajul commit-ului
care a introdus-o, pe vremea când încă părea acceptabilă — seturile sunt duplicate
„cu obligația explicită, scrisă în comentariu, de a le actualiza odată cu schema".
O obligație scrisă într-un comentariu nu e un mecanism, e o speranță cu sintaxă.
Agravant: setul de câmpuri de heartbeat apărea în două fișiere, deci sincronizarea
manuală cerea două intervenții, nu una.

**Un singur repo.** Ar face posibil commit-ul care atinge ambele părți, ceea ce
pare să atace cauza. Respins pentru că atacă doar simptomul: fără CI, un repo unic
nu rulează nimic în plus, deci mută granița fără s-o verifice. Și plătește pentru
asta dizolvarea unei separări care are motivele ei — două cicluri de versionare,
iar agentul ajunge pe mașini pe care serverul n-are ce căuta.

**Client generat din OpenAPI.** FastAPI publică deja schema, deci clientul
agentului s-ar putea genera din ea. Respins din trei motive, ultimul decisiv:
acoperă doar direcția agent → server, lăsând descoperit exact canalul pe care
agentul citește cu `.get()`; introduce un pas de generare într-un lanț în care
nimic nu rulează automat; și **un generator nu poate exprima `forbidden`**.
Generarea copiază ce spune schema, iar invarianta care contează aici e că un câmp
*nu* are voie să apară în schemă. Nu există generator care să emită „câmpul ăsta
nu trebuie să existe niciodată aici, și iată de ce".

**Doar logare la runtime.** Serverul poate observa cheile pe care schema nu le
declară și le poate scrie în log cu numele lor. Respinsă *ca mecanism unic*,
pentru că se declanșează abia când un payload greșit ajunge efectiv la server,
într-o rulare reală — iar într-un sistem gândit pentru medii izolate, serverul
poate lipsi săptămâni. Descoperirea ar avea loc după greșeală, departe de ea, în
alt repo. Dar n-a fost respinsă *ca mecanism*: patru zile mai târziu e a doua
jumătate a răspunsului.

## Alegerea {#alegerea}

`contracts/wire-contract.json`, comis identic în ambele repo-uri, devine singura
sursă de adevăr pentru numele de pe fir. Descrie cele cinci modele schimbate între
agent și server, fiecare cu trei categorii: `required` — câmpuri fără valoare
implicită, pe care emitătorul e obligat să le trimită; `optional` — declarate, dar
cu valoare implicită; `forbidden` — câmpuri a căror simplă prezență rupe o
invariantă, descrisă în dreptul lor la `notes`.

Fiecare parte își validează propriul cod față de exemplarul local. Asta e toată
propoziția: **o schimbare de schemă pică suita în repo-ul care a făcut-o, în
commit-ul care a făcut-o** — nu peste șase luni, în celălalt repo, dacă se
întâmplă ca cineva să ruleze testele cu ambele clone pe disc.

Categoria `forbidden` are astăzi o singură intrare, și merită citită întreagă,
pentru că e primul loc din proiect în care o invariantă are enunț, motiv și gardă
în același obiect:

```json
"agent_register_request": {
  "server_model":  "app/schemas/agent.py::AgentRegisterRequest",
  "agent_builder": "agent.py::build_agent_registration_payload",
  "forbidden": ["agent_instance_id"],
  "notes": "agent_instance_id este interzis aici pentru ca incarnarea apartine
            exclusiv canalului de heartbeat. La repornire, reinregistrarea
            ruleaza inaintea primului heartbeat, iar register_agent() face
            update() peste inregistrarea existenta: o incarnare venita prin
            inregistrare ar suprascrie baseline-ul inainte ca heartbeat-ul sa
            il poata compara, si restart_detected n-ar mai fi True niciodata."
}
```

Regula e păzită din trei direcții, deliberat: agentul verifică să n-o emită
(`test_no_builder_emits_a_field_the_contract_forbids`), serverul verifică să n-o
declare (`test_schema_does_not_declare_a_field_the_contract_forbids`), iar a treia
verifică *regula însăși* —
`test_the_contract_still_forbids_the_incarnation_at_registration` pică dacă
interdicția dispare din contract. Fără ea, ștergerea unei linii din JSON ar face
celelalte două teste să treacă triumfal peste o invariantă deja pierdută.

**Al doilea mecanism, pe 10 august.** `WireModel` devine baza celor trei scheme
care primesc date de la agent și face trei lucruri, în ordine: acceptă cererea,
loghează cheia necunoscută cu numele ei și cu modelul pe care a apărut, apoi o
șterge. Nu înlocuiește contractul și nu e înlocuit de el, pentru că cele două nu
văd același lucru:

| | contractul | `WireModel` |
|---|---|---|
| întrebarea | ce nume avem voie să folosim? | ce nume a ajuns efectiv pe fir? |
| momentul | la commit | la rulare |
| locul unde se vede | în repo-ul care a greșit | în logul serverului |
| acoperă | codul comis de ambele repo-uri | orice emitent, inclusiv unul necunoscut |
| ratează | un emitent care nu trece prin suită | greșeala care încă n-a ajuns la server |

Rândul care contează e penultimul. Contractul acoperă cod; `WireModel` acoperă
firul — un build vechi rămas în parc, un `curl` scris de mână, un agent recompilat
din altă ramură. Niciunul dintre ele nu trece prin suita vreunui repo, și exact
despre ele contractul nu poate spune nimic.

**De ce nu `extra="forbid"`**, deși pare răspunsul evident. Pentru că aici 422 nu
e zgomot, e oprire. Agentul clasifică orice 4xx în afară de 404/408/429 drept
`FatalTransportError`, iar de acolo pleacă trei drumuri, toate mai grave decât un
câmp gol: la heartbeat, `heartbeat_loop()` face `return`, deci agentul tace până
la repornirea procesului; la `/api/events`, `EventDispatcher` tratează respingerea
ca poison message și șterge evenimentul din spool, adică pierdere de date; la
înregistrare, `register_agent_with_retry()` întoarce `False` și agentul nu mai
pornește deloc. Greșeala pe care `forbid` o face vizibilă ar opri monitorizarea
mașinii.

**De ce se șterg cheile după logare**, în loc să rămână pe model. Cu
`extra="allow"` ele intră în `model_dump()`, iar `register_agent()` face `update()`
peste înregistrarea existentă. Un `agent_instance_id` trimis din greșeală la
înregistrare ar ajunge astfel în store și ar suprascrie baseline-ul incarnării —
adică fix invarianta pe care contractul o apără cu `forbidden`. Mecanismul care
face greșeala audibilă era la două linii distanță de a sparge invarianta apărată
de celălalt. Ștergerea readuce semantica lui `extra="ignore"` pentru tot codul de
după validare: pe fir nu se schimbă nimic, se schimbă doar că acum se aude.

Două detalii plictisitoare, fără de care mecanismul ar produce eșecuri false:
exemplarele se compară pe JSON parsat, nu pe octeți, pentru că repo-urile sunt
clonate și pe Windows, și prin WSL, iar o diferență CRLF/LF n-are nicio legătură
cu numele de pe fir; iar citirea se face cu `utf-8-sig`, nu `utf-8`, pentru că
editoarele de pe Windows salvează des cu BOM, și `json.loads` ar crăpa atunci cu o
eroare care nu spune nimic despre contract.

## Costul acceptat {#cost}

**Jumătatea de sincronizare se degradează la skip.** Verificarea că exemplarul
local coincide cu cel din repo-ul pereche rulează doar când ambele clone sunt pe
disc. Fără CI, asta înseamnă: pe mașina mea, dacă îmi amintesc să rulez ambele
suite. Verificarea de conformitate a codului cu exemplarul local rulează
necondiționat, în fiecare repo, și aceea e partea care închide golul — dar cea
care poate lipsi e exact cea care prinde divergența dintre copii, adică singura
problemă pe care fișierul unic în două exemplare o introduce.

**Un fișier în plus de ținut în pas.** O schimbare de schemă e acum trei editări
plus incrementarea lui `contract_version`, în aceeași sesiune de lucru. Disciplina
n-a dispărut, s-a mutat: din „ține minte să actualizezi copia din celălalt repo"
în „ține minte să pornești din contract". Diferența e că a doua variantă e
verificată, prima nu era. Dar rămâne o regulă de proces, iar regulile de proces se
uită.

**`contract_version` e un marcaj, nu un invariant.** Nimic nu-i verifică monotonia
și nimic nu impune incrementarea când trebuie; testul compară doar dacă cele două
exemplare o au egală. Un contract schimbat în ambele părți fără incrementare trece
nesesizat.

**Registrul de invariante are populația unu.** Un singur câmp `forbidden`, pe un
singur model. E suficient ca să fie util și insuficient ca să justifice mutarea
lui într-o structură proprie a jurnalului: celelalte invariante ale sistemului —
de pildă „`last_sequence` e comparabil doar în interiorul unei incarnări cunoscute
și neschimbate" — trăiesc în docstring-uri, deci nu sunt verificate de nimic, iar
un registru care le-ar aduna la un loc le-ar face să arate la fel de solide ca
aceasta. E aceeași greșeală ca oglinda, cu un nivel mai sus. Până atunci registrul
e `wire-contract.json`, iar faptul că e citit de teste din trei direcții îl face
mai bun decât orice fișier de jurnal. Declanșatorul pentru revenire e scris aici,
ca „mai târziu" să nu însemne „niciodată": **a doua intrare în `forbidden`, sau
momentul în care banda de incertitudine a PDP-ului are nevoie de un loc unde
să-și scrie invariantul.**

**Avertismentul lui `WireModel` se vede doar în logul serverului.** E aceeași
degradare pe care am numit-o
[pe 11 iulie]({{ '/intrari/2026-07-11-agentul-observa-inainte-sa-ceara-voie/' | relative_url }}):
un mod de eșec vizibil doar în loguri locale e, practic, invizibil până când
cineva bănuiește deja ceva. Cheia necunoscută e acum audibilă, dar nu e raportată
nicăieri unde s-ar uita cineva fără motiv.

## Ce am învățat {#invatat}

**O copie pe care nimic n-o impune nu e o verificare, e o notă.** Testele de
dinainte aveau toate atributele unei verificări — nume descriptive, aserțiuni
reale, culoare verde — și zero putere, pentru că ambele capete ale comparației
fuseseră scrise de aceeași mână, în același fișier. Un test care compară două
constante pe care le-ai scris tu nu întreabă nimic pe nimeni. Întrebarea care
desface cazul: *ce anume, din afara acestui fișier, ar trebui să se schimbe ca
testul să pice?* Dacă răspunsul e „nimic", e o tautologie cu sintaxă de test.

**Cea mai bună alternativă respinsă e cea pe care ai livrat-o.** Oglinda nu e în
secțiunea de alternative pentru că am imaginat-o și am găsit-o slabă, ci pentru că
am scris-o, am comis-o și i-am văzut defectul douăzeci și două de ore mai târziu. E
singurul fel de alternativă pe care n-o poți inventa retroactiv, și e motivul
pentru care propoziția din mesajul lui `be78e8c` — scrisă când duplicarea încă
părea o concesie rezonabilă, nu o greșeală — valorează mai mult decât orice
reconstrucție de-a mea de acum.

**„Al doilea mecanism, nu încă o clauză" nu era despre debouncer.** Am formulat
regula
[pe 4 august]({{ '/intrari/2026-08-04-al-doilea-mecanism-nu-inca-o-clauza/' | relative_url }}),
crezând că e o observație despre plafonul de capacitate. Două zile mai târziu a
apărut din nou, în altă parte a sistemului, cu aceeași formă: două cerințe care
par una singură se separă după *momentul* în care pot acționa și după *ce anume
pot vedea*, nu după cât de tare e fiecare. Un principiu care apare de două ori
independent, la două săptămâni distanță, în două straturi fără legătură între ele,
nu mai e o soluție punctuală.

**Între două degradări se alege cea care păstrează observația adevărată.**
Argumentul împotriva lui `extra="forbid"` e al patrulea din aceeași familie:
înregistrarea
[nu abandonează niciodată]({{ '/intrari/2026-07-11-agentul-observa-inainte-sa-ceara-voie/' | relative_url }}),
plafonul debouncer-ului acceptă duplicate ca să nu fie oprit de sistem, iar aici
un câmp gol e preferabil unui agent tăcut.

Regula are însă o graniță, fără de care devine slogan, iar granița e chiar
[prima intrare din jurnal]({{ '/intrari/2026-06-05-mai-bine-niciun-agent-decat-unul-care-crede/' | relative_url }}):
acolo agentul refuză să pornească pe o configurație invalidă, adică aleg deliberat
degradarea zgomotoasă și totală. Nu e o contradicție, e cazul care ascute regula.
La `forbid`, alternativa era „agent oprit" contra „agent care observă corect, cu
un câmp pierdut" — observația supraviețuiește, deci o păstrezi. La configurație
invalidă, alternativa era „agent oprit" contra „agent care pare că observă și nu
observă nimic" — acolo nu există observație de păstrat, iar becul verde e mai rău
decât absența. Criteriul nu e „păstrează procesul", e **„păstrează observația
adevărată"**; când starea degradată încetează să mai producă observație adevărată,
regula se inversează singură.
