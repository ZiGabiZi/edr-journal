---
title: Fișierele care intrau prin mutare erau invizibile
date: 2026-06-24
tip: incident
rezumat: Monitorizarea asculta `on_created` și `on_modified`. Un fișier adus de pe stick sau din Downloads pe același volum nu produce niciunul dintre ele — produce o redenumire, raportată doar directorului sursă.
tags: [detectie]
capitol: "3.1"
componente: agent
commits: [edr-agent@719268c]
teste: []
status: partial
---

## Context {#context}

Prima versiune a monitorizării, scrisă în aceeași zi, punea `watchdog` să observe
directoarele din configurație și trata două evenimente:

```python
def on_created(self, event): ...
def on_modified(self, event): ...
```

Adică: a apărut un fișier nou, s-a modificat un fișier existent. Din perspectiva
unui director monitorizat, păreau cele două lucruri care i se pot întâmpla.

Testul meu era simplu și trecea de fiecare dată: deschid un editor, creez un fișier
în `C:\EDR_Test`, salvez. Evenimentul apărea în log și ajungea la server.

## Simptom {#simptom}

Am încercat scenariul real în loc de cel comod: am luat un fișier din `Downloads`
și l-am tras cu mouse-ul în directorul monitorizat.

Nimic. Niciun log, niciun eveniment, niciun `POST`. Fișierul era acolo, se vedea în
explorer, iar agentul rula și răspundea normal la heartbeat.

Repetat cu un fișier de pe alt disc: evenimentul apărea. Repetat de pe același
disc: tăcere.

## Ce am crezut {#ipoteza}

Că am o problemă de filtrare sau de cale — că `C:\Users\...\Downloads` intra cumva
în vreo listă de excludere, sau că normalizarea căii strica potrivirea. M-am uitat
întâi acolo pentru că era singura parte a codului care putea decide *să nu*
raporteze ceva.

Ipoteza era greșită într-un fel util: presupunea că evenimentul ajunge la mine și e
respins. Nu ajungea deloc.

Diferența dintre „de pe alt disc merge" și „de pe același disc nu" e cea care
închide cazul, pentru că e o distincție pe care nicio filtrare din codul meu n-o
putea face — nimic din ce scrisesem nu știa pe ce volum stătea fișierul înainte.

## Cauza reală {#cauza}

Un fișier mutat în interiorul aceluiași sistem de fișiere nu e copiat și șters. E
redenumit. Sistemul de operare nu creează nimic: schimbă o intrare de director.

`watchdog` raportează asta ca `FileMovedEvent`, cu `src_path` și `dest_path`. Iar
evenimentul e livrat observatorului care urmărea **sursa**, nu destinația.
Directorul monitorizat nu primește niciun `on_created`, pentru că din punctul de
vedere al sistemului de fișiere nu s-a creat nimic acolo.

De pe alt disc funcționa fiindcă o mutare între volume nu poate fi o redenumire:
conținutul chiar trebuie copiat, deci apare un fișier nou și, cu el, `on_created`.

Ce înseamnă asta pentru un EDR e mai important decât mecanismul. Modul cel mai
frecvent în care un fișier ajunge într-un director de pe o stație — adus de pe un
stick, tras din Downloads după ce a fost descărcat, scos dintr-o arhivă
dezarhivată alături — trecea prin exact ramura pe care n-o ascultam. Acopeream
crearea și modificarea, adică fișierele care se nasc pe loc, și rata sosirea, care
e cazul interesant.

## Soluția {#solutia}

Un al treilea handler, care traduce o mutare în limbajul directorului monitorizat:

```python
def on_moved(self, event: FileSystemEvent) -> None:
    if not isinstance(event, FileMovedEvent) or event.is_directory:
        return

    dest_path = os.fsdecode(event.dest_path)
    if self._is_in_monitored_directory(dest_path):
        self._handle_file_event(dest_path, "file_created")
```

Trei decizii în cinci rânduri.

**Se raportează `dest_path`, nu `src_path`.** Sursa poate fi oriunde, inclusiv
undeva ce nu monitorizez și despre care n-am nimic de spus. Ce contează e unde a
ajuns.

**Tipul raportat e `file_created`.** Nu e apelul de sistem care s-a executat, dar e
ce s-a întâmplat cu directorul monitorizat: are un fișier pe care nu-l avea.
Evenimentul descrie schimbarea de stare a lucrului supravegheat, nu operația care
a produs-o — altfel aș fi împins în server o distincție de sistem de fișiere pe
care nicio regulă de detecție n-ar folosi-o.

**Se verifică explicit că destinația e într-un director monitorizat**, prin
`os.path.commonpath` peste căile normalizate. Fără verificarea asta, orice mutare
raportată de un observator ar fi fost tratată ca sosire — inclusiv una care scoate
un fișier *afară*.

## Cum știu că e rezolvat {#regresie}

Prin repetarea manuală a scenariului: fișier tras din `Downloads` în directorul
monitorizat, pe același volum, eveniment în log și la server.

`teste` e gol, și de-asta intrarea rămâne `partial`. Nu există niciun test peste
`file_monitor.py` — nici pentru cazul ăsta, nici pentru filtrarea pe extensii sau
pentru containment-ul de directoare adăugate în același commit. Toate trei sunt
verificabile fără `watchdog` real, construind evenimente sintetice și apelând
handler-ele direct, ceea ce le face datorie, nu dificultate.

## Ce am învățat {#invatat}

**Setul de evenimente al bibliotecii nu e setul de întrebări al domeniului meu.**
`watchdog` expune ce face sistemul de fișiere: creare, modificare, ștergere,
redenumire. Eu aveam nevoie de altceva — *a apărut un fișier în locul ăsta* — care
nu corespunde unui singur eveniment al bibliotecii. Am scris cod pentru
vocabularul uneltei și am presupus că acoperă vocabularul problemei.

**Testul comod și testul real testează lucruri diferite.** Crearea unui fișier
dintr-un editor era felul în care *eu* produceam evenimente, nu felul în care
fișierele ajung în realitate pe o stație. Un an de testat așa n-ar fi găsit nimic,
pentru că metoda de test excludea exact clasa de intrare care conta.

**Un gol de acoperire e tăcut prin construcție.** Un bug obișnuit produce ceva
greșit; ăsta nu producea nimic. Nu există log al evenimentelor care n-au fost
generate, deci singurul mod de a găsi așa ceva e să enumeri dinainte căile prin
care lucrul supravegheat se poate schimba, și să le bifezi pe rând. Într-un sistem
de detecție, întrebarea „ce nu văd" nu are un mecanism care s-o pună în locul meu.

**Am rezolvat sosirea, nu și plecarea.** Verificarea că destinația e monitorizată
înseamnă că un fișier mutat *din* directorul supravegheat oriunde altundeva nu
produce niciun eveniment. E o alegere corectă pentru scopul de atunci — voiam să
văd ce intră — dar merită spus pe față, pentru că e fix contrariul tezei
sistemului: un jurnal care urmărește ce ajunge pe endpoint și tace când ceva pleacă
de acolo are un gol în partea care contează cel mai mult.
