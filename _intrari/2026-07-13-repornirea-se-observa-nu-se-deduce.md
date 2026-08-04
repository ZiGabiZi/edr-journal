---
title: Repornirea agentului nu se deduce din contor, se observă
date: 2026-07-13
tip: corectie
rezumat: Derivasem repornirea din regresia contorului de secvență. Regresia e un simptom al repornirii, nu definiția ei — și simptomele au și fals-negative, și fals-pozitive.
tags: [identitate, observabilitate, retea]
capitol: "3.3"
componente: ambele
commits: [edr-server@ad808b0, edr-server@476fade, edr-server@e993733, edr-agent@4a25c36]
teste: [app/tests/test_heartbeat_sequence.py::test_restart_detected_even_when_sequence_is_higher, app/tests/test_heartbeat_sequence.py::test_equal_sequence_same_instance_is_duplicate_not_restart, app/tests/test_heartbeat_sequence.py::test_sequence_gap_counts_missed_heartbeats]
status: partial
---

## Decizia originală {#originala}

Pe 3 iulie am adăugat în heartbeat un contor de secvență: un număr monoton per
proces al agentului, care pornește de la 1 la fiecare lansare și crește cu
fiecare bătaie. Serverul scotea din el două verdicte deodată — câte
heartbeat-uri s-au pierdut, și dacă agentul a repornit:

```python
elif sequence <= last_sequence:
    # Contorul agentului a scăzut/resetat -> procesul a repornit.
    restart_detected = True
    agent["restart_count"] = agent.get("restart_count", 0) + 1
elif sequence > last_sequence + 1:
    # Gol în secvență -> heartbeat-uri pierdute între două primiri.
    missed = sequence - last_sequence - 1
```

Un singur semnal, două întrebări diferite.

## Raționamentul de atunci {#rationament}

Contorul exista oricum, pentru numărarea heartbeat-urilor pierdute. Repornirea
părea un corolar gratuit: dacă procesul repornește, contorul lui o ia de la 1,
deci o scădere înseamnă proces nou. Zero câmpuri noi în protocol, zero suprafață
adăugată.

Partea cu adevărat importantă a deciziei era însă alta, și rămâne corectă:
detecția trebuie să fie **server-side**. Un agent care moare prin crash, prin
`kill`, sau pentru că cineva l-a oprit intenționat nu apucă să anunțe nimic. Dacă
serverul așteaptă o notificare de la agent ca să afle că agentul a repornit,
tocmai cazurile care contează pentru securitate sunt cele care nu produc
notificarea. Verdictul trebuia derivat din ce vede serverul, nu din ce declară
agentul.

## Ce nu vedeam {#gol}

Că regresia contorului e un *simptom* al repornirii, nu *definiția* ei. Regula
se declanșa doar dacă noua încarnare ajungea la un număr mai mic sau egal cu
ultimul văzut de server. Nimic nu garanta asta — serverul nu controlează
contorul, doar îl observă.

Când noul proces raportează o secvență **mai mare**, regula tace. Mai rău, nu
tace neutru: gol-ul e interpretat ca heartbeat-uri pierdute, deci o repornire
nedetectată se transformă în statistici false despre continuitate. Testul care
fixează cazul e explicit:

```python
def test_restart_detected_even_when_sequence_is_higher():
    _register()
    _heartbeat("agent-1", sequence=5, instance_id="inst-A")
    body = _heartbeat("agent-1", sequence=100, instance_id="inst-B").json()
    assert body["restart_detected"] is True
    assert body["missed_heartbeats"] == 0
```

Sub regula veche, asta era un gol de 94 de bătăi și nicio repornire.

Recitind codul original am găsit și gaura simetrică, pe care n-o căutam.
Condiția era `<=`, nu `<`. O retransmisie exactă a aceluiași heartbeat — același
număr, același proces — era înregistrată ca repornire. Deci mecanismul greșea în
ambele direcții: rata reporniri reale când contorul nu regresa, și inventa
reporniri când rețeaua doar dubla un pachet.

Numitorul comun: încercam să stabilesc identitatea unui proces dintr-un efect
secundar numeric, în loc s-o cer direct.

## Ce am schimbat {#schimbat}

Agentul își declară acum încarnarea. La fiecare pornire generează un
`agent_instance_id` — un UUID4 creat o singură dată, la lansarea procesului — și
îl trimite cu fiecare heartbeat. Serverul compară încarnări, nu numere:

```python
if instance_id is not None:
    last_instance = agent.get("agent_instance_id")

    if last_instance is None:
        agent["agent_instance_id"] = instance_id      # doar baseline
    elif instance_id != last_instance:
        agent["restart_count"] = agent.get("restart_count", 0) + 1
        agent["agent_instance_id"] = instance_id
        agent["last_sequence"] = sequence
        return HeartbeatResult(..., restart_detected=True, missed_heartbeats=0)
```

Verificarea rulează **înaintea** oricărei logici de secvență și iese imediat.
Un identificator diferit înseamnă proces nou, indiferent ce număr poartă bătaia.
Nu mai există o valoare a contorului care să ascundă o repornire, pentru că
verdictul nu se mai uită la contor.

Resetarea lui `last_sequence` la valoarea noii încarnări e partea care închide
bucla: fără ea, prima bătaie de după repornire ar fi produs un gol fantomă de
mărimea diferenței dintre cele două contoare.

Decizia din 3 iulie de a ține detecția server-side n-a fost atinsă. Agentul nu
anunță „am repornit"; el doar spune cine este, iar concluzia rămâne a serverului.

## Ce a rămas valid {#ramas}

Contorul de secvență n-a fost aruncat. Și-a păstrat exact treaba pentru care era
bun, și doar pe aceea: continuitatea în interiorul unei încarnări. Numără
heartbeat-urile pierdute dintr-un gol, recunoaște retransmisiile exacte ca
idempotente și ignoră pachetele întârziate care sosesc cu un număr mai mic.
`test_sequence_gap_counts_missed_heartbeats` trece azi neschimbat.

A rămas valid și principiul care motiva decizia originală: detecția aparține
serverului, pentru că un agent oprit brutal nu raportează nimic.

Ce s-a mutat a fost strict **autoritatea**. Contorul răspunde la „au lipsit
bătăi?". Încarnarea răspunde la „mai e același proces?". Înainte, o singură
valoare răspundea la ambele, iar corectitudinea celui de-al doilea răspuns
depindea de o presupunere pe care serverul n-avea cum s-o verifice.

Greșeala n-a fost contorul. A fost că i-am cerut să certifice ceva ce nu putea
observa.
