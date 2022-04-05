import pickledb
import os
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, Updater, CommandHandler, MessageHandler, CallbackQueryHandler, BaseFilter, Filters, PicklePersistence
from datetime import datetime, timezone, timedelta, time, date

import logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)

updater = Updater(
    token='1771951064:AAG58KNlXQDa4CJGKTFFrI68OG9MvN95ntw',
    # token='929969080:AAEnUoS6-OFUGSvzybObCTmDpjgH0w5PcEQ',  # FOR DEBUGGING
    persistence=PicklePersistence(filename='bot_data'),
    use_context=True
)
dispatcher = updater.dispatcher
jq = updater.job_queue

FEVER_TEMP = 37.5

TEAM_STRING = {
    "A": "NSMEN 1",
    "B": "NSMEN 2",
    "B1": "NSMEN 3"
}

EXTEND = False

db = pickledb.load("database.db", True)
# db = pickledb.load("debug.db", True)

# Helper Functions


def broadcast(list_name, text, context: CallbackContext):
    list = db.get(list_name) or []
    for chat_id in list:
        try:
            context.bot.send_message(
                chat_id=chat_id,
                parse_mode="markdown",
                text=text,
                timeout=10)
        except:
            for chat_id in list:
                print('Removed chat_id ' + chat_id)
                list.remove(chat_id)
            continue


def broadcast_callback(context: CallbackContext):
    list_name = context.job.context["list"]
    text = context.job.context["text"]
    broadcast(list_name, text, context)


# Initialisation
def initialise_db():
    today = date.today()
    today_string = str(today)
    if db.get(str((today_string, 0, "A"))):
        print("BROKENNNNN")
        return

    # FORMAT: db.get(date,is_afternoon,team) == arr[s/no]
    # date is str(date)
    # is_afternoon is 0 for morn, 1 for aft
    # team is A/B/B1
    # s/no is 01 to the total no.

    TEAM_COUNT = db.get("TEAM_COUNT")

    db.set(str((today_string, 0, "A")), [-1] * TEAM_COUNT["A"])
    db.set(str((today_string, 1, "A")), [-1] * TEAM_COUNT["A"])
    db.set(str((today_string, 0, "B")), [-1] * TEAM_COUNT["B"])
    db.set(str((today_string, 1, "B")), [-1] * TEAM_COUNT["B"])
    db.set(str((today_string, 0, "B1")), [-1] * TEAM_COUNT["B1"])
    db.set(str((today_string, 1, "B1")), [-1] * TEAM_COUNT["B1"])

    # TODO: delete old data
    delete_date = str(today - timedelta(days=32))
    if db.get(str((delete_date, 0, "A"))):
        db.rem(str((delete_date, 0, "A")))
    if db.get(str((delete_date, 1, "A"))):
        db.rem(str((delete_date, 1, "A")))
    if db.get(str((delete_date, 0, "B"))):
        db.rem(str((delete_date, 0, "B")))
    if db.get(str((delete_date, 1, "B"))):
        db.rem(str((delete_date, 1, "B")))
    if db.get(str((delete_date, 0, "B1"))):
        db.rem(str((delete_date, 0, "B1")))
    if db.get(str((delete_date, 1, "B1"))):
        db.rem(str((delete_date, 1, "B1")))


def initialise_reminders():
    # jq.run_daily(initialise_db,
    #              time(hour=0, minute=0, tzinfo=timezone(timedelta(hours=8))))

    # Morning messages
    MORNING_MESSAGE = "Morning temperature taking has started. What is your temperature?"
    jq.run_daily(broadcast_callback,
                 time(hour=6, minute=0, tzinfo=timezone(timedelta(hours=8))),
                 context={
                     "list": "A_LIST",
                     "text": MORNING_MESSAGE
                 })
    jq.run_daily(broadcast_callback,
                 time(hour=6, minute=0, tzinfo=timezone(timedelta(hours=8))),
                 context={
                     "list": "B_LIST",
                     "text": MORNING_MESSAGE
                 })
    jq.run_daily(broadcast_callback,
                 time(hour=6, minute=0, tzinfo=timezone(timedelta(hours=8))),
                 context={
                     "list": "B1_LIST",
                     "text": MORNING_MESSAGE
                 })

    # Afternoon messages
    AFTERNOON_MESSAGE = "Afternoon temperature taking has started. What is your temperature?"
    jq.run_daily(broadcast_callback,
                 time(hour=13, minute=30, tzinfo=timezone(timedelta(hours=8))),
                 context={
                     "list": "A_LIST",
                     "text": AFTERNOON_MESSAGE
                 })
    jq.run_daily(broadcast_callback,
                 time(hour=13, minute=30, tzinfo=timezone(timedelta(hours=8))),
                 context={
                     "list": "B_LIST",
                     "text": AFTERNOON_MESSAGE
                 })
    jq.run_daily(broadcast_callback,
                 time(hour=13, minute=30, tzinfo=timezone(timedelta(hours=8))),
                 context={
                     "list": "B1_LIST",
                     "text": AFTERNOON_MESSAGE
                 })


def valid_temp(temp):
    if len(temp) > 4:
        temp = temp[0:4]
    return (len(temp) > 1
            and temp[0].isdigit()
            and temp[1].isdigit()
            and (len(temp) == 2
                 or len(temp) == 4
                 and temp[3].isdigit()
                 and temp[2] == '.'))


class TemperatureFilter(BaseFilter):
    def filter(self, message):
        return valid_temp(message.text)


class MassTemperatureFilter(BaseFilter):
    def filter(self, message):
        # args = message.text.split()
        args = message.text.split()
        if len(args) % 2:
            return False

        # All even (0-indexed) arguments must be serial numbers
        for i in range(0, len(args), 2):
            if not args[i].isdigit():
                return False

        # All odd arguments must be valid temperatures
        for i in range(1, len(args), 2):
            if not valid_temp(args[i]):
                return False
        return True


class NumberFilter(BaseFilter):
    def filter(self, message):
        return message.text.isdigit()


# Generators
def generate_summary(working_date, is_afternoon, team):
    DISABLED_SNO = db.get("DISABLED_SNO")

    working_date_string = str(working_date)
    working_list = db.get(str((working_date_string, is_afternoon, team)))

    total_strength = len(working_list)
    total_valid_strength = total_strength - len(DISABLED_SNO[team])
    reported_strength = 0
    unreported_list = []
    fever_list = []

    for i in range(total_strength):
        temp = working_list[i]
        if temp != -1:
            reported_strength += 1
            if temp >= 37.5:
                fever_list.append("{0:0=2d}".format(i+1) + ". " +
                                  str(temp) + "°C")
        elif not (i+1) in DISABLED_SNO[team]:
            unreported_list.append("{0:0=2d}".format(i+1))

    unreported_strength = total_valid_strength - reported_strength
    unreported_string = ', '.join(unreported_list)
    fever_string = '\n'.join(fever_list)

    return ("Team " + team + " temperature taking status (" + working_date.strftime("%d %b %Y, %A, ") + ("Afternoon" if is_afternoon else "Morning")
            + ") as follows:\n\n"
            + "*Total strength*  : " + str(total_valid_strength)
            + "\n*Reported*          : " + str(reported_strength)
            + "\n*Unreported*       : "
            + (str(unreported_strength)
               + "\n\n*The following people have not reported their temperature:*\n"
               + unreported_string
               if unreported_strength else "0")
            + ("\n\n*The following people have HIGH TEMPERATURES:*\n"
               + fever_string
               if fever_string else "\n\nThere is no high temperature detected for those who have reported their temperature."))


def generate_full(working_date, team, is_afternoon):
    DISABLED_SNO = db.get("DISABLED_SNO")

    working_date_string = str(working_date)
    working_list = db.get(str((working_date_string, is_afternoon, team)))
    total_strength = len(working_list)
    temp_list = []

    for i in range(total_strength):
        # temp = db[working_date][is_afternoon][team][i]
        temp = working_list[i]
        if temp >= 37.5:
            temp_list.append("{0:0=2d}".format(i+1) + ". *" +
                             str(temp) + "°C (⚠ FEVER)*")
        elif temp != -1:
            temp_list.append("{0:0=2d}".format(i+1) + ". " +
                             str(temp) + "°C")
        elif (i+1) in DISABLED_SNO[team]:
            temp_list.append("{0:0=2d}".format(i+1) + ". N/A (posted out)")
        else:
            temp_list.append("{0:0=2d}".format(i+1) + ". UNREPORTED")
    temp_string = "\n".join(temp_list)

    return ("*Temperatures for Team " + team + "\n"
            + working_date.strftime("%d %b %Y, %A, (")
            + ("Afternoon" if is_afternoon else "Morning") + ")*\n" + temp_string)


def set_serial(update: Update, context: CallbackContext):
    if "mode" in context.chat_data and context.chat_data["mode"] == "set_serial":
        team = context.user_data["newteam"]
        TEAM_COUNT = db.get("TEAM_COUNT")
        DISABLED_SNO = db.get("DISABLED_SNO")

        try:
            serial = int(update.message.text)
        except:
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                parse_mode="markdown",
                text="S/No. " + serial + " is invalid. Please enter a number from 01 to " + str(TEAM_COUNT[team]))
            return
        if serial > TEAM_COUNT[team]:
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                parse_mode="markdown",
                text="S/No. *{0:0=2d}*".format(serial) + " is invalid. Please enter a number from 01 to " + str(TEAM_COUNT[team]))
            return

        if serial in DISABLED_SNO[team]:
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                parse_mode="markdown",
                text="S/No. *{0:0=2d}*".format(serial) + " has been disabled. Please enter another number from 01 to " + str(TEAM_COUNT[team]))
            return

        # context.bot_data[""].append(update.effective_chat.id)

        context.bot.send_message(
            chat_id=update.effective_chat.id,
            parse_mode="markdown",
            text="Your Serial Number has been set to *" + "{0:0=2d}".format(serial) + "*. Type /start to change your details.")
        # if team == "A":
        #     context.bot.send_message(
        #         chat_id=update.effective_chat.id,
        #         parse_mode="markdown",
        #         text="Send me your temperature at the following timings\n1) 0600-0800hrs\n2) 1330-1430hrs\n\nWhen submitting temperature, *no serial number is needed*, only your temperature.\ne.g.\n`35.6`")
        # else:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            parse_mode="markdown",
            text="Send me your temperature at the following timings\n1) 0600-0800hrs\n2) 1330-1430hrs\n\nWhen submitting temperature, *no serial number is needed*, only your temperature.\ne.g.\n`35.6` \nAt the end of your ICT please remember to unsuscribe from the bot by using /stop")
        context.user_data["serial"] = serial
        context.chat_data["mode"] = "temperature"


def set_serial_message(update: Update, context: CallbackContext):
    team = context.user_data["newteam"]
    TEAM_COUNT = db.get("TEAM_COUNT")

    context.chat_data["mode"] = "set_serial"
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        parse_mode="markdown",
        text="What is your Serial Number (01 to " + str(TEAM_COUNT[team]) + ")? I will remember it.")


def get_time_of_day(team):
    time_now = datetime.now(timezone(timedelta(hours=8)))

    AM_START = datetime(time_now.year, time_now.month, time_now.day, tzinfo=timezone(timedelta(hours=8)),
                        hour=6, minute=0)
    AM_END = datetime(time_now.year, time_now.month, time_now.day, tzinfo=timezone(timedelta(hours=8)),
                      hour=8, minute=1)

    # if team == "A":
    #     PM_START = datetime(time_now.year, time_now.month, time_now.day, tzinfo=timezone(timedelta(hours=8)),
    #                         hour=11, minute=30)
    # else:
    #     PM_START = datetime(time_now.year, time_now.month, time_now.day, tzinfo=timezone(timedelta(hours=8)),
    #                         hour=12, minute=0)
    PM_START = datetime(time_now.year, time_now.month, time_now.day, tzinfo=timezone(timedelta(hours=8)),
                        hour=13, minute=30)
    PM_END = datetime(time_now.year, time_now.month, time_now.day, tzinfo=timezone(timedelta(hours=8)),
                      hour=14, minute=31)

    if time_now < AM_START:
        return "before_morning"
    elif time_now < AM_END or time_now < PM_START and EXTEND:
        return "morning"
    elif time_now < PM_START:
        return "late_morning"
    elif time_now < PM_END or EXTEND:
        return "afternoon"
    else:
        return "late_afternoon"


def start(update: Update, context: CallbackContext):
    if update.effective_chat.type == "group" or update.effective_chat.type == "supergroup":
        keyboard = [[InlineKeyboardButton(
            "💬 Tap to message me", url="https://t.me/ICTtempbot?start=_")]]

        context.bot.send_message(
            chat_id=update.effective_chat.id,
            parse_mode="markdown",
            text="Message me to begin",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif (update.effective_chat.type == "private"):
        if not "mode" in context.chat_data or not "serial" in context.user_data:
            keyboard = [[InlineKeyboardButton("NSMEN 1", callback_data="A")],
                        [InlineKeyboardButton("NSMEN 2", callback_data="B")],
                        [InlineKeyboardButton("NSMEN 3", callback_data="B1")]]

            context.bot.send_message(
                chat_id=update.effective_chat.id,
                parse_mode="markdown",
                text="Hello I am *FCTU NSMEN ICT Temperature Bot*! Which team are you?",
                reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            if context.user_data["newteam"] == "A1":
                context.user_data["newteam"] = "B1"

            team = context.user_data["newteam"]
            serial = context.user_data["serial"]
            keyboard = [[InlineKeyboardButton("NSMEN 1", callback_data="A")],
                        [InlineKeyboardButton("NSMEN 2", callback_data="B")],
                        [InlineKeyboardButton("NSMEN 3", callback_data="B1")],
                        [InlineKeyboardButton("Cancel", callback_data="cancel")]]

            context.bot.send_message(
                chat_id=update.effective_chat.id,
                parse_mode="markdown",
                text="*Current Team:* " + TEAM_STRING[team] + "\n*Current S/No.: *" + str(
                    serial) + "\n\nWould you like to change your details?",
                reply_markup=InlineKeyboardMarkup(keyboard))


def stop(update: Update, context: CallbackContext):
    if (update.effective_chat.type == "private") and "mode" in context.chat_data and "newteam" in context.user_data:
        team = context.user_data["newteam"]
        chat_id = update.effective_chat.id
        list = db.get(team+"_LIST") or []
        for chat_id in list:
            list.remove(chat_id)
        db.set(team+"_LIST", list)

        list2 = db.get(team+"_SUB") or []
        for chat_id in list2:
            list2.remove(chat_id)
        db.set(team+"_SUB", list2)

        context.chat_data.clear()
        context.user_data.clear()
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            parse_mode="markdown",
            text="✅ Successfully unregistered. Type '/start' to register again.")


def help(update: Update, context: CallbackContext):
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        parse_mode="markdown",
        text="Report your own temperature by typing out the value\n\n*e.g.*\n`36.5`")

    # text="Hello, I am *Paradise Temperature Bot*!\n\n"
    # + "*FEATURES*\n\n"
    # + "1️⃣ Report your own temperature by typing out the value\n\n*e.g.*\n`36.5`\n\n"
    # + "2️⃣ Report temperature for others in your team by using the following format:\n"
    # + "`<Index No.> <Temperature (in °C)>`\n\n"
    # + "*e.g.*\n`33 36.5\n38 36.3\n44 36.8`")


def temperature(update: Update, context: CallbackContext):
    today = date.today()
    today_string = str(today)
    is_afternoon = 0
    TEAM_COUNT = db.get("TEAM_COUNT")
    DISABLED_SNO = db.get("DISABLED_SNO")

    if not "mode" in context.chat_data:
        start(update, context)
        return

    if not db.get(str((today_string, 0, "A"))):
        initialise_db()

    if context.chat_data["mode"] == "set_serial":
        set_serial(update, context)
        return
    elif context.chat_data["mode"] == "temperature":
        if not "serial" in context.user_data:
            start(update, context)
            return
        # subscribe to reminders

        if context.user_data["newteam"] == "A1":
            context.user_data["newteam"] = "B1"

        team = context.user_data["newteam"]
        serial = context.user_data["serial"]
        chat_id = update.effective_chat.id

        list = db.get(team+"_LIST") or []
        if not chat_id in list:
            list.append(chat_id)
            db.set(team+"_LIST", list)

        if serial in DISABLED_SNO[team] or serial > TEAM_COUNT[team]:
            context.bot.send_message(
                chat_id=chat_id,
                parse_mode="markdown",
                text="❌ Your S/No. has been disabled. Please contact your team coxswain.\n\nUse /stop to unregister from this bot."
            )
            return

        temp = update.message.text
        if len(temp) > 4:
            temp = temp[0:4]
        temp = float(temp)

        # TODO: Check AM or PM
        time_of_day = get_time_of_day(team)
        if time_of_day == "before_morning":
            context.bot.send_message(
                chat_id=chat_id,
                parse_mode="markdown",
                text="❌ Your temperature was NOT recorded. Morning temperature taking has not started. Time: *0600-0800hrs*.")
            return
        elif time_of_day == "late_morning":
            # if team == "A":
            #     context.bot.send_message(
            #         chat_id=chat_id,
            #         parse_mode="markdown",
            #         text="❌ Your temperature was NOT recorded.\n\nMorning temperature taking: *0600-0800hrs* (ENDED)\nAfternoon temperature taking:*1330-1430hrs*\n\nContact your Team Coxswain to update your temperature.")
            # else:
            context.bot.send_message(
                chat_id=chat_id,
                parse_mode="markdown",
                text="❌ Your temperature was NOT recorded.\n\nMorning temperature taking: *0600-0800hrs* (ENDED)\nAfternoon temperature taking:*1330-1430hrs*\n\nContact your Team Coxswain to update your temperature.")
            return
        elif time_of_day == "late_afternoon":
            # if team == "A":
            #     context.bot.send_message(
            #         chat_id=chat_id,
            #         parse_mode="markdown",
            #         text="❌ Your temperature was NOT recorded.\n\nMorning temperature taking: *0600-0800hrs* (ENDED)\nAfternoon temperature taking:*1330-1430hrs* (ENDED)\n\nContact your Team Coxswain to update your temperature.")
            # else:
            context.bot.send_message(
                chat_id=chat_id,
                parse_mode="markdown",
                text="❌ Your temperature was NOT recorded.\n\nMorning temperature taking: *0600-0800hrs* (ENDED)\nAfternoon temperature taking:*1330-1430hrs* (ENDED)\n\nContact your Team Coxswain to update your temperature.")
            return

        # Set temperature (0-indexed)
        if time_of_day == "afternoon":
            # db[today][0][team][serial-1] = temp
            is_afternoon = 1

        working_key = str((today_string, is_afternoon, team))

        working_list = db.get(working_key)

        if serial > len(working_list):
            working_list.extend([-1] * (TEAM_COUNT[team] - len(working_list)))

        if working_list[serial-1] != -1:
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                parse_mode="markdown",
                text="Deleting your previously recorded temperature...")

        working_list[serial-1] = temp
        db.set(working_key, working_list)

        if temp >= FEVER_TEMP:
            broadcast(team+"_SUB",
                      "⚠ S/No. " +
                      "*{0:0=2d}*".format(serial) +
                      " just reported *"+str(temp)+"°C*",
                      context)

            context.bot.send_message(
                chat_id=update.effective_chat.id,
                parse_mode="markdown",
                text="*⚠ WARNING!*\nYour temperature is *very high*.\nPlease inform the unit then report sick.")

        context.bot.send_message(
            chat_id=update.effective_chat.id,
            parse_mode="markdown",
            text="*✅ UPDATED (" + time_of_day + ")*\n\n*Team:* " + TEAM_STRING[team] + "\n*S/N:* " + "{0:0=2d}".format(serial) + "\n*Temp:* " + str(temp) + "°C")

        for i in working_list:
            if i == -1:
                break
        else:
            broadcast(team+"_SUB",
                      "✅ All temperatures reported for Team " +
                      TEAM_STRING[team],
                      context)
            broadcast(team+"_SUB",
                      generate_summary(today, is_afternoon, team),
                      context)


def mass_temperature(update: Update, context: CallbackContext):
    today_string = str(date.today())
    is_afternoon = 0

    if not "mode" in context.chat_data or not "serial" in context.user_data:
        start(update, context)
        return

    if context.chat_data["mode"] == "set_serial":
        set_serial(update, context)
        return
    elif context.chat_data["mode"] == "temperature":
        # subscribe to reminders
        if context.user_data["newteam"] == "A1":
            context.user_data["newteam"] = "B1"

        team = context.user_data["newteam"]
        chat_id = update.effective_chat.id

        list = db.get(team+"_LIST") or []
        if not chat_id in list:
            list.append(chat_id)
            db.set(team+"_LIST", list)

        # TODO: Check AM or PM
        time_of_day = get_time_of_day(team)
        if time_of_day == "before_morning":
            context.bot.send_message(
                chat_id=chat_id,
                parse_mode="markdown",
                text="❌ Your temperature was NOT recorded. Morning temperature taking has not started. Time: *0600-0800hrs*.")
            return
        elif time_of_day == "late_morning":
            # if team == "A":
            #     context.bot.send_message(
            #         chat_id=chat_id,
            #         parse_mode="markdown",
            #         text="❌ Your temperature was NOT recorded.\n\nMorning temperature taking: *0600-0800hrs* (ENDED)\nAfternoon temperature taking:*1330-1430hrs*\n\nContact your Team Coxswain to update your temperature.")
            # else:
            context.bot.send_message(
                chat_id=chat_id,
                parse_mode="markdown",
                text="❌ Your temperature was NOT recorded.\n\nMorning temperature taking: *0600-0800hrs* (ENDED)\nAfternoon temperature taking:*1330-1430hrs*\n\nContact your Team Coxswain to update your temperature.")
            return
        elif time_of_day == "late_afternoon":
            # if team == "A":
            #     context.bot.send_message(
            #         chat_id=chat_id,
            #         parse_mode="markdown",
            #         text="❌ Your temperature was NOT recorded.\n\nMorning temperature taking: *0600-0800hrs* (ENDED)\nAfternoon temperature taking:*1330-1430hrs* (ENDED)\n\nContact your Team Coxswain to update your temperature.")
            # else:
            context.bot.send_message(
                chat_id=chat_id,
                parse_mode="markdown",
                text="❌ Your temperature was NOT recorded.\n\nMorning temperature taking: *0600-0800hrs* (ENDED)\nAfternoon temperature taking:*1330-1430hrs* (ENDED)\n\nContact your Team Coxswain to update your temperature.")
            return

        today = date.today()
        today_string = str(today)

        # Set temperature (0-indexed)
        if time_of_day == "afternoon":
            is_afternoon = 1

        working_key = str((today_string, is_afternoon, team))
        working_list = db.get(working_key)

        # temp = update.message.text
        # if len(temp) > 4:
        #     temp = temp[0:4]
        # temp = float(temp)

        args = update.message.text.split()

        # All even (0-indexed) arguments must be serial numbers
        for i in range(0, len(args), 2):
            serial = int(args[i])
            temp = float(args[i+1])

            if working_list[serial-1] != -1:
                context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    parse_mode="markdown",
                    text="Deleting previously recorded temperature for S/No. "+"*{0:0=2d}*".format(serial)+"...")

            working_list[serial-1] = temp
            db.set(working_key, working_list)

            if temp >= FEVER_TEMP:
                broadcast(team+"_SUB",
                          "⚠ S/No. " +
                          "*{0:0=2d}*".format(serial) +
                          " just reported *"+str(temp)+"°C*",
                          context)

                context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    parse_mode="markdown",
                    text="*⚠ WARNING!*\nTemperature for S/No. "+"*{0:0=2d}*".format(serial)+" is *very high*.\nPlease inform the unit then report sick.")

            context.bot.send_message(
                chat_id=update.effective_chat.id,
                parse_mode="markdown",
                text="*✅ UPDATED (" + time_of_day + ")*\n\n*Team:* " + TEAM_STRING[team] + "\n*S/N:* " + "{0:0=2d}".format(serial) + "\n*Temp:* " + str(temp) + "°C")

        for i in working_list:
            if i == -1:
                break
        else:
            broadcast(team+"_SUB",
                      "✅ All temperatures reported for Team " +
                      TEAM_STRING[team],
                      context)
            broadcast(team+"_SUB",
                      generate_summary(today, is_afternoon, team),
                      context)


def summary(update: Update, context: CallbackContext):
    if context.user_data["newteam"] == "A1":
        context.user_data["newteam"] = "B1"

    if not "newteam" in context.user_data:
        start(update, context)
        return

    team = context.user_data["newteam"]
    working_date = date.today()
    is_afternoon = 0

    if not db.get(str((str(working_date), 0, "A"))):
        initialise_db()

    time_of_day = get_time_of_day(team)
    if time_of_day == "before_morning":
        working_date = date.today() - timedelta(days=1)
    elif time_of_day == "afternoon" or time_of_day == "late_afternoon":
        is_afternoon = 1

    context.bot.send_message(
        chat_id=update.effective_chat.id,
        parse_mode="markdown",
        text=generate_summary(working_date, is_afternoon, team))


def full(update: Update, context: CallbackContext):
    if context.user_data["newteam"] == "A1":
        context.user_data["newteam"] = "B1"

    # Print all data in database
    if not "newteam" in context.user_data:
        start(update, context)
        return

    team = context.user_data["newteam"]
    working_date = date.today()
    is_afternoon = 0

    if not db.get(str((str(working_date), 0, "A"))):
        initialise_db()

    time_of_day = get_time_of_day(team)
    if time_of_day == "before_morning":
        working_date = date.today() - timedelta(days=1)
    elif time_of_day == "afternoon" or time_of_day == "late_afternoon":
        is_afternoon = 1

    context.bot.send_message(
        chat_id=update.effective_chat.id,
        parse_mode="markdown",
        text=generate_full(working_date, team, is_afternoon))


def history(update: Update, context: CallbackContext):
    # Ask user to pick which day, then show the full for that day
    keyboard = []
    for i in range(0, 15):
        working_date = date.today() - timedelta(days=i)
        if db.get(str((str(working_date), 0, "A"))):
            keyboard.append([
                InlineKeyboardButton(working_date.strftime(
                    "%d %b %Y, %A"), callback_data=str(working_date))
            ])
    keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel")])
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        parse_mode="markdown",
        text="📆 View records for which date?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def subscribe(update: Update, context: CallbackContext):
    if not "newteam" in context.user_data:
        start(update, context)
        return

    team = context.user_data["newteam"]
    chat_id = update.effective_chat.id

    list = db.get(team+"_SUB") or []

    if chat_id in list:
        list.remove(chat_id)
        context.bot.send_message(
            chat_id=chat_id,
            parse_mode="markdown",
            text="You have unsubscribed to updates for Team "+TEAM_STRING[team]
            + "\n\nType '/subscribe' again to resubscribe.")
    else:
        list.append(chat_id)
        context.bot.send_message(
            chat_id=chat_id,
            parse_mode="markdown",
            text="You have subscribed to updates for Team "+TEAM_STRING[team]
            + "\n\nType '/subscribe' again to unsubscribe."
            + "\n\n*You will be notified when:*"
            + "\n1) Someone reports high temperature"
            + "\n2) All temperatures reported")

    db.set(team+"_SUB", list)


def inline_button(update: Update, context: CallbackContext):
    query = update.callback_query

    if query.data == "cancel":
        query.edit_message_text(
            "❌ Operation cancelled", parse_mode="markdown")

    elif query.data == "A" or query.data == "B" or query.data == "B1":
        # Unsubscribe to other team reminders if team already exists
        chat_id = update.effective_chat.id
        if "newteam" in context.user_data:
            old_team = context.user_data["newteam"]

            list = db.get(old_team+"_LIST") or []
            for chat_id in list:
                list.remove(chat_id)
            old_team = context.user_data["newteam"]
            db.set(old_team+"_LIST", list)
            old_team = context.user_data["newteam"]

            list2 = db.get(old_team+"_SUB") or []
            for chat_id in list2:
                list2.remove(chat_id)
            old_team = context.user_data["newteam"]
            db.set(old_team+"_SUB", list2)

        # Set team
        context.user_data["newteam"] = query.data
        query.edit_message_text(
            "Your team is *Team " + TEAM_STRING[query.data] + "*", parse_mode="markdown")
        set_serial_message(update, context)

        # Subscribe to reminders
        list = db.get(query.data+"_LIST") or []
        list.append(chat_id)
        db.set(query.data+"_LIST", list)

    # Date for history
    elif query.data.split("-")[0].isdigit():
        working_date = datetime.strptime(query.data, "%Y-%m-%d").date()
        context.user_data["history_date"] = working_date
        keyboard = [
            [
                InlineKeyboardButton("NSMEN 1 (AM)", callback_data="hist A 0"),
                InlineKeyboardButton("NSMEN 1 (PM)", callback_data="hist A 1"),
            ],
            [
                InlineKeyboardButton("NSMEN 2 (AM)", callback_data="hist B 0"),
                InlineKeyboardButton("NSMEN 2 (PM)", callback_data="hist B 1"),
            ],
            [
                InlineKeyboardButton("NSMEN 3 (AM)", callback_data="hist B1 0"),
                InlineKeyboardButton("NSMEN 3 (PM)", callback_data="hist B1 1"),
            ],
            [InlineKeyboardButton("Cancel", callback_data="cancel")]
        ]
        query.edit_message_text(
            "🌡 View which record for " +
            working_date.strftime("%d %b %Y, %A")+"?",
            parse_mode="markdown",
            reply_markup=InlineKeyboardMarkup(keyboard))

    # Team and AM/PM for history
    elif query.data.split()[0] == "hist":
        args = query.data.split()
        working_date = context.user_data["history_date"]
        query.edit_message_text(generate_full(
            working_date, args[1], int(args[2])),
            parse_mode="markdown")


def debug(update: Update, context: CallbackContext):
    if not db.get(str((today_string, 0, "A"))):
        initialise_db()
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            parse_mode="markdown",
            reply_to_message_id=update.message.message_id,
            text="💻 Database initialised succesfully")
    else:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            parse_mode="markdown",
            reply_to_message_id=update.message.message_id,
            text="❌ Database has already been initialised")


def extend(update: Update, context: CallbackContext):
    global EXTEND
    EXTEND = not EXTEND
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        parse_mode="markdown",
        reply_to_message_id=update.message.message_id,
        text="⏰ Time extension is " + ("*enabled*" if EXTEND else "*disabled* (default)."))


def disable(update: Update, context: CallbackContext):
    TEAM_COUNT = db.get("TEAM_COUNT")
    DISABLED_SNO = db.get("DISABLED_SNO")

    if not "newteam" in context.user_data:
        start(update, context)
    if context.user_data["newteam"] == "A1":
        context.user_data["newteam"] = "B1"
    team = context.user_data["newteam"]

    if len(context.args) != 1 or not context.args[0].isdigit or int(context.args[0]) > TEAM_COUNT[team]:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            parse_mode="markdown",
            text="Invalid command\n\n"
            + "*Current Disabled S/No.*: " +
            ", ".join(str(i) for i in DISABLED_SNO[team])
            + "\n\nType '/dis <S/No.>' to disable/enable a S/No. for your team\n\nE.g.\n`/dis 32`"
        )
    else:
        disable_serial = int(context.args[0])
        action = ""

        if disable_serial in DISABLED_SNO[team]:
            DISABLED_SNO[team].remove(disable_serial)
            action = "ENABLED"
        else:
            DISABLED_SNO[team].append(disable_serial)
            action = "DISABLED"

        db.set("DISABLED_SNO", DISABLED_SNO)

        context.bot.send_message(
            chat_id=update.effective_chat.id,
            parse_mode="markdown",
            text="Team " + team + ", S/No. " +
            str(disable_serial) + " " + action
        )


def change_strength(update: Update, context: CallbackContext):
    TEAM_COUNT = db.get("TEAM_COUNT")
    DISABLED_SNO = db.get("DISABLED_SNO")

    if not "newteam" in context.user_data:
        start(update, context)
    if context.user_data["newteam"] == "A1":
        context.user_data["newteam"] = "B1"
    team = context.user_data["newteam"]

    if len(context.args) != 1 or not context.args[0].isdigit or int(context.args[0]) < 1:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            parse_mode="markdown",
            text="Invalid command\n\n"
            + "*Current Strength*: " + str(TEAM_COUNT[team])
            + "\n\nType '/str <Number>' to change the strength of your team to <Number>\n\nE.g.\n`/str 54`"
        )
    else:
        max_serial = int(context.args[0])
        action = ""

        time_of_day = get_time_of_day(team)
        today = date.today()
        today_string = str(today)

        if max_serial < TEAM_COUNT[team]:
            action = "REDUCED"
            DISABLED_SNO[team] = [
                i for i in DISABLED_SNO[team] if i <= max_serial]
            
            if time_of_day == "before_morning":
                working_key = str((today_string, 0, team))
                working_list = db.get(working_key)
                working_list = working_list[0:max_serial-1]
                db.set(working_key, working_list)
            if time_of_day != "afternoon" and time_of_day != "late_afternoon":
                working_key = str((today_string, 1, team))
                working_list = db.get(working_key)
                working_list = working_list[0:max_serial]
                db.set(working_key, working_list)
        elif max_serial < TEAM_COUNT[team]:
            action = "NOT CHANGED"
        else:
            if time_of_day == "before_morning":
                working_key = str((today_string, 0, team))
                working_list = db.get(working_key)
                working_list += [-1] * (max_serial - len(working_list))
                db.set(working_key, working_list)
            if time_of_day != "afternoon" and time_of_day != "late_afternoon":
                working_key = str((today_string, 1, team))
                working_list = db.get(working_key)
                working_list += [-1] * (max_serial - len(working_list))
                db.set(working_key, working_list)
            action = "INCREASED"

        TEAM_COUNT[team] = max_serial

        db.set("TEAM_COUNT", TEAM_COUNT)
        db.set("DISABLED_SNO", DISABLED_SNO)

        context.bot.send_message(
            chat_id=update.effective_chat.id,
            parse_mode="markdown",
            text="Team " + team + " max S/No. " + action + " to " + str(max_serial) +
            ("\nChanges will take effect during the next temperature taking." if action == "REDUCED" else "")
        )


def under_construction(update: Update, context: CallbackContext):
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        parse_mode="markdown",
        reply_to_message_id=update.message.message_id,
        text="This feature is under construction.")


dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('stop', stop))
dispatcher.add_handler(CommandHandler('help', help))
dispatcher.add_handler(CommandHandler('summary', summary))
dispatcher.add_handler(CommandHandler('full', full))
dispatcher.add_handler(CommandHandler('debug', debug))
dispatcher.add_handler(CommandHandler('extend', extend))
dispatcher.add_handler(CommandHandler('subscribe', subscribe))
dispatcher.add_handler(CommandHandler('history', history))
dispatcher.add_handler(CommandHandler('dis', disable))
dispatcher.add_handler(CommandHandler('str', change_strength))
dispatcher.add_handler(CallbackQueryHandler(inline_button))

dispatcher.add_handler(MessageHandler(
    Filters.text & TemperatureFilter(), temperature))
dispatcher.add_handler(MessageHandler(
    Filters.text & MassTemperatureFilter(), mass_temperature))
dispatcher.add_handler(MessageHandler(
    Filters.text & NumberFilter(), set_serial))
# dispatcher.add_handler(MessageHandler(
#     Filters.text, invalid_command))

if not db.get("TEAM_COUNT"):
    db.set("TEAM_COUNT", {"A": 200, "B": 200, "B1": 200})

if not db.get("DISABLED_SNO"):
    db.set("DISABLED_SNO", {"A": [], "B": [], "B1": []})

today_string = str(date.today())
if not db.get(str((today_string, 0, "A"))):
    initialise_db()





initialise_reminders()

#updater.start_polling()
updater.start_webhook(listen='0.0.0.0',
                      port=80,
                      url_path='TOKENS',
                      key='private.key',
                      cert='cert.pem',
                      webhook_url='https://206.189.149.120:80/TOKENS')


# 🔴 A
# 🟢 B
# 🟢 B1