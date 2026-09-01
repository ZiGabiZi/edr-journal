---
title: Ce pretinde lucrarea, și ce ar dovedi că mă înșel
date: 2026-08-27
tip: decizie
rezumat: Propoziția de contribuție fixată înaintea mecanismului de escaladare, împreună cu criteriile care ar infirma-o.
tags: [pdp, observabilitate]
capitol: "2.4"
componente: ambele
commits: [edr-server@d39c220]
teste: []
status: partial
---

## Context {#context}

Etapa 0 din planul de implementare a PDP-ului s-a încheiat: agentul produce o
amprentă în care pot avea încredere, la momentul potrivit, cu vocabular pentru
fiecare cale de eșec. Serverul primește amprenta și raportează, prin
`/api/metrics/disclosure`, un raport de ~567× față de un sistem always-upload.

Cifra e calculată corect și nu răspunde la nicio întrebare.

444 de fișiere, 143,1 MiB, adică aproximativ 322 KB pe fișier. Un eveniment
serializat are câteva sute de octeți. Raportul de 567× este, cu aproximație
bună, dimensiunea medie a metadatelor împărțită la dimensiunea medie a
fișierului. **Un sistem fără niciun protocol de divulgare — care raportează doar
amprente și nu escaladează niciodată — ar produce exact aceeași cifră.** Iar
dacă pun un ISO de 4 GB în directorul monitorizat, devine 20.000×, fără ca
protocolul să se fi schimbat.

Am măsurat înainte să decid ce pretind. Urmează să construiesc banda de
incertitudine și treptele T1–T3, iar ce se instrumentează acum decide ce se
poate măsura la final: `file_size` a fost impus prin contract cu doi pași
înainte să existe hashing, și e singurul motiv pentru care raportul se poate
calcula azi. Aceeași disciplină cere ca propoziția să existe înaintea
mecanismului care o servește.

## Forța {#forta}

Patru tensiuni, fiecare cu o alegere care închide o ușă.

**Afirmația tare împotriva mecanismului.** Aș vrea să pretind că verdictele sunt
identice cu cele ale analizei complete. Dar banda de incertitudine e, prin
definiție, un pariu: când divulgarea se oprește, sistemul nu *știe* că analiza
completă ar fi spus același lucru — o presupune, pe baza incertitudinii rămase.
O afirmație pe care mecanismul o garantează prin construcție ar însemna că
mecanismul nu decide nimic.

**Calitatea absolută împotriva calității relative.** Aș putea pretinde rate de
detecție bune. Dar ele depind de cât de bun e rulesetul meu YARA, unde nu am
cum să concurez cu motoare antrenate pe ani de date. O rată mediocră ar
compromite o teză care n-are nicio legătură cu ea.

**Fișierul împotriva parcului.** Afirmația per fișier se măsoară pe o singură
mașină și e ușor de apărat. Afirmația per parc cere un montaj pe care nu-l am —
dar deduplicarea și escaladarea conștientă de prevalență, pe care le-am numit
contribuții, există *numai* acolo. Pe un singur endpoint nu pot demonstra
niciuna.

**Mecanismul T2 acum împotriva mecanismului T2 pe date.** Selecția adaptivă a
interogării e partea cu cea mai puțină artă anterioară. Dar nu știu încă dacă e
necesară — asta depinde de ce fracțiune din corpus e efectiv nedecidabilă, iar
distribuția aia se măsoară abia la Etapa 2, prima care trece corpusul prin motor.
Iar dacă fixez acum forma cererii ca pachet predefinit, ușa se închide.

## Alternative {#alternative}

**Echivalență universală — „verdictele sunt întotdeauna identice".** Respinsă ca
imposibilă, nu ca riscantă. Singura calibrare care garantează verdicte identice
e cea care escaladează totul la T3, adică exact always-upload. Afirmația e falsă
sau vidă.

**Prag procentual — „divergență sub X%".** Respinsă pentru că X s-ar alege după
ce văd datele, și pentru că nu e măsurabil onest la scara corpusului meu: pe 200
de mostre malițioase, diferența dintre 0,5% și 1,5% e sub zgomotul măsurătorii.
În plus, un scalar ascunde direcția — 3% divergență poate însemna malware ratat
sau alarme false, iar cele două nu se compară.

**Calitatea absolută ca afirmație.** Respinsă pentru că ar cupla teza de
calitatea rulesetului. TPR și FPR față de etichetele reale rămân în lucrare, dar
ca **context**, nu ca afirmație.

**Fișierul ca unitate principală.** Respinsă pentru că e adevărată și aproape
banală: o amprentă are 32 de octeți, un fișier are megaocteți. Rămâne ca
afirmație de sprijin.

**Scara fixă, decisă acum.** Respinsă pentru că ar închide selecția adaptivă
înainte să existe datele care ar spune dacă e necesară.

## Alegerea {#alegerea}

Propoziția de contribuție:

> Analiza statică distribuită între endpoint și server poate fi organizată ca
> achiziție secvențială guvernată de incertitudine, astfel încât costul per
> endpoint să scadă pe măsură ce parcul crește, iar la o calibrare identificată
> verdictele să coincidă cu cele ale aceluiași motor alimentat cu fișierele
> integrale.

Cuantificatorul e **existențial, nu universal**: *există* o calibrare la care
verdictele coincid. Frontiera dintre octeți transferați și divergență se
raportează ca rezultat, obținută prin baleiajul parametrului de cost — nu ca
avertisment în subsol.

**Oracolul e același motor alimentat cu fișierele integrale**, nu eticheta
reală. Poate greși; tocmai de aceea afirmația e independentă de calitatea
rulesetului. Orice divergență e, prin construcție, o eroare de calibrare a
benzii, adică exact obiectul lucrării. Asta funcționează doar pentru că
baseline-ul e un **mod comutabil pe același drum de cod**: cu două
implementări separate, comparația ar fi confundată de diferențele dintre ele.

**Divergența se numără pe direcții.** Malițios→curat e malware ratat.
Curat→malițios e timp de analist irosit. Contopite, metrica ascunde exact ce
contează, iar funcția de cost le ponderează asimetric.

**Abținerea are coloană proprie.** Un fișier care epuizează plafonul de
divulgare fără verdict nu e nici acord, nici dezacord. Numărat ca dezacord ar
umfla divergența; ignorat, ar ascunde cazuri ratate.

**Parcul e afirmația principală, fișierul e sprijinul.** Ordinea decide ce apăr
la susținere și în jurul cărui lucru se scrie 2.4.

**Cererea de escaladare poartă un descriptor de regiune, nu un identificator de
pachet.** Mecanismul de selecție nu se fixează în propoziție. Selecția fixă se
implementează prima, iar cea adaptivă devine un al treilea mod de politică pe
același drum de cod — deci comparația fix-vs-adaptiv devine încă o figură în
evaluare, măsurată exact ca baseline-ul. Dacă adaptivul nu apucă să fie
implementat, rămâne direcție viitoare argumentată, nu lipsă.

### Ce ar dovedi că mă înșel

**Afirmația e falsă dacă divergența zero costă cât always-upload.** Dacă singura
calibrare fără divergență e cea care urcă tot, afirmația existențială moare.

**Afirmația principală e falsă dacă curba nu coboară cu parcul.** Costul per
endpoint măsurat la 1, 5, 20 și 50 de agenți: dacă rămâne plat, deduplicarea și
prevalența nu produc nimic. Criteriul e direcția curbei, nu un prag.

**Protocolul e inutilizabil dacă apar ratări malițios→curat la punctul de
funcționare declarat.** Pragul e **zero**, exprimat ca număr, nu ca procent:
regiunea utilizabilă a frontierei e zona fără nicio ratare. Restul curbei se
raportează ca informație — „dincolo de aici, fiecare procent suplimentar de
economie costă N ratări" — dar marcat explicit ca fiind în afara ei.

Zero ratări pe un corpus finit nu înseamnă zero ratări în general. Formularea
onestă e o margine superioară: la zero eșecuri în N încercări, rata reală se
poate susține doar sub aproximativ 3/N. Pentru „sub 1%" e nevoie de cel puțin
300 de mostre malițioase — ceea ce face din asta o cerință a corpusului, nu o
alegere liberă.

**Două criterii rămân neinstanțiate.** Sub ce procent de fișiere ajunse la T2
afirmația devine trivială, și peste ce rată de abținere protocolul devine
inutilizabil. Amândouă au nevoie de distribuția reală, măsurată la Etapa 2. Le
las declarate și fără prag, deliberat: un prag ales acum ar fi ghicit, iar unul
ales după măsurătoare ar fi ales ca să treacă.

### O predicție, nu un criteriu

Sub un prag de dimensiune, protocolul transferă **mai mult** decât
always-upload: antetul fix plus vectorul de trăsături depășesc fișierul însuși.
Nu e un defect de implementat mai bine, e o proprietate a oricărei scări de
divulgare cu antet fix. Punctul de trecere se estimează pe hârtie acum și se
verifică la Etapa 6, în evaluare.

## Costul acceptat {#cost}

**Afirmația existențială e mai slabă decât cea universală.** Nu ajunge s-o
enunț: trebuie să *identific* calibrarea și să arăt că e o alegere rezonabilă,
nu una pescuită.

**Afirmația despre parc cere un montaj care nu există.** Mai multe instanțe de
agent, corpus cu suprapunere controlată între endpoint-uri — fără suprapunere,
deduplicarea n-are ce demonstra; cu suprapunere totală, rezultatul e nerealist
de bun. Proporția devine parametru de experiment, adică o obligație în plus la
2.12.

**Corpusul are acum o cerință numerică, nu o preferință.** 300 de mostre
malițioase ca să pot spune „sub 1%". Sub 100, nu pot susține nimic util despre
ratări, oricât de curat ar ieși rezultatul.

**Decizia rămâne cu două goluri.** Statusul e `partial`, nu `rezolvat`, și așa
trebuie să rămână până la Etapa 2.

**Descriptorul de regiune costă complexitate de contract chiar dacă adaptivul nu
se implementează niciodată.** E prețul ușii lăsate deschise.

## Ce am învățat {#invatat}

Tăria unei afirmații nu stă în cuantificator, ci în capacitatea ei de a eșua.
„Verdictele sunt întotdeauna identice" sună mai puternic decât „există o
calibrare la care coincid", dar prima e imposibilă, deci nu riscă nimic. A doua
poate fi infirmată de o singură măsurătoare — și tocmai de aceea valorează ceva.

Corolarul e mai neplăcut: **o măsurătoare făcută înainte de a ști ce pretinzi
produce un număr care nu răspunde la nimic.** 567× e calculat corect, publicat,
apărat de un validator — și descrie deopotrivă protocolul meu și un sistem care
raportează doar amprente. Instrumentul a fost construit înaintea întrebării, și
a măsurat ce era ușor de măsurat.

Regula generalizabilă: înainte de un instrument de măsură, scrie ce rezultat
te-ar face să renunți la ipoteză. Dacă nu există unul, instrumentul măsoară
altceva decât crezi.
