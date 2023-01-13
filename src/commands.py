from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import discord

import commonbot.utils
from commonbot.user import UserLookup

import config
import db
from blocks import BlockedUsers
from client import client
from config import LogTypes, CMD_PREFIX, BAN_APPEAL
from forwarder import MessageForwarder
import visualize
from waiting import AnsweringMachine

ul = UserLookup()
bu = BlockedUsers()
reply_am = AnsweringMachine()
ban_am = AnsweringMachine()

BAN_KICK_MES = "Вітання! Вас було {type} на Discord сервері Stardew Valley Україна за порушення правил: `{mes}`."
SCAM_MES = "Вітання! Вас було заблоковано на Discord сервері Stardew Valley Україна за розміщення оманливого посилання."
WARN_MES = "Вітання! Ви отримали попередження #{count} на Discord сервері Stardew Valley Україна за порушення правил: `{mes}`. Просимо вас переглянути <#1002978786800844901> для детальнішої інформації. Якщо у вас виникли запитання, ви можете відповісти безпосередньо на це повідомлення, щоб зв'язатися з персоналом."


async def send_help_mes(mes: discord.Message, _):
    dm_warns = "On" if config.DM_WARN else "Off"
    dm_bans = "On" if config.DM_BAN else "Off"
    reply_threads = "On" if config.FORWARDING_CREATE_THREADS else "Off"
    help_mes = (
        f"Зробити попередження: `{CMD_PREFIX}warn <user> <message>`\n"
        f"Заблокувати: `{CMD_PREFIX}ban <user> <reason>`\n"
        f"Розблокувати: `{CMD_PREFIX}unban <user> <reason>`\n"
        f"Вигнати: `{CMD_PREFIX}kick <user> <reason>`\n"
        f"Заблокувати через заздалегідь створене оманливе повідомлення: `{CMD_PREFIX}scam <user>`\n"
        f"Попередній перегляд того, що буде надіслано користувачеві `{CMD_PREFIX}preview <warn/ban/kick> <reason>`\n"
        "\n"
        f"Знайти користувача: `{CMD_PREFIX}search <user>`\n"
        f"Створити примітку про користувача: `{CMD_PREFIX}note <user> <message>`\n"
        f"Видалити журнал користувача: `{CMD_PREFIX}remove <user> <index(optional)>`\n"
        f"Редагувати примітку про користувача: `{CMD_PREFIX}edit <user> <index(optional)> <new_message>`\n"
        "\n"
        f"Відповісти користувачеві в ПП: `{CMD_PREFIX}reply <user> <message>`\n"
        f" - Щоб відповісти на останнє ПП: `{CMD_PREFIX}reply ^ <message>`\n"
        f" - Ви також можете відповісти Discord на ПП за допомогою `{CMD_PREFIX}reply <message>`\n"
        f"Переглянути користувачів, які очікують на відповідь: `{CMD_PREFIX}waiting`. Очистити - `{CMD_PREFIX}clear`\n"
        f"Заборонити користувачеві надсилати нам ПП: `{CMD_PREFIX}block/{CMD_PREFIX}unblock <user>`\n"
        f"Створення/використання гілок для нового повідомлення користувача: `{reply_threads}`\n"
        "\n"
        f"Синхронізувати команди бота з сервером: `{CMD_PREFIX}sync`\n"
        f"Розглушити користувача.: `{CMD_PREFIX}unmute <user>`\n"
        f"Надіслати повідомлення від імені бота: `{CMD_PREFIX}say <channel> <message>`\n"
        "\n"
        f"Відстежувати кожен рух користувача: `{CMD_PREFIX}watch <user>`\n"
        f"Видалити користувача зі списку відстеження: `{CMD_PREFIX}unwatch <user>`\n"
        f"Показати список відстежуваних користувачів: `{CMD_PREFIX}watchlist`\n"
        "\n"
        f"Переглянути час роботи бота: `{CMD_PREFIX}uptime`\n"
        "\n"
        f"Надсилати користувачам ПП, коли вони забанені - `{dm_bans}`\n"
        f"Надсилати користувачам ПП, коли вони попереджені - `{dm_warns}`"
    )

    await mes.channel.send(help_mes)


def lookup_username(uid: int) -> Optional[str]:
    username = ul.fetch_username(client, uid)

    if not username:
        check_db = db.search(uid)
        if check_db:
            username = check_db[-1].name
        else:
            return None

    return username


async def clear_am(message: discord.Message, _):
    if message.channel.id == BAN_APPEAL:
        ban_am.clear_entries()
    else:
        reply_am.clear_entries()


async def list_waiting(message: discord.Message, _):
    if message.channel.id == BAN_APPEAL:
        mes_list = ban_am.gen_waiting_list()
    else:
        mes_list = reply_am.gen_waiting_list()

    if len(mes_list) == 0:
        await message.channel.send("Немає повідомлень, що очікують на розгляд")
    else:
        for mes in mes_list:
            await message.channel.send(mes)


async def sync(message: discord.Message, _):
    await client.sync_guild(message.guild)
    await message.channel.send("Сервер синхронізовано")


"""
User Search
Searches the database for the specified user, given a message
"""


async def search_command(mes: discord.Message, _):
    userid = ul.parse_id(mes)
    if not userid:
        await mes.channel.send(
            f"Мені не вдалося знайти користувача ніде на основі цього повідомлення. `{CMD_PREFIX}search КОРИСТУВАЧ`")
        return

    output = await search_helper(userid)
    await commonbot.utils.send_message(output, mes.channel)


async def search_helper(uid: int) -> str:
    ret = ""
    # Get database values for given user
    search_results = db.search(uid)
    username = lookup_username(uid)

    if not search_results:
        if username:
            ret += f"Користувача {username} не знайдено в базі даних\n"
        else:
            return "Цього користувача не знайдено ні в базі даних, ні на сервері\n"
    else:
        # Format output message
        out = f"Користувача `{username}` (ID: {uid}) знайдено з наступними порушеннями\n"
        for index, item in enumerate(search_results):
            out += f"{index + 1}. {str(item)}"
        ret += out

    return ret


"""
Log User
Notes an infraction for a user
"""


async def log_user(mes: discord.Message, state: LogTypes):
    # Attempt to generate user object
    userid = ul.parse_id(mes)
    if not userid:
        if state == LogTypes.NOTE:
            await mes.channel.send(f"Я не зміг зрозуміти це повідомлення: `{CMD_PREFIX}note КОРИСТУВАЧ`")
        else:
            await mes.channel.send(f"Я не зміг зрозуміти це повідомлення: `{CMD_PREFIX}log КОРИСТУВАЧ`")
        return

    # Calculate value for 'num' category in database
    # For warns, it's the newest number of warns, otherwise it's a special value
    if state == LogTypes.WARN:
        count = db.get_warn_count(userid)
    else:
        count = state.value
    current_time = datetime.now(timezone.utc)

    # Attempt to fetch the username for the user
    username = lookup_username(userid)
    if not username:
        username = "ID: " + str(userid)
        await mes.channel.send(
            "Мені не вдалося знайти ім'я користувача для цього користувача, але як би там не було, я все одно це зроблю.")

    # Generate log message, adding URLs of any attachments
    content = commonbot.utils.combine_message(mes)
    output = commonbot.utils.parse_message(content, username)

    if state == LogTypes.SCAM:
        output = "Заблоковано за надсилання оманливого вмісту в чаті."

    # If they didn't give a message, abort
    if output == "":
        await mes.channel.send("Укажіть причину, чому ви хочете занести користувача в журнал.")
        return

    # Update records for graphing
    if state == LogTypes.BAN or state == LogTypes.SCAM:
        visualize.update_cache(mes.author.name, (1, 0), commonbot.utils.format_time(current_time))
    elif state == LogTypes.WARN:
        visualize.update_cache(mes.author.name, (0, 1), commonbot.utils.format_time(current_time))
    elif state == LogTypes.UNBAN:
        await mes.channel.send("Видалення всіх старих журналів про розблокування")
        db.clear_user_logs(userid)

    # Generate message for log channel
    globalcount = db.get_dbid()
    new_log = db.UserLogEntry(globalcount + 1, userid, username, count, current_time, output, mes.author.name, None)
    log_message = str(new_log)
    await mes.channel.send(log_message)

    # Send ban recommendation, if needed
    if state == LogTypes.WARN and count >= config.WARN_THRESHOLD:
        await mes.channel.send(
            f"Цей користувач отримав {config.WARN_THRESHOLD} попередження, а може й більше. Раджу заблокувати його.")

    log_mes_id = 0
    # If we aren't noting, need to also write to log channel
    if state != LogTypes.NOTE:
        # Post to channel, keep track of message ID
        chan = discord.utils.get(mes.guild.channels, id=config.LOG_CHAN)
        log_mes = await chan.send(log_message)
        log_mes_id = log_mes.id

        try:
            # Send a DM to the user
            user = client.get_user(userid)
            if user:
                dm_chan = user.dm_channel
                # If first time DMing, need to create channel
                if not dm_chan:
                    dm_chan = await user.create_dm()

                # Only send DM when specified in configs
                if state == LogTypes.BAN and config.DM_BAN:
                    await dm_chan.send(BAN_KICK_MES.format(type="заблоковано", mes=output))
                elif state == LogTypes.WARN and config.DM_WARN:
                    await dm_chan.send(WARN_MES.format(count=count, mes=output))
                elif state == LogTypes.KICK and config.DM_BAN:
                    await dm_chan.send(BAN_KICK_MES.format(type="вигнано", mes=output))
                elif state == LogTypes.SCAM and config.DM_BAN:
                    await dm_chan.send(SCAM_MES)
        # Exception handling
        except discord.errors.HTTPException as err:
            if err.code == 50007:
                await mes.channel.send(
                    "Неможливо надіслати повідомлення цьому користувачеві. Ймовірно, він закрив ПП або заблокував мене.")
            else:
                await mes.channel.send(
                    f"ПОМИЛКА: Під час спроби надіслати ПП сталася несподівана помилка. Повідом про це Danielle: {err}")

    # Update database
    new_log.message_id = log_mes_id
    db.add_log(new_log)


"""
Preview message
Prints out Bouncer's DM message as the user will receive it
"""


async def preview(mes: discord.Message, _):
    output = commonbot.utils.strip_words(mes.content, 1)

    state_raw = commonbot.utils.get_first_word(output)
    output = commonbot.utils.strip_words(output, 1)

    if state_raw == "ban":
        state = LogTypes.BAN
    elif state_raw == "kick":
        state = LogTypes.KICK
    elif state_raw == "warn":
        state = LogTypes.WARN
    elif state_raw == "scam":
        state = LogTypes.SCAM
    else:
        await mes.channel.send(
            f"Я поняття не маю, що таке {state_raw}, але це точно не `бан`, `попередження` чи `вигнання`.")
        return

    # Might as well mimic logging behavior
    if output == "" and state != LogTypes.SCAM:
        await mes.channel.send("Укажіть причину, чому ви хочете внести це до журналу.")
        return

    if state == LogTypes.BAN:
        if config.DM_BAN:
            await mes.channel.send(BAN_KICK_MES.format(type="заблоковано", mes=output))
        else:
            await mes.channel.send(
                "Опцію надсилання ПП користувачу про його бани наразі вимкнено, він не бачитиме жодного повідомлення")
    elif state == LogTypes.WARN:
        if config.DM_WARN:
            await mes.channel.send(WARN_MES.format(count="X", mes=output))
        else:
            await mes.channel.send(
                "Опцію надсилання ПП користувачу про його попередження наразі вимкнено, він не бачитиме жодного повідомлення")
    elif state == LogTypes.KICK:
        if config.DM_BAN:
            await mes.channel.send(BAN_KICK_MES.format(type="вигнано", mes=output))
        else:
            await mes.channel.send(
                "Опцію надсилання ПП користувачу про його вигнання наразі вимкнено, він не бачитиме жодного повідомлення")
    elif state == LogTypes.SCAM:
        if config.DM_BAN:
            await mes.channel.send(SCAM_MES)
        else:
            await mes.channel.send(
                "Опцію надсилання ПП користувачу про його бани наразі вимкнено, він не бачитиме жодного повідомлення")


"""
Remove Error
Removes last database entry for specified user
"""


async def remove_error(mes: discord.Message, edit: bool):
    userid = ul.parse_id(mes)
    if not userid:
        if edit:
            await mes.channel.send(
                f"Я не зміг зрозуміти це повідомлення: `{CMD_PREFIX}remove КОРИСТУВАЧ [num] new_message`")
        else:
            await mes.channel.send(f"Я не зміг зрозуміти це повідомлення: `{CMD_PREFIX}remove КОРИСТУВАЧ [num]`")
        return

    username = lookup_username(userid)
    if not username:
        username = str(userid)

    # If editing, and no message specified, abort.
    output = commonbot.utils.parse_message(mes.content, username)
    if output == "":
        if edit:
            await mes.channel.send("Потрібно налаштувати реєстрацію редагування повідомлень")
            return
        else:
            output = "0"

    try:
        index = int(output.split()[0]) - 1
        output = commonbot.utils.strip_words(output, 1)
    except (IndexError, ValueError):
        index = -1

    # Find most recent entry in database for specified user
    search_results = db.search(userid)
    # If no results in database found, can't modify
    if not search_results:
        await mes.channel.send("Мені не вдалося знайти цього користувача в базі даних")
    # If invalid index given, yell
    elif (index > len(search_results) - 1) or index < -1:
        await mes.channel.send(f"Я не можу змінити номер {index + 1}, для цього користувача цього не так багато")
    else:
        item = search_results[index]
        if edit:
            if item.log_type == LogTypes.NOTE.value:
                item.timestamp = datetime.now(timezone.utc)
                item.log_message = output
                item.staff = mes.author.name
                db.add_log(item)
                out = f"Тепер у журналі зазначено наступне:\n{str(item)}\n"
                await mes.channel.send(out)
            else:
                await mes.channel.send("Наразі ви можете лише редагувати примітки")
            return

        # Everything after here is deletion
        db.remove_log(item.dbid)
        out = "Наведений журнал було видалено:\n"
        out += str(item)

        if item.log_type == LogTypes.BAN:
            visualize.update_cache(item.staff, (-1, 0), commonbot.utils.format_time(item.timestamp))
        elif item.log_type == LogTypes.WARN:
            visualize.update_cache(item.staff, (0, -1), commonbot.utils.format_time(item.timestamp))
        await mes.channel.send(out)

        # Search logging channel for matching post, and remove it
        try:
            if item.message_id != 0:
                chan = discord.utils.get(mes.guild.channels, id=config.LOG_CHAN)
                old_mes = await chan.fetch_message(item.message_id)
                await old_mes.delete()
        # Print message if unable to find message to delete, but don't stop
        except discord.errors.HTTPException as err:
            print(f"Не вдалося знайти повідомлення для видалення: {str(err)}")


"""
Block User
Prevents DMs from a given user from being forwarded
"""


async def block_user(mes: discord.Message, block: bool):
    userid = ul.parse_id(mes)
    if not userid:
        if block:
            await mes.channel.send(f"Я не зміг зрозуміти це повідомлення: `{CMD_PREFIX}block КОРИСТУВАЧ`")
        else:
            await mes.channel.send(f"Я не зміг зрозуміти це повідомлення: `{CMD_PREFIX}unblock КОРИСТУВАЧ`")
        return

    username = lookup_username(userid)
    if not username:
        username = str(userid)

    # Store in the database that the given user is un/blocked
    # Also update current block list to match
    if block:
        if bu.is_in_blocklist(userid):
            await mes.channel.send("Гм... Цього користувача вже заблоковано...")
        else:
            bu.block_user(userid)
            await mes.channel.send(
                f"Я заблокував користувача {username}. Повідомлення від нього більше не відображатимуться в чаті, але вони будуть зареєстровані для подальшого перегляду.")
    else:
        if not bu.is_in_blocklist(userid):
            await mes.channel.send("Цього користувача не заблоковано...")
        else:
            bu.unblock_user(userid)
            await mes.channel.send(
                f"Я розблокував користувача {username}. Ви знову зможете почути його тупу фігню в чаті.")


"""
Reply
Sends a private message to the specified user
"""


async def reply(mes: discord.Message, message_forwarder: MessageForwarder):
    try:
        user, metadata_words = _get_user_for_reply(mes, message_forwarder)
    except GetUserForReplyException as err:
        await mes.channel.send(str(err))
        return
    # If we couldn't find anyone, then they aren't in the server, and can't be DMed
    if not user:
        if mes.reference:
            await mes.channel.send(
                "Вибачте, але мені не вдалося отримати користувача з повідомлення. Ймовірно, бот був перезапущений після того, як це було надіслано. Вам потрібно буде зробити це 'старим добрим способом'")
        else:
            await mes.channel.send(
                "Вибачте, але користувач повинен бути на сервері, щоб я міг йому надіслати повідомлення")
        return

    try:
        content = commonbot.utils.combine_message(mes)
        output = commonbot.utils.strip_words(content, metadata_words)

        # Don't allow blank messages
        if len(output) == 0 or output.isspace():
            await mes.channel.send("...Це повідомлення було порожнім. Будь ласка, надішліть актуальне повідомлення")
            return

        dm_chan = user.dm_channel
        # If first DMing, need to create DM channel
        if not dm_chan:
            dm_chan = await client.create_dm(user)
        # Message sent to user
        await dm_chan.send(f"Повідомлення від персоналу сервера SDV Україна: {output}")
        # Notification of sent message to the senders
        await mes.channel.send(f"Повідомлення надіслано користувачеві `{str(user)}`.")

        # If they were in our answering machine, they have been replied to, and can be removed
        if mes.channel.id == BAN_APPEAL:
            ban_am.remove_entry(user.id)
        else:
            reply_am.remove_entry(user.id)

    # Exception handling
    except discord.errors.HTTPException as err:
        if err.code == 50007:
            await mes.channel.send(
                "Неможливо надіслати повідомлення цьому користувачеві. Ймовірно, він закрив ПП або заблокував мене.")
        else:
            await mes.channel.send(
                f"ПОМИЛКА: Під час спроби надіслати ПП сталася несподівана помилка. Повідом про це Danielle: {err}")


class GetUserForReplyException(Exception):
    """
    Helper exception to make _get_user_for_reply easier to write.
    By raising this the function can bail out early, so fewer levels of if/else nesting are needed.
    """
    pass


"""
_get_user_for_reply
Gets the user to reply to for a reply command.
Based on the reply command staff wrote, and the channel it was sent in, this figures out who to DM.
Returns a user (or None, if staff mentioned a user not in the server) and the number of words to strip from the reply command.
"""


def _get_user_for_reply(message: discord.Message, message_forwarder: MessageForwarder) -> (discord.User | None, int):
    # If it's a Discord reply to a Bouncer message, use the mention in the message
    if message.reference:
        user_reply = message.reference.cached_message
        if user_reply:
            if user_reply.author == client.user and len(user_reply.mentions) == 1:
                return user_reply.mentions[0], 1

    # If it's a reply thread, the user the reply thread is for, otherwise None
    thread_user = message_forwarder.get_userid_for_user_reply_thread(message)

    # If given '^' instead of user, message the last person to DM bouncer
    # Uses whoever DMed last since last startup, don't bother keeping in database or anything like that
    if message.content.split()[1] == "^":
        # Disable '^' if reply threads are on
        if config.FORWARDING_CREATE_THREADS:
            raise GetUserForReplyException(
                f"Гілки-відповіді для ПП користувачів увімкнені, тому `^` вимкнено. Використовуйте `{CMD_PREFIX}reply ПВД`, щоб відповісти користувачеві, для якого призначена гілка (або згадати будь-якого користувача поза темою).")

        # If reply threads are off but staff is messaging in an old reply thread, so take '^' to mean the user the thread is for
        if thread_user is not None:
            return client.get_user(thread_user), 2
        elif message.channel.id == BAN_APPEAL and ban_am.recent_reply_exists():
            return ban_am.get_recent_reply(), 2
        elif message.channel.id != BAN_APPEAL and reply_am.recent_reply_exists():
            return reply_am.get_recent_reply(), 2
        else:
            raise GetUserForReplyException(
                "Вибачте, у мене не зберігається попередній користувач. Доведеться робити це старим добрим способом.")

    # The mentioned user, or None if no user is mentioned
    userid = ul.parse_id(message)

    # Otherwise, we pick the user to reply to based on the following table
    # |                     | User Mention                                                    | No User Mention                |
    # |---------------------|-----------------------------------------------------------------|--------------------------------|
    # | Not In Reply Thread | Use the mentioned user                                          | Error - Unknown who to message |
    # | In Reply Thread     | Error - Users are not supposed to be mentioned in reply threads | Use the reply thread user      |

    if userid:
        if thread_user is None:  # User mentioned, not a thread -> use the mentioned user
            return client.get_user(userid), 2
        else:  # User mentioned, reply thread -> error, users are not supposed to be mentioned in reply threads
            raise GetUserForReplyException(
                f"У гілках-відповідей користувачів згадування користувачів вимкнено. Використовуйте `{CMD_PREFIX}reply ПВД`, щоб відповісти користувачеві, для якого призначена гілка (або згадати будь-якого користувача поза темою).")
    else:
        if thread_user is None:  # No user mentioned, not a reply thread -> error, unknown who to message
            raise GetUserForReplyException(f"Я не зміг розібрати це повідомлення: `{CMD_PREFIX}reply КОРИСТУВАЧ`")
        else:  # No user mentioned, reply thread -> use reply thread user
            return client.get_user(thread_user), 1


"""
Say
Speaks a message to the specified channel as the bot
"""


async def say(message: discord.Message, _):
    try:
        payload = commonbot.utils.strip_words(message.content, 1)
        channel_id = commonbot.utils.get_first_word(payload)
        channel = discord.utils.get(message.guild.channels, id=int(channel_id))
        output = commonbot.utils.strip_words(payload, 1)
        if output == "" and len(message.attachments) == 0:
            await message.channel.send("Не можна надсилати порожні повідомлення.")

        for item in message.attachments:
            file = await item.to_file()
            await channel.send(file=file)

        if output != "":
            await channel.send(output)

        return "Повідомлення надіслано."
    except (IndexError, ValueError):
        await message.channel.send(f"Мені не вдалося знайти ID каналу в цьому пов. `{CMD_PREFIX}say CHAN_ID message`")
    except AttributeError:
        await message.channel.send("Ви впевнені, що це було ID каналу?")
    except discord.errors.HTTPException as err:
        if err.code == 50013:
            await message.channel.send("Ви не маєте дозволу на публікацію повідомлень в цьому каналі.")
        else:
            await message.channel.send(f"Йой, щось пішло не так, усі панікують! {str(err)}")
