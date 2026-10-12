"""التوصيات النهائية: تجمع نتائج فحص الإعدادات وتحليل الـNoise في قائمة مرتبة حسب الأهمية."""
from rules import BAD, TIP, WARN

NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"]
MAX_ITEMS = 6
PRIORITY = {BAD: 0, WARN: 1, TIP: 2}


def _noise_items(res):
    """توصيات من تحليل الـNoise: (أولوية، عنوان، شرح، أمر)."""
    if res is None:
        return []
    out = []
    no_filters = bool(res.heat_png) and not res.filter_lines and not res.filter_hidden
    if no_filters:
        out.append((0, "الـGyro و D-term Lowpass Filters مطفية",
                    "الطيارة تطير بالـNoise الخام، وهذا يسخّن الـMotors بسرعة. رجّعها للقيم الافتراضية "
                    "من تبويب الـPID Tuning، أو اكتب في الـCLI:",
                    "set gyro_lpf1_dyn_min_hz = 250\nset gyro_lpf1_dyn_max_hz = 500\n"
                    "set gyro_lpf2_static_hz = 500\nset dterm_lpf1_dyn_min_hz = 75\n"
                    "set dterm_lpf1_dyn_max_hz = 150\nset dterm_lpf2_static_hz = 150\nsave"))
    elif res.reduction_db is not None and res.reduction_db < 8:
        out.append((1, "الـFilters ما تشيل كفاية",
                    f"شالت بس تقريباً {res.reduction_db:.0f}dB من الـNoise. "
                    "راجع إعدادات الـFilters أو فعّل الـRPM Filter.", ""))

    if res.peaks:
        low = [hz for _, hz, _ in res.peaks if hz < 120]
        where = ", ".join(f"{axis} {hz:.0f}Hz" for axis, hz, _ in res.peaks)
        if low:
            out.append((1, "افحص الـFrame والبراغي",
                        f"فيه Noise منخفض التردد ({where}). شد براغي الـFrame والـStack، "
                        "وتأكد ما فيه Arm مشقوق أو شي يهتز.", ""))
        else:
            out.append((1, "افحص الـProps والـMotors",
                        f"فيه قمة Noise ({where}). غيّر الـProps، ولف كل Motor بإيدك "
                        "وحس أي خشونة في الـBearing.", ""))

    if res.sample_rate and res.sample_rate < 1000:
        out.append((2, "سجّل الـBlackbox بسرعة أعلى",
                    f"ملفك مسجل تقريباً بـ{res.sample_rate:.0f}Hz، فالتحليل يوقف عند "
                    f"{res.sample_rate / 2:.0f}Hz وتختفي تفاصيل الـMotors. ارفع السرعة للطلعة الجاية:",
                    "set blackbox_sample_rate = 1/2\nsave"))
    return out


def build(findings, noise_res=None):
    """يرجع [(رقم، عنوان، شرح، أمر)] مرتبة، أو [] إذا كل شي سليم."""
    items = []
    seen = set()
    for f in findings:
        if f.level not in PRIORITY:
            continue
        items.append((PRIORITY[f.level], f.title, f.detail, f.code))
        seen.add(f.title)
    items += _noise_items(noise_res)
    items.sort(key=lambda x: x[0])
    return [(NUMS[i], t, d, c) for i, (_, t, d, c) in enumerate(items[:MAX_ITEMS])]


def summary_line(items):
    if not items:
        return "✅ ما لقيت شي يحتاج تعديل. طيارتك سليمة 👌"
    return f"لقيت **{len(items)}** أشياء تستاهل تنتبه لها، مرتبة من الأهم:"
