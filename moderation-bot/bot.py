import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"logged in as {bot.user}")

@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name="ogólny")
    if channel:
        embed = discord.Embed(
            title=f"Witaj {member.name}!",
            description=f"Miło cię widzieć na **{member.guild.name}**.",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await channel.send(content=member.mention, embed=embed)

@bot.command(name="ping")
async def ping(ctx):
    await ctx.reply(f"pong — {round(bot.latency * 1000)}ms")

if __name__ == "__main__":
    bot.run(TOKEN)