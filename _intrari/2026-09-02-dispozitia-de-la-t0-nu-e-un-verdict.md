---
title: Dispoziția de la T0 nu e un verdict
date: 2026-09-02
tip: decizie
rezumat: Ce întoarce serverul la ingestia unui eveniment cu hash e o dispoziție de treaptă — cinci valori care enumeră 2×2-ul depozitului plus indisponibilitatea, în engleză ca tot vocabularul de fir — nu un verdict. Iar direcția descendentă a rutei de evenimente, nedeclarată în contract până acum, se declară înainte să poarte ceva.
tags: [pdp, contract, reputatie]
capitol: "2.4"
componente: ambele
commits: [edr-server@96bcbfc, edr-server@60ce429, edr-server@eab31a6, edr-server@bffd10c, edr-agent@52fa481, edr-agent@c786567, edr-agent@d04bdb2]
teste: [app/tests/test_event_contract.py::test_event_response_declares_every_stored_field, app/tests/test_event_hash_contract.py::test_sha256_with_whitespace_is_rejected_although_fromhex_would_accept_it, app/tests/test_reputation_disposition.py::test_a_hash_from_rds_is_known_software_and_never_a_benign_word, app/tests/test_reputation_disposition.py::test_an_unreachable_snapshot_is_not_unknown, app/tests/test_reputation_disposition.py::test_a_retransmission_keeps_the_disposition_of_the_first_arrival, app/tests/test_reputation_disposition.py::test_the_published_figure_carries_no_benign_term_and_no_closure_rate, app/tests/test_reputation_disposition.py::test_the_snapshot_is_warmed_at_startup_not_on_the_first_event]
status: rezolvat
---

## Context {#context}

P2.2 a construit depozitul de reputație. P2.3 îl pune în drum: la primirea unui
eveniment care poartă `sha256`, serverul îl consultă, persistă rezultatul lângă
eveniment și îl declară în răspuns.

Golul care definește pasul e ușor de verificat: **nimic nu apelează `lookup()`
pe calea evenimentului**. `receive_event` validează identitatea, verifică
existența agentului, persistă și întoarce `next_action: "none"`, codificat fix
în rută. Depozitul e cunoaștere moartă — niciun octet din el nu ajunge pe fir.

Miza nu e plumbăria. Afirmația din §L2.4 — divulgarea per endpoint scade cu
dimensiunea parcului — devine literalmente adevărată abia când al doilea
endpoint primește la T0 ce a plătit primul. Fără consultare la ingestie, P2.2 e
o bibliotecă frumoasă pe care n-o citește nimeni, iar mecanismul descris în
[intrarea despre cele două axe]({{ '/intrari/2026-09-01-doua-axe-de-cunoastere-nu-trei-stari/' | relative_url }})
rămâne o promisiune de structură.

Intrarea asta se scrie înainte de prima linie de cod, ca și cea de la P2.2. Iar
citirea codului dinaintea ei a schimbat ordinea pasului: **primul commit nu e
consultarea, e declararea răspunsului.**

**O notă de numerotare, a treia.** Deciziile de aici se numesc **F1–F11**, de la
*fir*. `D*` e luat de `METRICS.md` §9.2–9.4, `R*` de intrarea de reputație. A
treia coliziune de etichete într-un proiect cu documente sincronizate în două
repo-uri ar fi cea mai scumpă, fiindcă abia atunci ambiguitatea devine regulă,
nu accident.

## Forța {#forta}

**Cuvântul „verdict" cere mai mult decât produce T0.**

Formularea naturală a pasului — „serverul caută și întoarce verdictul" — e falsă
din două direcții pe care codul le apără deja. `CORPUS.md` §5.4: apartenența la
RDS nu poate produce „curat", deci pentru un hash cunoscut ca software răspunsul
nu are voie să fie un termen de benignitate. Și verdictele imuabile, legate de
conținut, cu cheia `(sha256, versiune_ruleset, treaptă_de_dovadă)`, sunt Etapa 3.
Ce produce T0 e *ce se știe la adâncimea T0*, nu o judecată finală. Confuzia
dintre ele e chiar „spălarea verdictului ieftin ca verdict scump", mutată de la
nivelul depozitului la nivelul protocolului.

**Slotul de fir e liber acum și scump mai târziu.**

`next_action` călătorește în fiecare răspuns și agentul nu-l consumă: îl primește
prin `parse_json_response` și îl aruncă. Semantica răspunsului se poate schimba
azi fără să rupă nimic pe partea de agent. E singura fereastră în care declararea
canalului costă un commit, nu o migrare.

**Dar canalul pe care urmează să circule primul mecanism vizibil al protocolului
nu e declarat de nimeni.**

`contracts/wire-contract.json` are șapte modele: cererea de înregistrare, cererea
de eveniment, cererea și răspunsul de heartbeat, directiva, și cele două blocuri
ale evenimentului. **Niciun răspuns de eveniment.** `next_action` e un câmp de fir
pe care niciun contract nu-l cunoaște, iar `EventResponse` din
`app/schemas/event.py` e cod mort: ruta întoarce un dict construit pe loc, deci
`test_wire_contract.py` n-are ce verifica.

Nota proprie a contractului despre `heartbeat_response` descrie exact ce se
întâmplă pe direcția asta: agentul citește cu `dict.get()`, deci un câmp
redenumit pe server nu produce nicio eroare, ci un `None` ignorat. Direcția aceea
măcar e declarată. A rutei de evenimente nu e.

**Iar distincția dintre „am întrebat și nu știe" și „n-am putut întreba" nu e
politețe.**

Dacă instantaneul lipsește sau nu se deschide, tentația e să se întoarcă
`unknown`. Contopite, o pană a depozitului arată **identic cu un corpus genuin
nou** — adică exact variabila de care depinde afirmația centrală. Un fișier lipsă
ar imita perfect brațul rece al ablației, fără nicio eroare vizibilă nicăieri.

## Alternative {#alternative}

**`verdict` ca nume de câmp.** Respinsă. Pe lângă §5.4, ar ocupa în avans numele
de care are nevoie Etapa 3, iar cheia de acolo — cu treapta de dovadă inclusă —
n-ar mai avea unde să se așeze fără o redenumire pe fir.

**Un enum de trei stări pe fir: `malicious | clean | unknown`.** Respinsă. Enumul
interzis la R1 în depozit s-ar întoarce pe ușa din dos, doar că pe legătură în
loc de în tabel. Interdicția structurală n-ar mai apăra nimic dacă ce iese din
structură se colapsează la ieșire.

**`unknown` pentru instantaneu indisponibil.** Respinsă, vezi F4. E singura
alegere din pasul ăsta care ar strica o cifră fără să producă niciun simptom.

**Respingerea evenimentului cu 5xx când reputația lipsește.** Respinsă. Ar cupla
disponibilitatea telemetriei de disponibilitatea reputației: coada agentului e
at-least-once (§1.3), deci ar reîncerca la nesfârșit un eveniment perfect valid,
iar o pană de reputație s-ar transforma într-o pană de colectare. Evenimentul se
acceptă; dispoziția spune cinstit că depozitul n-a putut fi întrebat.

**Dispoziția pe canalul de heartbeat, ca directivă.** Respinsă. Dispoziția e
despre un fișier, heartbeat-ul e despre agent; ar sosi ruptă de evenimentul care
a produs-o, iar corelarea ar cere un identificator în plus pe fir pentru ceva ce
răspunsul are deja gratis.

**Consultarea la citire, nu la ingestie.** Respinsă, și e aceeași formă de eroare
pe care `event_service` o descrie deja pentru eticheta de rulare: aplicată la
interogare, toate evenimentele din depozit ar migra spre instantaneul curent la
fiecare schimb, iar măsurătorile vechi și-ar schimba tăcut înțelesul. Un eveniment
aparține instantaneului în care a sosit.

**Identitatea completă a instantaneului pe fiecare eveniment.** Respinsă, vezi F8.
Nu e o chestiune de eleganță: `snapshot_identity()` cheamă `fingerprint()`, care
citește tot fișierul.

**Amânarea declarării răspunsului până când agentul chiar îl consumă.** Respinsă.
E argumentul care a ținut direcția asta nedeclarată până acum, și se
autoconsumă: canalul devine consumat exact în pasul în care începe să poarte
ceva, adică prea târziu ca declararea să mai fie gratis.

## Alegerea {#alegerea}

**F1. Ce întoarce T0 e o dispoziție de treaptă, nu un verdict.** Numele câmpului
e `disposition`, nu `verdict`. Spune ce se știe la adâncimea T0 și atât — nicio
escaladare, niciun scor, nicio bandă; alea sunt P2.6+.

**F2. Cinci valori care enumeră 2×2-ul, nu îl proiectează.**

| valoare | sursă | ce spune |
|---|---|---|
| `known_malicious` | `known_malicious`, absent din RDS | dovadă externă de amenințare; poartă proveniența |
| `known_software` | `known_software`, fără amenințare | prezent în RDS; **nu** înseamnă curat |
| `both_axes` | ambele axe adevărate | celula de suprapunere; se numără, nu se colapsează |
| `unknown` | `UNKNOWN` | candidatul T1 — rezultatul care justifică lucrarea |
| `reputation_unavailable` | instantaneul nu s-a putut deschide | depozitul n-a fost consultat |

Cele cinci valori sunt patru celule plus indisponibilitatea, adică o **bijecție
cu 2×2-ul**, nu o proiecție a lui. De aceea vocabularul nu reintroduce enumul
respins la R1: nu pierde nicio celulă. `both_axes` nu se prăbușește în
`known_malicious`, deși acțiunea de mai târziu va fi probabil aceeași — maparea
„ambele axe se tratează ca amenințare" aparține benzii (§L2.7), nu vocabularului.

**F3. Valorile sunt în engleză, ca tot vocabularul de fir.** `ok`, `unstable`,
`too_large`, `skipped_capacity`, `no_key`, `software`, `threat` — româna e limba
jurnalului și a comentariilor, nu a firului. `cunoscut_malitios` lângă
`hash_status: "ok"` în același payload ar fi o graniță de limbă imposibil de
mutat după ce agentul o consumă. `both_axes` refolosește deliberat numele
proprietății existente de pe `Knowledge`: același fapt nu are voie să aibă două
nume în două straturi — aceeași disciplină ca la `skipped_capacity` față de
`forced_reason`.

**F4. `reputation_unavailable` nu e `unknown`, iar evenimentul se acceptă
oricum.** `unknown` înseamnă „depozitul a fost consultat și nu știe" — un răspuns
cu conținut, cum e `UNKNOWN` în depozit. `reputation_unavailable` înseamnă
„depozitul n-a fost consultat". Contopite, otrăvesc metrica de închidere la T0 în
direcția care contează cel mai mult: mulțimea candidaților la T1 s-ar umple cu
fișiere despre care nimeni n-a întrebat nimic.

**F5. Niciun termen de benignitate pe fir, niciodată.** Nici cheie, nici valoare.
Se apără printr-un test-gardă pe formă, în stilul lui
`test_event_model_never_carries_file_content`: `clean|benign|safe|curat`
interzise în răspunsul rutei. Garda verifică forma numelui, nu semantica —
aceeași limitare declarată ca la garda de conținut.

**F6. Pe fir circulă dispoziția și, doar pe axa de amenințare, proveniența.**
`software_source` rămâne pe server: proveniența RDS nu poate justifica nicio
acțiune (§5.4), deci ar fi octeți plătiți ca să se spună „cunoscut, dar asta nu
înseamnă nimic". Amprenta instantaneului **nu** urcă pe fir: agentul n-are ce
face cu ea, iar `METRICS.md` §8 o cere lângă cifră, nu lângă răspuns.

```
"reputation": { "disposition": "known_malicious", "source": "malwarebazaar" }
```

**F7. Direcția descendentă se declară înainte să poarte ceva.** Primul commit al
pasului, cu zero schimbare de comportament: `event_create_response` intră în
contract cu exact câmpurile de azi (`message`, `event`, `next_action`), ruta
întoarce modelul declarat în loc de dict, `EventResponse` încetează să fie cod
mort, `contract_version` 5 → 6, `test_wire_contract.py` acoperă și direcția asta,
iar documentul se comite identic în ambele repo-uri în aceeași sesiune — regula
proprie a contractului. Abia după el, fiecare câmp adăugat la P2.3 e o schimbare
care pică un test dacă divergează.

**F8. Identitatea instantaneului se declară pe rulare, nu pe eveniment.**
`snapshot_identity()` cheamă `fingerprint()`, care citește tot fișierul în bucăți
de 1 MB — până la pragul de 20 GB fixat la R1 — și o face **ținând `_lock`**,
adică serializează toate consultările din proces. Un apel per eveniment ar
re-hash-ui instantaneul la fiecare fișier atins. Structural, identitatea nici nu e
o proprietate a evenimentului: conexiunea se deschide o dată per proces, iar
`immutable=1` e chiar promisiunea că fișierul nu se schimbă dedesubt. Deci:
identitatea completă, cu lista surselor, o dată pe rulare, lângă
`measurement_runs`; pe eveniment, cel mult amprenta de 64 de caractere. E același
argument ca la sursa stocată ca întreg în schema de reputație — ce e proprietate a
întregului nu se repetă pe fiecare rând.

**F9. La retransmisie, dispoziția e cea stocată, nu una proaspătă.**
`insert_event` întoarce rândul existent la conflict pe `client_event_id`, deci
dispoziția intră în payload **înainte** de insert, iar răspunsul se construiește
din evenimentul stocat, niciodată din variabila locală. Altfel o retransmisie
sosită după un schimb de instantaneu ar raporta altă dispoziție decât cea
persistată: același eveniment, două adevăruri, iar „închis la T0" nu se mai poate
reconstrui.

**F10. Hexul se validează în model, se decodează în serviciu.** Hex invalid e o
minciună de contract, nu incertitudine: 422. Nu introduce o clasă nouă de eșec —
câmpul `sha256` produce deja 422 prin invarianta v3 — deci obiecția
poison-message care a ținut `hash_status` fără validator la v3 nu se aplică aici:
atunci agentul curent omitea legitim câmpul, acum niciun agent corect nu emite hex
invalid. Verificarea de format stă lângă invarianta v3, în `EventCreateRequest`,
nu în rută: un singur loc decide ce e un `sha256` valid. Serviciul primește ceva
deja validat și face `bytes.fromhex`. Consultarea se face doar pe ramura
`hash_status == 'ok'`; invarianta v3 rămâne neatinsă.

**F11. `next_action` rămâne `"none"`.** Directivă și dispoziție sunt lucruri
diferite: dispoziția spune ce se știe, directiva cere o acțiune, iar directiva
aparține benzii și canalului de heartbeat. Două mecanisme de decizie în același
răspuns ar fi exact al doilea mecanism refuzat la R1.

## Ordinea, schimbată de ce am găsit în cod {#ordine}

1. **Declararea răspunsului** (F7). Contract v6, model folosit, test extins,
   ambele repo-uri. Zero comportament nou, verificabil prin diff pe fir.
2. **Granița** (F10). Format validat în model, decodare în serviciu.
3. **Consultarea la ingestie.** `lookup()` pe ramura `hash_status == 'ok'`,
   `ReputationStoreError` → `reputation_unavailable`, dispoziția în payload
   înainte de insert (F9), identitatea instantaneului la nivel de rulare (F8).
4. **Câmpurile de dispoziție în răspuns**, ca modificare a unui model **deja
   declarat**. Contract v7.
5. **Testele de sens**, nu de mecanică: hash din sursa de amenințări →
   `known_malicious` cu proveniență; hash din RDS → `known_software` și niciun
   termen de benignitate nicăieri în răspuns; hash absent → `unknown`; hash pe
   ambele axe → `both_axes`, necolapsat; eveniment fără `sha256` → nicio
   consultare și nicio dispoziție; instantaneu de neconsultat → eveniment
   acceptat, `reputation_unavailable`, distinct de `unknown`; retransmisie după
   schimb de instantaneu → dispoziția primei sosiri.
6. **Criteriul de ieșire**, reformulat: pe un server cu instantaneu
   semiînzestrat, un eveniment cu hash cunoscut-malițios se închide la T0, cu
   dispoziția în răspuns și zero octeți **ascendenți** suplimentari; un hash
   absent primește explicit `unknown`, persistat și interogabil per rulare,
   lângă amprenta instantaneului care a răspuns.

Granița hex era pasul 2 în planul inițial. A coborât nu pentru că e mai puțin
importantă, ci pentru că e aditivă: se poate face oricând. Declararea răspunsului
e singurul pas care devine mai scump cu fiecare câmp adăugat înaintea lui.

## Costul acceptat {#cost}

**Direcția descendentă rămâne nemăsurată, iar criteriul de ieșire trebuie să
spună asta.** `wire_middleware` citește `Content-Length` al **cererii**, iar
`wire_accounting` numără doar octeți primiți. Câmpurile noi de răspuns nu trec
prin niciun registru. Un criteriu formulat ca „zero octeți de divulgare
suplimentară în registru" ar fi adevărat prin orbire, nu prin proiectare — exact
genul de cifră refuzat la §2.1 și §3.3. Deci se scrie „zero octeți ascendenți",
iar direcția descendentă rămâne gol declarat: câteva zeci de octeți per eveniment
de fișier, necontabilizați. Contabilizarea ei e alt pas, nu ăsta.

**Dispoziția e o cifră despre depozit, nu despre fișier.** `unknown` la T0
înseamnă că instantaneul nu-l știe, nu că fișierul e nou în parc — prevalența nu
există încă. Deci „T0 închide X%" măsoară în bună parte acoperirea
instantaneului, adică exact ce trebuie să separe ablația rece/semiînzestrat. Nu
se publică niciodată fără identitatea instantaneului (`METRICS.md` §8).

**Apare un al doilea sens pentru „închis la T0", lângă tabelul din
`METRICS.md` §3.4.** Numitorul tabelului pe trepte e `events_with_tier`, adică ce
declară **agentul** în blocul `disclosure`; dispoziția e ce conchide **serverul**.
Cele două pot diverge — un eveniment care poartă treapta T0 și primește
`unknown` a divulgat la T0 fără să se închidă acolo. Nu se adună și nu se
confundă: tabelul pe trepte rămâne despre octeți divulgați, închiderea la T0 e o
cifră separată, cu numitorul ei propriu (evenimentele cu `sha256` și
`hash_status == 'ok'`), publicată alături. §3.4 vorbește deja despre „procentul
de verdicte închise acolo" — până acum nimic nu măsura închiderea, deci fraza
n-avea referent; de la P2.3 are doi, și trebuie ținuți separați.

**Un contract nou pentru zero comportament.** F7 cere `contract_version` 6 și un
commit în ambele repo-uri fără ca vreun octet de pe fir să se schimbe. E cost
pur, plătit acum fiindcă e singurul moment când e mic.

**Dispoziția stă în payload-ul JSON al evenimentului**, deci „interogabil per
rulare" înseamnă scanare, nu index — depozitul de evenimente are coloane doar
pentru `run_id`, `agent_id`, `client_event_id` și `received_at`. Acceptat: dacă
cifra devine scumpă, răspunsul e un tabel derivat, nu o coloană nouă. Payload-ul
rămâne singurul adevăr.

## Amendament: ce a ieșit {#schimbat}

Intrarea a fost scrisă înainte de prima linie de cod. Cinci din cei șase pași
sunt livrați, în trei versiuni de contract — v6 declară răspunsul, v7 impune
forma hash-ului, v8 aduce dispoziția. Ce urmează e diferența dintre ce prezicea
intrarea și ce a ieșit.

**Pașii 3 și 4 nu s-au putut separa, iar asta e o veste bună.** Intrarea îi
enumeră ca etape distincte: întâi consultarea și persistarea, apoi câmpurile în
răspuns. În practică, în clipa în care dispoziția a intrat în payload, suita a
picat cu exact un test — garda scrisă la v6, care cere ca evenimentul stocat și
modelul de răspuns să declare aceleași câmpuri. Separarea era imposibilă prin
construcție. Nu e o scăpare a planului, ci proprietatea pe care F7 o cumpărase
fără să o numească: „persistat pe server" și „declarat pe fir" nu mai pot
diverge. Singura excepție rămâne amprenta instantaneului, și tocmai de aceea nu
se persistă pe eveniment.

**`EventResponse` îi lipsea `run_id`, iar intrarea n-a văzut asta.** F7 spunea
că modelul încetează să fie cod mort și că adoptarea lui nu schimbă niciun octet
pe fir. A doua jumătate era falsă și s-a văzut abia la implementare: ruta trimite
`run_id` de la 1.4.2 încoace, modelul nu-l declara, iar un model de răspuns
filtrează, nu completează. Adoptat literal, commit-ul care promitea „zero
schimbare" ar fi șters un câmp de pe fir. Promisiunea s-a păstrat verificând-o,
nu afirmând-o: răspunsul nou a fost comparat octet cu octet cu corpul produs de
dicționarul de dinainte.

**Două decizii au apărut la implementare, fiindcă intrarea nu acoperea cazul.**
Prima: majusculele în `sha256`. F10 fixa formatul, nu și notația. Se acceptă și
se coboară la minuscule — sunt același hash scris altfel, deci un 422 ar șterge
din spool un eveniment corect, dar șirul se și stochează, iar prevalența se
numără pe hash-uri distincte, unde două scrieri ale aceluiași hash ar deveni
două fișiere. A doua: `reputation` e interzis pe cerere. Dispoziția se produce pe
server; un endpoint care și-ar declara singur reputația ar face memoria
partajată să depindă de ce afirmă mașina observată.

**Argumentul de la F8 era corect, dar socoteala era incompletă.** Intrarea a
mutat identitatea instantaneului la nivel de rulare fiindcă
`snapshot_identity()` recitește tot fișierul. Adevărat — dar `_connection_locked()`
îl mai amprenta o dată, pentru linia de log de la deschidere. Primul eveniment cu
hash al unei rulări ar fi hash-uit 3,06 GB de **două** ori, ținând lacătul global
de fiecare dată. Amprenta se calculează acum o dată per instantaneu deschis, ceea
ce `immutable=1` garanta oricum: a doua citire a acelorași octeți nu poate da alt
răspuns.

**Și un gol pe care intrarea nu-l vedea deloc: suita citea instantaneul de
producție.** Calea implicită e `storage/reputation.db`, iar acolo stau 3,28 GB
reali. Fără izolare, fiecare deschidere din teste ar fi amprentat fișierul acela,
iar un test care afirmă „hash absent → `unknown`" ar fi trecut pe o mașină și ar
fi picat pe alta — cifra n-ar mai fi fost despre cod. Suita arată acum spre un
fișier inexistent, deci implicitul ei e `reputation_unavailable`, iar testele
care au nevoie de răspunsuri își construiesc propriul instantaneu. Aceeași formă
de greșeală ca la P2.2, unde mutarea construirii în afara serverului rezolvase
problema spațiului fără s-o bugeteze la noua adresă: o decizie corectă despre
producție, nedusă până la montajul care o măsoară.

**Ce s-a confirmat.** F9 nu era o precauție teoretică: mutând o singură linie —
răspunsul construit din consultarea proaspătă în loc de din evenimentul stocat —
testul de retransmisie devine roșu, deci invarianta chiar se poate rupe tăcut și
chiar e păzită. Vocabularul a rămas exact cel din tabel, cu numele englezești.

**Ce rămânea, și de ce intrarea a stat pe `partial`.** Pasul 6, criteriul de
ieșire: o rulare pe instantaneu semiînzestrat, cu cifra de închidere la T0 lângă
amprentă. Serverul nu avea încă niciun contor publicat — dispoziția era
interogabilă prin fluxul de evenimente și prin `run_reputation`, dar nu agregată.
Împreună cu ea rămânea deschisă și distincția din secțiunea de cost: „închis la
T0" înseamnă de acum două lucruri, unul declarat de agent prin treaptă și unul
conchis de server prin dispoziție, iar cifra care se publică trebuie să spună
care dintre ele e.

## Al doilea amendament: criteriul de ieșire {#criteriu}

**Criteriul a fost rulat pe instantaneul real**, nu pe unul de test:
72.029.536 de rânduri, NSRL RDS `2026.03.1` plus inventarul MalwareBazaar,
amprenta `6567fc31a629b9b8…` — brațul semiînzestrat al ablației. Trei
evenimente, fiecare cu treapta T0 și zero octeți de conținut:

| hash | dispoziție | proveniență | latență |
|---|---|---|---|
| din MalwareBazaar (familia Quakbot) | `known_malicious` | `MalwareBazaar` | 13 ms |
| din NSRL RDS | `known_software` | `None` | 9 ms |
| absent din ambele | `unknown` | `None` | 13 ms |

`next_action` a rămas `"none"` la toate trei: dispoziția a călătorit pe răspunsul
aceleiași cereri. Pe canalul de evenimente s-au măsurat **1092 de octeți pentru
trei mesaje**, iar `control`, `enrollment` și `other` au rămas la zero — nicio
cerere suplimentară n-a existat, deci închiderea la T0 a costat exact evenimentul
T0. Cu asta, jumătatea de citire a propoziției „un fișier escaladează o dată,
parcul primește la T0" are prima ei demonstrație pe date reale.

Celula de suprapunere e goală și aici, ca la P2.2.6: `both_axes` are contorul
zero. E o observație corectă despre instantaneul de azi, nu un rând lipsă — dar
înseamnă și că singura acoperire a acelei ramuri de cod vine din instantaneul
sintetic al suitei.

**Cifra publicată nu conține o rată de închidere, deliberat.** `GET
/api/metrics/disclosure` capătă secțiunea `reputation`, cu cele cinci contoare,
numitorul `events_with_hash` și instantaneele consemnate. Nu și un procent de
„închis la T0": ar cere maparea dispoziție → închis, care e chiar decizia benzii
(§L2.7). Cazul care o face nebanală e `known_software` — numărat ca închis, cifra
ar spăla apartenența la RDS drept verdict de benignitate, pe ușa din dos a unei
metrici, după ce structura depozitului a închis-o pe cea din față. Cine vrea rata
o compune declarând ce a numărat ca închis.

**Și criteriul a scos la iveală un defect pe care niciun test nu-l putea vedea.**
Prima rulare a arătat 8349 ms pe primul eveniment: amprentarea celor 3,28 GB,
calculată leneș, cădea pe calea de ingestie. Timeout-ul agentului e de 5 secunde,
deci primul eveniment cu hash al FIECĂREI porniri de server expira garantat. Nu
se pierdea nimic — un timeout nu e 4xx, deci coada îl reia — dar cererea expirată
ajunsese deja la server și fusese cântărită de middleware, așa că fiecare pornire
injecta o retransmisie în numărătorul măsurat al afirmației principale. Mică,
sistematică, produsă de noi. Mutată în `lifespan`, secundele se plătesc unde nu
așteaptă nimeni: 8349 ms → 13 ms.

Lecția e mai generală decât reparația. F8 a mutat costul de la per-eveniment la
per-rulare pe un argument corect, iar suita l-a confirmat — pe un instantaneu
gol, unde amprentarea e instantanee. Costul rămas, o dată per proces, a devenit
vizibil abia la 3,28 GB. Un montaj de test care e mai mic decât realitatea nu
măsoară greșit, ci nu măsoară deloc constrângerea; e aceeași formă cu spațiul
tranzitoriu de la P2.2, mutat de pe disc pe ceas.

**Ce NU demonstrează criteriul.** Trei evenimente sintetice pe o mașină, nu o
măsurătoare. Afirmația de la §3.1 — costul marginal al celui de-al `N`-lea
endpoint — cere endpoint-uri adăugate eșalonat și corpusul întreg, iar §2.12
fixează montajul. Ce s-a demonstrat aici e că mecanismul există și că răspunsul
nu costă octeți ascendenți în plus; cât economisește parcul rămâne de măsurat.

Rămâne deschis, în afara acestui pas: banda de incertitudine, care va da în
sfârșit un sens lui „închis"; contabilizarea direcției descendente, declarată ca
gol în secțiunea de cost; și mașina de stări per fișier, de la Etapa 3.

## Ce am învățat {#invatat}

**Contractul a crescut unde greșelile erau vizibile, nu unde erau scumpe.**
Direcția agent → server are `WireModel`, care loghează orice cheie necunoscută;
direcția server → agent n-are nimic, fiindcă agentul citește cu `dict.get()` și
nu se plânge niciodată. Ambele erau cunoscute — nota despre `heartbeat_response`
o spune explicit. Și totuși singura direcție rămasă complet nedeclarată e cea a
rutei prin care urmează să treacă primul mecanism al protocolului. Un canal pe
care nimeni nu-l consumă e un canal pe care nimeni nu-l declară, exact până în
clipa în care începe să poarte ceva.

**O stare care numește propria absență e ce ține celelalte stări măsurabile.**
`UNKNOWN` e un răspuns cu conținut doar atâta timp cât există un alt nume pentru
„n-am putut întreba". Fără `reputation_unavailable`, `unknown` ar aduna două
lucruri și n-ar mai putea fi numărat pentru niciunul — nu fiindcă ar minți
cineva, ci fiindcă n-ar avea unde pune adevărul. E aceeași formă de argument ca
la cele două axe, mutată de la structura depozitului la vocabularul firului.

**Costul unei funcții se citește la locul apelului, nu la definiție.**
`snapshot_identity()` e corectă și ieftină o dată pe rulare; aceeași funcție,
chemată per eveniment, re-hash-uiește 3 GB ținând lacătul global. Nimic din
numele ei nu spune asta. Planul o cerea „lângă fiecare eveniment" și suna
rezonabil până la prima citire a implementării.
