# edr-journal

Jurnalul de parcurs al unui sistem EDR construit ca lucrare de licență — povestea din
spatele fiecărei componente, fiecărui bug și fiecărei decizii de arhitectură.

**Site live:** https://ZiGabiZi.github.io/edr-journal/

---

## Ce este acest repo

Codul unui proiect spune *ce* face sistemul. Nu spune niciodată *de ce* arată așa.

Acest jurnal completează golul: pentru fiecare mecanism din sistemul EDR există o
intrare care explică ce problemă concretă l-a provocat, ce am crezut inițial că era
cauza, ce era de fapt și cum știu că problema e rezolvată.

Este scris în primul rând pentru mine — ca memorie de lucru și ca material brut pentru
capitolul de implementare al lucrării. Dar este public, pentru că un cititor care vrea
să înțeleagă traseul proiectului găsește aici mult mai mult decât într-un `git log`.

**Ce nu este:** nu este documentația de utilizare a sistemului EDR, nu este lucrarea de
licență și nu este un blog tehnic cu articole generale. Fiecare intrare e legată de o
problemă reală, întâlnită în acest proiect, la o dată anume.

### Proiectul documentat

Un prototip de sistem Endpoint Detection and Response axat pe **analiza statică** a
fișierelor, cu arhitectură agent–server și cu accent pe medii izolate (air-gapped) și
organizații sensibile la confidențialitatea datelor.

Codul propriu-zis trăiește în două repo-uri separate:

| Repo | Rol |
|---|---|
| [`edr-agent`](https://github.com/ZiGabiZi/edr-agent) | Agentul de pe endpoint (Python, watchdog, SQLite) |
| [`edr-server`](https://github.com/ZiGabiZi/edr-server) | Serverul central (Python, FastAPI) |

Jurnalul este intenționat un al treilea repo: majoritatea poveștilor sunt
*cross-cutting* și ating ambele componente simultan. A le găzdui într-unul din cele
două ar minți despre locul problemei.

---

## Tipuri de intrări

Fiecare intrare aparține uneia dintre două categorii, cu structuri narative diferite:

### `incident`
Ceva era rupt și am aflat de ce.

> Context → Simptom → Ce am crezut inițial → Cauza reală → Soluția → Cum știu că e rezolvat → Ce am învățat

Secțiunea **„Ce am crezut inițial"** este cea care lipsește din documentația obișnuită
și exact cea care mă ajută cel mai mult la recitire. Ipoteza greșită se păstrează
explicit, nu se rescrie istoria.

### `decizie`
Nimic nu era rupt, dar aveam de ales.

> Context → Forța care preseaza → Alternative → Alegerea → Costul acceptat → Ce am învățat

Format inspirat de ADR (Architecture Decision Record). Costul acceptat se scrie
întotdeauna — o decizie fără trade-off documentat este o decizie neanalizată.

---

## Structura repo-ului

```
edr-journal/
├── _config.yml              # configurația Jekyll (colecții, baseurl, valori implicite)
├── index.md                 # pagina de start — timeline-ul intrărilor
├── parcurs.md               # timeline generat din istoricul git al celor două repo-uri
├── _layouts/
│   ├── default.html         # scheletul comun (head, CSS, subsol)
│   ├── acasa.html           # pagina de start
│   └── intrare.html         # pagina unei intrări
├── _intrari/                # colecția de intrări (conținutul propriu-zis)
│   ├── _sablon.md           # șablon de copiat pentru o intrare nouă
│   └── *.md
├── _data/
│   └── commits.json         # generat automat, nu se editează manual
├── scripts/
│   └── genereaza_timeline.py
└── assets/
```

Fișierele care încep cu `_` în `_intrari/` (ex. `_sablon.md`, `_backlog.md`) nu sunt
publicate — sunt unelte de lucru.

---

## Cum adaug o intrare nouă

**1.** Copiază șablonul:

```bash
cp _intrari/_sablon.md _intrari/spool-evenimente-pierdute.md
```

Numele fișierului devine URL-ul (`/intrari/spool-evenimente-pierdute/`), deci scrie-l
descriptiv, cu cratime, fără diacritice.

**2.** Completează front-matter-ul:

```yaml
---
title: Evenimentele dispăreau când serverul era oprit
date: 2026-07-20
tip: incident
rezumat: Evenimentele de fișier erau trimise fire-and-forget; orice eșec de transport le pierdea definitiv.
tags: [persistenta, retea]
capitol: "3.2"
componente: ambele
commits: [edr-agent@a1b2c3d, edr-server@e4f5g6h]
teste: [app/tests/test_idempotenta.py::test_duplicate_client_event_id_is_idempotent]
status: rezolvat
---
```

`commits` și `teste` sunt liste plate, nu structuri imbricate — layout-ul de intrare
sparge fiecare element de `commits` pe `@` ca să construiască link-ul către GitHub, deci
formatul `repo@hash` e obligatoriu.

**3.** Scrie corpul respectând H2-urile fixe ale tipului ales. Structura constantă e ce
face jurnalul parcurgibil de cineva care sare direct la mijloc.

### Câmpuri de front-matter

| Câmp | Obligatoriu | Valori |
|---|---|---|
| `title` | da | frază descriptivă, nu titlu de commit |
| `date` | da | `AAAA-LL-ZZ` |
| `tip` | da | `incident` \| `decizie` |
| `rezumat` | da | o singură frază, apare în listă |
| `tags` | da | vocabular controlat (vezi mai jos) |
| `capitol` | nu | secțiunea din `_data/capitole.yml`, ex. `"3.2"` |
| `status` | nu | `rezolvat` \| `partial` \| `deschis` |
| `componente` | nu | `agent` \| `server` \| `ambele` |
| `commits` | nu | listă de `repo@hash` |
| `teste` | nu | listă de `cale::nume_test` |

### Vocabular de tag-uri

Listă închisă, deliberat. Fără disciplina asta se ajunge rapid la `retea`, `network` și
`rețea` ca trei tag-uri distincte:

Sursa unică de adevăr e `_data/teme.yml`, nu lista de aici. Un tag folosit într-o intrare
dar absent de acolo e semnalat vizibil pe `/teme/`.

`retea` · `contract` · `concurenta` · `persistenta` · `identitate` ·
`observabilitate` · `detectie` · `pdp` · `infrastructura`

Un tag nou se adaugă întâi în `_data/teme.yml` (plus un stub în `teme/`), abia apoi se
folosește într-o intrare.

### Legătura cu lucrarea

`capitol` leagă intrarea de secțiunea din Capitolul 3 pe care o susține. Secțiunile sunt
definite în `_data/capitole.yml`, iar `/capitole/` arată lanțul în ambele sensuri: ce
intrări susțin o secțiune și — mai important — care secțiuni n-au încă niciun suport
scris. O intrare fără `capitol` apare acolo ca nemapată.

---

## Dezvoltare locală

### Cerințe

**Ruby 3.3.x** — nu o versiune mai nouă. Stack-ul Jekyll folosit aici depinde de
`String#untaint`, metodă eliminată din Ruby 3.2, și de biblioteci scoase din stdlib în
Ruby 3.4 (`csv`, `logger`, `base64`). Ruby 4.x produce erori de build care nu se pot
rezolva prin gem-uri de compatibilitate.

Pe Windows: [RubyInstaller](https://rubyinstaller.org/) — varianta **Ruby+Devkit 3.3.x
(x64)**, cu `ridk install` rulat la final (opțiunea 3).

### Pornire

```bash
bundle install
bundle exec jekyll serve --livereload
```

Site-ul devine disponibil la **http://127.0.0.1:4000/edr-journal/** — sufixul contează,
vine din `baseurl`.

`--livereload` reîmprospătează browserul automat la salvarea unui fișier.

### De reținut

- Modificările din `_config.yml` **nu** sunt preluate live — oprește serverul (`Ctrl+C`)
  și repornește-l.
- Dacă `bundle` sau `gem` nu sunt recunoscute pe Windows, folosește shortcut-ul
  **„Start Command Prompt with Ruby"** din meniul Start; setează PATH-ul corect garantat.
- `_site/`, `.jekyll-cache/` și `Gemfile.lock` sunt ignorate de git.

---

## Regenerarea timeline-ului

Pagina `parcurs.md` afișează istoricul de commit-uri al celor două repo-uri de cod,
marcând vizual care commit-uri au deja o intrare scrisă și care nu.

```bash
python scripts/genereaza_timeline.py
```

Scriptul citește `git log` din `edr-agent` și `edr-server` și rescrie
`_data/commits.json`.

Efectul secundar util: jurnalul își generează singur backlog-ul — commit-urile
nemarcate sunt exact poveștile care așteaptă să fie scrise.

**Fișierul se comite.** GitHub Pages nu rulează scriptul, deci timeline-ul de pe site e
la fel de proaspăt ca ultima rulare comisă. Ca să nu depindă de memorie, instalează
hook-ul de pre-commit — regenerează și include fișierul la fiecare commit:

```bash
cp scripts/hook-pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

Un pas echivalent în GitHub Actions nu funcționează fără muncă disproporționată:
scriptul are nevoie de istoricul celor două repo-uri de cod, care în CI ar trebui clonate
separat, cu token dacă sunt private, iar build-ul implicit de Pages ar trebui înlocuit cu
un workflow propriu. Regenerarea aparține singurului loc unde există toate trei
repo-urile — mașina de lucru.

---

## Publicare

Push pe `main` declanșează build-ul GitHub Pages. Starea build-ului se vede în tab-ul
**Actions**; publicarea durează 1–2 minute.

---

## Ritual de întreținere

Riscul real al unui jurnal de proiect nu e că e o idee proastă — e că devine un al
treilea proiect care concurează cu cel principal. Regulile care îl țin în viață:

1. **Intrarea se scrie imediat după fix**, cât contextul e încă în cap. Douăzeci de
   minute, imperfect. Nu retroactiv.
2. **Un test de regresie cu nume descriptiv este deja titlul intrării.**
   `test_stale_agent_becomes_offline_without_new_heartbeat` documentează bug-ul original
   în chiar numele lui.
3. **Un backlog de 15 povești nescrise înseamnă că jurnalul a murit deja.** Dacă se
   acumulează, se taie, nu se recuperează.

---

## Autor

Țilică Gabriel-Lucian — Facultatea de Matematică și Informatică, Universitatea din
București. Lucrare de licență coordonată de conf. dr. Paul Irofti.

Conținutul jurnalului este material de lucru personal, publicat pentru transparența
procesului. Codul din repo-urile asociate are propriile licențe.