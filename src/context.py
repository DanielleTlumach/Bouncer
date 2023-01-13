# Updated
import discord
from client import client
from config import MAILBOX
from commonbot.utils import combine_message, send_message


@client.tree.context_menu(name="Report")
async def report_context(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.send_message("Ви успішно повідомили нам про це повідомлення. Дякуємо!", ephemeral=True)

    log_chan = interaction.guild.get_channel(MAILBOX)
    reported_mes = combine_message(message)
    out = f"Про повідомлення від <@{message.author.id}> повідомив користувач  <@{interaction.user.id}>: {reported_mes}\n{message.jump_url}"
    await send_message(out, log_chan)
