---
title: Cum numeri heartbeat-urile care n-au ajuns niciodată
date: 2026-07-03
tip: decizie
rezumat: Serverul știa doar când a văzut ultima oară un agent, deci o bătaie pierdută nu lăsa nicio urmă. Am pus agentul să-și numeroteze bătăile, ca absența unui mesaj să devină o valoare pe care serverul o poate citi.
tags: [observabilitate, retea, identitate]
capitol: "3.4"
componente: ambele
commits: [edr-agent@46fd833, edr-server@ad808b0]
teste: [app/tests/test_heartbeat_sequence.py::test_sequence_gap_counts_missed_heartbeats, app/tests/test_heartbeat_sequence.py::test_monotonic_sequence_is_normal, app/tests/test_heartbeat_sequence.py::test_first_sequence_sets_baseline_without_restart, app/tests/test_heartbeat_sequence.py::test_legacy_heartbeat_without_sequence_is_backward_compatible]
status: partial
---

## Context {#context}

Până pe 3 iulie, tot ce făcea serverul la primirea unui heartbeat era o singură
atribuire:

```python
agent["last_seen"] = _utc_now()
```

Cu două zile înainte mutasem starea agentului pe derivare din vechimea acestui
câmp — `online` sub 30 de secunde, `degraded` sub 90, `offline` peste
([Agentul mort rămânea „active"]({{ '/intrari/2026-07-01-agentul-mort-ramanea-active/' | relative_url }})) —
deci serverul răspundea corect la o întrebare: **e viu acum?**

Nu răspundea la a doua: **am pierdut ceva între timp?** `last_seen` nu
înregistrează absențe. Rămâne în urmă cât timp nu vine nimic, apoi sare înainte
la prima bătaie care ajunge, și în clipa aia nu mai există nicio urmă a
intervalului sărit. Un agent care a pierdut cinci bătăi din șase și unul perfect
sănătos arată identic imediat ce a șasea ajunge: amândoi cu `last_seen` proaspăt,
amândoi `online`. Golul nu e în starea curentă, e în istoric — iar un câmp care se
suprascrie nu are istoric.

A treia întrebare stătea și mai prost: **mai e același proces?** Singurul semnal
de oprire pe care îl avea agentul era evenimentul de shutdown, construit explicit
pentru oprirea controlată:

```python
"event_type": "agent_shutdown",
"description": f"Agent stopped manually at {current_time}",
```

Adică singura oprire pe care serverul o vedea era exact cea care nu mă
interesează. Un `kill -9`, un crash, o mașină căreia i se ia curentul, cineva
care oprește procesul intenționat — toate produc tăcere, iar tăcerea arată la fel
ca o rețea proastă. Iar după repornire agentul revine cu același `agent_id`, pe
aceeași înregistrare, cu `last_seen` proaspăt. Din perspectiva serverului nu s-a
întâmplat nimic.

Toate trei sunt aceeași lipsă: serverul știe doar ce a primit, iar ce n-a primit
nu lasă nimic în urmă.

## Forța {#forta}

**Absența nu produce niciun mesaj.** Asta e constrângerea de bază, și e mai
puternică decât pare. Un heartbeat pierdut nu e un eveniment negativ pe care
cineva îl poate observa; e lipsa unui eveniment pozitiv. Nu poate fi detectat
direct de nimeni — poate fi doar *dedus*, și numai dacă structura care permite
deducția a fost pusă în mesaje înainte ca ele să se piardă.

**Cazul care contează e cel în care agentul nu poate vorbi.** Orice mecanism care
depinde de un mesaj trimis *în momentul* opririi acoperă fix mulțimea de situații
care nu mă îngrijorează. Un agent care apucă să anunțe că se oprește e un agent
sănătos, într-un sistem sănătos.

**Verdictul trebuie să fie al serverului, dar datele vin de la agent.** Nu pot
muta observația pe server, pentru că serverul nu poate număra ce n-a primit. Dar
nici nu pot lăsa agentul să pronunțe concluzii despre propria stare, pentru că
tocmai stările care contează sunt cele în care nu mai e în măsură s-o facă. Deci
agentul furnizează o observație brută, iar serverul o interpretează — și granița
dintre cele două e o decizie, nu un detaliu de implementare.

**Parcul nu se actualizează dintr-o bucată.** Un câmp nou în heartbeat trebuie să
fie opțional. Dacă îl fac obligatoriu, prima instalare parțială scoate din
funcțiune agenții vechi, adică produce endpoint-uri oarbe — exact ce încerc să
detectez.

**Serverul nu are memorie de risipit.** `agents_store` e un dicționar în memorie.
Nu-mi permit un istoric per agent, deci mecanismul trebuie să încapă în câțiva
întregi pe înregistrare și să decidă din prima, fără să se uite în urmă.

## Alternative {#alternative}

**Doar `last_seen` cu praguri, ce exista deja.** Respins ca insuficient, nu ca
greșit — mecanismul a rămas, cu rolul lui. Dar un prag răspunde la o întrebare
despre prezent: dacă ultima bătaie e mai veche de 90 de secunde, agentul e
offline. Nu poate spune că agentul a fost offline acum zece minute și a revenit,
pentru că momentul în care ar fi putut spune asta a trecut fără ca nimeni să se
uite. Detecția prin prag cere ca cineva să întrebe la momentul potrivit;
numerotarea lasă dovada în mesajul următor și o poate citi oricând.

**Fiecare bătaie poartă ceasul agentului.** Ar da și „câte", și „cât". Respins
pentru că sursa nu e de încredere: în medii izolate nu există sincronizare de
timp, ceasurile derivă, iar un ceas local e manipulabil de oricine are drepturi
pe endpoint. Mai rău, un ceas greșit și niște bătăi pierdute produc același
simptom — un salt — și n-am cum să le disting. Un contor nu are unități, deci nu
poate fi greșit cu trei ore; poate fi doar mai mare sau mai mic decât precedentul.

**Serverul numără singur, cu un timer sau o scanare per agent.** Respins pe două
motive. Costul: fie N timere, fie o baleiere periodică a întregului parc, pentru
o informație pe care agentul o are gratis. Și, mai important, serverul și-ar
număra propriile *așteptări*, nu încercările agentului — or cadența e dictată de
server prin `next_heartbeat_seconds`, iar agentul poate fi între timp pe o treaptă
de backoff. Serverul ar fi greșit exact în intervalele în care ceva chiar se
întâmplă.

**Agentul anunță explicit repornirea.** Un eveniment de start cu un marcaj, sau
un câmp „am repornit". Respins pentru că e o declarație, nu o observație: agentul
ucis nu o trimite, iar agentul compromis o trimite pe cea care îi convine. Voiam
ca serverul să deducă, nu să creadă.

**Confirmări per bătaie sau fereastră glisantă de secvențe văzute.** Semantic mai
bogat, dar disproporționat: stare per agent proporțională cu istoricul, pentru o
întrebare la care răspunde un singur întreg.

## Alegerea {#alegerea}

Agentul își numerotează bătăile; serverul citește diferențele dintre numere.

În bucla de heartbeat, un contor local ([46fd833](https://github.com/ZiGabiZi/edr-agent/commit/46fd833)):

```python
heartbeat_sequence += 1
heartbeat_payload = {
    "sequence": heartbeat_sequence,
    "agent_version": config.get("agent_version"),
}
response = send_heartbeat(server_url, config["agent_id"], heartbeat_payload)
```

Patru linii, două decizii.

**Contorul e per proces și nu se persistă nicăieri.** Trăiește într-o variabilă
locală a buclei; nimic nu-l scrie pe disc. Nu e comoditate — resetarea la
repornire *este* semnalul. Un contor care ar fi supraviețuit repornirii ar fi fost
mai „corect" ca numerotare și ar fi spus strict mai puțin.

**Se incrementează la fiecare încercare, nu la fiecare succes.** Incrementul e
înaintea apelului de rețea, deci o bătaie care eșuează consumă un număr.
Deliberat: contorul numără intenții, iar o bătaie pierdută în rețea e exact ce
vreau să se vadă ca pierdută. Dacă incrementam după răspunsul serverului,
secvența ar fi ieșit densă și golul ar fi dispărut — aș fi distrus informația în
timp ce o produceam.

Pe server, `record_heartbeat` primește secvența, ține `last_sequence` pe
înregistrarea agentului și întoarce un verdict în loc de un dicționar
([ad808b0](https://github.com/ZiGabiZi/edr-server/commit/ad808b0)):

```python
if last_sequence is None:
    pass                                          # baseline, fără verdict
elif sequence <= last_sequence:
    restart_detected = True
    agent["restart_count"] = agent.get("restart_count", 0) + 1
elif sequence > last_sequence + 1:
    missed = sequence - last_sequence - 1
    agent["missed_heartbeats_total"] = (
        agent.get("missed_heartbeats_total", 0) + missed
    )
```

Trei lucruri în jurul acestor rânduri contează la fel de mult ca ele:

**Câmpul e opțional.** `sequence: Optional[int] = None` în schemă. Un agent care
nu-l trimite primește exact comportamentul de dinainte — doar `last_seen` — și
niciun verdict fals. Regula de baseline există din același motiv: după o
repornire a serverului sau după actualizarea unui agent, primul număr văzut nu
înseamnă nimic comparativ, pentru că nu are cu ce fi comparat.

**Verdictul se întoarce și în răspuns.** `restart_detected` și `missed_heartbeats`
intră în `HeartbeatResponse`, deci agentul află ce a concluzionat serverul despre
el. Într-un mediu izolat, unde depanarea începe de la logul de pe endpoint, asta
face diferența dintre a citi o poveste și a citi jumătate din ea.

**Repornirea produce un eveniment, nu doar un contor.** Ruta emite un
`agent_restart` prin fluxul normal de evenimente. Un câmp pe înregistrarea
agentului e o stare la care trebuie să se ducă cineva să se uite; un eveniment
ajunge acolo unde se uită oricum.

Partea de repornire din regula de mai sus s-a dovedit greșită zece zile mai
târziu și a fost mutată pe o identitate de încarnare declarată explicit de agent —
scrisă separat, în
[Repornirea agentului nu se deduce din contor, se observă]({{ '/intrari/2026-07-13-repornirea-se-observa-nu-se-deduce/' | relative_url }}).
Ce descriu aici e decizia din 3 iulie, cu tot cu jumătatea care a căzut.

## Costul acceptat {#cost}

**Contorul e o declarație a agentului, nu o măsurătoare a serverului.** Un proces
compromis poate trimite ce numere vrea, iar cine oprește agentul și pornește o
versiune modificată păstrând numerotarea nu produce niciun semnal. Mecanismul e
proiectat împotriva accidentelor — crash, kill, rețea căzută — nu împotriva unui
adversar cu drepturi pe endpoint. Ridică puțin costul unei manipulări; nu o
împiedică. Am acceptat asta pentru că orice semnal nefalsificabil ar cere ceva ce
nu am pe endpoint: un secret pe care agentul să nu-l dețină, sau atestare
hardware.

**„Câte" nu înseamnă „cât".** `missed_heartbeats` numără bătăi, nu timp. Cu
cadența dictată de server și cu backoff pe partea agentului, o bătaie nu e o
unitate constantă: trei bătăi lipsă pot însemna 30 de secunde sau câteva minute.
Contorul răspunde la „câte", niciodată la „cât", iar eu am citit inițial cele
două ca fiind interschimbabile.

**Starea trăiește cât procesul serverului.** `last_sequence`, `restart_count` și
`missed_heartbeats_total` sunt în `agents_store`, adică în memorie. O repornire a
serverului le șterge, iar prima bătaie de după e din nou un baseline fără verdict.
E deliberat — alternativa ar fi fost o alarmă de repornire falsă pentru tot parcul
la fiecare repornire de server — dar înseamnă că momentul cel mai agitat e exact
momentul în care mecanismul tace.

**Verdictul e local, între două bătăi consecutive.** Fără istoric nu pot răspunde
la „cât de des pierde agentul ăsta bătăi". `missed_heartbeats_total` se adună fără
nicio dimensiune temporală: un agent cu 400 de bătăi pierdute în șase luni și unul
cu 400 într-o oră arată identic.

**Am cerut unei singure valori să răspundă la două întrebări.** Contorul exista
oricum pentru continuitate, deci repornirea părea un corolar gratuit — zero
câmpuri noi, zero suprafață adăugată. Costul marginal în cod chiar era zero, și
exact de-asta nu l-am cântărit. Reutilizarea unui semnal existent e ieftină în
linii scrise și scumpă în semantică.

**Testele verifică regula serverului, nu contractul dintre procese.** Toate
testele din `test_heartbeat_sequence.py` construiesc payload-ul direct și îl
trimit în endpoint, deci acoperă bine ce face serverul cu un număr: baseline, gol,
continuitate normală, agent vechi fără câmp. Nimic nu verifică partea agentului —
că incrementează per încercare, și nici măcar că payload-ul pe care îl compune
poartă cheile pe care serverul le citește. Sârma dintre cele două procese e
singura parte netestată, și e singura care nu poate fi reparată dintr-un singur
depozit. De-asta intrarea e `partial`.

## Ce am învățat {#invatat}

**Absența nu e un eveniment; numerotarea o transformă într-o valoare.** Un sistem
care raportează doar ce s-a întâmplat nu poate raporta ce n-a apucat să se
întâmple. Diferența dintre două numere consecutive e locul în care lipsa devine
ceva ce se poate citi — dar structura trebuie pusă în mesaje *înainte* ca ele să
se piardă, pentru că după aceea nu mai există nimic peste care s-o pui.

**Un câmp care se suprascrie nu poate răspunde la întrebări despre trecut.**
`last_seen` era corect și inutil pentru ce voiam: fiecare bătaie ștergea urma
celei dinainte. Starea curentă și istoricul sunt două nevoi diferite, iar prima nu
degenerează în a doua oricât de des ai actualiza-o.

**Semnalul trebuie generat de partea care poate vedea discontinuitatea.** Serverul
nu poate număra ce n-a primit; agentul nu poate raporta că a murit. Contorul
funcționează pentru că e produs de agent cât timp trăiește și interpretat de
server după ce agentul a tăcut. Împărțirea asta — observația la unul, verdictul la
celălalt — e partea din decizie care a supraviețuit tuturor revizuirilor
ulterioare.

**Întrebarea corectă nu e ce pot citi dintr-o valoare, ci ce garantează ea.** Un
contor monoton garantează ordinea în interiorul unui proces. Nu garantează nimic
despre identitatea procesului — iar eu i-am cerut exact asta, pentru că era la
îndemână. Când un semnal e ieftin, tentația nu e să-l folosești prost; e să-l
folosești la mai multe lucruri decât poate susține, fără să te oprești să scrii ce
susține de fapt.
