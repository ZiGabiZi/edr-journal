---
title: Identitatea se derivă o dată, nu la fiecare pornire
date: 2026-08-26
tip: decizie
rezumat: "`agent_id` scris fix în `config.json`, iar fișierul se copiază între mașini la fiecare desfășurare — a doua mașină revendica un nume deja legat de altă amprentă. Întrebarea nu era din ce derivăm numele, ci dacă îl recalculăm la fiecare pornire: legat de cheia de API, un `agent_id` recalculat ar fi transformat o redenumire de mașină în blocaj permanent."
tags: [identitate, infrastructura]
capitol: "3.3"
componente: agent
commits: [edr-agent@9aee32f, edr-agent@1411acc]
teste: [tests/test_agent_identity.py::test_a_renamed_machine_keeps_its_frozen_identity, tests/test_agent_identity.py::test_the_same_machine_always_derives_the_same_id, tests/test_agent_identity.py::test_two_machines_with_the_same_hostname_do_not_collide, tests/test_agent_identity.py::test_a_derived_id_survives_url_quoting_unchanged, tests/test_agent_identity.py::test_a_machine_without_a_stable_fingerprint_still_gets_a_stable_id, tests/test_agent_identity.py::test_a_write_failure_does_not_stop_the_agent, tests/test_agent_identity.py::test_a_path_with_a_null_byte_is_survived_too, tests/test_config_template.py::test_the_template_does_not_freeze_an_identity, tests/test_config_template.py::test_the_template_survives_the_real_validator]
status: rezolvat
---

## Context {#context}

`config.json` avea `agent_id` scris fix. Fișierul se copiază între mașini la
fiecare desfășurare, deci al doilea endpoint revendica un nume deja legat de altă
amprentă de mașină. Serverul întorcea `409`, agentul îl clasifica drept eroare
fatală și se oprea la pornire. **Mașina care ar fi trebuit monitorizată nu apărea
deloc în consolă.**

Clasificarea lui `409` s-a reparat cu o zi înainte, la
[autentificare]({{ '/intrari/2026-08-23-un-401-nu-e-un-payload-stricat/' | relative_url }}):
agentul nu mai moare, păstrează coada și reîncearcă. Dar asta transformă un
blackout într-o buclă de reîncercare — nu rezolvă cauza, care e că două mașini chiar
revendică același nume.

Regula de pe server exista deja din iulie. Intrarea despre
[cei doi agenți care nu știu cine sunt]({{ '/intrari/2026-07-12-doi-agenti-care-nu-stiu-cine-sunt/' | relative_url }})
se închisese cu o concluzie care a rămas valabilă: identitatea mașinii bate numele
din configurație. Serverul o aplica deja la deduplicare. Ce lipsea era partea
cealaltă — agentul să nu mai producă, în primul rând, un nume din configurație.

## Forța {#forta}

**Sursa nu era axa problemei.** Prima jumătate din discuție a fost despre de unde
se derivă: hostname, `MachineGuid`, `/etc/machine-id`, adresa MAC, și cât de stabil
e fiecare. Stabilitatea sursei contează însă doar dacă derivarea se **recalculează
la fiecare boot**. Derivat o dată și înghețat pe disc, un hostname instabil nu mai e
o problemă: a fost fotografiat la înrolare și nu se mai mișcă.

**Înghețarea nu e o opțiune, e obligatorie — și motivul vine din pasul de dinainte.**
`agent_id` e legat de cheia de API emisă pentru el. Dacă s-ar recalcula și
componenta lui s-ar schimba, adică cineva redenumește mașina:

1. agentul derivă un `agent_id` nou;
2. pe disc are `agent_key`, emisă pentru numele vechi;
3. `register` trimite cheia împreună cu noul `agent_id`;
4. secretul de înrolare fiind consumat, autorizarea cade pe a doua cale, găsește că
   acea cheie aparține numelui **vechi** și răspunde `403`.

Iar `403` e, prin decizia luată la autentificare, exact eroarea care nu se repară
niciodată singură. **O redenumire de mașină ar fi devenit un blocaj permanent al
identității**, cu coada crescând până la reprovizionarea manuală pe acea mașină.

**Unicitatea nu e suficientă, mai trebuie și idempotență.** Un identificator complet
aleator ar fi fost la fel de unic, dar ar fi creat o înregistrare nouă la fiecare
reinstalare — adică exact parcul care crește cu fiecare intervenție de mentenanță,
împotriva căruia serverul își construise deduplicarea în iulie.

## Alternative {#alternative}

**Starea de fapt — `agent_id` scris de operator în `config.json`.** Respinsă: e
chiar bug-ul. Un nume dat de om într-un fișier care se copiază nu e o identitate.

**Înghețarea tot în `config.json`.** Respinsă pentru că acela e fișierul copiat
între mașini, deci scrierea acolo ar fi reprodus exact bug-ul de la care s-a plecat,
la următoarea desfășurare. Și e configurare de operator, nu stare locală de mașină —
două lucruri cu proceduri diferite de instalare.

**Derivare la fiecare pornire.** Respinsă din cauza lanțului de `403` de mai sus.

**Identificator complet aleator.** Respins pentru că pierde idempotența la
reinstalare.

**Doar amprenta mașinii, fără hostname.** Respinsă pentru consolă: un ID care e doar
un hash e corect și inutilizabil de omul care se uită la lista de endpoint-uri.

**Oprirea agentului când identitatea nu se poate scrie pe disc.** Respinsă:
identitatea ține pentru rularea curentă și se rederivă la următoarea, stabilă oricum
cât timp hostname-ul și amprenta nu s-au schimbat. Un disc plin nu are voie să
producă un agent care refuză să pornească.

## Alegerea {#alegerea}

**Precedența: config explicit, apoi fișierul înghețat, apoi derivarea.** Forma:
`hostname-primele8dinhash`.

Ordinea contează în raționament, nu în șirul rezultat: **nucleul determinist e
amprenta mașinii, hostname-ul e doar prefix lizibil.** Partea din hash garantează
unicitatea și, mai important, idempotența la reinstalare — dacă fișierul de
identitate se pierde și agentul se reinstalează pe aceeași mașină, derivarea produce
același `agent_id`, deci aceeași înregistrare pe server, fără dublură.

**Se îngheață lipit de `agent_key`, ca stare locală.** Procedura de instalare
copiază `config.json` și secretul de înrolare; nu copiază niciodată starea locală.
Modulul e separat de `agent_credentials` tocmai pentru că `agent_id` **nu e un
secret**: scrierea e atomică, dar permisiunile nu se restrâng, fiindcă numele apare
oricum în fiecare cerere și în consolă.

**Contrastul cu încarnarea merită observat, pentru că cele două sunt exact opuse și
stau una lângă alta:**

| | `agent_instance_id` | `agent_id` |
|---|---|---|
| ce răspunde | care *rulare* raportează? | care *mașină* raportează? |
| valoarea din config | **ignorată** deliberat | **preferată** |
| trebuie să | difere la fiecare rulare | rămână aceeași cât timp mașina e aceeași |

Încarnarea, mecanismul pe care se sprijină
[detecția de repornire]({{ '/intrari/2026-07-13-repornirea-se-observa-nu-se-deduce/' | relative_url }}),
aruncă deliberat o valoare din configurație. Identitatea o preferă. Aceeași sursă,
regulă opusă, și motivul e în ce anume promite fiecare câmp.

**Două detalii care nu sunt cosmetice:**

**Normalizarea.** Valoarea ajunge într-o cale de URL, prin `quote()` cu `safe` gol,
și în consola operatorului. Un hostname cu puncte, spații sau diacritice ar fi produs
secvențe procentuale în URL, imposibil de căutat în jurnale. Se reduce la minuscule
și la setul `[a-z0-9-]`, iar testul trece rezultatul chiar prin `quote()` și verifică
egalitatea — deci păzește invarianta reală, nu o aproximare a ei.

**Lipsa amprentei.** Când toate cele trei surse eșuează, nucleul determinist lipsește
și sufixul devine aleator, **de aceeași lățime de opt caractere** ca prefixul de
hash, ca cele două cazuri să arate identic în consolă. Nu e o problemă tocmai pentru
că rezultatul se îngheață: lipsa de determinism nu se mai vede după prima pornire.
Cazul se loghează la WARNING, nu INFO, cu consecința scrisă — o reinstalare după
pierderea fișierului va produce o a doua înregistrare.

## Costul acceptat {#cost}

**Idempotența se pierde dacă mașina e și redenumită, și reinstalată.** Cu hostname
în ID, combinația celor două rupe derivarea. Rezultatul e o înregistrare duplicat,
nu un blocaj, iar combinația e rară. Lizibilitatea în consolă merită prețul — dar e
un preț, nu un detaliu, și trebuie să apară la evaluare dacă se numără endpoint-uri.

**Un al treilea fișier de stare locală.** `CREDENTIAL_PATH_KEYS` a devenit
`LOCAL_STATE_PATH_KEYS` și include acum și calea identității, fiindcă toate trei
descriu fișiere care nu se copiază între mașini. Orice procedură de instalare
viitoare are de respectat distincția asta, iar singurul lucru care o apără e un test.

**Mecanismul a fost inert două zile.** Ăsta e costul care nu se vede în cod.
`config.json` era versionat cu `agent_id=endpoint-01`, iar precedența taie derivarea
când cheia e prezentă. Orice instalare pornită din repo revendica același nume, deci
a doua mașină primea `409` — exact bug-ul de la care plecasem. **Derivarea exista în
cod de la primul commit și nu rula niciodată într-o desfășurare reală.**

Reparat pe 26 august: șablonul devine `config.example.json`, fără `agent_id`, iar
`config.json` trece în `.gitignore` ca stare a mașinii. Testul nou nu păzește codul,
ci **artefactul livrat** — trece șablonul prin validatorul real, deci și o divergență
viitoare, nu doar revenirea cheii, cade la teste în loc să cadă la prima instalare.

**Două găuri găsite pe drum, amândouă în funcții defensive.** `os.mkdir` ridică
`ValueError`, nu `OSError`, când calea conține un octet nul — iar calea vine din
`config.json`, unde JSON poate purta un astfel de octet. Netratată, excepția ieșea
din rezolvarea identității și oprea agentul la pornire, adică **exact eșecul pe care
funcția există ca să-l evite**. Aceeași gaură era și în `agent_credentials`; acolo ar
fi crăpat fix în clipa în care înrolarea reușise.

## Ce am învățat {#invatat}

**Am dezbătut sursa când axa era frecvența.** Cât de stabil e un hostname, cât de
sigur e `MachineGuid`, ce faci pe o mașină fără `/etc/machine-id` — toate întrebări
reale, și toate irelevante odată ce răspunsul la „o dată sau la fiecare pornire?" e
*o dată*. Când o discuție despre calitatea unei surse nu se termină, merită întrebat
dacă sursa e chiar variabila care contează.

**Un mecanism corect poate fi inert dacă artefactul livrat îl ocolește.** Codul era
bun de la primul commit, cu șaptesprezece teste care îl demonstrau, și n-a rulat o
singură dată într-o instalare adevărată. Testele acopereau codul; nimic nu acoperea
fișierul livrat odată cu el. Diferența dintre „codul e corect" și „instalarea
funcționează" e un test care trece **artefactul** prin validatorul real.

**Consecințele unei decizii nu se opresc la intrarea care o documentează.** Regula
aleasă la autentificare — `403` nu se repară niciodată singur — a devenit, a doua zi,
constrângerea dură care a decis forma identității. Nu era prevăzută acolo și nu putea
fi: s-a văzut abia când următorul mecanism s-a lovit de ea.

**Două mecanisme cu reguli opuse despre aceeași cheie de configurare se documentează
reciproc.** `agent_instance_id` o ignoră, `agent_id` o preferă, și stau una lângă
alta în cod. Contrastul e mai lizibil decât ar fi fost oricare dintre ele explicată
singură — cu condiția ca cineva să-l scrie undeva, pentru că din cod se vede doar că
diferă, nu de ce.
