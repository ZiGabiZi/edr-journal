---
title: Curățarea care nu pornea niciodată, apoi pornea la fiecare eveniment
date: 2026-06-25
tip: incident
rezumat: Garda care decidea când se curăță dicționarul debouncer-ului combina o limită de frecvență cu un prag de dimensiune. Cu AND, curățarea era imposibilă sub prag; cu OR, se executa la fiecare eveniment peste prag. Niciunul dintre operatori nu era răspunsul.
tags: [concurenta]
componente: agent
commits: [edr-agent@bcf300c, edr-agent@e08c798, edr-agent@87af315, edr-agent@61a5bb5]
teste: [tests/test_event_debouncer.py::test_cleanup_runs_even_when_the_dictionary_stays_small, tests/test_event_debouncer.py::test_cleanup_body_is_rate_limited_regardless_of_event_volume, tests/test_event_debouncer.py::test_pass_drops_entries_older_than_two_intervals_and_keeps_newer]
status: rezolvat
---

## Context {#context}

Pe 24 iunie tocmai construisem monitorizarea minimă de fișiere. `watchdog`
raportează evenimente de sistem de fișiere, iar prima problemă pe care ți-o pune
nu e detecția, ci repetiția: o singură scriere logică produce mai multe
evenimente, pentru că sistemul de operare și aplicațiile scriu în bucăți,
redenumesc fișiere temporare și ating metadate separat.

De aici `EventDebouncer`: un dicționar de la `"{tip_eveniment}:{cale}"` la
momentul ultimei apariții, și un verdict simplu.

```python
if previous_time is None:
    return False

return (current_time - previous_time) < self.interval_seconds
```

Două secunde. Orice se repetă înăuntrul ferestrei e duplicat.

Dicționarul, însă, doar crește: `is_duplicate` scrie o cheie pentru fiecare
eveniment și nu șterge niciodată. Deci am scris o curățare, apelată din interiorul
lui `is_duplicate`, sub același lock:

```python
if len(self._last_seen) < _DEBOUNCE_CLEANUP_THRESHOLD:              # 500
    return

if (current_time - self._last_cleanup_time) < _DEBOUNCE_CLEANUP_INTERVAL_SECONDS:  # 60
    return

cutoff = current_time - self.interval_seconds * 2
self._last_seen = {
    key: timestamp
    for key, timestamp in self._last_seen.items()
    if timestamp > cutoff
}
self._last_cleanup_time = current_time
```

Se citește rezonabil: nu te obosi să cureți un dicționar mic, și nu curăța mai des
de o dată pe minut. Două precauții împotriva muncii inutile, una sub alta.

## Simptom {#simptom}

Niciunul. Ăsta e simptomul, și merită scris ca atare în loc să fie sărit.

Directorul meu monitorizat avea o mână de fișiere. Dicționarul n-a trecut
niciodată de câteva zeci de intrări, adică niciodată de pragul de 500. Fără linie
de log, fără încetinire, fără eroare. Agentul se comporta exact ca înainte.

Iar a doua problemă are nevoie, ca să se vadă, de 500 de chei distincte în
aceeași fereastră de patru secunde — adică de o mașină pe care se dezarhivează
ceva, se compilează ceva sau se instalează ceva într-un director urmărit. Pe o
mașină de dezvoltare cu un `C:\EDR_Test` în care arunc fișiere de mână, condiția
nu apare o dată pe lună.

Amândouă sunt bug-uri care nu se anunță singure la scara la care le scrii.

## Ce am crezut {#ipoteza}

**Prima dată:** că cele două condiții spun același fel de lucru și pot sta sub
aceeași gardă. „Nu curăța un dicționar mic" și „nu curăța mai des de un minut" se
citesc amândouă ca prudență împotriva muncii degeaba, deci le-am pus una sub alta,
ca două `return`-uri timpurii — fără să observ că asta le face pe amândouă
*obligatorii*.

**A doua oară:** că greșeala e operatorul. Când am văzut că sub prag curățarea nu
se face niciodată, am rescris garda ca disjuncție:

```python
threshold_exceeded = len(self._last_seen) >= _DEBOUNCE_CLEANUP_THRESHOLD
time_elapsed = (current_time - self._last_cleanup_time) >= _DEBOUNCE_CLEANUP_INTERVAL_SECONDS

if not (threshold_exceeded or time_elapsed):
    return
```

Corect pentru simptomul pe care îl țintea. Ba chiar mai mult: varianta asta ține
memoria mai jos decât oricare alta, inclusiv decât cea de azi. Doar că mutase
problema din memorie în procesor.

Părea plauzibil pentru că întrebarea pe care mi-o puneam era „care operator?", iar
cu doar doi din care să aleg, unul dintre ei trebuia neapărat să fie răspunsul.

## Cauza reală {#cauza}

Cele două condiții nu răspund la aceeași întrebare.

Condiția de timp e o **limită de frecvență**: o margine superioară pentru cât de
des are voie munca să se întâmple. Condiția de dimensiune era gândită ca
**declanșator**: o margine inferioară pentru când merită ca munca să se întâmple.

O limită de frecvență și un declanșator nu se combină cu un operator boolean,
pentru că una vorbește despre permisiune, celălalt despre nevoie. Oricare operator
ai alege, unul dintre ele ajunge subordonat celuilalt:

- **Cu AND**, declanșatorul devine precondiție pentru limita de frecvență. Dacă
  dimensiunea nu ajunge la 500, cronometrul nu apucă niciodată să conteze.
  Curățarea nu e rară — e imposibilă.
- **Cu OR**, declanșatorul ocolește limita de frecvență. Odată trecut de 500,
  `threshold_exceeded` rămâne adevărat, deci garda lasă să treacă *fiecare* apel.
  Iar pentru că trupul funcției actualizează `_last_cleanup_time` la fiecare
  trecere, cronometrul nu apucă nici măcar să devină constrângerea activă: cât ține
  rafala, limita de frecvență e cod mort.

Rulând logica gărzii peste două fluxuri sintetice de evenimente:

| flux de evenimente | AND | OR | doar timp |
|---|---|---|---|
| 300 fișiere distincte, în 10 minute | **0** curățări, 300 intrări rămase | 10 curățări, 31 intrări | 10 curățări, 31 intrări |
| 20.000 fișiere distincte, în 20 de secunde | 1 curățare, vârf 20.000 | **19.501** curățări, vârf 4.001 | 1 curățare, vârf 20.000 |

Primul rând e scurgerea. Trei sute de intrări care încetaseră să însemne ceva după
patru secunde rămâneau până la oprirea procesului, pentru că 300 < 500. Nu produc
verdicte greșite — comparația de timp din `is_duplicate` le ignoră corect — deci
nu e o problemă de corectitudine, e o structură care nu se golește niciodată.

Al doilea rând e thrashing-ul, și e mai rău decât arată numărul. Fiecare dintre
cele 19.501 rulări reconstruiește tot dicționarul, adică e o operație în O(n).
Toate se execută **sub lock**, ținut de `is_duplicate`. Și toate rulează pe firul
observer-ului `watchdog` — singurul fir care vede evenimente de fișiere. La data
aia, callback-ul de pe firul ăla trimitea și evenimentul prin HTTP, sincron, cu
timeout de 5 secunde;
[coada persistentă]({{ '/intrari/2026-07-12-coada-persistenta-de-evenimente/' | relative_url }})
care avea să-l elibereze abia peste zece zile. Deci mecanismul care trebuia să
apere memoria adăuga muncă pătratică exact pe firul deja saturat, exact în timpul
rafalei care justifica existența monitorizării.

## Soluția {#solutia}

Condiția de dimensiune dispare cu totul:

```diff
-        threshold_exceeded = len(self._last_seen) >= _DEBOUNCE_CLEANUP_THRESHOLD
-        time_elapsed = (current_time - self._last_cleanup_time) >= _DEBOUNCE_CLEANUP_INTERVAL_SECONDS
-
-        if not (threshold_exceeded or time_elapsed):
+        if (current_time - self._last_cleanup_time) < _DEBOUNCE_CLEANUP_INTERVAL_SECONDS:
             return
```

O gardă, o întrebare: a trecut un minut? Curățarea redevine ce era de la început —
o trecere de întreținere cu frecvență limitată, fără opinii despre dacă merită.
`_DEBOUNCE_CLEANUP_THRESHOLD` a rămas nefolosit și a fost șters mai târziu, în
trecere, într-un commit despre altceva.

Soluția nu e „operatorul corect". E că una dintre cele două condiții n-avea ce
căuta în garda aia. Dimensiunea nu era un declanșator prost; era un declanșator
pus într-un loc în care încăpea doar o limită de frecvență.

**Ce nu rezolvă.** Varianta de azi curăță cel mult o dată la 60 de secunde, deci o
rafală mai scurtă de un minut nu e tăiată deloc pe parcurs: vârful de memorie
rămâne un minut întreg de chei distincte — coloana a treia din tabel, identică cu
prima. Condiția de dimensiune era singurul lucru care se opunea vreodată
scenariului ăstuia, și acum nu mai există. Dacă se întoarce, trebuie să se
întoarcă drept al doilea mecanism, separat — un plafon dur pe dicționar, cu
evacuare — nu ca încă o clauză în același `if`.

## Cum știu că e rezolvat {#regresie}

Nu știu, în sensul în care întreabă rubrica. `teste` e gol. Nu există niciun test
peste `EventDebouncer`, și niciunul dintre cele două bug-uri n-ar fi fost prins de
ceva ce exista pe 25 iunie sau există azi.

Sunt însă ieftin de scris, ceea ce le face datorie, nu dificultate. Trei teste
acoperă toată povestea:

- un debouncer care primește sub 500 de chei distincte, pe mai mult de un minut,
  ajunge cu dicționarul mai mic decât numărul de chei primite — bug-ul cu AND;
- trupul curățării nu se execută de mai multe ori pe interval, oricâte evenimente
  ar sosi — bug-ul cu OR;
- o intrare mai veche de `2 × interval` dispare la prima curățare, una mai nouă
  rămâne — contractul propriu-zis, care până acum n-a fost niciodată scris nicăieri.

Toate trei cer o singură schimbare în cod: un ceas care se poate controla din
afară, în loc de apelul direct la `time.monotonic()`. De-asta intrarea e `partial`
și nu `rezolvat` — bug-ul e reparat, dar nimic nu-l împiedică să se întoarcă.

**Actualizare, 4 august 2026.** Cele trei teste există, cu numele din
`teste` de mai sus, iar `EventDebouncer` primește ceasul ca parametru de
constructor — implicit `time.monotonic`, deci comportamentul din producție e
neschimbat. Ceasul fals avansează timpul instantaneu: cele 10 minute din primul
test și rafala de 20.000 de evenimente din al doilea rulează în sub o zecime de
secundă.

Fiecare test a fost verificat prin rejucarea variantei istorice pe care o
țintește, ca să nu rămână o asigurare care nu asigură nimic: cu AND pică primul
(300 de chei intrate, 300 rămase) și al treilea (intrarea veche nu dispare
niciodată); cu OR pică al doilea (19.501 execuții ale trupului, față de una
permisă). Testele gărzii primesc explicit un plafon peste volumul lor, ca
mecanismul adăugat între timp să nu poată masca o gardă defectă.

Capătul liber din secțiunea anterioară — rafala mai scurtă decât garda, pe care
limita de timp n-o poate tăia — s-a închis separat, ca mecanism distinct, în
[Al doilea mecanism, nu încă o clauză]({{ '/intrari/2026-08-04-al-doilea-mecanism-nu-inca-o-clauza/' | relative_url }}).
Intrarea trece pe `rezolvat` abia acum, și pentru al doilea motiv, nu doar pentru
primul.

## Ce am învățat {#invatat}

**Două condiții care răspund la întrebări diferite nu se combină cu un operator.**
Una spunea „ai voie cel mult atât de des", cealaltă „merită doar dacă e destul de
mare". Orice operator aleg, una ajunge subordonată celeilalte. Semnalul că
problema nu e alegerea a fost chiar faptul că *ambele* variante ale unei alegeri
binare produceau comportamente greșite — când niciun răspuns nu e bun, întrebarea
e prost pusă.

**O optimizare pusă într-o gardă de corectitudine devine o condiție de
corectitudine.** „Nu te obosi cu un dicționar mic" e o idee despre performanță.
Scrisă ca `return` timpuriu în singurul loc care întreținea invariantul, a încetat
să fie optimizare și a devenit o regulă despre când are voie invariantul să fie
adevărat. Munca ieftină ocolită condiționat e mai scumpă decât munca ieftină
făcută întotdeauna.

**Un bug de resurse se mută, nu dispare.** Varianta cu OR a reparat memoria și a
mutat costul pe procesor, pe cel mai prost fir posibil. Se vede în tabel: are cel
mai mic vârf de memorie dintre toate trei. Făcea exact munca potrivită — doar de
19.500 de ori mai des decât trebuia. Judecarea unui fix numai după metrica ce era
stricată e felul în care se produce incidentul următor.

**Schimbarea care conta nu apare în mesajul commit-ului.** Trecerea de la AND la OR
a venit într-un commit intitulat „Adaugare protectie la double-start + fix
redundanta". Redundanța din titlu e altceva:
`os.path.normpath(os.path.abspath(...))` devenit `os.path.abspath(...)`. Modificarea
care a reparat un bug și a creat altul nu e pomenită nicăieri. Peste un an, `git
log` e singurul index al depozitului ăstuia, iar schimbarea asta nu e în el — sau,
mai exact, n-a fost până acum.
