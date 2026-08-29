"""Where everything lives.

The one place that knows the repository layout, so a module that moves does not
take a hardcoded `parent.parent` with it.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CORPUS = ROOT / "corpus"
RECORDS = CORPUS / "records"

MABINOGION = RECORDS / "R12.2" / "artifacts" / "mabinogion"
GEMATRIA_PRIMUS = RECORDS / "R13.2" / "artifacts" / "gematria-primus"
LP = RECORDS / "R14.7" / "artifacts" / "liber-primus"
COMMUNICATIONS_INDEX = CORPUS / "communications.csv"
CICADA_PUBLIC_KEY = CORPUS / "identity" / "cicada-3301-public-key.asc"

# Preserved primary data: the source exports cannot be reacquired.
DISCORD_DB = ROOT / "discord.db"
