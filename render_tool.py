"""ربط البوت بأداة BlackBox_CSV_Render (nerdCopter).

الأداة تقرأ ملف BBL وتطلع رسومات PNG. نقص من الملف الطلعة المطلوبة بس،
عشان الأداة ما تحلل كل الطلعات وتطوّل.
الكود: https://github.com/nerdCopter/BlackBox_CSV_Render  (AGPL-3.0)
"""
import os
import pathlib
import shutil
import subprocess
import tempfile

SOURCE_URL = "https://github.com/nerdCopter/BlackBox_CSV_Render"
_EXE = "BlackBox_CSV_Render.exe" if os.name == "nt" else "BlackBox_CSV_Render"
_DEFAULT = pathlib.Path(__file__).resolve().parent.parent / "BlackBox_CSV_Render" / "target" / "release" / _EXE
BIN = pathlib.Path(os.getenv("RENDER_BIN") or _DEFAULT)
TIMEOUT_S = int(os.getenv("RENDER_TIMEOUT", "180"))
MAX_TOTAL_BYTES = 9_000_000  # حد الرفع في ديسكورد

# (جزء من اسم الملف، العنوان، الشرح)
PLOTS = [
    ("Step_Response", "Step Response",
     "سرعة استجابة الطيارة لحركة الستك. الخط المثالي يطلع بسرعة لـ1 ويوقف بدون ما يتعداه كثير."),
    ("SetpointVsGyro", "Setpoint vs Gyro",
     "الـSetpoint وين تبي الطيارة تروح، والـGyro وين راحت فعلاً. كل ما تطابقوا أحسن."),
    ("Gyro_Spectrums", "Gyro Spectrum",
     "الـNoise في الـGyro قبل الـFilters وبعدها، مع القمم المكتشفة."),
    ("Throttle_Freq_Heatmap", "Throttle / Frequency Heatmap",
     "الـNoise مقابل الـThrottle، نفس رسمة الـBlackbox Explorer."),
    ("D_Term_Spectrums", "D-Term Spectrum",
     "الـNoise اللي يوصل للـD-term، وهو اللي يسخّن الـMotors."),
    ("Motor_Spectrums", "Motor Spectrum",
     "اهتزاز إشارة كل Motor. لو Motor واحد مختلف عن الباقي، افحصه."),
]


# مطفية افتراضياً إلى ما يوافق صاحب الأداة. للتفعيل: ENABLE_RENDER=1 في ملف .env
ENABLED = os.getenv("ENABLE_RENDER", "0") == "1"


def available() -> bool:
    return ENABLED and BIN.is_file()


def _split_flight(data: bytes, index: int) -> bytes:
    """يرجع بايتات طلعة وحدة (index يبدأ من 1)."""
    marker = b"H Product:"
    offs, pos = [], data.find(marker)
    while pos >= 0:
        offs.append(pos)
        pos = data.find(marker, pos + 1)
    if not offs or index < 1 or index > len(offs):
        return data
    end = offs[index] if index < len(offs) else len(data)
    return data[offs[index - 1]:end]


def render(data: bytes, flight_index: int):
    """يشغّل الأداة ويرجع (مجلد مؤقت، [(عنوان، شرح، مسار الصورة)], رسالة خطأ)."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="bbr_"))
    src = tmp / "flight.bbl"
    src.write_bytes(_split_flight(data, flight_index))
    out = tmp / "out"
    out.mkdir()
    cmd = [str(BIN), str(src), "--extended", "-F", "-O", str(out)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S,
                              encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return tmp, [], f"الأداة طوّلت أكثر من {TIMEOUT_S} ثانية"
    pngs = sorted(out.rglob("*.png")) + sorted(tmp.glob("*.png"))
    if not pngs:
        log = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip().splitlines()
        tail = " | ".join(log[-8:]) if log else "(no output)"
        files = ", ".join(p.name for p in tmp.rglob("*") if p.is_file())
        return tmp, [], f"exit={proc.returncode} files=[{files}] output: {tail}"

    picked, total = [], 0
    for key, title, desc in PLOTS:
        match = next((p for p in pngs if key in p.name), None)
        if not match:
            continue
        size = match.stat().st_size
        if total + size > MAX_TOTAL_BYTES:
            break
        total += size
        picked.append((title, desc, match))
    return tmp, picked, None


def cleanup(tmp: pathlib.Path):
    shutil.rmtree(tmp, ignore_errors=True)
