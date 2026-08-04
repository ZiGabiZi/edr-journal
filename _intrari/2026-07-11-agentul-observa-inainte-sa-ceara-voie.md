---
title: Agentul observă înainte să ceară voie
date: 2026-07-11
tip: decizie
rezumat: Monitorizarea locală pornea doar după ce serverul confirma înregistrarea, deci un server indisponibil la boot lăsa endpoint-ul complet neobservat. Am inversat ordinea — discul local întâi, rețeaua după — pentru că înregistrarea nu-i dă agentului nimic din ce-i trebuie ca să observe.
tags: [retea, persistenta]
capitol: "3.5"
componente: agent
commits: [edr-agent@d495321, edr-agent@d6b7cb0, edr-agent@ac2a9b7]
teste: [tests/test_agent_startup.py::test_local_monitoring_starts_before_the_server_is_contacted, tests/test_agent_startup.py::test_monitoring_survives_a_server_that_never_answers, tests/test_agent_startup.py::test_startup_event_is_queued_before_the_server_is_reachable, tests/test_agent_startup.py::test_keeps_retrying_past_the_warning_threshold, tests/test_config_loader.py::test_default_config_path_is_independent_of_working_directory]
status: rezolvat
---

## Context {#context}

Până pe 11 iulie, `run_agent()` avea forma asta:

```python
registered = startup_loop(config, server_url, system_info, stop_event)

if registered:
    event_spool = EventSpool(logger=logger)
    event_dispatcher = EventDispatcher(...)
    event_dispatcher.start()
    file_monitor = start_file_monitoring(...)

    heartbeat_loop(...)
```

Tot ce e local — coada pe disc, firul de livrare, observatorul de fișiere — stătea
înăuntrul lui `if registered`. Citită ca propoziție: **agentul supraveghează
endpoint-ul dacă și numai dacă serverul a confirmat că-l cunoaște.**

Iar `startup_loop` renunța după 15 încercări. Cu backoff-ul de startup (bază 5s,
plafon 60s) asta înseamnă în jur de unsprezece minute de reîncercări, după care
funcția întorcea `False`, `run_agent` sărea peste tot, iar procesul se termina.
Server indisponibil la pornire → agentul insistă unsprezece minute → iese → nu mai
rămâne nimeni pe endpoint care să se răzgândească.

Scenariul nu e exotic. Revine curentul într-o clădire și toate stațiile pornesc
odată, în timp ce serverul e și el în boot sau e o mașină virtuală care pornește
mai târziu. Se repornește infrastructura. Agentul e instalat ca serviciu pe o
mașină care pornește înaintea segmentului de rețea care duce la server. În toate,
agentul pornește primul și moare înainte să apuce serverul să existe.

Același scenariu scosese la iveală și altceva, reparat în același commit:
`CONFIG_PATH` era `Path("config.json")`, adică relativ la directorul de lucru. Un
agent pornit de mână, din folderul lui, îl găsea. Un agent pornit de managerul de
servicii, cu alt director de lucru, nu. Codul nu presupunea doar că serverul e
disponibil; presupunea și că cineva l-a lansat cu mâna.

## Forța {#forta}

**Monitorizarea locală nu depinde de nimic din afara mașinii.** `watchdog` peste
niște directoare, SQLite peste un fișier local. Niciuna dintre operațiile astea nu
atinge rețeaua. Și totuși erau condiționate de ea.

**Fereastra de după boot nu e o fereastră oarecare.** Atunci pornesc serviciile,
atunci rulează sarcinile programate, atunci se declanșează mecanismele de
persistență. Dacă e să fiu orb câteva minute, ăsta e cel mai prost interval în
care să se întâmple, și e exact intervalul pe care îl acopeream cel mai prost.

**Sistemul e gândit pentru medii izolate.** Într-o rețea air-gapped, serverul poate
fi inaccesibil perioade lungi prin proiect, nu din defect. Un agent care are nevoie
de o strângere de mână cu serverul ca să-și facă treaba locală are direcția
dependenței greșită față de mediul în care urmează să ruleze.

**Înregistrarea rămâne obligatorie.** Nu e o opțiune s-o arunc: serverul trebuie să
știe că agentul există ca să-i accepte evenimentele, iar heartbeat-ul presupune un
agent înregistrat. Întrebarea nu era dacă e necesară, ci ce anume are voie să
blocheze.

**Livrarea era deja decuplată de detecție.** Coada persistentă exista de o
săptămână, iar `404` era deja clasificat ca eroare recuperabilă. Fără ele,
„monitorizează întâi" n-ar fi însemnat nimic — aș fi produs evenimente care n-au
unde să se ducă, adică le-aș fi pierdut mai devreme, nu mai târziu.

## Alternative {#alternative}

**Păstrez ordinea și cresc numărul de reîncercări.** Cea mai ieftină schimbare — un
`15` devine `1000`. Respinsă pentru că mută granița fără s-o desființeze. Orice
număr finit e un moment în care endpoint-ul orbește definitiv, iar numărul ar
trebui ales împotriva celei mai lungi indisponibilități plauzibile — care,
într-un mediu izolat, nu are o limită pe care s-o pot scrie.

**Pornesc monitorizarea în paralel cu înregistrarea, pe un fir separat.** Rezolvă
sincronizarea, dar păstrează cuplajul ca presupunere implicită și introduce o
întrebare de ordonare pe care n-o am. Nimic din spool sau din observator nu are
nevoie de rezultatul înregistrării, deci nu e nimic de suprapus: o secvență simplă
ajunge, și e mai ușor de citit decât o cursă pe care aș fi creat-o singur.

**Monitorizare cu tampon în memorie până la înregistrare.** Adică exact designul de
dinainte de coadă. Respinsă pentru că fereastra de boot e fix cea în care e cel mai
probabil ca procesul să se repornească sau mașina să se închidă la loc, deci
tamponul e cel mai probabil să dispară exact când conține ceva.

## Alegerea {#alegerea}

Ordinea se inversează. Ce are nevoie doar de discul local pornește primul; rețeaua
vine după, peste un fundal care observă deja:

```python
event_spool = EventSpool(logger=logger)
event_dispatcher = EventDispatcher(...)
event_spool.enqueue(startup_event_payload)
event_dispatcher.start()
file_monitor = start_file_monitoring(...)

registered = register_agent_with_retry(config, server_url, system_info, stop_event)

if registered:
    heartbeat_loop(...)
```

Motivul pentru care inversarea e posibilă e mai important decât inversarea în
sine: **tot ce-i trebuie monitorizării vine din `config.json`** — `agent_id`,
directoarele urmărite, calea cozii. Înregistrarea nu-i dă agentului nimic din ce
are nevoie ca să observe. Îi dă *serverului* dreptul să accepte ce a observat.
Vechea ordine confunda cele două, și de-aia blocul greșit ajunsese înăuntrul
condiției greșite.

Evenimentele produse înainte de înregistrare intră în coadă, dispatcher-ul încearcă
să le livreze, serverul răspunde `404`, iar `AgentNotRegisteredError` e deja
clasificat ca temporar — deci rămân pe disc. În momentul în care înregistrarea
reușește, coada se golește singură, fără ca cineva s-o anunțe. Interblocarea asta
nu e nouă, e
[coada persistentă]({{ '/intrari/2026-07-12-coada-persistenta-de-evenimente/' | relative_url }})
de dinainte; reordonarea e primul lucru pe care îl plătește.

**Evenimentul de startup a intrat și el în coadă**, în loc să fie trimis direct.
Are două efecte. Supraviețuiește serverului picat la boot — adică exact momentul pe
care îl descrie. Și elimină un duplicat: `register_agent_with_retry` e apelată și
din `heartbeat_loop`, la directiva `reregister` sau la un `404`, iar vechiul
`startup_loop` retrimitea payload-ul de startup la fiecare dintre ele. Funcția a
fost redenumită ca să spună ce face acum: înregistrează, nu anunță.

Două corecții din ziua următoare completează mecanismul. Dacă spool-ul nu poate fi
deschis, evenimentul de startup se trimite direct după înregistrare — altfel s-ar
fi pierdut cu totul, fiindcă `enqueue`-ul trăia doar pe ramura cu coadă validă. Și
payload-ul a primit `occurred_at`, pentru că un eveniment livrat din coadă poate
ajunge mult mai târziu decât momentul pe care îl descrie; fără el, serverul ar fi
datat pornirea la ora recepției.

## Costul acceptat {#cost}

**Coada crește exact când nimic n-o golește.** Între pornirea observatorului și
înregistrarea reușită, evenimentele se adună pentru un `agent_id` pe care serverul
nu-l cunoaște. Sunt păstrate corect, dar plafonul de 10.000 și eliminarea FIFO se
aplică la fel: o indisponibilitate suficient de lungă la boot taie tăcut începutul
poveștii de boot, adică fix partea în care s-ar vedea cum a intrat ceva.

**Momentul pornirii nu mai e momentul raportării.** Evenimentul de startup trece
prin coadă, deci ora la care ajunge nu spune nimic despre ora la care a pornit
agentul. `occurred_at` acoperă cazul, dar numai pentru cine îl citește: orice
corelare făcută pe ora recepției e greșită pentru livrările întârziate, iar
livrările întârziate sunt cele care vin din incidentele care contează.

**Dacă spool-ul nu se deschide, nu se monitorizează nimic — și nu se vede.**
`file_monitor` se construiește doar pe ramura cu `event_spool is not None`. Un disc
plin, o permisiune lipsă sau un fișier de bază de date blocat lasă endpoint-ul
nesupravegheat, în timp ce agentul continuă să trimită heartbeat-uri și apare
`online` în consolă. E o degradare mai proastă decât cea veche: aceea omora
agentul, adică se vedea. Asta lasă în urmă un agent care arată perfect sănătos și
nu observă nimic. Starea derivată din `last_seen` răspunde la „e viu", nu la „face
ce trebuie", și
[am aflat asta cu zece zile înainte]({{ '/intrari/2026-07-01-agentul-mort-ramanea-active/' | relative_url }}),
din direcția cealaltă.

**Decizia a stat trei săptămâni implementată pe jumătate.** Intenția era ca
înregistrarea să nu mai renunțe niciodată — comentariul commit-ului o spune,
parametrul a fost redenumit din `max_retries` în `warn_after_retries`, nivelul de
log a coborât din `critical` în `warning`, iar textul mesajului a devenit
„Continuing startup loop." Ce n-a fost șters e instrucțiunea de sub el:

```python
if backoff.consecutive_failures == warn_after_retries:
    logger.warning(
        f"Agent failed to register after {warn_after_retries} attempts. "
        "Possible misconfiguration. Continuing startup loop."
    )
    return False
```

Deci agentul tot renunța la a 15-a încercare, tot sărea peste `heartbeat_loop`, tot
cădea în blocul final care oprește observatorul, oprește dispatcher-ul și închide
coada. Ce schimbase reordonarea era doar conținutul celor unsprezece minute: din
unsprezece minute de orbire urmate de moarte, în unsprezece minute de observație
scrisă pe disc, urmate de aceeași moarte. Câștigul era real — evenimentele alea
supraviețuiesc și se livrează la următoarea pornire reușită — dar garanția pentru
care făcusem schimbarea, aceea că un endpoint izolat observă *oricum*, ținea
unsprezece minute și pe urmă cădea.

`return`-ul a fost șters pe 3 august, împreună cu redenumirea constantei în
`_STARTUP_WARN_AFTER_RETRIES` și cu un docstring care spune acum explicit că pragul
nu limitează reîncercările. Singurele ieșiri rămase sunt `FatalTransportError` — o
configurare sau o autentificare greșită, pe care reîncercarea n-o poate repara — și
`stop_event`, adică o oprire cerută.

**Ordonarea a căpătat test abia la sfârșit.** Testele venite cu commit-ul original
acopereau ancorarea căii de configurare, nu secvența din `run_agent`: nimic nu
verifica nici că monitorizarea pornește înaintea înregistrării, nici că un server
indisponibil lasă agentul în viață. A doua ar fi prins `return`-ul de mai sus din
prima zi. Golul s-a închis odată cu el —
`test_local_monitoring_starts_before_the_server_is_contacted` și
`test_monitoring_survives_a_server_that_never_answers` sunt exact propozițiile pe
care decizia le afirma și pe care nu le verifica nimeni.

## Ce am învățat {#invatat}

**Ordinea de inițializare e o afirmație despre dependențe.** `if registered:` în
jurul monitorizării nu era un detaliu de programare a pornirii; era propoziția
„observația locală depinde de o confirmare de la distanță", care e falsă. Și n-a
decis-o nimeni — a rezultat din ordinea în care au fost construite funcționalitățile.
Codul capătă dependențe din accidentul cronologiei, iar apoi ele stau acolo arătând
deliberat.

**A avea nevoie de ceva și a cere voie sunt lucruri diferite.** Înregistrarea era
necesară — pentru server. Nimic din ea nu era necesar pentru a observa. Construirea
secvenței în jurul a cine trebuie întrebat, în loc de cine de ce are nevoie, e
ce a băgat blocul greșit sub condiția greșită. Întrebarea care desface nodul e
mereu aceeași: *ce anume din pasul ăsta îmi lipsește dacă îl sar?*

**O degradare logată nu e o degradare raportată.** Ramura care pierde spool-ul
scrie un `error` în logul local și merge mai departe. Din afară, agentul e sănătos.
Logurile locale se citesc după ce deja bănuiești ceva, deci un mod de eșec vizibil
doar acolo e, practic, invizibil până când nu mai contează.

**Un mesaj care spune ce voiai să faci nu verifică ce ai făcut.** `return False` a
supraviețuit unei redenumiri de parametru, unei schimbări de nivel de log, unui
mesaj rescris ca să spună exact contrariul și unei descrieri de commit care
afirmă comportamentul opus. Tot ce era în jurul instrucțiunii s-a schimbat ca să se
potrivească intenției noi; instrucțiunea nu. Nimic n-o testa, deci nimic n-a
obiectat — iar eu am recitit blocul de destule ori, convins că îl citesc pe cel
nou, pentru că numele și textul din jur îmi confirmau ce credeam. Ce a scos-o la
iveală, trei săptămâni mai târziu, n-a fost un simptom în producție. A fost
scrierea intrării ăsteia, adică singurul moment în care am fost obligat să
formulez în cuvinte ce credeam că face codul.
