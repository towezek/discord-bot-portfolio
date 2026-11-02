import os
import io
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
STAFF_ROLE_ID = int(os.getenv("STAFF_ROLE_ID", 0))
TRANSCRIPT_CHANNEL_ID = int(os.getenv("TRANSCRIPT_CHANNEL_ID", 0))

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

class AddUserModal(discord.ui.Modal, title="Dodaj osobę"):
    user_id = discord.ui.TextInput(label="ID użytkownika", required=True)
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user = await interaction.guild.fetch_member(int(self.user_id.value))
            await self.channel.set_permissions(user, view_channel=True, send_messages=True, read_message_history=True)
            await interaction.response.send_message(f"Dodano {user.mention}.", ephemeral=True)
        except:
            await interaction.response.send_message("Złe ID.", ephemeral=True)

class CloseModal(discord.ui.Modal, title="Zamknij zgłoszenie"):
    reason = discord.ui.TextInput(label="Powód zamknięcia", required=True)
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("Zamykanie...", ephemeral=True)
        transcript = io.BytesIO()
        lines = []
        async for msg in self.channel.history(limit=1000, oldest_first=True):
            lines.append(f"[{msg.created_at.strftime('%Y-%m-%d %H:%M')}] {msg.author.name}: {msg.content}")
        transcript.write("\n".join(lines).encode('utf-8'))
        transcript.seek(0)
        log_channel = interaction.guild.get_channel(TRANSCRIPT_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(title="Zamknięto zgłoszenie", description=f"Powód: {self.reason.value}\nPrzez: {interaction.user.mention}", color=discord.Color.red())
            await log_channel.send(embed=embed, file=discord.File(transcript, filename=f"{self.channel.name}.txt"))
        await self.channel.delete(reason=self.reason.value)

class TicketControls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Przejmij", style=discord.ButtonStyle.success, custom_id="ticket:claim", emoji="✋")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if STAFF_ROLE_ID and STAFF_ROLE_ID not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message("Brak uprawnień!", ephemeral=True)
            return
        button.disabled = True
        button.label = f"Przejęte przez {interaction.user.name}"
        button.style = discord.ButtonStyle.secondary
        await interaction.message.edit(view=self)
        await interaction.response.send_message(f"Przejęte przez {interaction.user.mention}.")

    @discord.ui.button(label="Dodaj osobę", style=discord.ButtonStyle.secondary, custom_id="ticket:add", emoji="➕")
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddUserModal(interaction.channel))

    @discord.ui.button(label="Zamknij", style=discord.ButtonStyle.danger, custom_id="ticket:close", emoji="🔒")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CloseModal(interaction.channel))

class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Pomoc ogólna", description="Masz pytanie lub problem techniczny?", emoji="❓"),
            discord.SelectOption(label="Zgłoś użytkownika", description="Ktoś łamie regulamin serwera?", emoji="🚨"),
            discord.SelectOption(label="Współpraca", description="Chcesz nawiązać współpracę lub reklamę?", emoji="🤝")
        ]
        super().__init__(placeholder="Wybierz kategorię zgłoszenia...", min_values=1, max_values=1, options=options, custom_id="ticket:select")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            guild = interaction.guild
            category_name = self.values[0]
            
            existing = discord.utils.get(guild.text_channels, name=f"ticket-{interaction.user.name.lower()}")
            if existing:
                await interaction.followup.send(f"Masz już otwarte zgłoszenie: {existing.mention}", ephemeral=True)
                return

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
            }
            
            staff_role = guild.get_role(STAFF_ROLE_ID)
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_messages=True)

            channel = await guild.create_text_channel(
                name=f"ticket-{interaction.user.name.lower()}",
                overwrites=overwrites,
                topic=f"Kategoria: {category_name} | Od: {interaction.user} ({interaction.user.id})"
            )

            embed = discord.Embed(
                title=f"Zgłoszenie: {category_name}",
                description=f"Witaj {interaction.user.mention}! Opisz swój problem poniżej. Administracja zaraz się odezwie.",
                color=discord.Color.green()
            )
            await channel.send(content=f"{interaction.user.mention} {staff_role.mention if staff_role else ''}", embed=embed, view=TicketControls())
            await interaction.followup.send(f"Utworzono zgłoszenie: {channel.mention}", ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ **Błąd:** `{e}`", ephemeral=True)

class TicketPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

@bot.event
async def on_ready():
    bot.add_view(TicketPanel())
    bot.add_view(TicketControls())
    await bot.tree.sync()
    print(f"logged in as {bot.user}")

@bot.tree.command(name="panel", description="Wysyła panel do zgłoszeń")
@app_commands.checks.has_permissions(administrator=True)
async def panel_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎫 Centrum Pomocy", 
        description="Wybierz kategorię z menu poniżej, aby otworzyć prywatne zgłoszenie.", 
        color=discord.Color.blue()
    )
    await interaction.channel.send(embed=embed, view=TicketPanel())
    await interaction.response.send_message("Panel wysłany!", ephemeral=True)

if __name__ == "__main__":
    bot.run(TOKEN)