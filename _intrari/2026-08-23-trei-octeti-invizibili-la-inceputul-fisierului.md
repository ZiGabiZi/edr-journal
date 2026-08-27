---
title: Trei octeți invizibili la începutul fișierului
date: 2026-08-23
tip: incident
rezumat: Uneltele obișnuite de pe Windows scriu UTF-8 cu BOM. Citit ca utf-8 curat, BOM-ul devine U+FEFF la începutul secretului, iar `strip()` nu îl elimină. Pe agent a ieșit un traceback despre codecuri din adâncul lui urllib3, în care fișierul vinovat nu apărea deloc; pe server, același caz producea 500 exact pe stratul care decide cine are voie să scrie.
tags: [contract, identitate, infrastructura]
capitol: "3.8"
componente: ambele
commits: [edr-agent@4bfab22, edr-server@d665f3d]
teste: [tests/test_api_authentication.py::test_a_secret_saved_with_a_bom_is_read_cleanly, tests/test_api_authentication.py::test_a_key_saved_with_a_bom_is_read_cleanly, tests/test_api_authentication.py::test_a_credential_that_cannot_be_a_header_is_refused_not_crashed, app/tests/test_api_authentication.py::test_a_non_ascii_enrollment_secret_is_refused_not_a_server_error, app/tests/test_api_authentication.py::test_an_enrollment_secret_file_with_a_bom_still_matches]
status: rezolvat
---

## Context {#context}

[Autentificarea]({{ '/intrari/2026-08-23-un-401-nu-e-un-payload-stricat/' | relative_url }})
tocmai intrase în ambele repo-uri, cu suita verde pe amândouă. Urma prima rulare
adevărată pe un endpoint: secretul de înrolare scris într-un fișier, cu uneltele
pe care le are omul la îndemână pe mașina aia.

## Simptom {#simptom}

Agentul moare la pornire. Pe ecran, un `UnicodeEncodeError` pe codecul `latin-1`,
aruncat din adâncul lui `urllib3`, cu un stack care trece prin trei biblioteci și
în care **niciun fișier al proiectului nu apare**.

Separat, căutând cauza pe partea cealaltă, un `curl` scris de mână către server
producea `500` pe ruta de înregistrare. Nu `401`. Eroare de server, pe stratul de
autentificare.

## Ce am crezut {#ipoteza}

**Că secretul e pur și simplu greșit.** O greșeală de copiere, un spațiu în plus,
un caracter lipsă. Ipoteza era rezonabilă tocmai pentru că agentul nu spunea nimic
despre vreun fișier — dacă ar fi fost o problemă de credențială, mă așteptam la
mesajul pe care îl scrisesem chiar eu pentru cazul ăla.

**Iar traceback-ul arăta către transport.** `urllib3`, codec `latin-1`,
`http.client` — toate numele din stack aparțineau stratului de rețea. Prima
jumătate de oră am căutat o incompatibilitate de bibliotecă.

Fișierul de secret l-am deschis, l-am comparat vizual cu valoarea de pe server, și
erau identice. Chiar erau.

## Cauza reală {#cauza}

**Fișierele de credențiale erau citite cu `utf-8` curat. Fiecare unealtă
obișnuită de pe Windows scrie însă UTF-8 CU BOM:** `Set-Content -Encoding utf8`
din PowerShell 5.1, Notepad, redirectarea în fișier.

Citit ca `utf-8`, BOM-ul devine caracterul de format `U+FEFF` la începutul
secretului. `strip()` nu îl elimină, pentru că **nu e spațiu alb, e un caracter
de format**. Și nu se vede la nicio inspecție vizuală, ceea ce explică de ce cele
două valori „identice" chiar arătau identice.

Ce urmează e mult mai rău decât un secret greșit:

```
fisier scris cu BOM
  -> citit ca utf-8      -> "﻿SECRET"
  -> strip()             -> "﻿SECRET"   (neschimbat)
  -> antet HTTP          -> http.client codeaza antetele latin-1
  -> UnicodeEncodeError aruncat din urllib3
```

Excepția **nu e nici `TransportError`, nici `ConfigError`**, deci trece prin toate
ramurile de tratare a erorilor din `register_agent_with_retry` și ajunge în plasa
generică din `run_agent`, care oprește agentul. Operatorul vede un traceback
despre codecuri, iar cauza reală — un fișier salvat cu BOM — nu e numită nicăieri.

**Agentul moare la pornire pentru că cineva a folosit editorul implicit al
sistemului pe care rulează.**

Pe server, aceeași cauză ia altă formă. `hmac.compare_digest` refuză să compare
șiruri care conțin non-ASCII și ridică `TypeError`. Antetele HTTP se decodează
`latin-1`, deci un client poate trimite oricând octeți care devin caractere
non-ASCII, iar `verify_enrollment_secret` îi dădea direct lui `compare_digest`.
Netratată, excepția ieșea din rută ca `500`.

Iar cazul are **și o formă complet nevinovată**: un fișier de secret salvat cu
BOM arată exact așa, privit dinspre server.

**Convenția exista deja în proiect.** Încărcătorul de contract al serverului
folosea `utf-8-sig` din exact același motiv, cu un comentariu care spune că
editoarele de pe Windows salvează des cu BOM. Am aplicat-o la un fișier și nu la
celălalt, iar diferența a costat o rulare întreagă.

## Soluția {#solutia}

**Pe agent, `utf-8-sig` la citirea ambelor fișiere de credențiale**, plus
curățarea unui BOM rămas *după* un spațiu, pentru fișierele editate de două ori cu
unelte diferite.

**A doua gardă, înainte de rețea:** valoarea trebuie să se poată coda `latin-1`,
altfel e refuzată la încărcare, cu un ERROR care numește fișierul, cauza probabilă
și ce trebuie făcut. Un fișier salvat într-o codificare exotică e tratat de acum
ca **lipsă de credențială** — adică exact ca un agent neînrolat: reîncearcă,
escaladează în log și **nu pierde evenimente**. Un fișier care nu poate fi decodat
deloc, tipic UTF-16, primește același tratament, cu alt mesaj.

**Pe server, refuz în loc de eroare.** Un secret care nu poate fi comparat nu poate
fi corect, deci răspunsul e `401`, cu un WARNING care numește cazul. Plus
`utf-8-sig` la citirea lui `enrollment_secret.txt` și `agent_keys.json`: primul
poate fi scris de un operator pe Windows, al doilea e scris de server dar poate fi
editat sau restaurat de un om. Un fișier de secret care nu e UTF-8 valid oprește
acum pornirea cu un mesaj care spune ce trebuie făcut, în loc să fie interpretat
greșit în tăcere.

## Cum știu că e rezolvat {#regresie}

Trei teste pe agent — un secret cu BOM se citește curat, o cheie cu BOM la fel, și
o credențială care nu poate deveni antet e refuzată la încărcare în loc să omoare
procesul.

Două pe server — un antet cu octeți non-ASCII primește `401` și nu `500`, iar un
fișier de secret cu BOM se potrivește în continuare cu valoarea trimisă de agent.

Ultimul e cel care contează cel mai mult: e singurul care testează **traversarea**,
adică exact locul unde cele două repo-uri se ating și unde niciuna dintre suite
nu privea până acum.

## Ce am învățat {#invatat}

**O convenție aplicată la un fișier și nu la celălalt nu e o convenție, e o
coincidență.** Comentariul care explica exact acest caz exista deja în proiect, la
trei fișiere distanță, scris de mine. Nu l-am uitat — pur și simplu nu exista
nimic care să-l aplice a doua oară. O regulă care trăiește într-un comentariu se
respectă doar cât timp cineva își amintește de ea.

**Aceeași cauză traversează granița dintre repo-uri și ia altă formă pe fiecare
parte.** Pe agent: moarte la pornire, cu un traceback care acuză transportul. Pe
server: `500` pe frontiera de încredere. Niciunul dintre cele două istorice de
commit-uri nu arată ambele fețe, și niciuna dintre cele două suite nu putea găsi
cazul singură. E argumentul cel mai concret de până acum pentru care jurnalul e un
al treilea repo.

**O excepție care nu aparține niciuneia dintre clasele tale de eroare trece prin
toate ramurile de tratare.** Plasa generică de la vârf nu e o plasă de siguranță,
e locul unde moare diagnosticabilitatea: prinde totul și nu știe nimic despre ce a
prins. Fiecare valoare care vine de pe disc și pleacă pe rețea are nevoie de o
gardă la **încărcare**, unde numele fișierului e încă în mână, nu la folosire,
unde nu mai e.

**Autentificarea nu are voie să aibă o cale prin care o intrare oarecare produce
altceva decât „da" sau „nu".** Un `500` acolo e și un bug, și informație oferită
gratis: îi spune celui care sondează că intrarea lui a ajuns undeva unde nu era
așteptată.
