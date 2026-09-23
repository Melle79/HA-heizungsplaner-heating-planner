"""Die Fassung – eine Quelle, nicht zwei.

Sie stand hier einmal als Zeichenkette, und genau das ging schief: Beim
Ausliefern wurde ``config.yaml`` hochgezählt und diese Datei vergessen. Die
Oberfläche zeigte über drei Fassungen hinweg „v1.31.1“, während das Add-on
längst etwas anderes war – eine Lüge, die niemandem auffällt, bis jemand
wissen will, ob ein Fehler schon behoben ist.

Jetzt wird gefragt: ``run.sh`` reicht die Nummer durch, die der Supervisor
kennt, und sonst steht sie in der ``config.yaml`` daneben. Beides kommt aus
derselben Zeile.
"""
from __future__ import annotations

import os
import pathlib
import re


def _aus_config() -> str:
    # Die config.yaml liegt im Abbild neben dem Quelltext. Ein Zeilenmuster
    # genügt – für eine einzige Zahl lohnt keine YAML-Bibliothek.
    for pfad in (pathlib.Path(__file__).resolve().parent.parent / "config.yaml",
                 pathlib.Path("/app/config.yaml")):
        try:
            treffer = re.search(r'^version:\s*"?([^"\s]+)"?',
                                pfad.read_text(encoding="utf-8"), re.M)
        except OSError:
            continue
        if treffer:
            return treffer.group(1)
    return "?"


VERSION = os.environ.get("ADDON_VERSION") or _aus_config()
