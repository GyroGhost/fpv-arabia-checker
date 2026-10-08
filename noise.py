"""تحليل الـNoise من ملف Blackbox ورسم الـSpectrum.

يفك الملف بمكتبة orangebox، ويختار أطول طلعة، ويحسب الـFFT للـGyro
قبل الفلترة (gyroUnfilt) وبعدها (gyroADC) لكل محور.
"""
import io
import logging
import os
import tempfile
from dataclasses import dataclass, field

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from orangebox import Parser  # noqa: E402

logging.getLogger("orangebox").setLevel(logging.ERROR)

AXES = ["Roll", "Pitch", "Yaw"]
MIN_SECONDS = 1.5

# ألوان الثيم الداكن (مثل ديسكورد)
SURFACE = "#1a1a19"
TEXT = "#ffffff"
TEXT_2 = "#c3c2b7"
GRID = "#3a3a38"
RAW = "#d95926"       # قبل الفلترة
FILTERED = "#3987e5"  # بعد الفلترة


@dataclass
class NoiseResult:
    log_index: int
    seconds: float
    sample_rate: float
    has_unfiltered: bool
    peaks: list = field(default_factory=list)       # [(axis, hz, strength_db)]
    reduction_db: float | None = None                 # قد إيش الفلاتر شالت من الـNoise
    png: bytes = b""


def _welch(x: np.ndarray, fs: float, nper: int = 512):
    """Power Spectral Density بطريقة Welch (بدون scipy)."""
    x = x - np.mean(x)
    nper = min(nper, len(x))
    step = nper // 2
    win = np.hanning(nper)
    scale = fs * (win ** 2).sum()
    segs = [x[i:i + nper] for i in range(0, len(x) - nper + 1, step)]
    psd = np.mean([np.abs(np.fft.rfft(s * win)) ** 2 for s in segs], axis=0) / scale
    freqs = np.fft.rfftfreq(nper, 1 / fs)
    return freqs, psd


def _load_longest(path: str):
    parser = Parser.load(path)
    best = None
    for i in range(1, parser.reader.log_count + 1):
        try:
            parser.set_log_index(i)
            names = parser.field_names
            rows = [f.data for f in parser.frames()]
        except Exception:
            continue
        if len(rows) < 100 or "time" not in names:
            continue
        if best is None or len(rows) > len(best[2]):
            best = (i, names, rows)
    return best


def _db(p):
    return 10 * np.log10(np.maximum(p, 1e-12))


def analyze_noise(data: bytes) -> NoiseResult | None:
    with tempfile.NamedTemporaryFile(suffix=".bbl", delete=False) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        best = _load_longest(path)
    finally:
        os.unlink(path)
    if not best:
        return None

    log_index, names, rows = best
    wanted = ["time"] + [f"gyroADC[{i}]" for i in range(3)] + [f"gyroUnfilt[{i}]" for i in range(3)]
    idx = [names.index(n) for n in wanted if n in names]
    clean = []
    for r in rows:
        try:
            clean.append([float(r[j]) for j in idx])
        except (ValueError, TypeError, IndexError):
            continue
    names = [names[j] for j in idx]
    arr = np.array(clean, dtype=float)
    arr = arr[np.argsort(arr[:, 0])]
    t = arr[:, names.index("time")] / 1e6
    seconds = float(t[-1] - t[0])
    if seconds < MIN_SECONDS:
        return None
    fs = 1 / float(np.median(np.diff(t)))

    def col(name):
        return arr[:, names.index(name)] if name in names else None

    has_unf = all(col(f"gyroUnfilt[{i}]") is not None for i in range(3))
    res = NoiseResult(log_index, seconds, fs, has_unf)

    plt.rcParams.update({"font.size": 10, "font.family": "DejaVu Sans"})
    fig, axs = plt.subplots(3, 1, figsize=(9, 8.2), sharex=True, facecolor=SURFACE)
    raw_band, filt_band = [], []

    for i, ax in enumerate(axs):
        ax.set_facecolor(SURFACE)
        f, p_filt = _welch(col(f"gyroADC[{i}]"), fs)
        band = (f >= 60) & (f <= fs / 2 * 0.95)

        if has_unf:
            _, p_raw = _welch(col(f"gyroUnfilt[{i}]"), fs)
            ax.plot(f, _db(p_raw), color=RAW, lw=2, label="Before filters (gyroUnfilt)")
            raw_band.append(p_raw[band].mean())
            src = p_raw
        else:
            src = p_filt
        ax.plot(f, _db(p_filt), color=FILTERED, lw=2, label="After filters (gyroADC)")
        filt_band.append(p_filt[band].mean())

        # أعلى قمة في المنطقة المهمة، ونقارنها بالمستوى العادي حولها
        sd = _db(src)
        smooth = np.convolve(sd, np.ones(5) / 5, mode="same")
        k = int(np.argmax(np.where(band, smooth, -np.inf)))
        strength = float(smooth[k] - np.median(smooth[band]))
        k = max(range(max(k - 3, 0), min(k + 4, len(sd))), key=lambda j: sd[j])
        if strength >= 6:
            res.peaks.append((AXES[i], float(f[k]), strength))
            ax.annotate(f"{f[k]:.0f} Hz", (f[k], sd[k]), xytext=(8, -2),
                        textcoords="offset points", color=TEXT, fontsize=10, fontweight="bold")
            ax.plot([f[k]], [sd[k]], "o", ms=8, color=RAW if has_unf else FILTERED,
                    mec=SURFACE, mew=2)

        ax.set_ylabel(f"{AXES[i]}\n(dB)", color=TEXT_2)
        ax.grid(True, color=GRID, lw=0.6)
        ax.tick_params(colors=TEXT_2)
        for s in ax.spines.values():
            s.set_visible(False)

    if has_unf:
        res.reduction_db = float(_db(np.mean(raw_band)) - _db(np.mean(filt_band)))

    fig.legend(*axs[0].get_legend_handles_labels(), loc="upper left", ncol=2, frameon=False,
               labelcolor=TEXT, bbox_to_anchor=(0.05, 0.955))
    axs[-1].set_xlabel("Frequency (Hz)", color=TEXT_2)
    axs[-1].set_xlim(0, fs / 2)
    fig.suptitle(f"Gyro Noise Spectrum  ·  log {log_index}  ·  {seconds:.1f}s",
                 color=TEXT, fontsize=13, fontweight="bold", x=0.06, y=0.985, ha="left")
    fig.text(0.97, 0.985, "FPV Arabia", color=TEXT_2, ha="right", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.92))

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, facecolor=SURFACE)
    plt.close(fig)
    res.png = buf.getvalue()
    return res


def explain(res: NoiseResult, rpm_filter_on: bool | None) -> list[tuple[str, str]]:
    """شرح عربي للرسمة: [(العنوان، النص)]."""
    out = [("الطلعة اللي انحللت",
            f"أطول طلعة في الملف، رقم {res.log_index}، ومدتها {res.seconds:.1f} ثانية.")]

    if res.peaks:
        lines = []
        for axis, hz, strength in res.peaks:
            lines.append(f"• على الـ{axis} عند `{hz:.0f} Hz`")
        low = [hz for _, hz, _ in res.peaks if hz < 120]
        hint = ("غالباً سببها Frame مرتخي أو براغي الـStack، لأنها ترددات منخفضة."
                if low else
                "غالباً سببها Prop معوج أو Motor فيه مشكلة أو مو متوازن.")
        if rpm_filter_on is False:
            hint += "\nوالـRPM Filter عندك مطفي، تفعيله يشيل أغلب هالـNoise."
        out.append(("⚠️ فيه قمة Noise واضحة", "\n".join(lines) + "\n" + hint))
    else:
        out.append(("✅ ما فيه قمة Noise بارزة", "الـGyro نظيف نسبياً قبل الفلترة."))

    if res.reduction_db is not None:
        r = res.reduction_db
        verdict = ("الـFilters شغالة زين" if r >= 15 else
                   "الـFilters شغالة بس ممكن تتحسن" if r >= 8 else
                   "الـFilters ما تشيل كفاية")
        out.append(("الـFilters", f"{verdict}، شالت تقريباً `{r:.0f} dB` من الـNoise."))
    else:
        out.append(("الـFilters",
                    "الملف ما فيه الـGyro قبل الفلترة، فما أقدر أقيس أداء الـFilters.\n"
                    "فعّل تسجيله من تبويب الـBlackbox."))
    return out
