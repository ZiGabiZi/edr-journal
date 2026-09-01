---
title: Două axe de cunoaștere, nu trei stări
date: 2026-09-01
tip: decizie
rezumat: Depozitul de reputație întoarce două axe independente și un scor ordonat, nu o etichetă; se construiește în afara rețelei închise și se livrează ca fișier imutabil. Pragul de la R1 și starea inițială a depozitului se scriu acum, înainte să existe vreo cifră de acoperire.
tags: [reputatie, pdp, infrastructura]
capitol: "2.6"
componente: server
commits: []
teste: []
status: partial
---

## Context {#context}

Pasul P2.2 construiește depozitul de reputație: ce se știe despre un fișier
înainte ca protocolul să divulge ceva despre el. Tentația e să fie tratat ca
plumbărie — un tabel `sha256 → verdict`, o rută de interogare, gata — și ar fi
o citire greșită a propriei teze.

Afirmația centrală spune că **costul per endpoint scade pe măsură ce parcul
crește**. Mecanismul care face afirmația literalmente adevărată nu e banda de
incertitudine și nu sunt treptele: e depozitul. Un fișier escaladează o dată, pe
o mașină; toate celelalte endpoint-uri îl primesc la T0. Fără memorie partajată,
fiecare endpoint plătește escaladarea separat, iar costul per endpoint e
constant în dimensiunea parcului — adică afirmația principală devine falsă, nu
slabă.

Intrarea asta fixează forma depozitului înainte de prima linie de cod și
înainte de prima descărcare, din același motiv pentru care
[compoziția corpusului]({{ '/intrari/2026-09-01-corpusul-fixat-inainte-de-masuratoare/' | relative_url }})
a fost fixată înainte de prima măsurătoare.

**O notă de numerotare, ca să nu se contamineze două lucruri.** Deciziile de
aici se numesc **R1, R2, R3** — nu D1, D2, D3. Etichetele D* sunt deja luate
în `METRICS.md` §9.2–9.4, pentru numirea unei rulări, pentru ce descrie o cifră
implicit și pentru procesul unic; §9.5 chiar se referă la „(D3)" în proză. Două
seturi de decizii cu aceleași etichete, într-un contract sincronizat în ambele
repo-uri, ar fi a treia coliziune de nume din proiect și cea mai scumpă.

## Forța {#forta}

**Ce întoarce depozitul decide dacă 2.7 mai are obiect.**

Cu `{malițios, curat, necunoscut}`, regula de escaladare colapsează în
„escaladează dacă e necunoscut". Aia nu e o bandă de incertitudine, e un `if`.
Funcția de cost n-ar mai avea ce optimiza: trei puncte înseamnă un singur prag
posibil, deci niciun baleiaj de parametru și nicio curbă cost/divergență.
Rezultatul din capitolul 5 s-ar reduce la un punct, iar mecanismul, măsurat
cinstit, ar fi echivalent cu o listă de blocare.

**Dar un posterior calibrat pretinde mai mult decât are nevoie mecanismul.**

„Dintre fișierele cu scor 0,7, aproximativ 70% sunt malițioase" e o afirmație
tare, care cere validare separată și pe care o poate infirma oricine. Mai rău:
pentru un hash necunoscut, scorul ar veni dintr-un model, iar dacă modelul e
antrenat pe etichete, calitatea clasificatorului intră în afirmația lucrării —
exact cuplarea respinsă deja o dată.

**Iar RDS nu poate vorbi pe axa pe care ar fi convenabil să vorbească.**

`CORPUS.md` §5.4 e explicit: potrivirea în RDS nu poate produce verdictul
„curat", fiindcă RDS e o listă de software *cunoscut*, nu de software *bun*.
NIST avertizează el însuși că lista conține hash-uri ale unor aplicații care pot
fi considerate malițioase. Orice structură care obligă RDS-ul să se pronunțe pe
axa de amenințare minte la import.

## Alternative {#alternative}

**Trei stări într-un enum.** Respinsă. Colapsează un 2×2 și pierde tocmai
celula interesantă — fișierul prezent și în RDS, și într-o sursă de amenințări.
Cu un enum, celula aia trebuie să se prăbușească în altceva la import, iar
contorul de suprapunere devine imposibil de reconstruit după aceea.

**Posterior calibrat ca ieșire.** Respinsă ca precondiție, păstrată ca rezultat
opțional. Banda are nevoie doar de o axă continuă pe care alunecă un prag;
nimic din 2.7 nu depinde de interpretarea frecvențială. Calibrarea rămâne
posibilă mai târziu, ca o curbă de fiabilitate — dar atunci cere separare între
partea de corpus pe care calibrezi și cea pe care evaluezi, altfel e potrivire,
nu măsurătoare.

**Precedență aplicată la import.** Respinsă. Aplicată la import, distruge dovada
ireversibil; aplicată la derivare, e o linie de cod care se schimbă fără
reimport, deci fără instantaneu nou, deci fără invalidarea măsurătorilor de
dinainte.

**Depozitul replicat pe endpoint-uri.** Respinsă pentru montajul de măsurare.
Nu încape — 6–7 GB liberi în guest, din care mai trebuie să iasă agentul, coada
și lotul de corpus în lucru. Și, mai grav, cinci copii ale unui instantaneu nu
mai sunt un instantaneu: amprenta unică, pe care se sprijină tot pasul 3, își
pierde obiectul. Rămâne ca limitare declarată, nu ca implementare.

**Construirea depozitului pe server.** Respinsă. Construirea a zeci de milioane
de rânduri cu index cere sursa, baza în construcție și spațiu tranzitoriu
pentru index și `VACUUM` — la 2,5–3× dimensiunea finală, simultan. Un depozit
de 20 GB ar cere ~55 GB tranzitoriu din cei 66 liberi, pe o mașină care rulează
și serverul.

**Linia de bază măsurată prin transfer real.** Respinsă aritmetic, nu
metodologic: 5 × 26 GB ≈ 130 GB către un server cu 66 GB liberi — montajul nu
există fizic. Dar respingerea acoperă doar jumătate din problemă, și partea
cealaltă se vede abia citind `METRICS.md` cu atenție:

- **Numitorul** (§2) e definit contrafactual — „ce *ar fi* părăsit
  endpoint-ul" — deci se calculează din dimensiunile cunoscute. Zero octeți
  transferați. Aici respingerea e suficientă.
- **Oracolul** (§4.1) e definit ca *același motor de analiză alimentat cu
  fișierul integral*, adică sistemul rulat efectiv în modul `always_upload`.
  Aia nu e o cifră calculată, e o rulare. Dacă motorul ar sta pe server,
  fișierele ar trebui să ajungă acolo — exact cei 130 GB.

Ieșirea e deja în arhitectură: rulesetul coboară pe endpoint (§2.8), deci
același motor poate fi alimentat cu fișierul integral **local**, iar peste fir
trece doar verdictul. Oracolul se calculează unde stă fișierul, ceea ce e
chiar propoziția lucrării aplicată propriului montaj de măsurare.

`METRICS.md` §4.1 nu spune **unde** rulează modul `always_upload`. Ambiguitatea
e inofensivă azi și devine 130 GB la prima rulare completă, deci se închide în
contract, nu aici.

## Alegerea {#alegerea}

**1. Două axe independente, nu trei stări.**

|                              | în RDS                    | absent din RDS     |
|------------------------------|---------------------------|--------------------|
| **în sursă de amenințări**   | suprapunere — se numără   | cunoscut-malițios  |
| **absent**                   | cunoscut ca software      | necunoscut         |

Axa de amenințare (`known_malicious` / `not_known_malicious`) și axa de noutate
(`known_software` / `novel`) se stochează separat și se derivă separat. RDS
scrie doar pe a doua. Structura poartă limitarea din §5.4, în loc s-o
încredințeze unui comentariu.

**2. Interogarea nu întoarce niciodată un boolean și nu are valoare
implicită.** Întoarce ambele axe, iar apelantul e obligat să le trateze pe
amândouă. Separarea nu se impune prin două tabele — cineva scrie `LEFT JOIN` și
obține același lucru — ci prin tipul de retur.

**3. Ieșirea e un scor ordonat, cu semantică monotonă**, plus componentele din
care e compus (cunoscut/necunoscut, prevalență, viteză, clasă de cale). Mai
mare = mai probabil malițios. Atât cere banda. Fără revendicare frecvențială.

**4. Depozitul nu decide.** Furnizează dovadă; banda decide. Momentul în care
depozitul capătă un prag propriu e momentul în care 2.7 rămâne fără obiect și
există două mecanisme de decizie care se contrazic pe tăcute.

**5. R3 se dizolvă.** Ambele fapte se păstrează. La derivare, malițios câștigă
pe axa de amenințare, iar `known_software` rămâne adevărat pe axa de noutate.
Nu e un compromis — e ce spun cele două surse, fiecare despre ce știe. Contorul
de suprapunere iese gratis, ca interogare, nu ca instrumentare separată.

**6. R2 se rezolvă prin supra-import.** Familie unde există, primă observare,
sursă, plus un nume reprezentativ cu contor. Asimetria decide singură: costul
unei coloane nefolosite e spațiu; costul unei coloane lipsă e reimportul, adică
instantaneu nou, adică toate măsurătorile de dinainte descriu alt sistem.

**7. Hash-ul se stochează ca BLOB de 32 de octeți**, nu ca text hexazecimal.

**8. Depozitul e un fișier separat, cu versiune proprie și amprentă**, deschis
`mode=ro&immutable=1` la rulare. Fișierul livrat se produce cu `VACUUM INTO`,
în modul jurnal implicit: o bază lăsată în WAL nu se poate deschide read-only
fără drept de scriere, fiindcă cititorul are nevoie să creeze `-wal` și `-shm`.
Fără asta, „imutabil" e o intenție pe care prima deschidere o contrazice.

**9. Instantaneul se construiește în afara rețelei închise și se livrează ca
artefact.** Nu e doar economie de spațiu tranzitoriu: e chiar modelul de
operare pe care îl susține lucrarea. Într-un mediu izolat, o bază de reputație
nu se construiește înăuntru. E aceeași mișcare ca la coborârea rulesetului din
§2.8 — cunoașterea coboară ca datele să nu urce.

**10. Unealta de import aparține `edr-server`, deși rulează pe gazdă.** Schema
bazei pe care serverul o citește nu poate fi definită într-un repo care nu e al
serverului; prima schimbare de schemă ar călători separat de codul care o
citește. Locul rulării nu decide proprietatea.

**11. Fiecare rând poartă sursa din care a venit.** Astfel, selecția surselor
consultate e parametru de rulare, nu proprietate a depozitului — iar ablația
*rece* / *semiînzestrat* se face fără reimport și fără instantaneu nou.

**12. Starea inițială a depozitului e parametru pre-înregistrat.** Dacă ar fi
semiînzestrat cu hash-urile publice ale mostrelor, tot stratul malițios s-ar
închide la T0, raportul de divulgare ar ieși spectaculos și protocolul n-ar fi
făcut nimic. Diferența dintre rularea rece și cea semiînzestrată măsoară exact
cât din economie vine din reputație — artă anterioară — și cât din protocol.

## Pragul de la R1, scris înainte de cifre {#prag}

**Integral dacă instantaneul construit stă sub 20 GB ca fișier livrat; altfel
subsetul „pachete de sistem Windows", definit fără nicio referință la corpus.**

| | |
|---|---|
| liber în guest-ul de server (80 GB, ext4, 8,6 ocupat) | 66 GB |
| rezervă: SO, loguri, event store, spațiu de lucru | −6 GB |
| **disponibil** | **60 GB** |
| instantaneu curent + cel nou, coexistente la reimport | 2 × 20 = 40 GB |
| marjă rămasă | 20 GB (33%) |

Factorul 2 nu e prudență rotunjită: pasul 6 permite explicit **un** reimport
după verificarea de sănătate RDS, iar schimbul se face cu ambele versiuni pe
disc — altfel există o fereastră în care serverul n-are depozit. Ocuparea după
import rămâne la 36% din cei 80 GB, iar în timpul schimbului la 61%, sub linia
de 75% de la care ext4 începe să se fragmenteze vizibil.

Pe gazdă, două importuri înseamnă ~40 GB creștere a VM-ului de server, din
247,5 GB liberi. Endpoint-urile, fără instantaneu activ, sunt mărginite de
discul virtual de 20 GB — realist ~7 GB creștere fiecare, ~35 GB pentru toate
cinci, cu plafon dur la 100.

**De ce pragul se scrie acum:** după ce se vede dimensiunea reală a importului
și acoperirea peste manifest, orice prag ales e ales ca să treacă.

**Disciplina instantaneelor de mașină virtuală.** Cât timp un instantaneu e
activ, blocurile eliberate în guest rămân scrise în delta: ștergerea din
interior nu micșorează nimic pe gazdă. Cu instantanee active pe durata rulării,
delta fiecărui endpoint ar crește către tot ce s-a scris vreodată — ~26 GB, deși
în orice moment pe disc stau doar 4 GB. Cinci endpoint-uri × 26 GB ≈ 130 GB din
247,5: încape o dată, a doua rulare completă nu mai încape. Deci: instantaneele
se șterg înainte de import, **se așteaptă consolidarea deltelor** — care cere ea
însăși spațiu temporar pe gazdă — și abia apoi se copiază fișierul. Dacă se vrea
o plasă de siguranță, instantaneul se ia *după* import, când tot ce era mare
s-a scris deja în discul plat.

## Costul acceptat {#cost}

**Scorul nu se poate interpreta frecvențial.** Dacă cineva cere „ce înseamnă
0,7", răspunsul e „că e mai sus decât 0,6", nu o proporție. E o afirmație mai
slabă decât ar fi plăcut să se poată face.

**Amprenta acoperă fișierul livrat, nu procesul care l-a produs.** Reconstruirea
lui cere sursele externe, care se schimbă: versiuni de RDS se retrag, inventarul
MalwareBazaar se rotește. Se atenuează prin înregistrarea versiunii sursei la
import, nu se elimină.

**Pragul de 20 GB va forța probabil subsetul.** Un set complet de zeci de GB
cade, deci T0 va închide mai puțin decât ar putea, iar cifra din titlu va fi mai
mică. E o alegere făcută în avans, cu ochii deschiși: un prag care trece orice
n-ar fi o decizie, ar fi teatru.

**Depozitul stă doar pe server.** Montajul nu modelează un endpoint cu adevărat
deconectat, care ar trebui să decidă fără el. Rămâne limitare declarată în 2.6,
nu ceva ce se implementează.

**Două axe înseamnă mai mult cod decât un enum**, iar fiecare apelant plătește
obligația de a trata ambele.

## Ce rămâne pentru P2.3 {#urmeaza}

Registrul de prevalență — derivat din evenimente, cu ciclu de viață
incompatibil cu al depozitului importat, deci **nu se amprentează**: se declară
ca stare la începutul rulării, prin număr de hash-uri distincte și număr de
agenți. Fără distincția asta, `METRICS.md` §8 cere ceva imposibil pentru
jumătate din reputație. Prevalența se numără **pe agenți distincți, nu pe
evenimente** — o singură mașină care atinge un fișier de 500 de ori nu e un
parc, iar greșeala nu produce nicio eroare, doar o cifră greșită în direcția
favorabilă. Și intră în scor împreună cu vechimea, de la început: prezent pe
400 de mașini de trei luni ≠ apărut pe 50 de mașini în 10 minute.

Cheia verdictelor stocate: `(sha256, versiune_ruleset, treaptă_de_dovadă)`. Un
verdict obținut la T1 e o dovadă mai slabă decât unul obținut la T3; dacă se
stochează doar `hash → curat`, a doua oară o presupunere se întoarce ca fapt și
sistemul își spală propriul optimism.

Contractul de fir al răspunsului, funcția de agregare cu ponderi înghețate,
căutarea pe calea evenimentului.

**Notat acum, deși nu se implementează:** într-un deployment real, forma
naturală a listei e un filtru probabilistic, iar direcția erorii nu e simetrică.
Pe axa de noutate, un fals pozitiv declară cunoscut un fișier nou și suprimă
escaladarea — o ratare prin proiectare, exact ce interzice §5.4. Pe axa de
amenințare e acceptabil doar dacă apartenența *declanșează* escaladare, nu dacă
*produce* verdict. Permis pe o axă, interzis pe cealaltă.

## Ce am învățat {#invatat}

**Constrângerea care leagă rar e cea măsurată.** Serverul are 66 GB liberi,
ceea ce face ca aproape orice depozit să încapă — și, măsurat așa, pragul de la
R1 ar fi trecut orice. Ce leagă de fapt nu e rezultatul, ci spațiul tranzitoriu
al importului. Odată văzut, s-a dizolvat: construiești în altă parte și livrezi
fișierul. Constrângerea reală nu era cea pe care o măsuram, iar răspunsul n-a
fost un prag mai bun, ci un montaj care o elimină.

**O structură care poartă o limitare o respectă; un comentariu care o descrie e
respectat până la primul om grăbit.** §5.4 exista în text de la începutul
corpusului. Un enum de trei stări ar fi încălcat-o la primul import, fără să
mintă nimeni intenționat — pur și simplu n-ar fi avut unde să pună adevărul.
Cele două axe nu adaugă nicio regulă nouă; fac doar imposibilă exprimarea celei
false.
