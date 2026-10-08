"""قراءة ملف diff / dump من Betaflight CLI وتحويله إلى بيانات مرتبة."""
import re
from dataclasses import dataclass, field

# مثال: # Betaflight / STM32F7X2 (S7X2) 4.5.1 Jun 30 2024 / 10:13:59 ...
VERSION_RE = re.compile(
    r"#\s*(Betaflight|INAV|Emuflight)\s*/\s*(\S+)(?:\s*\(\S+\))?\s+(\d+\.\d+\.\d+)",
    re.IGNORECASE,
)
SET_RE = re.compile(r"^set\s+(\S+)\s*=\s*(.*)$", re.IGNORECASE)


@dataclass
class Config:
    firmware: str | None = None
    mcu: str | None = None
    version: str | None = None
    board: str | None = None
    craft_name: str | None = None
    master: dict = field(default_factory=dict)
    profiles: dict = field(default_factory=dict)
    rateprofiles: dict = field(default_factory=dict)
    active_profile: int = 0
    active_rateprofile: int = 0
    features_on: set = field(default_factory=set)
    features_off: set = field(default_factory=set)
    aux: list = field(default_factory=list)

    def get(self, key: str):
        """يدور على الإعداد في master ثم البروفايل النشط ثم بروفايل الريتس."""
        key = key.lower()
        for scope in (
            self.master,
            self.profiles.get(self.active_profile, {}),
            self.rateprofiles.get(self.active_rateprofile, {}),
        ):
            if key in scope:
                return scope[key]
        return None

    @property
    def changed_count(self) -> int:
        return (
            len(self.master)
            + sum(len(p) for p in self.profiles.values())
            + sum(len(r) for r in self.rateprofiles.values())
        )

    def looks_valid(self) -> bool:
        return self.version is not None or self.changed_count >= 3

    def version_tuple(self):
        if not self.version:
            return None
        return tuple(int(x) for x in self.version.split("."))


def parse(text: str) -> Config:
    cfg = Config()
    section, index = "master", None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        if line.startswith("#"):
            m = VERSION_RE.match(line)
            if m and cfg.version is None:
                cfg.firmware, cfg.mcu, cfg.version = m.group(1), m.group(2), m.group(3)
            continue

        parts = line.split()
        cmd = parts[0].lower()

        if cmd == "board_name" and len(parts) > 1:
            cfg.board = parts[1]
        elif cmd == "name" and len(parts) > 1:
            cfg.craft_name = " ".join(parts[1:])
        elif cmd == "profile" and len(parts) > 1 and parts[1].isdigit():
            section, index = "profile", int(parts[1])
            cfg.active_profile = index
        elif cmd == "rateprofile" and len(parts) > 1 and parts[1].isdigit():
            section, index = "rateprofile", int(parts[1])
            cfg.active_rateprofile = index
        elif cmd == "feature" and len(parts) > 1:
            name = parts[1].upper()
            if name.startswith("-"):
                cfg.features_off.add(name[1:])
            else:
                cfg.features_on.add(name)
        elif cmd == "aux":
            try:
                cfg.aux.append([int(x) for x in parts[1:]])
            except ValueError:
                pass
        elif cmd == "set":
            m = SET_RE.match(line)
            if not m:
                continue
            key, value = m.group(1).lower(), m.group(2).strip()
            if key == "craft_name" and value:
                cfg.craft_name = value
            if section == "profile":
                cfg.profiles.setdefault(index, {})[key] = value
            elif section == "rateprofile":
                cfg.rateprofiles.setdefault(index, {})[key] = value
            else:
                cfg.master[key] = value

    return cfg
