# FPV Arabia Checker 🔍

بوت ديسكورد لمجتمع **FPV Arabia** يقرأ ملفات الإعدادات وملفات الـBlackbox من Betaflight، ويرد بتقرير وشرح بالعربي.

A Discord bot for the Arabic FPV community *FPV Arabia*. Members upload a Betaflight `diff all` or a Blackbox log and get a settings check and noise analysis explained in Arabic.

---

## ماذا يفعل ؟ : 

**ملف الإعدادات** (من الـCLI بأمر `diff all`):
- ملخص الطيران : الـFirmware والـBoard والـProtocol والـRates
- فحص الإعدادات: سويتش الـARM، الـRPM Filter، الـFailsafe، حد البطارية، وغيرها
- كل تنبيه معه الأمر الجاهز للنسخ

**ملف الـBlackbox** (`.BBL` / `.BFL`):
- نفس فحص الإعدادات من معلومات الملف
- رسمة الـNoise Spectrum قبل الـFilters وبعدها، مع القمم المكتشفة
- خريطة الـNoise مقابل الـThrottle من كل الطلعات، مع خطوط الـGyro Filters
- تحليل متقدم من أداة BlackBox_CSV_Render (اختياري)

---

## الملفات

| الملف | وظيفته |
|---|---|
| `bot.py` | البوت نفسه |
| `cli_parser.py` | قراءة ملف `diff all` ومعلومات ملف الـBlackbox |
| `rules.py` | قواعد الفحص |
| `report.py` | ترتيب التقرير |
| `noise.py` | تحليل ورسم الـNoise |
| `render_tool.py` | الربط مع BlackBox_CSV_Render |
| `orangebox/` | مكتبة فك ملفات الـBlackbox (انظر الشكر تحت) |
| `test_local.py` | تجربة الفحص بدون ديسكورد |

---

## التشغيل على جهازك

```
pip install -r requirements.txt
```
انسخ `.env.example` إلى `.env` وعبّي القيم، بعدها:
```
python bot.py
```

| المتغير | الوصف |
|---|---|
| `DISCORD_TOKEN` | توكن البوت من Discord Developer Portal |
| `CHECK_CHANNEL_ID` | رقم قناة الفحص، و`0` يعني كل القنوات |
| `ENABLE_RENDER` | `1` لتفعيل BlackBox_CSV_Render |
| `RENDER_BIN` | مسار الأداة إذا مو في المكان الافتراضي |

لتجربة الفحص بدون ديسكورد:
```
python test_local.py sample_diff.txt
```

## الاستضافة

البوت مستضاف على Railway. ملف `Dockerfile` يبني أداة BlackBox_CSV_Render من الكود ويجهز البوت، وكل تحديث على فرع `main` يتنشر تلقائياً.

## إضافة قاعدة فحص جديدة

```python
def rule_my_check(cfg):
    if cfg.get("some_setting") == "X":
        return Finding(WARN, "العنوان", "الشرح", "set some_setting = Y")
    return None
```
بعدها أضفها لقائمة `RULES` في آخر `rules.py`.

---

## شكر وتقدير · Credits

**[BlackBox_CSV_Render](https://github.com/nerdCopter/BlackBox_CSV_Render)** by **nerdCopter**
التحليل المتقدم في البوت من هالأداة، ونستخدمها بإذن صاحبها. البوت يشغّلها بدون أي تعديل، ويذكرها مع رابطها في كل تقرير.
The advanced analysis plots come from BlackBox_CSV_Render, used unmodified and with the author's permission. Licensed under AGPL-3.0. Thank you nerdCopter!

**[orangebox](https://github.com/atomgomba/orangebox)** by **Károly Kiripolszky**
مكتبة فك ملفات الـBlackbox، ونسختها موجودة داخل المشروع في مجلد `orangebox/`.
Blackbox log parser, bundled in `orangebox/`. Licensed under GPL-3.0.

---

## الرخصة · License

البوت مجاني بالكامل، بدون أرباح ولا مميزات مدفوعة.
This bot is free and non-commercial. Licensed under **GPL-3.0**, see `LICENSE`.
