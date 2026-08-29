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

# Preserved primary data: the source exports cannot be reacquired.
DISCORD_DB = ROOT / "discord.db"
