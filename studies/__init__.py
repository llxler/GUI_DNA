"""GUI-DNA research protocols."""

from pathlib import Path
import sys


class _HistoricalStudyNames:
    """Resolve pre-publication package names for frozen commands on demand."""

    gui_dna_legacy_layout = True

    @classmethod
    def find_spec(cls, fullname, path=None, target=None):
        package, dot, name = fullname.partition(".")
        if not dot or package not in ("studies", "test") or "." in name or not path:
            return None
        base = Path(path[0])
        if (base / name).is_dir() or (base / (name + ".py")).is_file():
            return None
        from .layout import locations, restore

        if name in locations():
            restore()
        return None


if not any(getattr(finder, "gui_dna_legacy_layout", False) for finder in sys.meta_path):
    sys.meta_path.insert(0, _HistoricalStudyNames)
