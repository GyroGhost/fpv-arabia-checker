"""بوت FPV Arabia لفحص ملفات Betaflight CLI."""
import asyncio
import io
import os

import discord
from dotenv import load_dotenv

from cli_parser import parse, parse_blackbox
from report import BAD, OK, TIP, WARN, sections, summary_pairs, worst_level
from rules import analyze
import recommend

try:
    from noise import analyze_noise, explain
except ImportError:  # المكتبات مو مثبتة
    analyze_noise = None
import render_tool

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHECK_CHANNEL_ID", "0"))  # 0 = كل القنوات
MAX_BYTES = 200_000
MAX_BBL_BYTES = 25_000_000
MAX_FILES = 3  # أقصى عدد ملفات Blackbox نحللها من رسالة وحدة
COLORS = {OK: 0x2ECC71, TIP: 0x3498DB, WARN: 0xF1C40F, BAD: 0xE74C3C}
# تحليل ملف واحد بالدور: مكتبة الرسم ما تتحمل رسمتين بنفس اللحظة، والسيرفر ذاكرته محدودة
ANALYSIS_LOCK = asyncio.Lock()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


def looks_like_cli(text: str) -> bool:
    return "# Betaflight" in text or text.count("\nset ") >= 3


def strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    return text.rstrip("`").strip()


async def extract_text(msg: discord.Message) -> str | None:
    for att in msg.attachments:
        if att.filename.lower().endswith((".txt", ".log", ".cli")) and att.size <= MAX_BYTES:
            return (await att.read()).decode("utf-8", errors="replace")
    if looks_like_cli(msg.content):
        return strip_code_fence(msg.content)
    return None


HOW_TO = (
    "**الطريقة الصحيحة:**\n"
    "١. افتح الـBetaflight Configurator وروح لتبويب الـCLI\n"
    "٢. اكتب هذا الأمر واضغط Enter:\n"
    "```\ndiff all\n```\n"
    "٣. اضغط Save to File وارفع الملف هنا"
)


def wrong_file_message(filename: str) -> str:
    name = filename.lower()
    if name.endswith((".bbl", ".bfl")):
        head = "ملف الـBlackbox كبير بزيادة 📈 ارفع ملف أصغر أو استخدم ملف الإعدادات."
    elif name.endswith((".png", ".jpg", ".jpeg", ".webp")):
        head = "هذي صورة 🖼️ ما أقدر أقرأ الإعدادات منها، أحتاج الملف النصي."
    elif name.endswith((".txt", ".log", ".cli")):
        head = "الملف كبير بزيادة أو مو ملف إعدادات 🤔"
    else:
        head = "ما أعرف أقرأ هذا النوع من الملفات 🤔"
    return f"{head}\n\n{HOW_TO}"


def build_embed(cfg, findings) -> discord.Embed:
    embed = discord.Embed(
        title="🔍 فحص إعدادات الطيارة",
        color=COLORS[worst_level(findings)],
    )
    for label, value in summary_pairs(cfg):
        embed.add_field(name=label, value=f"`{value}`", inline=True)
    for name, text in sections(findings):
        embed.add_field(name=name, value=text, inline=False)
    footer = "FPV Arabia • فحص تلقائي، راجع أي شي قبل لا تطير"
    if cfg.source == "blackbox":
        footer = "مقروء من ملف Blackbox، لفحص أدق ارفع diff all • " + footer
    embed.set_footer(text=footer)
    return embed


@client.event
async def on_ready():
    print(f"Bot online as {client.user} in {len(client.guilds)} server(s): "
          f"{[g.name for g in client.guilds]}")


@client.event
async def on_message(msg: discord.Message):
    if msg.author.bot:
        return
    print(f"[msg] channel={msg.channel} attachments={[a.filename for a in msg.attachments]} "
          f"content_len={len(msg.content)}")
    if CHANNEL_ID and msg.channel.id != CHANNEL_ID:
        print("[skip] not the check channel")
        return

    bbls = [a for a in msg.attachments
            if a.filename.lower().endswith((".bbl", ".bfl")) and a.size <= MAX_BBL_BYTES][:MAX_FILES]
    if bbls:
        for i, bbl in enumerate(bbls, 1):
            if len(bbls) > 1:
                await msg.reply(f"📂 **الملف {i} من {len(bbls)}:** `{bbl.filename}`", mention_author=False)
            data = await bbl.read()
            cfg = parse_blackbox(data)
            if not cfg.looks_valid():
                await msg.reply(f"ما لقيت إعدادات في `{bbl.filename}` 🤔\n\n{HOW_TO}", mention_author=False)
                continue
            await send_report(msg, cfg)
            res = await send_noise(msg, data, cfg)
            await send_render(msg, data, res.log_index if res else 1)
            await send_recommendations(msg, cfg, res)
        return

    text = await extract_text(msg)
    if not text:
        print("[skip] no CLI text found")
        if CHANNEL_ID and msg.attachments:
            await msg.reply(wrong_file_message(msg.attachments[0].filename), mention_author=False)
        return

    cfg = parse(text)
    if not cfg.looks_valid():
        await msg.reply(f"ما قدرت أقرأ الإعدادات من هذا الملف 🤔\n\n{HOW_TO}", mention_author=False)
        return

    await send_report(msg, cfg)
    await send_recommendations(msg, cfg, None)


async def send_recommendations(msg: discord.Message, cfg, noise_res):
    """رسالة أخيرة تجمع كل التوصيات مرتبة من الأهم."""
    try:
        items = recommend.build(analyze(cfg), noise_res)
        embed = discord.Embed(title="📋 التوصيات النهائية", description=recommend.summary_line(items),
                              color=0x2ECC71 if not items else 0xF1C40F)
        for num, title, detail, code in items:
            value = detail + (f"\n```\n{code}\n```" if code else "")
            embed.add_field(name=f"{num} {title}", value=value[:1024], inline=False)
        if items:
            embed.set_footer(text="بعد أي تعديل في الـCLI لا تنسى save • جرّب طلعة وارفع ملف جديد للمقارنة")
        await msg.reply(embed=embed, mention_author=False)
        print(f"[ok] recommendations sent, {len(items)} items")
    except Exception as e:
        print(f"[error] recommendations {type(e).__name__}: {e}")


async def send_noise(msg: discord.Message, data: bytes, cfg):
    if analyze_noise is None:
        print("[skip] noise libs missing: pip install -r requirements.txt")
        return
    async with ANALYSIS_LOCK, msg.channel.typing():
        try:
            res = await asyncio.to_thread(analyze_noise, data)
        except Exception as e:
            print(f"[error] noise {type(e).__name__}: {e}")
            return
    if not res:
        await msg.reply("الطلعات في الملف قصيرة بزيادة، ما أقدر أحلل الـNoise منها 🤏", mention_author=False)
        return
    bidir = cfg.get("dshot_bidir")
    embed = discord.Embed(title="📈 تحليل الـNoise", color=0xD95926 if res.peaks else 0x2ECC71)
    for name, text in explain(res, None if bidir is None else bidir == "ON"):
        embed.add_field(name=name, value=text, inline=False)
    embed.set_image(url="attachment://noise.png")
    embed.set_footer(text="البرتقالي قبل الـFilters • الأزرق بعدها")
    embeds = [embed]
    files = [discord.File(io.BytesIO(res.png), filename="noise.png")]
    if res.heat_png:
        desc = (f"من كل الطلعات اللي في الملف ({res.flights_used}).\n"
                "الأسود هدوء، والأحمر Noise، والأبيض أقوى Noise.\n"
                "إذا شفت خط أبيض مايل يطلع مع الـThrottle، هذا Noise الـMotors.")
        if res.filter_lines:
            desc += "\n\nالخط الأخضر حد الـGyro Filter، وأي Noise على يمينه ينقص بقوة:\n" + \
                    "\n".join(f"`{n}`" for n in res.filter_lines)
        if res.filter_hidden:
            max_hz = int(res.sample_rate / 2)
            desc += ("\n\nفيه Filter أعلى من مدى الرسمة، لأن الـBlackbox مسجل بسرعة منخفضة "
                     f"والرسمة توقف عند {max_hz}Hz:\n" + "\n".join(f"`{n}`" for n in res.filter_hidden))
        if not res.filter_lines and not res.filter_hidden:
            desc += "\n\nما لقيت أي Gyro Lowpass Filter مفعّل في إعداداتك."
        heat = discord.Embed(title="🔥 الـNoise مقابل الـThrottle", description=desc, color=0xE00000)
        heat.set_image(url="attachment://heat.png")
        embeds.append(heat)
        files.append(discord.File(io.BytesIO(res.heat_png), filename="heat.png"))
    await msg.reply(embeds=embeds, files=files, mention_author=False)
    print(f"[ok] noise sent, peaks={[(a, round(h)) for a, h, _ in res.peaks]}")
    return res


async def send_render(msg: discord.Message, data: bytes, flight_index: int):
    """رسومات أداة BlackBox_CSV_Render."""
    if not render_tool.ENABLED:
        return
    if not render_tool.available():
        print(f"[skip] BlackBox_CSV_Render not found at {render_tool.BIN}")
        return
    async with ANALYSIS_LOCK, msg.channel.typing():
        tmp, plots, err = await asyncio.to_thread(render_tool.render, data, flight_index)
    try:
        if err or not plots:
            print(f"[error] render: {err or 'no plots'}")
            return
        embeds, files = [], []
        for i, (title, desc, path) in enumerate(plots):
            name = f"bbr{i}.png"
            e = discord.Embed(title=f"🛠️ {title}", description=desc, color=0x3987E5)
            e.set_image(url=f"attachment://{name}")
            embeds.append(e)
            files.append(discord.File(str(path), filename=name))
        embeds[-1].set_footer(text=f"الطلعة رقم {flight_index} • BlackBox_CSV_Render by nerdCopter • AGPL-3.0")
        await msg.reply(content=f"**تحليل متقدم من أداة BlackBox_CSV_Render**\n<{render_tool.SOURCE_URL}>",
                        embeds=embeds, files=files, mention_author=False)
        print(f"[ok] render sent, {len(plots)} plots")
    finally:
        render_tool.cleanup(tmp)


async def send_report(msg: discord.Message, cfg):
    try:
        await msg.reply(embed=build_embed(cfg, analyze(cfg)), mention_author=False)
        print("[ok] report sent")
    except discord.Forbidden:
        print("[error] missing permission to reply / embed in this channel")
    except Exception as e:
        print(f"[error] {type(e).__name__}: {e}")


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("حط DISCORD_TOKEN في ملف .env")
    client.run(TOKEN)
