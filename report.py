"""يحوّل نتيجة الفحص إلى تقرير (يستخدمه البوت ويستخدمه الاختبار المحلي)."""
from cli_parser import Config
from rules import BAD, OK, TIP, WARN, Finding

ICONS = {OK: "✅", TIP: "💡", WARN: "⚠️", BAD: "❌"}
SECTIONS = [(BAD, "مشاكل لازم تنحل"), (WARN, "تنبيهات"), (TIP, "نصائح"), (OK, "سليم")]


def summary_pairs(cfg: Config) -> list[tuple[str, str]]:
    rows = [
        ("الطيارة", cfg.craft_name),
        ("الـFirmware", f"{cfg.firmware} {cfg.version}" if cfg.version else None),
        ("الـBoard", cfg.board or cfg.mcu),
        ("الـProtocol", cfg.get("motor_pwm_protocol")),
        ("نوع الـRates", cfg.get("rates_type")),
        ("عدد الطلعات", str(cfg.log_count) if cfg.log_count else None),
        ("إعدادات متغيرة", str(cfg.changed_count) if cfg.source == "cli" else None),
    ]
    return [(k, v) for k, v in rows if v]


def summary_lines(cfg: Config) -> list[str]:
    return [f"**{k}:**\n`{v}`" for k, v in summary_pairs(cfg)]


def sections(findings: list[Finding]) -> list[tuple[str, str]]:
    """يرجع [(عنوان القسم، النص)] مع احترام حد ديسكورد 1024 حرف للحقل."""
    out = []
    for level, name in SECTIONS:
        items = [
            f"{ICONS[level]} **{f.title}**\n{f.detail}" + (f"\n```\n{f.code}\n```" if f.code else "")
            for f in findings if f.level == level
        ]
        if items:
            text = "\n\n".join(items)
            if len(text) > 1020:
                text = text[:1017] + "..."
            out.append((name, text))
    return out


def worst_level(findings: list[Finding]) -> str:
    for level in (BAD, WARN, TIP):
        if any(f.level == level for f in findings):
            return level
    return OK


def as_text(cfg: Config, findings: list[Finding]) -> str:
    parts = ["== فحص إعدادات الطيارة ==", *summary_lines(cfg), ""]
    for name, text in sections(findings):
        parts += [f"--- {name} ---", text, ""]
    return "\n".join(parts)
