# Bouncer
# https://github.com/ChulkyBow/Bouncer
# Updated

from datetime import datetime, timezone

import commonbot.utils
import discord
import humanize
from commonbot.debug import Debug
from commonbot.timekeep import Timekeeper

# Needs to happen before other imports that cause db to be queried
import db

db.initialize()

import commands
import config
import db
import visualize
from client import client
from config import LogTypes, USERID_LOG_PATH
from watcher import Watcher
from forwarder import MessageForwarder

# Initialize helper classes
db.initialize()
dbg = Debug(config.OWNER, config.CMD_PREFIX, config.DEBUG_BOT)
tk = Timekeeper()
watch = Watcher()
frwrdr = MessageForwarder(config.FORWARDING_CREATE_THREADS, config.MAILBOX, config.BAN_APPEAL, config.HOME_SERVER,
                          config.MODS_ROLES)

FUNC_DICT = {
    "ban": [commands.log_user, LogTypes.BAN],
    "block": [commands.block_user, True],
    "clear": [commands.clear_am, None],
    "edit": [commands.remove_error, True],
    "graph": [visualize.post_plots, None],
    "help": [commands.send_help_mes, None],
    "kick": [commands.log_user, LogTypes.KICK],
    "note": [commands.log_user, LogTypes.NOTE],
    "preview": [commands.preview, None],
    "remove": [commands.remove_error, False],
    "reply": [commands.reply, frwrdr],
    "say": [commands.say, None],
    "scam": [commands.log_user, LogTypes.SCAM],
    "search": [commands.search_command, None],
    "sync": [commands.sync, None],
    "unban": [commands.log_user, LogTypes.UNBAN],
    "unblock": [commands.block_user, False],
    "uptime": [tk.uptime, None],
    "waiting": [commands.list_waiting, None],
    "warn": [commands.log_user, LogTypes.WARN],
    "watch": [watch.watch_user, None],
    "watchlist": [watch.get_watchlist, None],
    "unwatch": [watch.unwatch_user, None],
}

"""
Delete message
A helper function that deletes and logs the given message
"""


async def delete_message_helper(message: discord.Message):
    timedelta = datetime.now(timezone.utc) - message.created_at
    mes = f":no_mobile_phones: **{str(message.author)}** видалив " \
          f"в <#{message.channel.id}>: `{message.content}` \n" \
          f":timer: Це повідомлення було видиме протягом {humanize.precisedelta(timedelta)}."
    chan = client.get_channel(config.SYS_LOG)
    # Adds URLs for any attachments that were included in deleted message
    # These will likely become invalid, but it's nice to note them anyway
    if message.attachments:
        for item in message.attachments:
            mes += '\n' + item.url

    await commonbot.utils.send_message(mes, chan)


"""
Should Log
Whether the bot should log this event in config.SYS_LOG
"""


def should_log(server: discord.Guild) -> bool:
    if not server:
        return False

    return not dbg.is_debug_bot() and server.id == config.HOME_SERVER


"""
On Ready
Occurs when Discord bot is first brought online
"""


@client.event
async def on_ready():
    print('Ви увійшли як')
    print(client.user.name)
    print(client.user.id)

    # Set Bouncer's activity status
    activity_object = discord.Activity(name="за вашими доповідями!", type=discord.ActivityType.watching)
    await client.change_presence(activity=activity_object)

    if not dbg.is_debug_bot():
        # Upload our DB file to a private channel as a backup
        chan = client.get_channel(config.LOG_CHAN)
        current_time = datetime.now(timezone.utc)
        filename = f"bouncer_backup_{commonbot.utils.format_time(current_time)}.db"
        with open(config.DATABASE_PATH, 'rb') as db_file:
            await chan.send(file=discord.File(db_file, filename=filename))


"""
On Guild Available
Runs when a guild (server) becomes available to the bot
"""


@client.event
async def on_guild_available(guild: discord.Guild):
    if not dbg.is_debug_bot():
        await client.sync_guild(guild)


"""
On Thread Create
Occurs when a new thread is created in the server
"""


@client.event
async def on_thread_create(thread: discord.Thread):
    await thread.join()
    await thread.edit(auto_archive_duration=10080)  # Set all new threads to maximum timeout


"""
On Member Update
Occurs when a user updates an attribute (nickname, roles, timeout)
"""


@client.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if not should_log(before.guild):
        return

    # If nickname has changed
    if before.nick != after.nick:
        # If they don't have an ending nickname, they reset to their actual username
        if not after.nick:
            mes = f"**:spy: {str(after)}** скидує своє ім'я користувача"
        else:
            mes = f"**:spy: Користувач {str(after)}** тепер знаний як `{after.nick}`"
        chan = client.get_channel(config.SYS_LOG)
        await chan.send(mes)
    # If role quantity has changed
    elif before.roles != after.roles:
        # Determine role difference, post about it
        removed = [r.name for r in before.roles if r not in after.roles]
        added = [r.name for r in after.roles if r not in before.roles]
        mes = ""
        if removed:
            removed_str = ', '.join(removed)
            mes += f":no_entry_sign: Користувача **{str(after)}** позбавлено ролі(ей) `{removed_str}`.\n"

        if added:
            added_str = ', '.join(added)
            mes += f":new: Користувачу **{str(after)}** надано роль(і) `{added_str}`."

        chan = client.get_channel(config.SYS_LOG)
        if mes != "":
            await chan.send(mes)
    # If they were timed out
    # Note, this won't trip when the timeout wears off, due to a Discord limitation
    if before.timed_out_until != after.timed_out_until:
        chan = client.get_channel(config.SYS_LOG)
        if after.timed_out_until:
            timedelta = after.timed_out_until - datetime.now(timezone.utc)
            timeout_str = humanize.precisedelta(timedelta, minimum_unit="seconds", format="%d")
            mes = f":zipper_mouth: {str(after)} заглушено на {timeout_str}."
            await chan.send(mes)
        else:
            await chan.send(f":grin: {str(after)} тепер розглушено.")


"""
On Member Ban
Occurs when a user is banned
"""


@client.event
async def on_member_ban(server: discord.Guild, member: discord.Member):
    if not should_log(server):
        return

    # We can remove banned user from our answering machine and watch list (if they exist)
    commands.reply_am.remove_entry(member.id)
    commands.ban_am.remove_entry(member.id)
    watch.remove_user(member.id)

    # Keep a record of their banning, in case the log is made after they're no longer here
    username = f"{str(member)}"
    commands.ul.add_ban(member.id, username)
    mes = f":newspaper2: **{username} ({member.id})** було заблоковано."
    chan = client.get_channel(config.SYS_LOG)
    await chan.send(mes)


"""
On Member Remove
Occurs when a user leaves the server
"""


@client.event
async def on_member_remove(member: discord.Member):
    if not should_log(member.guild):
        return

    # We can remove left users from our answering machine
    commands.reply_am.remove_entry(member.id)
    commands.ban_am.remove_entry(member.id)

    # Remember that the user has left, in case we want to log after they're gone
    username = f"{str(member)}"
    commands.ul.add_ban(member.id, username)
    mes = f":wave: **{username} ({member.id})** покидає сервер"
    chan = client.get_channel(config.SYS_LOG)
    await chan.send(mes)


"""
On Message Delete
Occurs when a user's message is deleted
"""


@client.event
async def on_message_delete(message: discord.Message):
    if not should_log(message.guild) or message.author.bot:
        return

    await delete_message_helper(message)


"""
On Bulk Message Delete
Occurs when a user's messages are bulk deleted, such as ban or kick
"""


@client.event
async def on_bulk_message_delete(messages: list[discord.Message]):
    if not should_log(messages[0].guild) or messages[0].author.bot:
        return

    for message in messages:
        await delete_message_helper(message)


"""
On Message Edit
Occurs when a user edits a message
"""


@client.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if not should_log(before.guild) or before.author.bot:
        return

    # Prevent embedding of content from triggering the log
    if before.content == after.content:
        return

    try:
        chan = client.get_channel(config.SYS_LOG)
        mes = f":pencil: **{str(before.author)}** змінює повідомлення в <#{before.channel.id}>: з `{before.content}` на `{after.content}`"
        await commonbot.utils.send_message(mes, chan)

        # If user is on watchlist, then post it there as well
        watching = watch.should_note(after.author.id)
        if watching:
            watchchan = client.get_channel(config.WATCHLIST_CHAN)
            await commonbot.utils.send_message(mes, watchchan)

    except discord.errors.HTTPException as err:
        print(
            f"Виникла невідома помилка під час редагування повідомлення. Це повідомлення не вдалося опублікувати з наступної причини: {err}\n")


"""
On Member Join
Occurs when a user joins the server
"""


@client.event
async def on_member_join(member: discord.Member):
    if not should_log(member.guild):
        return

    mes = f":confetti_ball: **{str(member)} ({member.id})** приєднується до серверу"
    chan = client.get_channel(config.SYS_LOG)
    await chan.send(mes)

    with open(USERID_LOG_PATH, 'a') as uid_file:
        uid_file.write(f"{member.id}\n")


"""
On Voice State Update
Occurs when a user joins/leaves an audio channel
"""


@client.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if not should_log(member.guild) or member.bot:
        return

    if not after.channel:
        mes = f":mute: **{str(member)}** покидає голосовий канал {before.channel.name}"
        chan = client.get_channel(config.SYS_LOG)
        await chan.send(mes)
    elif not before.channel:
        mes = f":loud_sound: **{str(member)}** приєднується до голосового каналу {after.channel.name}"
        chan = client.get_channel(config.SYS_LOG)
        await chan.send(mes)


"""
On Reaction Remove
Occurs when a user removes a reaction from a message
"""


@client.event
async def on_reaction_remove(reaction: discord.Reaction, user: discord.Member):
    if user.bot:
        return

    emoji_name = reaction.emoji if isinstance(reaction.emoji, str) else reaction.emoji.name
    chan = client.get_channel(config.SYS_LOG)
    await chan.send(f":face_in_clouds: {str(user)} ({user.id}) прибирає емоційку `{emoji_name}`")


"""
On Message
Occurs when a user posts a message
More or less the main function
"""


@client.event
async def on_message(message: discord.Message):
    # Bouncer should not react to its own messages
    if message.author.id == client.user.id:
        return

    try:
        # Allows the owner to enable debug mode
        if dbg.check_toggle(message):
            await dbg.toggle_debug(message)
            return

        if dbg.should_ignore_message(message):
            return

        # If bouncer detects a private DM sent to it, forward it to staff
        if isinstance(message.channel, discord.channel.DMChannel):
            await frwrdr.on_dm(message)
            return

        # Check if user is on watchlist, and should be tracked
        watching = watch.should_note(message.author.id)
        if watching:
            chan = client.get_channel(config.WATCHLIST_CHAN)
            content = commonbot.utils.combine_message(message)
            mes = f"<@{str(message.author.id)}> надсилає повідомлення в <#{message.channel.id}>: {content}"
            await commonbot.utils.send_message(mes, chan)

        # If a user pings bouncer, log into mod channel, unless it's us
        if client.user in message.mentions and message.channel.category_id not in config.INPUT_CATEGORIES:
            content = commonbot.utils.combine_message(message)
            mes = f"<@{str(message.author.id)}> згадує мене в <#{message.channel.id}>: {content}\n{message.jump_url}"
            chan = client.get_channel(config.MAILBOX)
            await commonbot.utils.send_message(mes, chan)

        # Only allow moderators to invoke commands, and only in staff category
        if message.content.startswith(config.CMD_PREFIX):
            if commonbot.utils.check_roles(message.author,
                                           config.MODS_ROLES) and message.channel.category_id in config.INPUT_CATEGORIES:
                cmd = commonbot.utils.strip_prefix(message.content, config.CMD_PREFIX)
                cmd = commonbot.utils.get_first_word(cmd)
                if cmd in FUNC_DICT:
                    func = FUNC_DICT[cmd][0]
                    arg = FUNC_DICT[cmd][1]
                    await func(message, arg)
    except discord.errors.Forbidden as err:
        if err.code == 50007:
            chan = client.get_channel(config.MAILBOX)
            await chan.send(
                "Не вдається надіслати повідомлення – не вдається надіслати повідомлення цьому користувачеві")


client.run(config.DISCORD_KEY)
