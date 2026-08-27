---
title: Un 401 nu e un payload stricat
date: 2026-08-23
tip: decizie
rezumat: Orice 4xx în afară de 404, 408 și 429 era eroare fatală, iar o eroare fatală trece prin aceeași metodă ca un succes — evenimentul dispare din coadă. Pentru 422 e corect. Pentru 401, spool-ul construit ca să garanteze at-least-once ar fi devenit at-most-once fix când ceva era stricat.
tags: [identitate, contract, retea, persistenta]
capitol: "2.8"
componente: ambele
commits: [edr-agent@045100b, edr-server@5f40087, edr-server@1011351, edr-agent@b4b695c, edr-agent@710b9ee, edr-agent@9f70450, edr-server@cd85bab, edr-agent@a88f596]
teste: [tests/test_api_authentication.py::test_401_is_not_a_fatal_error, tests/test_api_authentication.py::test_422_is_still_fatal, tests/test_api_authentication.py::test_authentication_failure_keeps_the_event_queued, tests/test_api_authentication.py::test_a_401_does_not_stop_the_heartbeat_loop, tests/test_api_authentication.py::test_a_name_conflict_keeps_the_agent_retrying, tests/test_api_authentication.py::test_the_dispatcher_picks_up_a_credential_fixed_on_disk, tests/test_api_authentication.py::test_a_key_that_could_not_be_written_keeps_the_secret, app/tests/test_api_authentication.py::test_an_agent_cannot_write_events_in_the_name_of_another, app/tests/test_api_authentication.py::test_identity_is_checked_before_the_agent_is_looked_up, app/tests/test_api_authentication.py::test_the_store_keeps_a_fingerprint_not_the_key, app/tests/test_api_authentication.py::test_the_public_agent_list_never_carries_key_material]
status: partial
---

## Context {#context}

Până acum, orice proces care putea deschide un socket către server putea scrie în
numele oricărui agent. `POST /api/events` cerea doar ca `agent_id`-ul din corp să
existe în registru, iar lista de agenți e o rută publică — deci și valorile
acceptate erau publice.

Registrul și
[detecția de repornire]({{ '/intrari/2026-07-13-repornirea-se-observa-nu-se-deduce/' | relative_url }})
se sprijină amândouă pe presupunerea că un eveniment vine chiar de la mașina pe
care o numește. Nimic nu verifica presupunerea.

Că trebuie autentificare era evident. Partea care a cerut o decizie a fost ce
face agentul cu un refuz.

## Forța {#forta}

**Reclasificarea e miezul, nu antetul.** `handle_response` trata orice 4xx în
afară de 404, 408 și 429 drept `FatalTransportError`, iar `EventDispatcher`
tratează o eroare fatală ca *poison message*: cheamă `mark_sent`, **aceeași
metodă ca la succes**. Din perspectiva cozii, evenimentul a fost livrat. Dispare,
definitiv.

Pentru 422 logica e corectă. Un payload stricat nu devine valid dacă îl mai
trimiți o dată, deci păstrarea lui ar bloca la nesfârșit tot ce vine după el.

Dar 401 era clasificat identic, iar motivul e complet diferit:

> **Un payload invalid e o proprietate a mesajului. Un 401 e o proprietate a
> relației dintre agent și server la momentul cererii.**

Un 401 poate fi adevărat acum și fals peste zece minute, din cauze care n-au
nicio legătură cu evenimentul: o cheie rotită pe care fișierul local n-a apucat
s-o preia, un server repornit cu alt depozit, o greșeală de deploy. Tratând-o pe
a doua ca pe prima, un blip de configurare de cinci minute ar fi șters ireversibil
tot ce era în coadă, câte un eveniment pe rând, cât timp cheia rămânea greșită.
Adică exact
[spool-ul persistent]({{ '/intrari/2026-07-12-coada-persistenta-de-evenimente/' | relative_url }})
construit ca să garanteze at-least-once ar fi devenit at-most-once fix când ceva
era stricat.

**Consecința de securitate e și mai directă.** Dacă spargerea autentificării ar
duce la golirea cozii, atunci pe un endpoint compromis *stricarea cheii devine o
metodă de a face dovezile să dispară de la sine.* Mecanismul care apără sistemul
ar fi devenit unealta împotriva lui.

**Dar nici „mereu temporar" nu era răspunsul.** Dacă 401 ar fi devenit ca 404 —
reîncercare tăcută la nesfârșit — o cheie revocată intenționat n-ar fi anunțat
niciodată că ceva e definitiv stricat. Coada ar fi crescut pe disc fără niciun
semnal, iar mașina ar fi rămas nemonitorizată server-side fără ca cineva să afle.

## Alternative {#alternative}

**Starea de fapt — 401 tratat ca 422.** Respinsă pentru cele două motive de mai
sus: pierdere de dovezi, și o cale prin care atacatorul o provoacă singur.

**401 tratat ca 404 — reîncercare tăcută.** Respinsă pentru că mută eșecul din
„vizibil și greșit" în „invizibil". O coadă care crește fără niciun avertisment e
un mod de eșec mai prost decât unul zgomotos.

**Plafon nou pentru coadă sub eșec de autentificare.** Respins deliberat, și e
aceeași respingere ca prima: orice mecanism care golește coada la refuz de
autentificare e exploatabil de cine poate provoca refuzul.

**Escaladare pe numărul de încercări.** Respinsă pentru că încercările sunt rărite
de backoff exponențial, deci contorul descrie retry-urile, nu durata. E aceeași
distincție pe care serverul o face deja între `failed_attempts` și
`missed_heartbeats`.

**O cheie comună pe tot parcul.** Respinsă: compromiterea unei singure mașini dă
tot, iar revocarea înseamnă reconfigurarea tuturor.

**Cheia ținută pe înregistrarea agentului.** Respinsă pentru că `GET /api/agents`
e publică în acest pas, deci cheia ar fi ajuns direct în răspunsul ei. Depozit
separat înseamnă că gaura de citire rămâne o problemă de confidențialitate a
inventarului, nu una de divulgare a credentialelor.

**Depozit de chei volatil, ca `agents_store`.** Respins pentru că registrul e
volatil *deliberat* — un restart îl golește și agenții se re-înregistrează singuri
prin directiva `reregister`. Dar agentul își consumă secretul de înrolare după
prima folosire reușită, deci un restart care ar șterge și cheile ar fi lăsat tot
parcul blocat afară, cu evenimentele adunându-se în spool, până la o reînrolare
manuală pe fiecare mașină.

## Alegerea {#alegerea}

**401 primește `AuthenticationError`, 403 primește `IdentityMismatchError`,
niciuna descinzând din `FatalTransportError`.** Recuperarea aleasă e *păstrează și
escaladează în timp*:

| cod | ce înseamnă | ce face agentul |
|---|---|---|
| 401 | identitate nerecunoscută | păstrează coada, reîncearcă, alarmă pe durată |
| 403 | identitate acceptată, acțiune refuzată | la fel |
| 409 | conflict de nume la înregistrare | la fel, cu ERROR de la prima apariție |
| 422 | acest mesaj e stricat | abandonează evenimentul, oprește bucla |

**Regresia e fixată printr-un test pe ierarhia de excepții, nu pe flux.**
`EventDispatcher` citește chiar ierarhia, iar o refactorizare de peste șase luni
ar putea lăsa un test de flux verde în timp ce reclasifică excepția.

**Alarma escaladează pe timp scurs, nu pe încercări.** Treizeci de secunde de 401
înseamnă o rotație prinsă la mijloc, care se repară singură. Treizeci de minute
înseamnă ceva ce nu se repară fără om. Amândouă arată identic la nivel de cerere;
doar durata le desparte. Ceasul e monoton, deci un ceas corectat de NTP nu poate
nici declanșa o alarmă instantaneu, nici amâna una la nesfârșit. Alarma raportează
și adâncimea cozii, calculată leneș, doar când chiar se emite: *autentificarea
eșuează de 32 de minute* e o informație de operare, dar *4.200 de evenimente
așteaptă pe disc* e cea care spune cât se pierde dacă endpoint-ul e reinstalat
înainte de reparație.

**Nici bucla de heartbeat, nici înregistrarea nu se mai opresc la un refuz.**
Ramura fatală făcea `return`, adică niciun heartbeat până la repornirea
procesului: o rotație de cheie ar fi scos definitiv endpoint-ul din consolă, iar
operatorul ar fi văzut o mașină moartă în loc de o credențială greșită. Iar
`run_agent` pornește spool-ul și file monitor-ul **înainte** de înregistrare, deci
un abandon acolo ar fi oprit colectarea locală din cauza unei chei greșite.

Pe server, trei părți, în ordinea importanței:

1. **Fiecare agent are cheia lui**, nu una comună pe parc.
2. **Serverul verifică faptul că `agent_id`-ul din corp corespunde cheii
   folosite.** E pasul cel mai ușor de uitat și fără de care restul nu valorează
   mare lucru: altfel toți agenții sunt autentificați și oricare poate scrie în
   numele oricui.
3. **Rutele de scriere sunt separate de cele de citire.** Cheia deschide
   `POST /api/events` și heartbeat-ul agentului ei, nimic altceva.

**Cheile se țin hash-uite.** Depozitul păstrează SHA-256, niciodată cheia.
Verificarea nu are nevoie de valoarea originală: se calculează amprenta celei
prezentate și se caută în dicționar, deci **căutarea însăși e comparația**. Nu
există o buclă care compară secretul candidat cu fiecare cheie stocată, deci nu se
scurge nimic prin durata ei.

**Ordinea verificărilor pe `/api/events`: identitate, apoi legarea cu corpul, abia
apoi existența agentului.** Dacă 404 ar veni înaintea lui 403, diferența dintre
404 și 200 ar spune unui agent autentificat care `agent_id`-uri există în parc —
adică o rută de enumerare oferită tocmai celui care nu are voie să știe.

## Costul acceptat {#cost}

**Coada e nemărginită sub eșec de autentificare, prin proiect.** O mașină care nu
se poate autentifica ore în șir umple discul. E compromisul ales conștient: un
disc plin e un incident de operare, o coadă golită e pierdere de dovezi.

**Cheia nu e criptată la repaus și nu e legată de mașină.** Un administrator local
o poate citi — dar el poate oricum citi memoria procesului, unde cheia trebuie să
existe ca să poată fi trimisă. Granița declarată e utilizatorul local obișnuit, nu
administratorul.

**Rutele de citire rămân neautentificate, deliberat.** `GET /api/agents` și
`GET /api/events` nu cer nicio credențială: analistul nu are încă un secret
propriu. Ambele rute poartă comentarii care numesc gaura, iar `AUTH.md` o descrie
în secțiunea de limitări. Statusul intrării e `partial` din acest motiv.

**Secretul de înrolare e comun pe parc.** Ștergerea lui după prima folosire
reușită nu e igienă, e reducerea ferestrei de expunere de la permanent la durata
instalării: cât timp există acolo, e o capabilitate permanentă de a cere o cheie
nouă pentru orice `agent_id`.

**Al doilea document de contract comis identic în ambele repo-uri.** `AUTH.md`
plătește a doua oară costul acceptat pe
[6 august]({{ '/intrari/2026-08-06-redenumirea-pica-in-repo-ul-care-a-facut-o/' | relative_url }}),
inclusiv obligația de a-l sincroniza când o parte se răzgândește — ceea ce s-a și
întâmplat, la rândul de 409.

**Trei defecte descoperite după, la rulare manuală, nu de suită.** Toate trei sunt
aceeași formă: mecanismul de recuperare exista, dar o cale de cod îl anula.

- Credențialele se citeau o singură dată, la pornire. Agentul nu abandonează la un
  401 tocmai ca operatorul să poată repara problema — dar când reparația **este**
  punerea fișierului la locul lui, procesul n-o observa niciodată. Recitirea se
  face acum doar după un refuz, singura situație în care discul are ceva de spus
  în plus față de memorie.
- `adopt_agent_key` întorcea același lucru și când cheia ajungea pe disc, și când
  scrierea eșua, deci secretul de înrolare se consuma oricum. La repornire agentul
  n-avea nici cheie, nici secret, iar reînrolarea promisă de log era imposibilă.
- Un 409 clasificat ca fatal oprea file monitor-ul și spool-ul. **O coliziune de
  nume oprea colectarea pe o mașină perfect sănătoasă, care dispărea complet din
  consolă** — iar pentru un EDR, tăcerea totală e cel mai prost simptom: nu se
  distinge de un endpoint oprit sau compromis.

## Ce am învățat {#invatat}

**Clasificarea după clasa codului HTTP ascunde exact distincția care contează.**
4xx înseamnă „e vina clientului", dar sub eticheta asta încap două lucruri
incompatibile: o proprietate a *mesajului*, care nu se schimbă niciodată, și o
proprietate a *relației*, care se schimbă singură. Un `if` care le tratează la fel
e corect pentru unul dintre ele și distructiv pentru celălalt.

**Un mecanism de securitate al cărui eșec distruge dovezi e o unealtă împotriva
sistemului.** Întrebarea utilă la orice mecanism nou nu e doar „ce apără?", ci
„ce se întâmplă când cineva îl face să eșueze intenționat?". Aici răspunsul,
înainte de schimbare, era „coada se golește singură" — adică fix ce ar fi vrut
atacatorul.

**Testul care contează e pe ierarhie, nu pe flux.** Comportamentul corect
al dispatcher-ului nu era codificat nicăieri într-o formă pe care o refactorizare
să nu o poată ocoli tăcut. Un test de flux ar fi rămas verde; unul care afirmă că
`AuthenticationError` **nu** e `FatalTransportError` nu poate.

**Autentificarea adăugată peste o coadă durabilă nu e o schimbare de transport.**
E o schimbare a înțelesului cuvântului „livrat" — și fiecare loc care confundă
„am terminat cu acest mesaj" cu „mesajul a ajuns" devine, în ziua în care apare
autentificarea, o cale de pierdere de date.
