"""بوت FPV Arabia لفحص ملفات Betaflight CLI."""
import asyncio
import io
import os

import discord
from dotenv import load_dotenv

from cli_parser import parse, parse_blackbox
from report import BAD, OK, TIP, WARN, sections, summary_pairs, worst_level
from rules import analyze

try:
    from noise import analyze_noise, explain
except ImportError:  # المكتبات مو مثبتة
    analyze_noise = None

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHECK_CHANNEL_ID", "0"))  # 0 = كل القنوات
MAX_BYTES = 200_000
MAX_BBL_BYTES = 25_000_000
COLORS = {OK: 0x2ECC71, TIP: 0x3498DB, WARN: 0xF1C40F, BAD: 0xE74C3C}

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

    bbl = next((a for a in msg.attachments
                if a.filename.lower().endswith((".bbl", ".bfl")) and a.size <= MAX_BBL_BYTES), None)
    if bbl:
        cfg = parse_blackbox(await bbl.read())
        if not cfg.looks_valid():
            await msg.reply(f"ما لقيت إعدادات في ملف الـBlackbox هذا 🤔\n\n{HOW_TO}", mention_author=False)
            return
        await send_report(msg, cfg)
        await send_noise(msg, await bbl.read(), cfg)
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


async def send_noise(msg: discord.Message, data: bytes, cfg):
    if analyze_noise is None:
        print("[skip] noise libs missing: pip install -r requirements.txt")
        return
    async with msg.channel.typing():
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
    await msg.reply(embed=embed, file=discord.File(io.BytesIO(res.png), filename="noise.png"),
                    mention_author=False)
    print(f"[ok] noise sent, peaks={[(a, round(h)) for a, h, _ in res.peaks]}")


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
