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
    source: str = "cli"  # cli أو blackbox
    log_count: int = 0  # عدد الطلعات في ملف البلاك بوكس

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


# ---------------- Blackbox (.BBL / .BFL) ----------------
# ملفات البلاك بوكس فيها كل الإعدادات في أولها كسطور تبدأ بـ "H "
# بعض القيم أرقام، فنحولها لأسمائها مثل الـCLI.
MOTOR_PROTOCOLS = ["PWM", "ONESHOT125", "ONESHOT42", "MULTISHOT", "BRUSHED",
                   "DSHOT150", "DSHOT300", "DSHOT600", "PROSHOT1000", "DISABLED"]
RATES_TYPES = ["BETAFLIGHT", "RACEFLIGHT", "KISS", "ACTUAL", "QUICK"]
FEATURE_GPS = 1 << 7
BBL_FW_RE = re.compile(r"(Betaflight|INAV|Emuflight)\s+(\d+\.\d+\.\d+)\S*.*?\s(\S+)$", re.IGNORECASE)


def _enum(values, raw):
    try:
        return values[int(raw)]
    except (ValueError, IndexError):
        return raw


def parse_blackbox(data: bytes) -> Config:
    cfg = Config(source="blackbox")
    cfg.log_count = data.count(b"H Product:")
    # نقرأ إعدادات آخر طلعة، لأنها الأحدث
    start = data.rfind(b"H Product:")
    if start < 0:
        return cfg
    headers = {}
    for raw in data[start:start + 200_000].split(b"\n"):
        if not raw.startswith(b"H "):
            break
        key, _, value = raw[2:].decode("latin1").partition(":")
        headers[key.strip()] = value.strip()

    m = BBL_FW_RE.search(headers.get("Firmware revision", ""))
    if m:
        cfg.firmware, cfg.version, cfg.mcu = m.group(1), m.group(2), m.group(3)
    board = headers.get("Board information", "").split()
    cfg.board = board[-1] if board else None
    cfg.craft_name = headers.get("Craft name") or None

    m = cfg.master
    if "motor_pwm_protocol" in headers:
        m["motor_pwm_protocol"] = _enum(MOTOR_PROTOCOLS, headers["motor_pwm_protocol"])
    if "dshot_bidir" in headers:
        m["dshot_bidir"] = "ON" if headers["dshot_bidir"] == "1" else "OFF"
    if "rates_type" in headers:
        m["rates_type"] = _enum(RATES_TYPES, headers["rates_type"])
    if "motor_poles" in headers:
        m["motor_poles"] = headers["motor_poles"]
    if "vbatcellvoltage" in headers:
        m["vbat_min_cell_voltage"] = headers["vbatcellvoltage"].split(",")[0]
    try:
        if int(headers.get("features", "0")) & FEATURE_GPS:
            cfg.features_on.add("GPS")
    except ValueError:
        pass
    return cfg
