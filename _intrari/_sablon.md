---
# ─────────────────────────────────────────────────────────────
#  ȘABLON DE INTRARE — copiază fișierul, nu-l edita pe loc.
#  Numele fișierului nou: aaaa-ll-zz-titlu-scurt.md (fără underscore).
#  Fișierul acesta începe cu "_", deci Jekyll nu îl publică.
# ─────────────────────────────────────────────────────────────

# ── OBLIGATORIU ──────────────────────────────────────────────
title:
date: 2026-07-25
tip: incident        # incident | decizie
rezumat:             # o singură frază — apare pe pagina de index
tags: []             # vocabular ÎNCHIS, doar din lista de mai jos:
                     #   retea, concurenta, persistenta, identitate,
                     #   observabilitate, pdp, infrastructura
                     # Nu inventa tag-uri noi în timp ce scrii. Dacă unul
                     # chiar lipsește, adaugă-l aici întâi, apoi folosește-l.

# ── OPȚIONAL, dar merită completat ───────────────────────────
componente:          # agent | server | ambele
commits: []          # [edr-agent@a1b2c3d, edr-server@e4f5g6h]
teste: []            # testele de regresie care prind bug-ul dacă revine
                     # [tests/test_event_spool.py::test_reia_dupa_restart]
status:              # rezolvat | partial | deschis
---

<!-- ═══════════════════════════════════════════════════════════
     VARIANTA A — pentru `tip: incident`
     Șterge varianta B de mai jos.

     NU șterge marcajele {#...} de după titluri. Ele dau layout-ului
     rolul fiecărei secțiuni (culoare, formă, eticheta „respinsă").
     Fără ele secțiunea se randează generic, dar nu se strică nimic.
     ═══════════════════════════════════════════════════════════ -->

## Context {#context}

<!-- La ce lucrai și de ce. Ce parte a sistemului, în ce moment. -->

## Simptom {#simptom}

<!-- Ce s-a văzut, concret: mesaj de eroare, log, comportament observat.
     Fără interpretare aici — doar ce era pe ecran. -->

## Ce am crezut {#ipoteza}

<!-- Ipoteza falsă, scrisă cinstit, plus de ce părea plauzibilă.
     Asta e partea care dă valoare jurnalului; nu o sări. -->

## Cauza reală {#cauza}

<!-- Ce se întâmpla de fapt și cum ai ajuns de la ipoteză la cauză. -->

## Soluția {#solutia}

<!-- Ce ai schimbat. Trimite la `commits` din front-matter. -->

## Cum știu că e rezolvat {#regresie}

<!-- Testul de regresie sau verificarea manuală reproductibilă.
     Trimite la `teste` din front-matter. -->

## Ce am învățat {#invatat}

<!-- Regula generalizabilă, nu rezumatul fixului. -->


<!-- ═══════════════════════════════════════════════════════════
     VARIANTA B — pentru `tip: decizie`
     Șterge varianta A de mai sus.
     ═══════════════════════════════════════════════════════════ -->

## Context {#context}

<!-- Situația care a impus o alegere. -->

## Forța {#forta}

<!-- Constrângerile aflate în tensiune: performanță vs. simplitate,
     livrare garantată vs. memorie, timp disponibil vs. corectitudine. -->

## Alternative {#alternative}

<!-- Opțiunile respinse și motivul concret al respingerii. -->

## Alegerea {#alegerea}

<!-- Ce ai decis, formulat la timpul prezent: „Agentul scrie pe disc...". -->

## Costul acceptat {#cost}

<!-- Ce pierzi prin decizia asta. O decizie fără cost e o decizie
     nedocumentată. -->

## Ce am învățat {#invatat}

<!-- Ce ai afla mai devreme data viitoare. -->
