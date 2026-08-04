---
title: De ce serverul nu sună niciodată agentul
date: 2026-06-27
tip: decizie
rezumat: Serverul trebuie să poată cere ceva agentului — un ruleset nou, mai târziu un fișier. Am refuzat orice canal de comandă separat și am pus directiva în răspunsul la heartbeat, adică într-o cerere pe care agentul o făcea oricum și al cărei răspuns îl arunca.
tags: [pdp, retea]
capitol: "3.7"
componente: ambele
commits: [edr-server@7ed592f, edr-agent@91c6b8d]
teste: [app/tests/test_agent_routes_integration.py::test_heartbeat_for_unknown_agent_requests_reregister]
status: partial
---

## Context {#context}

Până pe 27 iunie, heartbeat-ul era un eveniment. Agentul construia un payload cu
`event_type: "heartbeat"` și îl trimitea prin `POST /api/events`, pe aceeași
conductă cu evenimentele de fișier:

```python
def build_heartbeat_event_payload(config):
    return {
        "agent_id": config["agent_id"],
        "event_type": "heartbeat",
        "description": f"Agent heartbeat at {current_time}",
    }
```

Are două consecințe, și a doua e cea care contează.

Prima e murdărie: `events_store` se umplea cu un rând la fiecare zece secunde, per
agent. Evenimentele sunt lucruri care s-au întâmplat pe endpoint și pe care cineva
le va citi într-o investigație; un semn de viață nu e un eveniment de securitate,
e infrastructură. La zece secunde și o sută de endpoint-uri, semnalul dispare sub
propriul zgomot.

A doua e că **răspunsul se arunca**. `POST /api/events` întoarce confirmarea
evenimentului creat, iar agentul o loga și mergea mai departe. Aveam deci, deja
construit, un mecanism prin care fiecare endpoint contacta serverul la interval
fix și primea înapoi un răspuns pe care nu-l folosea nimeni.

Iar sistemul urma să aibă nevoie de direcția inversă. Nu imediat, dar inevitabil:
regulile de detecție trebuie să coboare la agent, iar mai târziu — dacă banda de
incertitudine o cere — serverul trebuie să poată urca o treaptă și să ceară mai
mult despre un fișier anume. Fără un drum de la server la agent, teza nu are cum
să existe.

## Forța {#forta}

**Endpoint-ul nu are voie să asculte.** Un agent care acceptă conexiuni de intrare
e un serviciu în plus pe fiecare mașină pe care ar trebui s-o apere, cu un port
deschis, o suprafață de atac proprie și nevoia de a autentifica cine sună. Într-un
produs de securitate, asta e exact tipul de componentă care ajunge titlu de
buletin.

**Rețeaua e ostilă prin proiect.** Sistemul țintește medii izolate: endpoint-uri
în spatele NAT-ului, segmente fără rutare de intrare, firewall-uri care taie tot
ce nu e inițiat dinăuntru. Orice mecanism în care serverul inițiază contactul
funcționează pe laptopul meu și nu funcționează acolo unde trebuie livrat.

**Serverul e cel care cade.** E singurul punct central, și indisponibilitatea lui e
starea normală, nu excepția — asta e presupunerea din care a ieșit
[coada persistentă]({{ '/intrari/2026-07-12-coada-persistenta-de-evenimente/' | relative_url }}).
Un canal care cere ca serverul să țină ceva deschis către fiecare agent transformă
o cădere de server într-o repornire a întregului parc.

**Comanda trebuie să ajungă previzibil.** Nu instantaneu — previzibil. Dacă
serverul cere un ruleset nou, vreau să pot spune peste cât timp îl are tot parcul.
Un canal care depinde de trafic spontan nu poate promite asta.

**Nu vreau un al doilea ceas.** Am deja o cadență, iar ea e deja dictată central.
Orice mecanism cu ritm propriu ar însemna două perioade de reglat, care se pot
contrazice.

## Alternative {#alternative}

**Serverul deschide o conexiune către agent.** Modelul clasic de C2, și cel mai
prost aici: cere ca fiecare endpoint să asculte pe un port. Respins pentru
suprafața de atac și pentru că nu traversează NAT-ul. Un EDR care își instalează
propriul serviciu de intrare pe toate stațiile a mutat problema, nu a rezolvat-o.

**Conexiune persistentă inițiată de agent — WebSocket sau long-polling.** Rezolvă
direcția: agentul sună, deci NAT-ul nu contează. Respins pentru ce se întâmplă
la cădere. Serverul ar ține o conexiune vie per endpoint, adică stare proporțională
cu parcul, iar la revenirea după o indisponibilitate toți agenții s-ar reconecta
odată — exact
[valul de care mă apăr cu jitter]({{ '/intrari/2026-06-26-desincronizarea-agentilor-fara-coordonare/' | relative_url }}),
dar cu o conexiune în loc de o cerere. Latența câștigată nu compensează
fragilitatea, într-un sistem în care indisponibilitatea lungă e prevăzută.

**Un endpoint separat de comenzi, pe care agentul îl interoghează.** Funcționează,
și e respins pentru risipă: dublează numărul de cereri ca să afle două lucruri
despre care serverul răspunde în același moment. Și introduce al doilea ceas —
dacă cele două cadențe diferă, apar stări în care serverul știe că agentul e viu
dar nu i-a putut spune nimic, sau invers.

**Comenzile călătoresc pe răspunsul la evenimente.** Tentant, pentru că acolo era
deja un răspuns aruncat. Respins pentru că evenimentele sunt în rafale sau absente:
pe o mașină liniștită, un agent poate să nu trimită nimic ore întregi. O comandă
livrată doar când se întâmplă să apară un fișier nou nu are nicio garanție de
timp.

## Alegerea {#alegerea}

Heartbeat-ul își primește endpoint-ul propriu, iar **răspunsul lui devine canalul
de comandă**:

```python
class HeartbeatDirective(BaseModel):
    action: str = "none"                     # "none" | "update_ruleset" | "collect_file"
    ruleset_version: Optional[str] = None
    collect_file_path: Optional[str] = None  # viitor: progressive disclosure
```

Agentul întreabă, serverul răspunde cu ce e de făcut. Nimic nu sună endpoint-ul,
nimic nu ascultă pe el, nu se deschide nicio conexiune în plus și nu apare niciun
al doilea ceas.

Observația care face decizia ieftină e că **nu construiesc un canal, ci încetez să
arunc unul**. Cererea periodică exista deja, cu cadență garantată și cu un răspuns
pe care nimeni nu-l citea. Costul marginal al unui canal de comandă a fost un câmp
în schema răspunsului.

Prima directivă implementată e și cea care demonstrează forma: `reregister`. Dacă
serverul primește un heartbeat de la un `agent_id` pe care nu-l cunoaște — pentru
că a fost repornit și store-ul e în memorie — nu răspunde cu o eroare, ci cu
instrucțiunea de a se reînregistra:

```python
if agent is None:
    return HeartbeatResponse(
        status="unregistered",
        agent_id=agent_id,
        directive=HeartbeatDirective(action="reregister"),
    )
```

Iar agentul o execută în bucla lui, fără intervenție. Un `404` ar fi fost o
constatare; directiva e o reparație. Diferența dintre „nu te cunosc" și „nu te
cunosc, prezintă-te" e tot ce desparte un parc care se vindecă singur după o
repornire de server de unul care cere cuiva să se plimbe pe la stații.

**De ce contează pentru teză.** `collect_file_path` e marcat în schemă, din prima
zi, drept viitorul canal de *progressive disclosure*. Scara de divulgare din
[pagina despre]({{ '/despre/' | relative_url }}) — metadate, apoi hash, apoi
trăsături, apoi conținut — are nevoie de exact un lucru ca să fie mai mult decât o
intenție: un drum pe care serverul poate cere treapta următoare. Ăsta e drumul, și
faptul că trece prin heartbeat îi dă o proprietate pe care un canal dedicat n-ar fi
avut-o: cererea de conținut călătorește pe aceeași sârmă, la aceeași cadență și în
același log ca verificarea de rutină a stării. O escaladare nu e o operație
specială, în afara benzii, pe care cineva ar putea s-o facă discret. E un câmp
într-un mesaj care se repetă de mii de ori pe zi și care se vede în trafic ca orice
altul.

## Costul acceptat {#cost}

**Latența comenzii e cadența heartbeat-ului.** O directivă nu poate ajunge la un
agent mai repede decât următoarea lui bătaie. Azi înseamnă până la zece secunde, cu
o coadă la care nu am ce reproșa. Dar cadența e dictată central prin
`next_heartbeat_seconds`, iar dacă vreodată o urc ca să scad încărcarea, urc în
aceeași mișcare și timpul de reacție al întregului parc. Sunt același buton, și
n-am nicăieri o notă care să spună asta.

**Directiva nu e confirmată.** Serverul o trimite în răspuns și nu află niciodată
dacă a fost executată. Pentru `reregister` gaura nu se vede, pentru că execuția
produce singură dovada: sosește o înregistrare. Pentru `update_ruleset` — și cu
atât mai mult pentru `collect_file` — n-ar mai fi așa. Un canal fără confirmare
poate cere, dar nu poate ști.

**Directiva nu se retransmite.** Trăiește într-un răspuns HTTP; dacă răspunsul se
pierde pe drum, se pierde și ea. Agentul va primi ce spune răspunsul *următoarei*
bătăi, ceea ce e perfect pentru o directivă care descrie o stare dorită
(„ruleset-ul tău ar trebui să fie versiunea N" — repetabilă, idempotentă) și
greșit pentru una imperativă („colectează fișierul ăsta" — care sau ajunge, sau
nu). Schema le amestecă azi pe amândouă sub același câmp `action`, iar distincția
n-o face nimic din cod. E datoria pe care o las scrisă aici, pentru că se va vedea
abia când `collect_file` chiar face ceva.

**O singură directivă per bătaie.** `action` e un șir, nu o listă. Un server care
are două lucruri de spus le spune în două bătăi, iar ordinea dintre ele nu e
exprimată nicăieri.

**A doua acțiune a fost moartă de la naștere.** În commit-ul de pe agent, ramura
`update_ruleset` a intrat greșit indentată — `elif` chemat de `if not registered`,
nu de `if action == ...` — deci nu se putea executa niciodată. A fost corectată în
commit-ul imediat următor, printre alte opt lucruri, și n-a produs nimic în
intervalul ăla pentru un motiv care merită reținut: nimeni nu trimitea încă
`update_ruleset`. Un canal cu un singur verb implementat nu poate să-ți spună că
celelalte sunt stricate.

## Ce am învățat {#invatat}

**Direcția în care se deschide o conexiune e o decizie de securitate, nu una de
transport.** Cine sună pe cine stabilește cine trebuie să asculte, cine trebuie să
autentifice și ce trebuie să lase firewall-ul să treacă. Am ales ca endpoint-ul să
nu asculte niciodată, iar toate restul proprietăților — traversarea NAT-ului,
absența unui port deschis, comportamentul la cădere de server — sunt consecințe ale
acelei alegeri, nu decizii separate.

**Un canal periodic există deja în orice sistem care are heartbeat.** Întrebarea
nu era cum construiesc un drum de la server la agent, ci de ce arunc răspunsul
drumului pe care îl am. Cele mai ieftine mecanisme se obțin observând ce trece deja
prin sistem fără să fie folosit.

**Cadența e un singur buton pentru două lucruri.** Perioada heartbeat-ului
guvernează și cât de repede aflu că un agent a tăcut, și cât de repede pot să-i
spun ceva. Cât timp cele două sunt același număr, orice reglaj făcut pentru unul e
un reglaj nedorit pentru celălalt — și e a doua oară în sistem când o constantă
guvernează două lucruri care n-au cerut asta.

**O cerere fără confirmare e o speranță cu antet HTTP.** Cât timp singura directivă
implementată își producea singură dovada execuției, absența unui mecanism de
confirmare nu se vedea. E exact felul de gol care se descoperă în ziua în care
canalul începe să ceară lucruri care contează — adică în ziua în care începe partea
pentru care există tot sistemul.
