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
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
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
FILTER_LINE = "#1baf7a"
# نفس ألوان الـBlackbox Explorer: أسود ← أحمر ← أبيض
HEAT = LinearSegmentedColormap.from_list(
    "bbx", [(0, "#000000"), (0.35, "#5a0000"), (0.65, "#e00000"), (0.85, "#ff6060"), (1, "#ffffff")])


@dataclass
class NoiseResult:
    log_index: int
    seconds: float
    sample_rate: float
    has_unfiltered: bool
    peaks: list = field(default_factory=list)       # [(axis, hz, strength_db)]
    reduction_db: float | None = None                 # قد إيش الفلاتر شالت من الـNoise
    png: bytes = b""
    heat_png: bytes = b""
    flights_used: int = 0


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
    """يرجع (أطول طلعة، كل الطلعات، الـheaders)."""
    parser = Parser.load(path)
    best = None
    logs = []
    headers = {}
    for i in range(1, parser.reader.log_count + 1):
        try:
            parser.set_log_index(i)
            names = parser.field_names
            rows = [f.data for f in parser.frames()]
        except Exception:
            continue
        if len(rows) < 100 or "time" not in names:
            continue
        headers = dict(parser.headers)
        logs.append((names, rows))
        if best is None or len(rows) > len(best[2]):
            best = (i, names, rows)
    return best, logs, headers


def _to_array(names, rows, wanted):
    idx = [names.index(n) for n in wanted if n in names]
    clean = []
    for r in rows:
        try:
            clean.append([float(r[j]) for j in idx])
        except (ValueError, TypeError, IndexError):
            continue
    if not clean:
        return None, []
    arr = np.array(clean, dtype=float)
    return arr[np.argsort(arr[:, 0])], [names[j] for j in idx]


def _db(p):
    return 10 * np.log10(np.maximum(p, 1e-12))


def analyze_noise(data: bytes) -> NoiseResult | None:
    with tempfile.NamedTemporaryFile(suffix=".bbl", delete=False) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        best, logs, headers = _load_longest(path)
    finally:
        os.unlink(path)
    if not best:
        return None

    log_index, names, rows = best
    wanted = ["time"] + [f"gyroADC[{i}]" for i in range(3)] + [f"gyroUnfilt[{i}]" for i in range(3)]
    arr, names = _to_array(names, rows, wanted)
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

    try:
        _heatmap(res, logs, headers)
    except Exception as e:  # الرسمة الثانية اختيارية
        print(f"[warn] heatmap {type(e).__name__}: {e}")
    return res


def _filter_lines(ax, headers, fmax):
    """خطوط الـGyro Filters مثل الـBlackbox Explorer."""
    def ints(key):
        v = headers.get(key, "")
        try:
            if isinstance(v, (list, tuple)):
                return [int(x) for x in v]
            return [int(x) for x in str(v).split(",")]
        except ValueError:
            return []
    thr = np.linspace(0, 100, 50)
    dyn = ints("gyro_lpf1_dyn_hz")
    if len(dyn) == 2 and dyn[0] > 0:
        expo = (ints("gyro_lpf1_dyn_expo") or [0])[0] / 10
        x = thr / 100
        curve = x * (1 - expo) + x ** 3 * expo  # تقريب لمنحنى الـexpo
        hz = dyn[0] + (dyn[1] - dyn[0]) * curve
        ax.plot(hz, thr, color=FILTER_LINE, lw=1.4)
        ax.text(dyn[0] + 4, 4, f"LPF1 dyn {dyn[0]}-{dyn[1]}Hz", color=FILTER_LINE, fontsize=8)
    else:
        st = (ints("gyro_lpf1_static_hz") or [0])[0]
        if 0 < st < fmax:
            ax.axvline(st, color=FILTER_LINE, lw=1.4)
            ax.text(st + 4, 96, f"LPF1 {st}Hz", color=FILTER_LINE, fontsize=8, va="top")
    st2 = (ints("gyro_lpf2_static_hz") or [0])[0]
    if 0 < st2 < fmax:
        ax.axvline(st2, color=FILTER_LINE, lw=1.4)
        ax.text(st2 - 4, 96, f"LPF2 {st2}Hz", color=FILTER_LINE, fontsize=8, va="top", ha="right")


def _heatmap(res: NoiseResult, logs, headers, nfft: int = 128, step: int = 16):
    """الـSpectrum مقابل الـThrottle من كل الطلعات اللي في الملف."""
    nbins = 100
    nf = nfft // 2 + 1
    grids = {"raw": np.zeros((nbins, nf)), "flt": np.zeros((nbins, nf))}
    counts = np.zeros(nbins)
    win = np.hanning(nfft)
    fs_all = []

    for names, rows in logs:
        wanted = (["time", "rcCommand[3]"] + [f"gyroADC[{i}]" for i in range(2)]
                  + [f"gyroUnfilt[{i}]" for i in range(2)])
        arr, cols = _to_array(names, rows, wanted)
        if arr is None or "rcCommand[3]" not in cols or len(arr) < nfft * 2:
            continue
        c = {n: arr[:, k] for k, n in enumerate(cols)}
        fs_all.append(1e6 / float(np.median(np.diff(c["time"]))))
        thr = np.clip((c["rcCommand[3]"] - 1000) / 10, 0, 99.9)
        flt = [c[f"gyroADC[{i}]"] for i in range(2)]
        raw = [c[f"gyroUnfilt[{i}]"] for i in range(2)] if "gyroUnfilt[0]" in c else flt
        res.flights_used += 1
        for a in range(0, len(arr) - nfft, step):
            b = int(thr[a:a + nfft].mean() / 100 * nbins)
            counts[b] += 1
            for key, sig in (("raw", raw), ("flt", flt)):
                for x in sig:
                    seg = x[a:a + nfft]
                    grids[key][b] += np.abs(np.fft.rfft((seg - seg.mean()) * win)) ** 2

    if not fs_all or counts.sum() < 10:
        return
    fs = float(np.median(fs_all))
    freqs = np.fft.rfftfreq(nfft, 1 / fs)
    # نعبي الـThrottle اللي ما طرت عليه بشكل خفيف من الجيران عشان الرسمة تكون ناعمة
    kernel = np.array([1, 2, 3, 4, 3, 2, 1], float)
    cnt = np.convolve(counts, kernel, mode="same")
    imgs = {}
    for key, g in grids.items():
        sm = np.apply_along_axis(lambda col_: np.convolve(col_, kernel, mode="same"), 0, g)
        with np.errstate(invalid="ignore", divide="ignore"):
            avg = np.where(cnt[:, None] > 0, sm / cnt[:, None], np.nan)
        imgs[key] = 10 * np.log10(np.maximum(avg, 1e-9))
    # المقياس من الترددات فوق 30Hz، عشان حركة الستك ما تغطي على الـNoise
    hi = imgs["raw"][:, freqs > 30]
    ref = hi[np.isfinite(hi)]
    vmax = np.percentile(ref, 99.7)
    vmin = vmax - 30

    has_raw = res.has_unfiltered
    panels = [("raw", "Before filters"), ("flt", "After filters")] if has_raw else [("flt", "Gyro")]
    fig, axs = plt.subplots(1, len(panels), figsize=(5.2 * len(panels), 5.6),
                            facecolor=SURFACE, squeeze=False)
    for ax, (key, title) in zip(axs[0], panels):
        ax.set_facecolor("#000000")
        ax.imshow(imgs[key], origin="lower", aspect="auto", cmap=HEAT, vmin=vmin, vmax=vmax,
                  extent=(0, fs / 2, 0, 100), interpolation="bilinear")
        _filter_lines(ax, headers, fs / 2)
        ax.set_xlim(0, fs / 2)
        ax.set_ylim(0, 100)
        ax.set_title(title, color=TEXT, fontsize=11, loc="left")
        ax.set_xlabel("Frequency (Hz)", color=TEXT_2)
        ax.tick_params(colors=TEXT_2)
        ax.grid(True, color="#ffffff", alpha=0.12, lw=0.6)
        for s_ in ax.spines.values():
            s_.set_visible(False)
    axs[0][0].set_ylabel("Throttle (%)", color=TEXT_2)
    fig.suptitle(f"Noise vs Throttle  ·  Roll + Pitch  ·  {res.flights_used} flights",
                 color=TEXT, fontsize=13, fontweight="bold", x=0.05, y=0.98, ha="left")
    fig.text(0.97, 0.98, "FPV Arabia", color=TEXT_2, ha="right", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, facecolor=SURFACE)
    plt.close(fig)
    res.heat_png = buf.getvalue()


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
