---
title: Mai bine niciun agent decât unul care crede că monitorizează
date: 2026-06-05
tip: decizie
rezumat: Configurația decide cine e agentul, unde raportează și ce supraveghează. O valoare greșită nu produce o eroare, produce liniște — deci agentul refuză să pornească pe orice nu poate dovedi că e valid, în loc să completeze cu valori rezonabile.
tags: [detectie]
capitol: "3.1"
componente: agent
commits: [edr-agent@dd84d34, edr-agent@10421cd]
teste: [tests/test_config_loader.py::test_default_config_path_is_independent_of_working_directory, tests/test_config_loader.py::test_explicit_config_path_still_overrides_default]
status: partial
---

## Context {#context}

A doua zi de cod real. Agentul citește `config.json`, și din fișierul ăla vine
absolut tot ce definește ce e el: `agent_id` — cine e; `server_url` — unde
raportează; mai târziu `monitored_directories` — ce supraveghează.

Întrebarea interesantă la momentul ăla nu e cum citesc un JSON. E ce fac când
fișierul spune ceva greșit.

## Forța {#forta}

**Agentul n-are pe cine să întrebe.** Nu e un program pe care îl pornește cineva
dintr-un terminal și se uită la ce scrie. E un serviciu care pornește la boot, pe
o mașină la care nu se conectează nimeni cu lunile. Orice decide la pornire,
decide singur, și rămâne așa.

**O configurație greșită nu se manifestă ca eroare, ci ca liniște.** Un
`monitored_directories` care arată spre o cale inexistentă produce exact ce
produce un director în care nu se întâmplă nimic: niciun eveniment. Un
`server_url` fără gazdă produce erori de conexiune care arată identic cu un server
picat. Niciuna dintre stările astea nu spune „sunt configurat greșit"; toate spun
„totul e în regulă, n-am ce raporta".

**Un endpoint aparent acoperit e mai rău decât unul declarat neacoperit.** Asta e
miezul, și e o afirmație de securitate, nu de inginerie. O mașină despre care
nimeni nu crede că e monitorizată primește atenție: cineva se întreabă de ce
lipsește, cineva o pune pe o listă. O mașină pe care toată lumea o vede în consolă
și care de fapt nu supraveghează nimic e un punct orb cu bec verde. A doua e o
stare pe care un atacator o poate prefera activ.

**Fișierul e local și cognoscibil.** Spre deosebire de server, a cărui
disponibilitate n-o pot ști dinainte, configurația e complet lizibilă în prima
milisecundă. Tot ce e în neregulă cu ea e demonstrabil pe loc, fără să aștept
nimic și fără să ghicesc.

## Alternative {#alternative}

**Valori implicite pentru tot ce lipsește.** Varianta prietenoasă: lipsește
`server_url`, pun `localhost`; lipsesc directoarele, pun ceva rezonabil. Respinsă
pentru că o valoare implicită transformă o eroare de configurare într-un agent
funcțional care face altceva decât ce voia cineva. Eroarea nu dispare — își pierde
doar mesajul.

**Validare la prima folosire.** Verific `server_url` când chiar trimit ceva,
directoarele când chiar pornesc observatorul. Respinsă pentru că mută eșecul la un
moment arbitrar de mai târziu, amestecat printre eșecuri reale de execuție, pe o
mașină la care nu se uită nimeni. O eroare de configurare raportată la ora trei
noaptea, în aceeași linie de log cu un timeout de rețea, nu mai e o eroare de
configurare — e zgomot.

**Avertisment și pornire.** Loghez problema și merg mai departe. Respinsă pentru
același motiv ca valorile implicite, plus unul în plus: mută decizia într-un fișier
de log pe care, prin construcție, nu-l citește nimeni până când nu e deja prea
târziu.

## Alegerea {#alegerea}

`load_config` refuză. Ridică `ConfigError` pentru fișier absent, JSON invalid,
cheie obligatorie lipsă, goală sau de alt tip, `server_url` fără schemă `http`/
`https`, fără gazdă sau cu port invalid, și `monitored_directories` care nu e o
listă nevidă de căi absolute. `run_agent` prinde `ConfigError`, îl loghează ca
atare și procesul se termină.

Ordinea dintre validare și normalizare e deliberată:

```python
validate_config(config)

validate_server_url(config["server_url"])
config["server_url"] = config["server_url"].rstrip("/")
```

Se validează ce a scris omul, se normalizează ce va folosi programul. Invers, aș fi
validat un șir pe care l-am fabricat eu, iar mesajul de eroare ar fi arătat spre o
valoare care nu există în niciun fișier.

Merită pusă alături de decizia din 11 iulie, pentru că par contradictorii și nu
sunt. Același program **refuză să pornească** pe o configurație invalidă și
**refuză să se oprească**
[când serverul nu răspunde]({{ '/intrari/2026-07-11-agentul-observa-inainte-sa-ceara-voie/' | relative_url }}).
Diferența nu e de temperament, e epistemică: configurația e locală, cognoscibilă
acum, și nu se repară singură; serverul e la distanță, tranzitoriu, și cel mai
probabil se repară singur. Refuză ce poți dovedi că e greșit, treci prin ce s-ar
putea îndrepta.

## Costul acceptat {#cost}

**Regulile de validare n-au niciun test, și se vede.** Douăzeci de zile,
`validate_monitored_directories` a verificat un singur element din listă:
normalizarea și verificarea de cale absolută stăteau *în afara* buclei, deci se
aplicau doar ultimei intrări.

```python
for index, directory in enumerate(directories):
    if not isinstance(directory, str) or not directory.strip():
        raise ConfigError(...)

normalized_directories = os.path.normpath(os.path.expanduser(directory.strip()))
if not Path(normalized_directories).is_absolute():
    raise ConfigError(...)
```

O configurație cu trei directoare, dintre care două relative, trecea validarea
dacă ultimul era absolut. Iar `valid_directories` primea o singură intrare, deci
restul se pierdeau tăcut. În același commit de corecție, `parsed.netloc` a devenit
`parsed.hostname` — pentru că `urlparse("http://:8080").netloc` e `":8080"`, adică
adevărat, deci un URL fără gazdă trecea și el.

Funcția al cărei unic scop era să refuze configurații invalide accepta tăcut
configurații invalide. E aceeași formă ca la debouncer: o gardă care se citește
corect și nu face ce scrie, într-un loc în care nimic nu verifică dacă face.

**Cheia care contează cel mai mult nu e obligatorie.** `REQUIRED_CONFIG_KEYS` are
trei nume, și `monitored_directories` nu e printre ele. Dacă lipsește, se
completează cu `DEFAULT_MONITORED_DIRECTORIES = [r"C:\EDR_Test"]` — un director de
test. Refuzul e strict exact pentru cheile fără de care agentul nu poate *vorbi*,
și permisiv exact pentru cea fără de care n-are *ce spune*.

Eșecul care urmează nu e tăcut, ca să fiu corect: dacă niciun director configurat
nu există, `FileMonitor` ridică `FileMonitorError` și agentul se oprește. Dar se
oprește prin handler-ul generic, ca „Unexpected error occurred" cu urmă de stivă,
nu ca diagnostic de configurare — și, de la reordonarea din 11 iulie, se oprește
*înainte* de înregistrare. Deci un endpoint configurat greșit nu apare în consolă
ca defect. Nu apare deloc. Iar absența unei mașini dintr-o listă e singurul lucru
pe care lista nu-l poate arăta.

**Fail-fast e o decizie despre pornire, nu despre viață.** Validarea rulează o
dată. Un director care e șters, redenumit sau demontat după pornire nu produce
nimic — observatorul rămâne atașat unei căi care nu mai există, iar agentul
continuă să raporteze că trăiește.

## Ce am învățat {#invatat}

**Un mod de eșec tăcut trebuie transformat în unul zgomotos cât timp mai ai unde.**
Pornirea e ultimul moment în care e plauzibil să existe un om prin apropiere —
cineva care tocmai a instalat, tocmai a editat, tocmai a repornit. Peste zece
minute nu mai e nimeni, iar peste o lună diferența dintre „nu s-a întâmplat nimic"
și „nu am văzut nimic" nu se mai poate reconstitui din nimic.

**Refuzul și persistența nu se contrazic — se despart după ce poți ști acum.** O
condiție locală, verificabilă și stabilă merită refuz. Una la distanță,
netestabilă în avans și probabil trecătoare merită răbdare. Am ajuns la regula asta
abia după ce le-am scris pe amândouă separat, la cinci săptămâni distanță, și am
observat că arată ca o inconsecvență.

**Un validator fără teste e o declarație de intenție.** E singura categorie de cod
care nu se autoverifică prin folosire: dacă funcționează greșit, rezultatul e că
programul merge mai departe — adică exact ce s-ar fi întâmplat și fără el. Restul
codului se plânge când e stricat. Un validator stricat tace, pentru că tăcerea e
și răspunsul lui corect.

**Valoarea implicită e cea mai tăcută formă de configurare greșită.** O cheie
lipsă e vizibilă; o cheie lipsă completată cu ceva plauzibil nu mai e. Fiecare
valoare implicită dintr-un sistem de detecție e o afirmație despre ce se
supraveghează atunci când nimeni n-a spus ce să se supravegheze — și e o afirmație
pe care o face programul, nu operatorul.
