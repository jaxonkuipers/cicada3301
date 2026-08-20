"""Where everything lives.

The one place that knows the repository layout, so a module that moves does not
take a hardcoded `parent.parent` with it.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CORPUS = ROOT / "corpus"
LP = CORPUS / "liber-primus"

DISCORD = ROOT / "discord"
# Regenerable. Delete it and rerun `python3 -m tools.build_discord_db`.
DISCORD_DB = ROOT / "discord.db"
