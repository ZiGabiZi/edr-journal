---
layout: despre
title: De ce acest EDR
permalink: /despre/
rezumat: Sistemul nu încearcă să fie un EDR mai bun. Încearcă să fie un EDR utilizabil acolo unde fișierul suspect nu are voie să plece.
---

## Problema {#problema}

Analiza statică a unui fișier suspect presupune, aproape fără excepție, că
fișierul ajunge la analizor. Un motor de reguli, un sandbox de detonare, un
serviciu de reputație — toate încep prin a cere artefactul. Într-o organizație
care lucrează cu date sensibile, presupunerea asta e adesea inacceptabilă:
fișierul suspect e chiar documentul care nu are voie să iasă din perimetru.
Fișa unui pacient, un dosar juridic, un document clasificat — ele nu devin
transmisibile pentru că un motor de detecție ar vrea să se uite la ele.

Alegerea care rezultă e falsă și costisitoare în ambele direcții: ori renunți
la analiză și rămâi orb, ori trimiți conținutul și încalci exact politica pe
care securitatea ar trebui s-o apere. Soluțiile comerciale o rezolvă implicit,
prin cloud — ceea ce înseamnă că organizațiile cu cea mai mare nevoie de
detecție sunt exact cele care nu le pot adopta.

## Invariantul {#invariant}

Sistemul inversează implicitul: analiza merge la fișier, nu fișierul la
analiză. Endpointul devine punctul unde se decide (*policy decision point*),
nu doar punctul de unde se raportează. Regulile coboară la agent, verdictul se
calculează local, iar spre server urcă strictul necesar.

> Nimic nu părăsește endpointul până când incertitudinea verdictului nu intră
> în banda în care dovezile locale nu mai pot decide.

Corolarul contează la fel de mult ca invariantul: un verdict sigur — în oricare
dintre direcții — nu justifică niciodată transferul conținutului. Curat înseamnă
că nu pleacă nimic. Confirmat malițios înseamnă tot că nu pleacă nimic, pentru
că decizia s-a putut lua deja pe loc. Doar zona ambiguă din mijloc poate cere
mai mult, și o cere în trepte, fiecare treaptă fiind o decizie explicită, cu
urmă în audit, nu un efect secundar al arhitecturii:

1. **metadate** — cale, tip de eveniment, moment;
2. **identitate** — hash-ul criptografic, care permite verificarea fără divulgare;
3. **trăsături** — ce a extras analiza locală despre fișier, fără fișier;
4. **conținutul** — ultima treaptă, sub politică explicită.

Scara asta nu e o intenție declarată în text. Protocolul o poartă deja:
directiva pe care serverul o întoarce la fiecare heartbeat acceptă
`update_ruleset` și `collect_file`, iar câmpul `collect_file_path` e marcat în
cod drept viitorul canal de *progressive disclosure*. Astăzi agentul se află pe
prima treaptă și doar pe ea: trimite cale și tip de eveniment, nu calculează
niciun hash al fișierelor monitorizate și nu are cum să transmită conținut.

## Ce urmează {#urmeaza}

Ce e construit până acum e canalul, nu decizia. Agentul observă local, scrie
evenimentele într-o coadă durabilă, le livrează cu semantică at-least-once, iar
serverul le deduplică; heartbeat-ul detectează reporniri și heartbeat-uri
pierdute și poartă canalul prin care serverul poate cere ceva agentului. Nimic
din toate astea nu e teza — sunt condițiile fără de care teza nu se poate
susține.

Ce urmează e chiar punctul de decizie: hash calculat pe endpoint, un ruleset
YARA împins prin directiva `update_ruleset` și evaluat local, iar peste el
banda de incertitudine care hotărăște dacă `collect_file` se declanșează
vreodată. `rules/`, `app/analysis/` și `storage/samples/` sunt goale în acest
moment — sunt exact locurile unde intră partea care justifică lucrarea.

De aceea jurnalul are sens ca jurnal, nu ca listă de rezolvări. [Coada
persistentă de evenimente]({{ '/intrari/2026-07-12-coada-persistenta-de-evenimente/' | relative_url }})
nu e „am pus o coadă ca să nu pierd evenimente". E condiția prealabilă a
afirmației: livrarea trebuie să fie garantată înainte să pot pretinde că
divulgarea e controlată. Un sistem care pierde tăcut evenimente nu poate
demonstra nimic despre ce alege să nu trimită.
