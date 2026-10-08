"""بوت FPV Arabia لفحص ملفات Betaflight CLI."""
import os

import discord
from dotenv import load_dotenv

from cli_parser import parse
from report import BAD, OK, TIP, WARN, sections, summary_pairs, worst_level
from rules import analyze

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHECK_CHANNEL_ID", "0"))  # 0 = كل القنوات
MAX_BYTES = 200_000
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


def build_embed(cfg, findings) -> discord.Embed:
    embed = discord.Embed(
        title="🔍 فحص إعدادات الطيارة",
        color=COLORS[worst_level(findings)],
    )
    for label, value in summary_pairs(cfg):
        embed.add_field(name=label, value=f"`{value}`", inline=True)
    for name, text in sections(findings):
        embed.add_field(name=name, value=text, inline=False)
    embed.set_footer(text="FPV Arabia • فحص تلقائي، راجع أي شي قبل لا تطير")
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

    text = await extract_text(msg)
    if not text:
        print("[skip] no CLI text found")
        return

    cfg = parse(text)
    if not cfg.looks_valid():
        await msg.reply("ما قدرت أقرأ الملف 🤔 اكتب `diff all` في CLI وارفع النتيجة كملف .txt",
                        mention_author=False)
        return

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
