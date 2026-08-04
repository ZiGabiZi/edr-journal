---
title: Când doi agenți nu știu cine sunt, serverul crede că sunt același
date: 2026-07-12
tip: corectie
rezumat: Deduplicarea la înregistrare compara hash-ul mașinii cu `==`, iar o mașină care nu se poate identifica trimite `None`. Trei încercări mai târziu, regula nu mai întreabă cât de tare e identificatorul, ci despre ce anume e o afirmație.
tags: [identitate]
capitol: "3.3"
componente: server
commits: [edr-server@c49cef8, edr-server@e7f67c4, edr-server@382cd49, edr-server@b218b0d]
teste: [app/tests/test_agent_routes_integration.py::test_agents_without_machine_id_hash_do_not_collide, app/tests/test_agent_routes_integration.py::test_fallback_machine_id_type_still_participates_in_dedup, app/tests/test_agent_routes_integration.py::test_same_hash_different_machine_id_type_is_not_merged, app/tests/test_agent_routes_integration.py::test_reregister_with_same_machine_id_merges_onto_existing_record]
status: rezolvat
---

## Decizia originală {#originala}

`register_agent` deduplica pe două ramuri, în ordine. Întâi după `agent_id`: dacă
îl cunosc deja, actualizez înregistrarea existentă. Dacă nu, caut o înregistrare cu
același `machine_id_hash`; dacă găsesc una, o preiau, îi mut cheia pe noul
`agent_id` și o șterg pe cea veche.

A doua ramură are un scop precis: o mașină pe care agentul e reinstalat primește un
`agent_id` nou, dar rămâne aceeași mașină. Fără ea, fiecare reinstalare ar fi
produs încă un endpoint în consolă, iar parcul ar fi crescut cu fiecare
intervenție de mentenanță.

## Raționamentul de atunci {#rationament}

`agent_id` vine din `config.json`. E un fișier: se editează, se copiază, se
regenerează la reinstalare. Nu e o identitate, e un nume pe care agentul îl poartă
pentru că i l-a dat cineva.

`machine_id_hash` vine din mașină. Agentul încearcă, în ordine, `MachineGuid` din
regiștrii Windows, `/etc/machine-id` pe Linux, și abia apoi adresa MAC. Valoarea nu
pleacă niciodată în clar — se trimite SHA-256-ul ei, deci serverul poate compara
două mașini fără să afle identificatorul niciuneia, ceea ce se potrivește cu restul
sistemului.

Concluzia — identitatea mașinii bate numele din configurație — era corectă și a
rămas corectă. Tot ce a urmat a fost despre *când* are voie ramura a doua să
vorbească.

## Ce nu vedeam {#gol}

Trei lucruri, în ordinea în care au mușcat.

**Că `None` se compară cu `None`.** Când toate cele trei surse eșuează,
`get_stable_machine_identifier()` întoarce `("unknown", None)`, iar
`hash_identifier(None)` întoarce `None`. Bucla compara cu `==`, deci fiecare mașină
care nu se poate identifica era egală cu fiecare altă mașină care nu se poate
identifica. Iar ramura nu doar unifică: face `agents_store.pop(old_agent_id)`. Deci
al doilea endpoint fără identitate care se înregistra nu se alătura primului — îl
ștergea. Un parc de mașini care nu se pot identifica se prăbușea într-o singură
înregistrare, câte una pe rând, fără nicio urmă.

Garda care oprea asta existase. `find_agent_by_machine_id_hash` începea cu
`if not machine_id_hash: return None`, și a dispărut cu două zile înainte, când am
mutat bucla în interiorul lock-ului și
[am inlinat funcția fără s-o recitesc]({{ '/intrari/2026-07-02-serverul-era-concurent-fara-sa-ceara-nimeni/' | relative_url }}).

**Că reparația mea era prea largă.** Prima corecție a introdus o listă albă:

```python
STRONG_MACHINE_ID_TYPES = {"windows_machine_guid", "linux_machine_id"}
```

Deduplicarea rula doar dacă hash-ul era non-`None` **și** tipul era în listă.
Instinctul era bun — o adresă MAC nu e o identitate de mașină: `uuid.getnode()`
inventează o valoare aleatorie când nu poate citi un adaptor real, iar mașinile
virtuale clonate împart frecvent același MAC. Dar regula arunca exact cazul pentru
care ramura fusese scrisă: pe o mașină care are doar MAC, fiecare reinstalare
producea din nou o înregistrare duplicat. Înlocuisem o unificare greșită cu o
despărțire greșită, și abia testul de regresie scris mai târziu a spus-o pe față.

**Că problema avea și o direcție opusă.** Ramura pe `agent_id` rula prima și
suprascria necondiționat, cu `update()`. Or `config.json` se copiază pe toate
endpoint-urile la instalare — ăsta e modul normal de a distribui agentul, nu un
accident. Două mașini cu același `agent_id` ajungeau să împartă o singură
înregistrare: telemetria se amesteca, iar contorul de secvență raporta o repornire
la fiecare alternanță între ele, pentru că două contoare independente care se
întrepătrund arată exact ca un contor care se tot resetează.

## Ce am schimbat {#schimbat}

Regula de azi nu mai întreabă cât de tare e identificatorul:

```python
if machine_id_hash and machine_id_hash.strip():
    for agent in agents_store.values():
        if (
            agent.get("machine_id_hash") == machine_id_hash
            and agent.get("machine_id_type") == machine_id_type
        ):
            existing_agent_by_machine_id = agent
            break
```

Două schimbări mici, care împreună desfac tot nodul.

Un hash absent sau gol nu deduplică nimic. „Necunoscut" încetează să fie o valoare
care se poate compara cu altă valoare — și asta e forma generală a primului bug,
nu un caz particular al lui `None`.

Comparația se face pe **perechea** `(hash, tip)`, nu pe hash. Consecința e că un
identificator slab își recapătă treaba legitimă: o mașină cu doar MAC se recunoaște
pe ea însăși la reinstalare, pentru că perechea e aceeași. Ce nu mai poate face e
să se confunde cu o mașină identificată altfel — două hash-uri egale provenite din
scheme diferite rămân două mașini.

Mutarea care contează e asta: tăria identificatorului a încetat să fie o poartă
peste *dacă* am voie să compar, și a devenit parte din *ce* compar. Cât timp am
încercat să decid care identificatori merită încredere, orice prag pe care îl
alegeam excludea pe cineva legitim. Întrebarea corectă nu era cât de bun e
identificatorul, ci despre ce anume e o afirmație — iar un MAC e o afirmație
despre un adaptor, nu despre o mașină, deci se poate compara doar cu alte afirmații
despre adaptoare.

A treia schimbare acoperă direcția opusă. Un `agent_id` deja înregistrat, cu
identitate de mașină non-goală, care primește o cerere de la o altă identitate de
mașină, nu mai e suprascris: serviciul ridică `AgentIdConflictError`, iar ruta îl
traduce în `409 Conflict`. Înregistrarea originală rămâne intactă. Conflictul se
declanșează doar când ambele părți au o identitate non-goală și ele diferă, deci
re-înregistrările legitime și agenții vechi fără hash se comportă ca înainte.

O notă de igienă: relaxarea de la lista albă la perechi a intrat într-un commit
intitulat despre idempotența evenimentelor. E a doua oară în repo când schimbarea
care contează nu apare în mesajul commit-ului sub care a călătorit.

## Ce a rămas valid {#ramas}

Structura pe două ramuri și ordinea lor. Identitatea mașinii bate în continuare
numele din configurație, iar hash-ul rămâne singurul lucru care traversează rețeaua
— serverul compară mașini fără să afle vreodată cine sunt.

A rămas valid și scopul: o reinstalare pe aceeași mașină nu trebuie să producă un
endpoint nou. Toate cele trei corecții au fost despre marginile regulii, niciodată
despre ea.

Iar partea pe care aș păstra-o și dacă restul ar cădea e alegerea modului de eșec.
Două înregistrări pentru o singură mașină e o dezordine vizibilă, pe care o poate
repara cineva care se uită la listă. O singură înregistrare pentru două mașini e
invizibilă și otrăvește tot ce vine după: starea derivată, numărul de reporniri,
contorul de secvență, corelarea evenimentelor. Toate cele trei schimbări merg în
aceeași direcție, și e singura direcție care s-a dovedit stabilă: **când identitatea
e incertă, desparte; când e contradictorie, refuză.** Niciodată unifica din
comoditate, pentru că unificarea e singura operație pe care nimeni n-o mai poate
desface.
