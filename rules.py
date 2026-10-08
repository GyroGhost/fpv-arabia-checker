"""قواعد الفحص. كل قاعدة دالة تستقبل Config وترجع Finding أو None.
لإضافة قاعدة جديدة: اكتب دالة وأضفها لقائمة RULES تحت."""
from dataclasses import dataclass

from cli_parser import Config

OK, TIP, WARN, BAD = "ok", "tip", "warn", "bad"


@dataclass
class Finding:
    level: str
    title: str
    detail: str
    code: str = ""  # أمر أو قيمة إنجليزية تنعرض في سطر لحالها


def rule_version(cfg: Config):
    v = cfg.version_tuple()
    if v is None:
        return Finding(WARN, "ما عرفت نسخة الـFirmware",
                       "استخدم هذا الأمر في الـCLI عشان يطلع سطر النسخة في أول الملف:", "diff all")
    if (cfg.firmware or "").lower() == "betaflight" and v < (4, 4, 0):
        return Finding(WARN, "نسخة Firmware قديمة",
                       "يفضّل تحدّث لآخر نسخة مستقرة، فيها تحسينات كبيرة في الـFilters والأمان. نسختك:",
                       f"{cfg.firmware} {cfg.version}")
    return Finding(OK, "نسخة Firmware حديثة", "نسختك:", f"{cfg.firmware} {cfg.version}")


def rule_arm_switch(cfg: Config):
    if cfg.source == "blackbox":
        return None  # ملف البلاك بوكس ما فيه الـModes
    # aux <index> <modeId> <channel> <start> <end> ...  — modeId 0 = ARM
    for row in cfg.aux:
        if len(row) >= 5 and row[1] == 0 and row[3] != row[4]:
            return Finding(OK, "سويتش الـARM موجود", "على القناة:", f"AUX{row[2] + 1}")
    return Finding(BAD, "ما فيه سويتش ARM",
                   "ما لقيت الـARM في تبويب Modes، يعني الطيارة ما راح تتسلح.", "ARM")


def rule_bidir(cfg: Config):
    if (cfg.get("dshot_bidir") or "").upper() == "ON":
        return Finding(OK, "الـRPM Filter مفعّل", "الإعداد شغال:", "dshot_bidir = ON")
    return Finding(TIP, "الـRPM Filter غير مفعّل",
                   "إذا الـESC يدعم Bidirectional DShot فعّله، لأنه يقلل الـNoise بشكل كبير. اكتب في الـCLI:",
                   "set dshot_bidir = ON")


def rule_protocol(cfg: Config):
    proto = (cfg.get("motor_pwm_protocol") or "").upper()
    if proto in {"PWM", "ONESHOT125", "ONESHOT42", "MULTISHOT", "BRUSHED"}:
        return Finding(WARN, "بروتوكول الـMotors قديم",
                       "الأفضل تغيره إلى DShot300 أو DShot600. بروتوكولك الحالي:", proto)
    return None


def rule_small_angle(cfg: Config):
    if cfg.get("small_angle") == "180":
        return Finding(WARN, "الـARM ممكن وهي مقلوبة",
                       "هذا الإعداد يسمح بالـARM بأي زاوية، انتبه وأنت تتعامل معها باليد:",
                       "small_angle = 180")
    return None


def rule_motor_poles(cfg: Config):
    poles = cfg.get("motor_poles")
    if poles and poles != "14":
        return Finding(TIP, "عدد الـMotor Poles غير معتاد",
                       "تأكد إنه مطابق لموتورك، لأن الرقم الغلط يخرب الـRPM Filter:",
                       f"motor_poles = {poles}")
    return None


def rule_low_voltage(cfg: Config):
    val = cfg.get("vbat_min_cell_voltage")
    if val and val.isdigit() and 100 < int(val) < 320:
        return Finding(WARN, "حد الـBattery منخفض",
                       "النزول تحت 3.2V للخلية يضر بطاريات الـLiPo، إلا إذا كانت Li-ion. حدك الحالي:",
                       f"{int(val) / 100:.2f}V")
    return None


def rule_gps_rescue(cfg: Config):
    if "GPS" in cfg.features_on and (cfg.get("failsafe_procedure") or "").upper() != "GPS-RESCUE":
        return Finding(TIP, "عندك GPS بس الـFailsafe مو GPS Rescue",
                       "خل الطيارة ترجع لحالها لو انقطع الإرسال. اكتب في الـCLI:",
                       "set failsafe_procedure = GPS-RESCUE")
    return None


RULES = [
    rule_version,
    rule_arm_switch,
    rule_protocol,
    rule_bidir,
    rule_motor_poles,
    rule_small_angle,
    rule_low_voltage,
    rule_gps_rescue,
]


def analyze(cfg: Config) -> list[Finding]:
    return [f for rule in RULES if (f := rule(cfg))]
