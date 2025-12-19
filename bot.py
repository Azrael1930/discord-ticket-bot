import discord
from discord.ext import commands
from discord.ui import View, Button
from dotenv import load_dotenv
import asyncio
import os
import time

# ================== LOAD ENV ==================
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
TICKET_CATEGORY_ID = int(os.getenv("TICKET_CATEGORY_ID"))
CLOSED_CATEGORY_ID = int(os.getenv("CLOSED_CATEGORY_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
SUPPORT_ROLE_ID = int(os.getenv("SUPPORT_ROLE_ID"))

# ================== CONFIG ==================
TICKET_COOLDOWN = 60  # seconds (anti-spam)

# ================== STATE ==================
user_cooldowns = {}

# ================== BOT ==================
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ================== HELPERS ==================
def get_next_ticket_number():
    if not os.path.exists("ticket_counter.txt"):
        with open("ticket_counter.txt", "w") as f:
            f.write("0")

    with open("ticket_counter.txt", "r") as f:
        num = int(f.read())

    num += 1
    with open("ticket_counter.txt", "w") as f:
        f.write(str(num))

    return num


def user_has_open_ticket(guild, user):
    for ch in guild.text_channels:
        if ch.category and ch.category.id == TICKET_CATEGORY_ID:
            if ch.topic == f"owner:{user.id}":
                return ch
    return None


def check_cooldown(user_id):
    now = time.time()
    last = user_cooldowns.get(user_id, 0)
    if now - last < TICKET_COOLDOWN:
        return int(TICKET_COOLDOWN - (now - last))
    user_cooldowns[user_id] = now
    return 0

# ================== CLOSE VIEW ==================
class CloseTicketView(View):
    def __init__(self, ticket_number, owner_id):
        super().__init__(timeout=None)
        self.ticket_number = ticket_number
        self.owner_id = owner_id

    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.danger)
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        support_role = interaction.guild.get_role(SUPPORT_ROLE_ID)
        if support_role not in interaction.user.roles:
            return await interaction.response.send_message(
                "❌ Only support staff can close tickets.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "🔒 Closing ticket...",
            ephemeral=True
        )

        owner = interaction.guild.get_member(self.owner_id)

        if owner:
            await interaction.channel.set_permissions(
                owner,
                read_messages=False,
                send_messages=False
            )

        closed_category = interaction.guild.get_channel(CLOSED_CATEGORY_ID)
        await interaction.channel.edit(
            name=f"closed-ticket-{self.ticket_number}",
            category=closed_category
        )

        await interaction.channel.send(
            f"🔒 **Ticket #{self.ticket_number} has been closed by {interaction.user.mention}.**"
        )

        log = interaction.guild.get_channel(LOG_CHANNEL_ID)
        if log:
            await log.send(
                f"🔒 Ticket #{self.ticket_number} closed by {interaction.user}"
            )

    @discord.ui.button(label="🗑️ Delete Ticket", style=discord.ButtonStyle.secondary)
    async def delete_ticket(self, interaction: discord.Interaction, button: Button):
        support_role = interaction.guild.get_role(SUPPORT_ROLE_ID)
        if support_role not in interaction.user.roles:
            return await interaction.response.send_message(
                "❌ Only support staff can delete tickets.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "🗑️ Ticket will be deleted in 3 seconds...",
            ephemeral=True
        )

        log = interaction.guild.get_channel(LOG_CHANNEL_ID)
        if log:
            await log.send(
                f"🗑️ Ticket #{self.ticket_number} deleted by {interaction.user}"
            )

        await asyncio.sleep(3)
        await interaction.channel.delete()

# ================== TICKET PANEL ==================
class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def create_ticket(self, interaction, ticket_type):
        guild = interaction.guild
        user = interaction.user

        remaining = check_cooldown(user.id)
        if remaining > 0:
            return await interaction.response.send_message(
                f"⏱️ Please wait **{remaining}s** before creating another ticket.",
                ephemeral=True
            )

        existing = user_has_open_ticket(guild, user)
        if existing:
            return await interaction.response.send_message(
                f"❌ You already have an open ticket: {existing.mention}",
                ephemeral=True
            )

        ticket_number = get_next_ticket_number()
        category = guild.get_channel(TICKET_CATEGORY_ID)
        support_role = guild.get_role(SUPPORT_ROLE_ID)

        channel = await guild.create_text_channel(
            name=f"{ticket_type}-{ticket_number}",
            category=category,
            topic=f"owner:{user.id}"
        )

        await channel.set_permissions(user, read_messages=True, send_messages=True)
        await channel.set_permissions(guild.default_role, read_messages=False)
        await channel.set_permissions(support_role, read_messages=True, send_messages=True)

        await channel.send(
            f"👋 Welcome {user.mention}\n"
            f"🎫 **Ticket ID:** `{ticket_number}`\n"
            f"📂 **Type:** {ticket_type}\n\n"
            f"{support_role.mention}",
            view=CloseTicketView(ticket_number, user.id)
        )

        log = guild.get_channel(LOG_CHANNEL_ID)
        if log:
            await log.send(
                f"📌 Ticket #{ticket_number} ({ticket_type}) opened by {user}"
            )

        await interaction.response.send_message(
            f"✅ Your ticket has been created: {channel.mention}",
            ephemeral=True
        )

    @discord.ui.button(label="📩 Question", style=discord.ButtonStyle.primary)
    async def question(self, interaction, button):
        await self.create_ticket(interaction, "question")

    @discord.ui.button(label="🛒 Purchase", style=discord.ButtonStyle.success)
    async def purchase(self, interaction, button):
        await self.create_ticket(interaction, "purchase")

    @discord.ui.button(label="⚠️ Complaint", style=discord.ButtonStyle.danger)
    async def complaint(self, interaction, button):
        await self.create_ticket(interaction, "complaint")

    @discord.ui.button(label="💡 Suggestion", style=discord.ButtonStyle.secondary)
    async def suggestion(self, interaction, button):
        await self.create_ticket(interaction, "suggestion")

# ================== EVENTS ==================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.command()
@commands.has_permissions(administrator=True)
async def ticketpanel(ctx):
    embed = discord.Embed(
        title="🎫 Ticket System",
        description="Select a ticket type using the buttons below.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed, view=TicketView())

bot.run(TOKEN)
