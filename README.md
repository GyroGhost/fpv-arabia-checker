# FPV Arabia CLI Checker 🔍

بوت ديسكورد يقرأ ملف `diff all` من Betaflight ويرد بتقرير عربي: ملخص الطيارة، المشاكل، التنبيهات، والنصائح.

## الملفات
| الملف | وظيفته |
|---|---|
| `cli_parser.py` | يقرأ الملف ويحوله لبيانات (النسخة، البورد، الإعدادات، البروفايلات، الـAUX) |
| `rules.py` | قواعد الفحص — هنا تضيف خبرتك |
| `report.py` | يرتب النتائج (نص أو Embed) |
| `bot.py` | البوت نفسه |
| `test_local.py` | تجربة بدون ديسكورد |

## التجربة محلياً
```bash
python test_local.py sample_diff.txt
```

## التشغيل
1. من [Discord Developer Portal](https://discord.com/developers/applications) سوّ Application ← Bot، وفعّل **Message Content Intent**.
2. انسخ التوكن، وسوّ ملف `.env` من `.env.example`.
3. (اختياري) حط رقم قناة `#فحص-الإعدادات` في `CHECK_CHANNEL_ID`.
4. ثبّت وشغّل:
```bash
pip install -r requirements.txt
python bot.py
```

## إضافة قاعدة جديدة
```python
def rule_my_check(cfg):
    if cfg.get("some_setting") == "X":
        return Finding(WARN, "العنوان", "الشرح")
    return None
```
ثم أضفها لقائمة `RULES` في آخر `rules.py`.
