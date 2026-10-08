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
        return Finding(WARN, "ما عرفت نسخة الفيرموير",
                       "استخدم هذا الأمر كامل عشان يطلع سطر النسخة في أول الملف:", "diff all")
    if (cfg.firmware or "").lower() == "betaflight" and v < (4, 4, 0):
        return Finding(WARN, "الفيرموير قديم",
                       "يفضّل تحدّث لآخر نسخة مستقرة، فيها تحسينات كبيرة في الفلاتر والأمان. نسختك:",
                       f"{cfg.firmware} {cfg.version}")
    return Finding(OK, "الفيرموير حديث", "نسختك:", f"{cfg.firmware} {cfg.version}")


def rule_arm_switch(cfg: Config):
    # aux <index> <modeId> <channel> <start> <end> ...  — modeId 0 = ARM
    for row in cfg.aux:
        if len(row) >= 5 and row[1] == 0 and row[3] != row[4]:
            return Finding(OK, "سويتش التسليح موجود", "على القناة:", f"AUX{row[2] + 1}")
    return Finding(BAD, "ما فيه سويتش تسليح",
                   "ما لقيت مود التسليح في تبويب المودات. الطيارة ما راح تتسلح.", "ARM")


def rule_bidir(cfg: Config):
    if (cfg.get("dshot_bidir") or "").upper() == "ON":
        return Finding(OK, "فلتر الدورات مفعّل", "الإعداد شغال:", "dshot_bidir = ON")
    return Finding(TIP, "فلتر الدورات غير مفعّل",
                   "إذا الإي إس سي يدعمه، فعّله لأنه يقلل النويز بشكل كبير. اكتب في الأوامر:",
                   "set dshot_bidir = ON")


def rule_protocol(cfg: Config):
    proto = (cfg.get("motor_pwm_protocol") or "").upper()
    if proto in {"PWM", "ONESHOT125", "ONESHOT42", "MULTISHOT", "BRUSHED"}:
        return Finding(WARN, "بروتوكول الموتورات قديم",
                       "الأفضل تغيره لداي شوت ٣٠٠ أو ٦٠٠. بروتوكولك الحالي:", proto)
    return None


def rule_small_angle(cfg: Config):
    if cfg.get("small_angle") == "180":
        return Finding(WARN, "التسليح ممكن وهي مقلوبة",
                       "هذا الإعداد يسمح بالتسليح بأي زاوية، انتبه وأنت تتعامل معها باليد:",
                       "small_angle = 180")
    return None


def rule_motor_poles(cfg: Config):
    poles = cfg.get("motor_poles")
    if poles and poles != "14":
        return Finding(TIP, "عدد أقطاب الموتور غير المعتاد",
                       "تأكد إنه مطابق لموتورك، لأن الرقم الغلط يخرب فلتر الدورات:",
                       f"motor_poles = {poles}")
    return None


def rule_low_voltage(cfg: Config):
    val = cfg.get("vbat_min_cell_voltage")
    if val and val.isdigit() and 100 < int(val) < 320:
        return Finding(WARN, "حد البطارية منخفض",
                       "النزول تحت ٣٫٢ فولت للخلية يضر بطاريات الليبو، إلا إذا كانت ليثيوم أيون. حدك الحالي:",
                       f"{int(val) / 100:.2f}V")
    return None


def rule_gps_rescue(cfg: Config):
    if "GPS" in cfg.features_on and (cfg.get("failsafe_procedure") or "").upper() != "GPS-RESCUE":
        return Finding(TIP, "عندك جي بي إس بس ما يستخدم للإنقاذ",
                       "خل الطيارة ترجع لحالها لو انقطع الإرسال. اكتب في الأوامر:",
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
