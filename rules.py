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


def rule_version(cfg: Config):
    v = cfg.version_tuple()
    if v is None:
        return Finding(WARN, "ما عرفت نسخة الفيرموير",
                       "استخدم أمر `diff all` كامل عشان يطلع سطر النسخة في أول الملف.")
    if (cfg.firmware or "").lower() == "betaflight" and v < (4, 4, 0):
        return Finding(WARN, f"الفيرموير قديم ({cfg.version})",
                       "يفضّل تحدّث لآخر نسخة مستقرة، فيها تحسينات كبيرة في الفلاتر والأمان.")
    return Finding(OK, f"الفيرموير {cfg.firmware} {cfg.version}", "نسخة حديثة.")


def rule_arm_switch(cfg: Config):
    # aux <index> <modeId> <channel> <start> <end> ...  — modeId 0 = ARM
    for row in cfg.aux:
        if len(row) >= 5 and row[1] == 0 and row[3] != row[4]:
            return Finding(OK, "سويتش التسليح موجود", f"ARM على AUX{row[2] + 1}.")
    return Finding(BAD, "ما فيه سويتش تسليح (ARM)",
                   "ما لقيت ARM في تبويب Modes. الطيارة ما راح تتسلح.")


def rule_bidir(cfg: Config):
    if (cfg.get("dshot_bidir") or "").upper() == "ON":
        return Finding(OK, "RPM Filter مفعّل", "Bidirectional DShot شغال.")
    return Finding(TIP, "RPM Filter غير مفعّل",
                   "إذا الـESC يدعم (BLHeli_32 / AM32 / Bluejay) فعّل `dshot_bidir = ON`، "
                   "يقلل النويز بشكل كبير.")


def rule_protocol(cfg: Config):
    proto = (cfg.get("motor_pwm_protocol") or "").upper()
    if proto in {"PWM", "ONESHOT125", "ONESHOT42", "MULTISHOT", "BRUSHED"}:
        return Finding(WARN, f"بروتوكول الموتورات {proto}",
                       "بروتوكول قديم. الأفضل DSHOT300 أو DSHOT600.")
    return None


def rule_small_angle(cfg: Config):
    if cfg.get("small_angle") == "180":
        return Finding(WARN, "التسليح ممكن وهي مقلوبة",
                       "`small_angle = 180` يسمح بالتسليح بأي زاوية. انتبه وأنت تتعامل معها باليد.")
    return None


def rule_motor_poles(cfg: Config):
    poles = cfg.get("motor_poles")
    if poles and poles != "14":
        return Finding(TIP, f"عدد أقطاب الموتور = {poles}",
                       "تأكد إنه مطابق لموتورك، لأن الرقم الغلط يخرب الـRPM filter.")
    return None


def rule_low_voltage(cfg: Config):
    val = cfg.get("vbat_min_cell_voltage")
    if val and val.isdigit() and 100 < int(val) < 320:
        return Finding(WARN, f"حد البطارية منخفض ({int(val) / 100:.2f}V للخلية)",
                       "النزول تحت 3.2V يضر بطاريات LiPo. إلا إذا كانت Li-ion.")
    return None


def rule_gps_rescue(cfg: Config):
    if "GPS" in cfg.features_on and (cfg.get("failsafe_procedure") or "").upper() != "GPS-RESCUE":
        return Finding(TIP, "عندك GPS بس الـFailsafe مو GPS Rescue",
                       "تقدر تخلي `failsafe_procedure = GPS-RESCUE` عشان ترجع الطيارة لو انقطع الإرسال.")
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
