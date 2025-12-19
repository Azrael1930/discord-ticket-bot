import discord
from discord.ext import commands
from discord.ui import View, Button
from dotenv import load_dotenv
import asyncio
import os

# ================== LOAD ENV ==================
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
TICKET_CATEGORY_ID = int(os.getenv("TICKET_CATEGORY_ID"))
CLOSED_CATEGORY_ID = int(os.getenv("CLOSED_CATEGORY_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
SUPPORT_ROLE_ID = int(os.getenv("SUPPORT_ROLE_ID"))
# ==============================================

# ================== Ticket Counter ==================
def get_next_ticket_number():
    if not os.path.exists("ticket_counter.txt"):
        with open("ticket_counter.txt", "w") as f:
            f.write("0")

    with open("ticket_counter.txt", "r") as f:
        number = int(f.read())

    number += 1

    with open("ticket_counter.txt", "w") as f:
        f.write(str(number))

    return number
# ====================================================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ================== Utils ==================
def user_has_open_ticket(guild, user):
    for channel in guild.text_channels:
        if (
            channel.category
            and channel.category.id == TICKET_CATEGORY_ID
            and channel.topic == f"owner:{user.id}"
        ):
            return channel
    return None
# ===========================================

# ================== Close Ticket View ==================
class CloseTicketView(View):
    def __init__(self, ticket_number):
        super().__init__(timeout=None)
        self.ticket_number = ticket_number

    @discord.ui.button(label="❌ Close Ticket", style=discord.ButtonStyle.danger)
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)

        support_role = interaction.guild.get_role(SUPPORT_ROLE_ID)
        if support_role not in interaction.user.roles:
            return await interaction.followup.send(
                "❌ Only support staff can close tickets."
            )

        # Get ticket owner from topic
        owner_id = int(interaction.channel.topic.replace("owner:", ""))
        owner = interaction.guild.get_member(owner_id)

        # Remove user's access completely (ticket disappears)
        if owner:
            await interaction.channel.set_permissions(owner, overwrite=None)

        closed_category = interaction.guild.get_channel(CLOSED_CATEGORY_ID)

        await interaction.channel.edit(
            name=f"closed-ticket-{self.ticket_number}",
            category=closed_category
        )

        await interaction.channel.send(
            f"🔒 Ticket **#{self.ticket_number}** has been closed by {interaction.user.mention}"
        )

        log = interaction.guild.get_channel(LOG_CHANNEL_ID)
        if log:
            await log.send(
                f"🔒 Ticket #{self.ticket_number} closed by {interaction.user}"
            )

        await interaction.followup.send(
            f"✅ Ticket #{self.ticket_number} closed successfully."
        )

    @discord.ui.button(label="🗑️ Delete Ticket", style=discord.ButtonStyle.secondary)
    async def delete_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)

        support_role = interaction.guild.get_role(SUPPORT_ROLE_ID)
        if support_role not in interaction.user.roles:
            return await interaction.followup.send(
                "❌ Only support staff can delete tickets."
            )

        log = interaction.guild.get_channel(LOG_CHANNEL_ID)
        if log:
            await log.send(
                f"🗑️ Ticket #{self.ticket_number} deleted by {interaction.user}"
            )

        await interaction.followup.send(
            "🗑️ Deleting ticket in 3 seconds..."
        )
        await asyncio.sleep(3)
        await interaction.channel.delete()
# ======================================================

# ================== Ticket Panel ======================
class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def create_ticket(self, interaction, ticket_type):
        guild = interaction.guild
        user = interaction.user

        existing_ticket = user_has_open_ticket(guild, user)
        if existing_ticket:
            return await interaction.response.send_message(
                f"❌ You already have an open ticket: {existing_ticket.mention}",
                ephemeral=True
            )

        ticket_number = get_next_ticket_number()
        category = guild.get_channel(TICKET_CATEGORY_ID)
        role = guild.get_role(SUPPORT_ROLE_ID)

        channel = await guild.create_text_channel(
            name=f"{ticket_type.lower()}-{ticket_number}",
            category=category,
            topic=f"owner:{user.id}"
        )

        await channel.set_permissions(user, read_messages=True, send_messages=True)
        await channel.set_permissions(guild.default_role, read_messages=False)
        await channel.set_permissions(role, read_messages=True, send_messages=True)

        await channel.send(
            f"👋 Hello {user.mention}\n"
            f"🎫 **Ticket ID:** `{ticket_number}`\n"
            f"📂 **Type:** {ticket_type}\n\n"
            f"{role.mention}",
            view=CloseTicketView(ticket_number)
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
        await self.create_ticket(interaction, "Question")

    @discord.ui.button(label="🛒 Purchase", style=discord.ButtonStyle.success)
    async def buy(self, interaction, button):
        await self.create_ticket(interaction, "Purchase")

    @discord.ui.button(label="⚠️ Complaint", style=discord.ButtonStyle.danger)
    async def complaint(self, interaction, button):
        await self.create_ticket(interaction, "Complaint")

    @discord.ui.button(label="💡 Suggestion", style=discord.ButtonStyle.secondary)
    async def idea(self, interaction, button):
        await self.create_ticket(interaction, "Suggestion")

    @discord.ui.button(label="☕ Other", style=discord.ButtonStyle.secondary)
    async def other(self, interaction, button):
        await self.create_ticket(interaction, "Other")
# ======================================================

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.command()
@commands.has_permissions(administrator=True)
async def ticketpanel(ctx):
    embed = discord.Embed(
        title="🎫 Ticket System",
        description="Choose a ticket type using the buttons below",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed, view=TicketView())

bot.run(TOKEN)
