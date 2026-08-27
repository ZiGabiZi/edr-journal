---
title: Fișierul scris continuu nu ieșea niciodată
date: 2026-08-20
tip: corectie
rezumat: Debouncer-ul răspundea la „am mai văzut asta recent?", dar analiza unui fișier are nevoie de răspuns la „s-a terminat de scris?". Garda rearma fereastra și pe calea suprimată, deci un fișier scris continuu nu era raportat niciodată — iar evenimentul pierdut era ultimul, singurul în care fișierul e complet.
tags: [detectie, concurenta, pdp]
capitol: "3.1"
componente: agent
commits: [edr-agent@9ac99ea, edr-agent@a9a8f0b]
teste: [tests/test_settle_tracker.py::test_continuous_writes_are_released_only_after_they_stop, tests/test_settle_tracker.py::test_endless_writes_are_released_at_the_ceiling, tests/test_settle_tracker.py::test_capacity_overflow_releases_early_instead_of_dropping, tests/test_settle_tracker.py::test_a_file_touched_again_after_release_opens_a_new_entry, tests/test_settle_releaser.py::test_the_releaser_never_builds_a_payload, tests/test_settle_releaser.py::test_drain_hands_over_everything_still_waiting]
status: rezolvat
---

## Decizia originală {#originala}

`EventDebouncer`, introdus în iunie și reparat de două ori de atunci: un filtru
care răspunde la întrebarea *am mai văzut `(tip, cale)` în ultimele două
secunde?* Dacă da, evenimentul se suprimă.

Mecanismul a primit deja două intrări în jurnal. Prima, pe
[garda care nu pornea niciodată]({{ '/intrari/2026-06-25-curatarea-care-nu-pornea-niciodata/' | relative_url }}),
a reparat curățarea periodică. A doua, pe
[al doilea mecanism]({{ '/intrari/2026-08-04-al-doilea-mecanism-nu-inca-o-clauza/' | relative_url }}),
i-a adăugat un plafon dur de capacitate cu evacuare LRU, plus testele care
lipseau cu totul.

Ambele intrări au tratat mecanismul ca fiind corect și implementarea ca fiind
de reglat.

## Raționamentul de atunci {#rationament}

`watchdog` emite mai multe notificări pentru o singură scriere logică. Un
fișier copiat produce un `created` urmat de un șir de `modified`; un editor care
salvează produce trei-patru evenimente pentru un `Ctrl+S`. Trimise toate,
serverul ar fi primit zgomot în locul faptelor.

Deduplicarea pe fereastră scurtă e răspunsul evident, și era răspunsul corect
la întrebarea pe care o punea. Pe evenimente izolate — un fișier apare, un
fișier e șters — filtrul funcționa exact cum trebuia, iar testele din 4 august
o confirmau.

Întrebarea era greșită, nu răspunsul.

## Ce nu vedeam {#gol}

**`is_duplicate()` rearma fereastra la fiecare apel, inclusiv pe calea
suprimată.** Ceasul se rescria înainte ca funcția să întoarcă „da, e duplicat".

Consecința, pe un fișier scris continuu — o descărcare, un log activ, o arhivă
care se dezarhivează:

| moment | observație | fereastră | rezultat |
|---|---|---|---|
| 0,0 s | `created` | se deschide | **raportat** |
| 0,8 s | `modified` | rearmată | suprimat |
| 1,5 s | `modified` | rearmată | suprimat |
| … | … | rearmată | suprimat |
| 40,0 s | `modified`, ultimul | rearmată | suprimat |

Fișierul e raportat o singură dată, la 0,0 s, când are zero octeți. Tot restul
se suprimă, iar **evenimentul pierdut e ultimul** — exact acela în care fișierul
e complet. Mecanismul nu raporta prea puțin; raporta fix versiunea inutilă.

Al doilea gol, mai mic: cheile separate pe `(tip, cale)` lăsau un fișier creat
și imediat scris să treacă de două ori. Un `created` și un `modified` la 50 ms
distanță sunt două intrări diferite în dicționar, deci nici măcar deduplicarea
pentru care exista clasa nu era completă.

**Ce a scos golul la iveală a fost treapta T0.** Cât timp agentul raporta doar
*că* a apărut un fișier, un eveniment prematur era o imprecizie. Din momentul în
care raportează *ce* a apărut, prematur înseamnă un SHA-256 calculat pe un
fișier pe jumătate scris — adică o amprentă corect calculată a unui lucru care
nu a existat niciodată. Un hash greșit e mai rău decât niciun hash: al doilea se
vede, primul nu.

Iar întrebarea *s-a terminat de scris?* nu se poate deduce din prezența
observațiilor. Se deduce din **absența** lor, iar un filtru nu are cum să
observe o absență: el rulează doar când e chemat, adică doar când există un
eveniment.

## Ce am schimbat {#schimbat}

`SettleTracker` — un **planificator, nu un filtru**. Diferența nu e de
implementare, e de rol: filtrul decide despre evenimentul din mână, planificatorul
deține politica de timp și decide singur când ceva a devenit gata.

```
watchdog  -> handler.observe()   (fir observer, revine imediat, fără I/O)
releaser  -> tracker.due()       (fir propriu, la 0,25 s)
```

`observe()` doar înregistrează și revine — rulează pe firul observer-ului
`watchdog`, unde orice poate dura sau eșua e interzis. `due()`, apelat de un fir
propriu, colectează ce s-a liniștit. Fără callback, fără I/O.

Restul deciziilor, fiecare cu un motiv:

- **Cheia e calea, nu `(tip, cale)`.** Un fișier creat și apoi scris de opt ori
  e o singură sosire. Tipul rămâne al observației care a deschis intrarea.
- **Plafon dur de așteptare.** Fără el, un log activ n-ar fi raportat niciodată
  — același bug în haine noi. Orice mecanism de suprimare fără termen-limită
  poate suprima pentru totdeauna.
- **Două ceasuri, deliberat.** Monoton pentru durate, imun la salturi NTP; ceas
  de perete doar pentru `occurred_at`, consultat exact o dată.
- **`occurred_at` e prima observație**, transmis explicit builder-ului. Calculat
  la emitere, ar fi fost momentul raportării, nu al faptului, iar serverul ar fi
  ordonat greșit — exact ce previne câmpul.
- **`settle_wait_ms` se populează sub `measurements`.** E latența introdusă de
  mecanism, nu durata scrierii. Fără ea, perioada de liniște s-ar calibra din
  burtă în loc de pe date reale.

Legarea în fluxul real a venit separat, cu o consecință care nu exista înainte:
`due()` **scoate** intrarea din tracker, iar fișierul s-a liniștit, deci niciun
eveniment `watchdog` nu-l mai regenerează. Un eșec de callback, până atunci
pierdere temporară care se repara singură la următoarea scriere, devenea
pierdere definitivă. De aceea un payload nelivrat se reține și se reîncearcă,
construit **o singură dată**, ca `client_event_id` să rămână stabil și
deduplicarea at-least-once a spool-ului să rămână valabilă.

**Costul, plătit conștient: raportarea întârzie cu aproximativ o secundă.** E
prețul raportării fișierului complet în locul unuia pe jumătate scris. Fără el
nu există hash corect, deci nu există treaptă de bază.

## Ce a rămas valid {#ramas}

**Lecția mărginirii memoriei, transplantată cu compromisul inversat.** Plafonul
scris pe 4 august nu s-a pierdut; s-a mutat, și și-a schimbat semnul:

| | `EventDebouncer` | `SettleTracker` |
|---|---|---|
| întrebarea | am mai văzut asta recent? | s-a terminat de scris? |
| rolul | filtru | planificator |
| la depășirea plafonului | evacuează cea mai veche | **eliberează forțat** cea mai veche |
| ce produce presiunea | un duplicat | o raportare prematură |
| ordinea în `OrderedDict` | ultima apariție (`move_to_end`) | prima apariție, **fără** `move_to_end` |

Aceeași structură de date, semantică opusă — și pentru un motiv care se citește
direct din tabel. La debouncer, pierderea unei chei dădea un duplicat, recuperabil
pe server. La tracker, ar da un **eveniment pierdut**. Compromisul se inversează
ca presiunea de memorie să devină raportare prematură, niciodată tăcere.

Ceea ce înseamnă că `move_to_end` — linia care în august avea un test doar al ei,
verificat prin ștergere — trebuie acum să lipsească, la fel de deliberat cum
atunci trebuia să existe. Nu e o regresie față de intrarea precedentă; e aceeași
regulă aplicată unei întrebări cu semnul schimbat.

**Plafonul de așteptare e lecția din iunie, generalizată.** În iunie problema era
o gardă care nu pornea niciodată; aici, un mecanism de suprimare care ar putea
suprima la nesfârșit. Amândouă sunt aceeași greșeală: un mecanism a cărui
condiție de ieșire nu e garantată.

**`EventDebouncer` a dispărut cu tot cu testele lui.** Cele 373 de linii de test
scrise pe 4 august au fost șterse odată cu clasa. Păstrate, ar fi rămas cod mort
cu teste verzi — adică impresia falsă că ceva e păzit. Derivarea trăiește acum în
docstring-urile tracker-ului, unde se citește lângă mecanismul pe care îl explică.
