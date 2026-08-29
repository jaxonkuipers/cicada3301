"""Where everything lives.

The one place that knows the repository layout, so a module that moves does not
take a hardcoded `parent.parent` with it.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CORPUS = ROOT / "corpus"
PUZZLE_2012 = CORPUS / "2012"
PUZZLE_2013 = CORPUS / "2013"
PUZZLE_2014 = CORPUS / "2014"

MABINOGION = PUZZLE_2012 / "mabinogion"
GEMATRIA_PRIMUS = PUZZLE_2013 / "gematria-primus"
LP = PUZZLE_2014 / "liber-primus"
COMMUNICATIONS_INDEX = CORPUS / "communications.csv"
CICADA_PUBLIC_KEY = CORPUS / "identity" / "cicada-3301-public-key.asc"

# Public-domain English prose used to train lib.fitness. Not Cicada material
# (that is corpus/) and not derived analysis (that is research/).
REFERENCE = ROOT / "reference"

DISCORD = ROOT / "discord"
# Regenerable. Delete it and rerun `python3 -m tools.build_discord_db`.
DISCORD_DB = ROOT / "discord.db"
