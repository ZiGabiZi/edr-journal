---
title: O amprentă pentru două întrebări
date: 2026-09-01
tip: corectie
rezumat: Instantaneul de reputație avea o singură amprentă, peste octeții fișierului. Un test scris ca să confirme criteriul de ieșire a picat, și avea dreptate — fișierul poartă momentul construirii, deci criteriul, așa cum era formulat, era imposibil de îndeplinit.
tags: [reputatie, contract]
capitol: "2.6"
componente: server
commits: [edr-server@ecf14bc, edr-server@c5acdb7, edr-server@d2d377e]
teste: [app/tests/test_reputation_import_rds.py::test_a_second_run_changes_nothing, app/tests/test_reputation_import_rds.py::test_the_file_fingerprint_still_moves_with_the_clock, app/tests/test_reputation_import_rds.py::test_a_resumed_import_matches_an_uninterrupted_one]
status: rezolvat
---

## Decizia originală {#originala}

La P2.2.3, instantaneul de reputație a primit o amprentă: SHA-256 peste octeții
fișierului, calculată la cerere și **nestocată înăuntru**.

```python
def fingerprint(path: str) -> str:
    """SHA-256 peste octeții fișierului, în hexazecimal."""
```

Comisă în `ecf14bc`, cu două criterii de ieșire pentru pas: o scriere în timpul
unei rulări trebuie să eșueze, iar amprenta trebuie să fie stabilă la
recalculare. Amândouă au trecut.

Pentru pasul următor, criteriul a fost scris în plan așa:

> **Gata când:** reimportul aceluiași fișier sursă produce aceeași amprentă.

## Raționamentul de atunci {#rationament}

Trei cerințe, toate corecte, și o singură valoare care părea să le satisfacă pe
toate.

**Verificabilă din afară.** `METRICS.md` 8 cere ca amprenta să apară lângă orice
cifră publicată. O valoare pe care oricine o poate recalcula cu `sha256sum`, fără
codul nostru, e mai tare decât una care cere să ai încredere în implementare.

**Nestocată în fișier.** O amprentă scrisă înăuntru ar face parte din ce
amprentează — un ou care-și conține propriul găinaț. Calculată din afară,
problema dispare.

**Una singură.** Două valori cu același nume ar fi părut exact felul de
complexitate pe care restul proiectului o refuză. O întrebare, un răspuns, o
comandă.

Nimic din raționamentul ăsta nu era greșit. Ce lipsea era observația că
*întrebarea* nu era una singură.

## Ce nu vedeam {#gol}

Contra-exemplul a venit dintr-un test scris ca să **confirme** criteriul de
ieșire, nu ca să-l pună la îndoială:

```python
def test_a_second_run_changes_nothing(...):
    rds.import_rds(sursa_rds, lucru, "test-1")
    intai = reputation_build.seal(lucru, tmp_path / "intai.db")

    rds.import_rds(sursa_rds, lucru, "test-1")
    apoi = reputation_build.seal(lucru, tmp_path / "apoi.db")

    assert intai == apoi
```

A picat. Și avea dreptate.

`seal()` scrie în instantaneu momentul construirii. `record_source()` scrie
momentul importului. **Două importuri identice, rulate la ore diferite, produc
fișiere diferite la octet.**

Deci criteriul de ieșire, așa cum fusese formulat, nu era greu — era
**imposibil**. Nicio implementare corectă nu l-ar fi putut îndeplini, iar dacă
testul ar fi trecut, ar fi însemnat că ceva era în neregulă cu amprenta, nu cu
criteriul.

Sub același cuvânt stăteau două întrebări diferite:

| întrebarea | cine o pune | ce cere |
|---|---|---|
| **ce a citit serverul** când a produs cifra asta | `METRICS.md` 8 | identitate, deci fișierul exact, ceas cu tot |
| **ce e înăuntru** | criteriul de idempotență | conținut, deci fără nimic derivat din ceas |

Prima are nevoie ca amprenta să se miște când se schimbă fișierul. A doua are
nevoie ca ea să **nu** se miște când se schimbă doar ora. Sunt cerințe opuse, iar
o singură valoare nu le poate satisface pe amândouă.

## Ce am schimbat {#schimbat}

A apărut o a doua amprentă, cu rol declarat separat:

```python
def content_fingerprint(connection) -> str:
    """Amprentă peste CONȚINUTUL logic, nu peste octeții fișierului."""
```

Trece peste rânduri în ordinea amprentei și peste surse în ordinea numelui,
sărind peste tot ce e ceas: `built_at`, `imported_at`, cursorul de reluare. Două
depozite cu același conținut dau aceeași valoare, oricând ar fi fost construite.

Repartizarea rolurilor, scrisă în `METRICS.md` 8.1 ca să nu se piardă:

- **lângă o cifră** merge amprenta fișierului — ea spune ce a citit serverul;
- **idempotența și reproductibilitatea** se verifică cu amprenta de conținut.

Testul care picase a fost rescris să compare conținutul. Dar am adăugat și
**reversul**, ca distincția să nu rămână o vorbă:

```python
def test_the_file_fingerprint_still_moves_with_the_clock(...):
    """Același conținut, două sigilări, două amprente de fișier diferite."""
```

Fără el, cineva ar fi putut „simplifica" mai târziu cele două valori înapoi
într-una, iar suita ar fi rămas verde.

Al treilea test verifică ce voia de fapt criteriul original: un import întrerupt
de trei ori ajunge la exact același **conținut** ca unul dintr-o bucată.

O corecție ulterioară, în `d2d377e`: amprenta de conținut a devenit opțională. La
72 de milioane de rânduri e o parcurgere completă, hashuită rând cu rând în
Python — cea mai lentă operațiune din tot lanțul. Rolul ei e să dovedească ceva
când vrei, nu să însoțească fiecare sigilare.

## Ce a rămas valid {#ramas}

**Amprenta originală, integral.** E tot SHA-256 peste octeți, tot calculată la
cerere, tot nestocată înăuntru, și tot ea merge lângă o cifră publicată. Nu s-a
aruncat nimic — s-a adăugat ceva lângă.

Ceea ce înseamnă că mecanismul n-a fost greșit niciodată. Greșită a fost
presupunerea despre **câte întrebări răspunde**. Iar asta e o distincție care
merită păstrată, fiindcă a doua zi a mai apărut de trei ori, în forme diferite:

- `D1`–`D3` însemnau simultan deciziile despre rulările de măsurătoare din
  `METRICS.md` 9.2–9.4 și deciziile despre depozitul de reputație;
- semnul de secțiune trimitea uneori la secțiuni proprii, alteori la secțiuni ale
  lucrării;
- vocabularul de tag-uri era scris în două locuri, care se despărțiseră.

Toate patru sunt același lucru: **un nume care acoperă două înțelesuri nu produce
nicio eroare — produce cifre plauzibile și greșite.** Singura care s-a apărat
singură a fost asta, fiindcă exista un test care putea să pice. Celelalte trei au
fost găsite citind, adică din noroc și disciplină, nu prin construcție.

Concluzia practică pentru ce urmează: când un cuvânt e folosit în două
propoziții care cer lucruri opuse de la el, sunt două cuvinte care încă n-au fost
despărțite.
