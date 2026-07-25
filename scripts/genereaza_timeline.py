#!/usr/bin/env python3
"""
Generează `_data/commits.json` din istoricul repo-urilor de cod.
================================================================

De ce există:
    Jurnalul trăiește în alt repo decât codul, iar GitHub Pages construiește
    site-ul fără să ruleze nimic din afara Jekyll. Deci istoricul din
    `edr-agent` și `edr-server` trebuie adus aici ca fișier de date, comis în
    repo, ca pagina `/parcurs/` să aibă ce randa în producție.

    Consecința practică: fișierul generat NU e efemer. Se comite. Timeline-ul
    de pe site e la fel de proaspăt ca ultima rulare a scriptului.

Efectul secundar util:
    Pagina marchează commit-urile care au deja o intrare asociată (prin câmpul
    `commits` din front-matter). Ce rămâne nemarcat e, practic, backlog-ul de
    povești nescrise. Scriptul îl raportează și în consolă, la final.

Folosire:
    python scripts/genereaza_timeline.py
    python scripts/genereaza_timeline.py --depozit edr-agent --depozit edr-server
    python scripts/genereaza_timeline.py --de-la 2026-06-01
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# Rădăcina jurnalului (scripts/ e direct sub ea), respectiv directorul care le
# conține pe toate trei: edr-journal, edr-agent, edr-server.
_RADACINA_JURNAL = Path(__file__).resolve().parent.parent
_RADACINA_PROIECT = _RADACINA_JURNAL.parent

DEPOZITE_IMPLICITE = ["edr-agent", "edr-server"]
FISIER_IESIRE = _RADACINA_JURNAL / "_data" / "commits.json"
DIRECTOR_INTRARI = _RADACINA_JURNAL / "_intrari"

# Separator de câmpuri: \x1f (unit separator) nu apare în mesaje de commit.
_SEP = "\x1f"
_MARCAJ = "__COMMIT__"
_FORMAT = f"{_MARCAJ}{_SEP}%h{_SEP}%aI{_SEP}%s"

# Lungimea hash-ului scurt e fixată explicit: potrivirea cu `commits` din
# front-matter e pe egalitate, deci trebuie să fie stabilă indiferent de câte
# obiecte are repo-ul (git creşte abbrev-ul singur pe repo-uri mari).
_LUNGIME_HASH = 7

_LUNI_RO = {
    1: "ianuarie", 2: "februarie", 3: "martie", 4: "aprilie",
    5: "mai", 6: "iunie", 7: "iulie", 8: "august",
    9: "septembrie", 10: "octombrie", 11: "noiembrie", 12: "decembrie",
}


def _forteaza_utf8_pe_consola() -> None:
    """
    Trece stdout/stderr pe UTF-8.

    Pe Windows consola e cp1252, iar raportul final conține diacritice: fără
    asta, scriptul își face treaba și apoi crapă la ultimul print.
    """
    for flux in (sys.stdout, sys.stderr):
        reconfigureaza = getattr(flux, "reconfigure", None)
        if reconfigureaza is not None:
            reconfigureaza(encoding="utf-8", errors="replace")


class EroareGit(Exception):
    """Ridicată când un apel `git` eșuează sau repo-ul lipsește."""


def ruleaza_git(argumente: List[str], cale_repo: Path) -> str:
    """
    Rulează o comandă git și întoarce stdout decodat ca UTF-8.

    Decodarea e explicită pentru că mesajele de commit conțin diacritice, iar
    pe Windows codificarea implicită a consolei (cp1252) le-ar strica.
    """
    try:
        rezultat = subprocess.run(
            ["git", "-C", str(cale_repo), *argumente],
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as eroare:
        raise EroareGit("`git` nu a fost găsit în PATH.") from eroare

    if rezultat.returncode != 0:
        detaliu = rezultat.stderr.decode("utf-8", errors="replace").strip()
        raise EroareGit(f"git {' '.join(argumente)} a eșuat în {cale_repo}: {detaliu}")

    return rezultat.stdout.decode("utf-8", errors="replace")


def parseaza_jurnal(brut: str, depozit: str) -> List[Dict[str, Any]]:
    """
    Transformă ieșirea `git log --numstat` într-o listă de commit-uri.

    Formatul așteptat, pe blocuri:
        __COMMIT__<US>hash<US>data-iso<US>mesaj
        <adăugate>\t<șterse>\t<cale>
        ...
    Fișierele binare apar cu "-" în loc de numere și sunt numărate ca 0 linii.
    """
    commituri: List[Dict[str, Any]] = []
    curent: Optional[Dict[str, Any]] = None

    for linie in brut.splitlines():
        if linie.startswith(_MARCAJ):
            parti = linie.split(_SEP)
            if len(parti) < 4:
                continue

            _, hash_scurt, data_iso, mesaj = parti[0], parti[1], parti[2], _SEP.join(parti[3:])
            moment = datetime.fromisoformat(data_iso)

            curent = {
                "depozit": depozit,
                "hash": hash_scurt,
                "data": moment.strftime("%Y-%m-%d"),
                "data_iso": data_iso,
                "luna": moment.strftime("%Y-%m"),
                "luna_afisata": f"{_LUNI_RO[moment.month]} {moment.year}",
                "mesaj": mesaj,
                "fisiere": [],
                "numar_fisiere": 0,
                "linii_adaugate": 0,
                "linii_sterse": 0,
            }
            commituri.append(curent)
            continue

        if not linie.strip() or curent is None:
            continue

        coloane = linie.split("\t")
        if len(coloane) < 3:
            continue

        adaugate, sterse, cale = coloane[0], coloane[1], coloane[2]
        curent["fisiere"].append(cale)
        curent["numar_fisiere"] += 1
        if adaugate.isdigit():
            curent["linii_adaugate"] += int(adaugate)
        if sterse.isdigit():
            curent["linii_sterse"] += int(sterse)

    return commituri


def citeste_commituri(cale_repo: Path, depozit: str, de_la: Optional[str]) -> List[Dict[str, Any]]:
    """Extrage istoricul unui repo, fără merge-uri (nu aduc conținut propriu)."""
    if not (cale_repo / ".git").exists():
        raise EroareGit(f"{cale_repo} nu pare a fi un repo git.")

    argumente = [
        "log",
        "--no-merges",
        f"--abbrev={_LUNGIME_HASH}",
        "--numstat",
        f"--format={_FORMAT}",
    ]
    if de_la:
        argumente.append(f"--since={de_la}")

    return parseaza_jurnal(ruleaza_git(argumente, cale_repo), depozit)


def extrage_commituri_din_intrare(text: str) -> List[str]:
    """
    Scoate valorile `commits` din front-matter-ul unei intrări.

    Parsare deliberat minimală (fără dependență de PyYAML): acoperă forma
    inline `commits: [a, b]` și forma pe blocuri cu `-`. E folosită doar pentru
    raportul din consolă — potrivirea care contează se face în Liquid, la build.
    """
    front_matter = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not front_matter:
        return []

    corp = front_matter.group(1)

    inline = re.search(r"^commits:\s*\[(.*?)\]\s*$", corp, re.MULTILINE)
    if inline:
        return [v.strip().strip("\"'") for v in inline.group(1).split(",") if v.strip()]

    bloc = re.search(r"^commits:\s*\n((?:\s*-\s*.+\n?)+)", corp, re.MULTILINE)
    if bloc:
        return [
            linie.strip().lstrip("-").strip().strip("\"'")
            for linie in bloc.group(1).splitlines()
            if linie.strip()
        ]

    return []


def aduna_referinte() -> set:
    """Toate perechile `depozit@hash` deja citate de vreo intrare din jurnal."""
    referinte = set()
    if not DIRECTOR_INTRARI.exists():
        return referinte

    for fisier in DIRECTOR_INTRARI.glob("*.md"):
        if fisier.name.startswith("_"):
            continue  # şablonul
        try:
            text = fisier.read_text(encoding="utf-8")
        except OSError:
            continue
        referinte.update(extrage_commituri_din_intrare(text))

    return referinte


def raporteaza(commituri: List[Dict[str, Any]], referinte: set) -> None:
    """Afișează acoperirea: ce are poveste scrisă și ce a rămas în backlog."""
    total = len(commituri)
    acoperite = [c for c in commituri if f"{c['depozit']}@{c['hash']}" in referinte]
    procent = (len(acoperite) / total * 100) if total else 0.0

    print(f"\n  {total} commit-uri, {len(acoperite)} cu intrare asociată ({procent:.0f}%).")

    # Referinţe care nu se potrivesc cu niciun commit real: hash scurtat altfel,
    # rescriere de istorie sau typo. În pagină ar dispărea tăcut, aici nu.
    hash_uri = {f"{c['depozit']}@{c['hash']}" for c in commituri}
    orfane = sorted(referinte - hash_uri)
    if orfane:
        print("\n  Referinţe din intrări fără commit corespunzător:")
        for referinta in orfane:
            print(f"    ! {referinta}")

    descoperite = [c for c in commituri if f"{c['depozit']}@{c['hash']}" not in referinte]
    if not descoperite:
        print("\n  Nimic în backlog.")
        return

    # Cele mai substanţiale commit-uri fără poveste, ca sugestie de scriere.
    candidati = sorted(descoperite, key=lambda c: c["linii_adaugate"], reverse=True)[:8]
    print("\n  Cele mai mari lucrări fără poveste scrisă:")
    for commit in candidati:
        print(
            f"    {commit['data']}  {commit['depozit']}@{commit['hash']}  "
            f"+{commit['linii_adaugate']:<5} {commit['mesaj'][:64]}"
        )


def main() -> int:
    _forteaza_utf8_pe_consola()

    analizor = argparse.ArgumentParser(
        description="Generează _data/commits.json din istoricul repo-urilor de cod."
    )
    analizor.add_argument(
        "--depozit",
        action="append",
        dest="depozite",
        metavar="NUME",
        help="Nume de director frate cu edr-journal (repetabil). "
             f"Implicit: {', '.join(DEPOZITE_IMPLICITE)}.",
    )
    analizor.add_argument(
        "--de-la",
        metavar="DATA",
        help="Limitează istoricul (orice format acceptat de --since, ex: 2026-06-01).",
    )
    argumente = analizor.parse_args()
    depozite = argumente.depozite or DEPOZITE_IMPLICITE

    toate: List[Dict[str, Any]] = []
    lipsa: List[str] = []

    for depozit in depozite:
        cale = _RADACINA_PROIECT / depozit
        try:
            commituri = citeste_commituri(cale, depozit, argumente.de_la)
        except EroareGit as eroare:
            print(f"  - {depozit}: {eroare}", file=sys.stderr)
            lipsa.append(depozit)
            continue

        print(f"  + {depozit}: {len(commituri)} commit-uri")
        toate.extend(commituri)

    if not toate:
        print("Niciun commit citit. Nu suprascriu fişierul de date.", file=sys.stderr)
        return 1

    # Cronologic descrescător: cel mai recent primul, ca în pagină.
    toate.sort(key=lambda c: (c["data_iso"], c["depozit"]), reverse=True)

    continut = {
        "generat_la": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "depozite": [d for d in depozite if d not in lipsa],
        "total": len(toate),
        "commituri": toate,
    }

    FISIER_IESIRE.parent.mkdir(parents=True, exist_ok=True)
    with open(FISIER_IESIRE, "w", encoding="utf-8", newline="\n") as fisier:
        json.dump(continut, fisier, ensure_ascii=False, indent=1)
        fisier.write("\n")

    print(f"\n  Scris {FISIER_IESIRE.relative_to(_RADACINA_JURNAL)} "
          f"({len(toate)} commit-uri din {len(continut['depozite'])} repo-uri).")

    raporteaza(toate, aduna_referinte())

    print("\n  Fişierul se comite în repo — GitHub Pages nu rulează scriptul.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
