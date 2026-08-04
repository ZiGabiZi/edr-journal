---
title: Un test verde peste un câmp care nu ajungea niciodată
date: 2026-08-03
tip: incident
rezumat: Agentul trimitea `agents_instance_id`, serverul citea `agent_instance_id`. Pydantic aruncă tăcut cheile necunoscute, deci detecția de repornire nu s-a declanșat niciodată în producție — în timp ce testele de pe server o verificau și treceau.
tags: [identitate, observabilitate]
capitol: "3.3"
componente: ambele
commits: [edr-agent@7af36f5]
teste: [tests/test_heartbeat_payload.py::test_payload_carries_instance_id_under_the_key_the_server_reads, tests/test_heartbeat_payload.py::test_payload_has_no_key_the_server_would_silently_drop, tests/test_heartbeat_payload.py::test_loop_sends_incrementing_sequence_with_instance_id]
status: rezolvat
---

## Context {#context}

Pe 13 iulie mutasem detecția repornirilor de pe regresia contorului de secvență pe
o încarnare declarată explicit:
[repornirea nu se deduce, se observă]({{ '/intrari/2026-07-13-repornirea-se-observa-nu-se-deduce/' | relative_url }}).
Agentul generează un UUID4 la fiecare pornire de proces și îl trimite cu fiecare
heartbeat; serverul compară încarnări și răspunde cu `restart_detected`.

Mecanismul e simplu tocmai ca să nu poată greși: un identificator diferit înseamnă
proces nou, indiferent ce număr poartă bătaia.

## Simptom {#simptom}

Niciunul, din nou — dar de data asta e mai rău, pentru că exista și un test care
spunea că totul e în regulă.

`test_restart_detected_even_when_sequence_is_higher` trecea. Trece și azi. Nu e un
test slab: pornește serverul real, înregistrează un agent, trimite două
heartbeat-uri cu încarnări diferite și cere `restart_detected is True`.

Agentul își loga la fiecare pornire încarnarea. Serverul răspundea `200` la fiecare
bătaie. `restart_detected` venea `false` — dar `false` e și răspunsul normal pentru
o bătaie care nu e o repornire, deci nimic din răspuns nu arăta greșit.

Singurul simptom real era o absență: în trei săptămâni, niciun eveniment
`agent_restart` și niciun `restart_count` diferit de zero, pe un sistem repornit de
zeci de ori în timpul dezvoltării. Un EDR care raportase exact zero reporniri.
Numai că nimeni nu are o alarmă pentru „o categorie de evenimente a încetat să mai
apară".

## Ce am crezut {#ipoteza}

Că mecanismul funcționează, pentru că îl verifica un test.

Și chiar îl verifica — doar că nu pe traseul care conta. Testele de pe server își
construiesc singure payload-ul de heartbeat, cu numele corecte ale câmpurilor,
pentru că altfel n-ar avea ce trimite. Ceea ce înseamnă că testează *regula* pe care
serverul o aplică unui payload valid, și nu ating niciodată singura parte care era
stricată: numele cheilor pe care le compune agentul.

Am recitit codul agentului de mai multe ori în perioada aia, inclusiv scriind
despre el. Cheia greșită se citește exact ca cea bună dacă știi deja ce ar trebui
să scrie acolo.

## Cauza reală {#cauza}

O literă:

```python
heartbeat_payload = {
    "agents_instance_id": config.get("agent_instance_id"),   # cheia trimisă
    ...
}
```

```python
class HeartbeatRequest(BaseModel):
    agent_instance_id: Optional[str] = None                  # cheia citită
```

Pydantic ignoră implicit câmpurile pe care nu le cunoaște. Nu e o eroare de
validare, nu e un `422`, nu e un avertisment — cheia dispare pur și simplu, iar
`body.agent_instance_id` rămâne `None` la fiecare bătaie. Ramura care compară
încarnări nu s-a executat niciodată.

Efectul secundar e partea care transformă un câmp lipsă într-o funcționalitate
absentă. Corecția din 13 iulie scosese, pe bună dreptate, vechea regulă bazată pe
regresia contorului. Deci nu mai exista nicio plasă: un agent repornit trimite
`sequence = 1` după ce serverul văzuse, să zicem, 500, cade pe ramura
`sequence < last_sequence` și e clasificat drept „duplicat vechi, reordonat —
ignorat". Repornirea nu doar că nu era detectată; era catalogată explicit drept
altceva.

Aceeași cerere, la o literă distanță, două verdicte:

```
{... "agent_instance_id": "B"}   ->  restart_detected: true
{... "agents_instance_id": "B"}  ->  restart_detected: false
```

Și mai e un motiv pentru care nimic n-a țipat, iar ăsta e o decizie de-a mea, nu un
accident: câmpul e `Optional[str] = None`, pentru compatibilitate cu agenții vechi
care nu-l trimit încă. Un câmp opțional nu are caz de eșec. „Absent pentru că
agentul e vechi" și „absent pentru că am scris prost cheia" sunt exact același lucru
pe sârmă.

## Soluția {#solutia}

Construirea payload-ului iese din buclă într-o funcție proprie, ca numele cheilor
să existe într-un singur loc și să poată fi verificate independent de tot restul:

```python
def build_heartbeat_payload(config: Dict[str, Any], sequence: int) -> Dict[str, Any]:
    return {
        "agent_instance_id": config.get("agent_instance_id"),
        "sequence": sequence,
        "agent_version": config.get("agent_version"),
    }
```

Iar docstring-ul ei spune de ce există, pentru că altfel funcția arată ca o
extragere cosmetică: numele trebuie să corespundă *exact* câmpurilor din
`HeartbeatRequest`, iar o cheie scrisă greșit nu produce nicio eroare.

## Cum știu că e rezolvat {#regresie}

Două teste noi, pe partea agentului — locul din care golul se putea închide, pentru
că serverul nu are cum să observe o cheie pe care n-o primește.

Primul verifică direct că payload-ul poartă `agent_instance_id`. Prinde exact
greșeala asta și numai pe ea.

Al doilea e cel care contează:
`test_payload_has_no_key_the_server_would_silently_drop`. Nu afirmă un nume, ci
absența numelor pe care cealaltă parte nu le cunoaște — deci prinde și următoarea
cheie scrisă greșit, care va fi altă cheie. Diferența dintre un test care apără un
caz și unul care apără o clasă e fix diferența dintre cele două.

Al treilea acoperă o proprietate învecinată, pe care n-o verifica nimic: secvența
avansează și peste un heartbeat eșuat, adică o bătaie pierdută în rețea rămâne
vizibilă ca gol.

## Ce am învățat {#invatat}

**Testele de pe ambele maluri pot fi verzi peste un pod rupt.** Testele serverului
își construiesc payload-ul cu numele corecte. Testele agentului, când or exista, îl
construiesc cu numele lui. Nici unele, nici celelalte nu compară vreodată cele două
seturi de nume, pentru că fiecare depozit conține doar o parte a contractului.
Contractul nu locuiește în niciunul dintre ele, deci nu-l testa niciunul.

**O validare permisivă transformă o greșeală de scriere într-o funcționalitate
lipsă.** Ignorarea câmpurilor necunoscute e opțiunea corectă: un server mai vechi
trebuie să tolereze câmpuri noi de la un agent mai nou, altfel nu poți actualiza
parcul în valuri. Aș alege-o din nou. Dar e aceeași proprietate, privită din
cealaltă direcție, care a făcut bug-ul invizibil — toleranța la ce nu recunoști
înseamnă tăcere la ce ai greșit.

**Un câmp opțional nu poate fi greșit, poate doar lipsi.** Opționalitatea a fost o
decizie deliberată, luată pentru motivul bun. Costul ei, pe care nu-l vedeam
atunci: șterge singura stare în care protocolul ar fi putut să se plângă. Când
absența e legitimă, absența nu mai e o informație.

**Absența unei categorii de evenimente e un simptom pe care nu-l urmărește nimeni.**
Trei săptămâni fără niciun `agent_restart` era, în principiu, vizibil — dar
sistemele de monitorizare se uită la ce apare, nu la ce a încetat să apară. E
aceeași observație pe care o făcusem construind contorul de secvență, întoarsă
împotriva mea: ca să vezi o lipsă, trebuie să fi pus dinainte structura care o face
numărabilă. Pentru heartbeat-uri o pusesem. Pentru propriile mele detecții, nu.
