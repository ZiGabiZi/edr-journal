---
title: Cum se desincronizează un parc de agenți fără coordonare centrală
date: 2026-06-26
tip: decizie
rezumat: Toți agenții reîncercau la exact același interval, deci revenirea serverului îi aducea înapoi în același val. Am derivat faza de reconectare a fiecărui agent din hash-ul identității lui, ca distribuția să apară fără niciun mesaj schimbat între ei.
tags: [retea, identitate, concurenta]
capitol: "3.5"
componente: agent
commits: [edr-agent@69ccc1e, edr-agent@8e10ff8]
teste: []
status: partial
---

## Context {#context}

Bucla agentului avea, până în 26 iunie, exact forma pe care o scrie oricine prima
dată:

```python
while True:
    try:
        send_event(server_url, build_heartbeat_event_payload(config))
    except TransportError as error:
        logger.error(f"Heartbeat transport error: {error}")

    time.sleep(heartbeat_interval_seconds)
```

Comportamentul la server indisponibil e vizibil în cod: se loghează eroarea și se
reîncearcă peste `heartbeat_interval_seconds`. La nesfârșit, la același interval.

Pe o singură mașină de test nu se vede nimic în neregulă. Agentul supraviețuiește
căderii serverului, revine singur când serverul revine, nu pierde heartbeat-uri
decât pe durata indisponibilității. Toate obiectivele par atinse.

Problema nu e a unui agent. E a parcului. `heartbeat_interval_seconds` e citit
din `config.json`, iar `config.json` e același fișier distribuit pe toate
endpoint-urile — 10 secunde peste tot. Dacă serverul cade, fiecare agent din
parc intră în același ciclu, cu aceeași perioadă. Iar căderea serverului e
evenimentul care îi sincronizează: până atunci fazele lor erau împrăștiate de
momentele diferite în care fuseseră porniți, dar un server care nu răspunde
transformă un parc împrăștiat într-un parc care bate la unison.

Mai era un caz, în aceeași familie, pe care codul nu-l trata deloc. Faza de
pornire — `check_server_health`, `register_agent`, evenimentul de startup — nu
avea nicio reîncercare. `TransportError` urca până la handler-ul din `run_agent`,
se loga, iar funcția se termina. Un agent pornit înainte de server, sau în timpul
unei reporniri de infrastructură, pur și simplu murea. Ceea ce înseamnă că
scenariul „revine curentul într-o clădire" producea simultan un parc de agenți
morți și, la repornirea lor manuală, un parc de agenți perfect sincronizați.

## Forța {#forta}

**Reîncercarea trebuie să fie insistentă.** Un agent care renunță e un endpoint
orb, iar un endpoint orb nu e o degradare de serviciu — e exact starea pe care
un atacator o vrea. Deci varianta „încearcă de trei ori și ieși" nu e pe masă.

**Reîncercarea insistentă a tuturor amplifică exact căderea pe care o traversează.**
Serverul care revine după o indisponibilitate e cea mai fragilă versiune a lui:
cache-uri reci, conexiuni de refăcut, store de agenți gol. Momentul în care
primește tot parcul deodată e fix momentul în care suportă cel mai puțin.
Reîncercarea sincronizată transformă o cădere scurtă într-una lungă.

**Într-un EDR, valul e el însuși un semnal fals.** Asta e partea care schimbă
calculul față de un serviciu obișnuit. Un vârf brusc de trafic de la sute de
endpoint-uri către serverul central e, ca formă, indistinct de un beacon
coordonat. Un sistem care își declanșează singur propriile euristici nu produce
doar încărcare — produce zgomot exact în canalul pe care mizează. Costul nu e
performanța, e credibilitatea semnalului.

**Nu am pe cine să întreb.** Sistemul e gândit pentru medii izolate, deci nu
există un serviciu de coordonare, un broker sau o autoritate care să împartă
sloturi. Și chiar dacă serverul central ar putea distribui ferestre de
reconectare, momentul în care ar fi nevoie de ele e fix momentul în care serverul
nu răspunde. Orice soluție care cere coordonare e circulară.

**Ce am totuși: fiecare agent știe cine e.** `agent_id` există înainte de orice
mesaj, e unic în parc și e stabil între reporniri. E singura informație
distribuită de care dispun fără să comunic.

## Alternative {#alternative}

**Backoff exponențial fără jitter.** Rezolvă supraîncărcarea susținută:
intervalele cresc, deci traficul total scade. Am respins-o pentru că nu atinge
sincronizarea, ci o adâncește. Agenții care au căzut împreună au același
`consecutive_failures`, deci urcă pe aceeași scară — 10s, 20s, 40s, 80s — și
lovesc împreună la fiecare treaptă. Valurile devin mai rare și mai înalte, ceea
ce e mai rău: un vârf de 500 de cereri simultane e mai greu de absorbit decât
aceleași cereri întinse pe un interval, chiar dacă media orară arată mai bine.

**Jitter pur aleatoriu (`random.uniform`) peste backoff.** Ăsta e răspunsul
standard, e ceea ce recomandă toată literatura de retry, și — spun asta explicit
— ar fi funcționat. Nu l-am respins pentru că ar fi greșit. L-am respins pentru
că îmi dă o garanție statistică acolo unde puteam obține una structurală: cu
jitter pur, separarea a doi agenți e un rezultat al fiecărei extrageri, deci
poate să nu se producă într-o rundă anume, mai ales pe un parc mic. Și pentru că
un timp de reîncercare complet aleatoriu nu se poate reproduce: într-o rețea
izolată, unde depanarea înseamnă un log citit pe loc, capacitatea de a calcula
dinainte când urma să reîncerce un anumit agent valorează mai mult decât într-un
mediu unde poți atașa un debugger prin rețea. Secundar, și fără să insist —
`random` e sămânțat din entropia sistemului la import, ceea ce e în regulă în
mod normal, dar preferam ca o proprietate cu miză de securitate să nu depindă de
starea RNG-ului de pe fiecare endpoint clonat dintr-o imagine comună.

**Sloturi atribuite de server la înregistrare.** Serverul dă fiecărui agent o
fereastră de reconectare. Corect ca distribuție, dar cere ca serverul să fi fost
disponibil ca să poată spune ceva despre indisponibilitatea lui viitoare, și cere
un câmp nou în protocol. Circular, cum ziceam.

**Hash pe hostname sau pe adresa IP.** Aceeași idee ca cea aleasă, cu altă sursă
de unicitate. Respinsă pentru că sursa e proastă: IP-ul se schimbă la reînnoirea
DHCP, deci faza agentului s-ar muta fără ca agentul să se schimbe, iar hostname-ul
nu e garantat unic într-un parc clonat. `agent_id` e deja cheia de identitate pe
care se face înregistrarea; folosirea altceva ar fi introdus o a doua noțiune de
„cine e agentul ăsta".

## Alegerea {#alegerea}

Fiecare agent își derivă o fază de reconectare proprie din hash-ul propriei
identități, și o combină cu o componentă aleatorie. Delay-ul e:

```
W = min(W_max, W_base × 2ⁿ) × (1 + φ_agent + ε_random)

    φ_agent  ∈ [0, jitter_ratio/2)   — determinist, derivat din agent_id
    ε_random ∈ [0, jitter_ratio/2)   — extras la fiecare tentativă
```

Faza deterministă e o funcție pură de `agent_id`:

```python
def _compute_agent_phase(agent_id: str, jitter_ratio: float) -> float:
    digest = hashlib.sha256(agent_id.encode("utf-8")).digest()
    agent_int = int.from_bytes(digest[:4], byteorder="big")
    return (agent_int % 10_000) / 10_000.0 * (jitter_ratio / 2.0)
```

SHA-256 face aici o singură treabă, dar esențială: decorelează. `endpoint-01` și
`endpoint-02` sunt vecine ca șiruri și complet nelegate ca faze. Fără difuzia
hash-ului, un parc numerotat secvențial ar fi produs faze secvențiale, adică
exact structura pe care încerc s-o distrug.

Cele două componente au deliberat aceeași greutate — fiecare `jitter_ratio/2` —
pentru că rezolvă probleme diferite și niciuna nu e suficientă:

- **Deterministul garantează separarea.** Doi agenți cu ID-uri distincte au faze
  distincte în fiecare rundă, nu în medie. Separarea nu se re-extrage și nu se
  poate anula prin ghinion.
- **Aleatoriul garantează că separarea nu e permanent greșită.** Faza cade în
  10.000 de intervale, deci coliziunile există: la vreo 120 de agenți, șansa ca
  două ID-uri să pice în același interval trece de 50%. Dacă jitter-ul ar fi doar
  determinist, perechea aia ar rămâne lipită la fiecare reîncercare, la fiecare
  cădere, pentru totdeauna. Componenta aleatorie face ca o coliziune de fază să
  fie un incident de o rundă, nu o proprietate a parcului.

Pe scurt: partea deterministă separă, partea aleatorie dezleagă.

Mecanismul e împachetat într-un `HeartbeatBackoffController` care ține starea
(`consecutive_failures`, `total_failures`) și expune două verbe — `record_success()`
și `record_failure()`, al doilea returnând delay-ul. Faza se calculează o singură
dată, în `__init__`.

Sunt **două profiluri de backoff**, nu unul. Bucla de heartbeat pornește de la
intervalul din configurație și urcă până la 300 de secunde. Faza de startup
pornește de la 5 secunde și se plafonează la 60. Diferența e intenționată:
înregistrarea e condiția de existență a agentului, iar la pornire e plauzibil să
existe un operator care așteaptă activ. Un agent care se înregistrează abia peste
cinci minute e, practic, un agent care n-a pornit.

Faza de startup a devenit ea însăși o buclă cu backoff, deci scenariul „agentul
pornește înaintea serverului" nu mai omoară agentul:

```python
while not stop_event.is_set():
    try:
        check_server_health(server_url)
        register_agent(server_url, build_agent_registration_payload(config, system_info))
        send_event(server_url, build_startup_event_payload(config))
        backoff.record_success()
        return True
    except TransportError as error:
        logger.error(f"Startup connection failed: {error}")
        stop_event.wait(timeout=backoff.record_failure())
```

Ultima linie e a doua jumătate a deciziei, și n-ar fi existat fără prima.
Acceptând delay-uri de până la 300 de secunde, `time.sleep()` devine inacceptabil:
un `Ctrl+C` ar fi rămas neobservat cinci minute, iar un `SIGTERM` de la managerul
de servicii ar fi expirat în timeout și ar fi terminat procesul brutal — adică
agentul ar fi apărut ca oprit anormal exact atunci când era oprit corect.
`stop_event.wait(timeout=delay)` are aceeași semantică în regim normal, dar se
trezește imediat la cerere de oprire. Backoff-ul lung e sustenabil doar pentru că
așteptarea e întreruptibilă.

## Costul acceptat {#cost}

**Jitter-ul e doar în sus.** Factorul e `(1 + φ + ε)`, deci întotdeauna
supraunitar. Fiecare agent așteaptă cel puțin delay-ul nominal, în medie cu 10%
mai mult. Am ales asta conștient — un heartbeat trimis mai devreme decât
intervalul nu ajută pe nimeni, iar o reîncercare mai devreme se apropie de exact
comportamentul de care fug. Consecința e o abatere tăcută între ce scrie în
configurație și ce se întâmplă: la un plafon declarat de 300 de secunde, așteptarea
reală se plimbă între 250 și 300, și niciun `heartbeat_interval_seconds` nu e
respectat exact.

**Dispersia e mică exact acolo unde valul e cel mai probabil.** Cu
`jitter_ratio = 0.20` și interval de 10 secunde, prima reîncercare a întregului
parc se împrăștie pe 2 secunde. Pentru 500 de agenți, asta înseamnă 250 de cereri
pe secundă — nu mai e un zid, dar nu e nici o distribuție. Abia după câteva
trepte lucrurile devin confortabile: la plafon, aceiași 500 de agenți se întind
pe 50 de secunde, adică 10 cereri pe secundă. Protecția reală vine din creșterea
exponențială; jitter-ul doar netezește. Am lăsat raportul la 20% pentru că o
valoare mai mare ar fi deformat vizibil intervalul de heartbeat în regim normal,
dar asta înseamnă că primul val de după o cădere rămâne cel mai brutal, și e fix
valul care lovește serverul cel mai puțin pregătit.

**Bucla fericită nu are jitter deloc.** La succes se așteaptă
`heartbeat_interval_seconds` curat. Parcul rămâne împrăștiat doar dacă ceva l-a
împrăștiat: agenții ies dintr-o cădere la momente diferite tocmai pentru că
reîncercările lor au fost distribuite, și moștenesc distribuția aia în regim
normal. Dar orice mecanism care îi aliniază în afara unei căderi — o instalare
simultană pe tot parcul, o repornire coordonată — produce un parc sincronizat
care va rămâne sincronizat, pentru că bucla normală n-are nicio forță proprie de
desincronizare. Mecanismul apără împotriva valului de la revenire, nu împotriva
sincronizării în sine.

**Plafonul a fost, trei zile, o minciună.** În forma inițială plafonam întâi și
aplicam jitter-ul după:

```python
capped_delay = min(max_delay, raw_delay)
return capped_delay * (1.0 + total_jitter)
```

Ceea ce înseamnă că `max_delay = 300` producea, la plafon, până la 360 de
secunde. Îmi scrisesem singur în docstring `300s–360s` la ultima treaptă și
citisem rândul de zeci de ori fără să văd contradicția cu cuvântul „plafon" de
două rânduri mai sus. Corectat în [8e10ff8](https://github.com/ZiGabiZi/edr-agent/commit/8e10ff8)
prin împărțirea plafonului înainte de comparație (`max_delay / (1 + jitter_ratio)`),
astfel încât rezultatul final să respecte limita declarată. Tot acolo am mutat
calculul SHA-256 în constructor — se refăcea la fiecare eșec, ceea ce e neglijabil
ca cost, dar recalcula o constantă.

**Nu am test de regresie.** `teste` e gol, și de-asta intrarea e `partial`.
Verificarea e deocamdată analitică plus observație pe două instanțe locale, ceea
ce e insuficient pentru exact proprietatea care contează. Testele care lipsesc
sunt însă evidente și ieftine, ceea ce le face mai degrabă o datorie decât o
problemă deschisă: că delay-ul nu depășește niciodată `max_delay` pentru niciun
număr de eșecuri (invariantul spart mai sus, care ar fi fost prins din prima), că
faza e stabilă pentru același `agent_id` între instanțe, și că fazele a câteva mii
de ID-uri sintetice acoperă uniform intervalul.

## Ce am învățat {#invatat}

**Identitatea e o sursă de coordonare.** Într-un sistem fără coordonator, ceea ce
au agenții în comun nu e un canal, e faptul că fiecare știe cine e și că nimeni
altcineva nu e el. Un hash peste identitate transformă unicitatea în distribuție,
cu zero mesaje schimbate. E aceeași observație pe care o făcusem despre cheia de
idempotență a evenimentelor, din altă direcție: proprietățile utile ale unui
sistem distribuit se obțin mai des din identități bine alese decât din protocol
în plus.

**Determinismul și aleatoriul nu sunt alternative, sunt garanții complementare.**
Determinismul îți dă separare care nu se poate anula prin ghinion; aleatoriul îți
dă certitudinea că nicio coliziune nu devine permanentă. Cât timp le-am privit ca
pe două opțiuni între care trebuie să aleg, ambele păreau insuficiente — și
ambele chiar erau.

**Ordinea dintre plafonare și jitter e semantică, nu stilistică.** `min()` urmat
de o înmulțire cu ceva supraunitar nu produce un plafon, produce o sugestie. Nu
am văzut greșeala recitind codul, pentru că se citea rezonabil; s-ar fi văzut
instantaneu dacă scriam separat invariantul pe care credeam că-l am — *rezultatul
nu depășește niciodată `max_delay`* — pentru că e o propoziție care se verifică
în cinci secunde. Un invariant nescris nu e un invariant, e o speranță.

**Rezistența la cădere se măsoară pe parc, nu pe instanță.** Toate testele mele
manuale de până atunci foloseau un agent și un server, și niciunul n-ar fi putut
arăta problema — nu pentru că erau superficiale, ci pentru că un singur agent nu
poate fi sincronizat cu nimeni. Clasa asta de bug-uri e invizibilă la scara la
care dezvolți și e singura care contează la scara la care rulezi.
