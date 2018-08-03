import functools
import itertools
from contextlib import contextmanager
from datetime import datetime, date, timedelta

import dateutil.parser
import dateutil.tz
import dateutil.utils
from colour import Color
from dateutil import rrule
from disco.bot import Plugin, Config
from disco.gateway.events import MessageReactionAdd, MessageCreate
from disco.types import Guild, GuildMember
from disco.util.snowflake import to_snowflake
from sqlalchemy import create_engine, exists
from sqlalchemy.orm import sessionmaker

from plugins.raid.calendar import Calendar
from plugins.raid.classes import ClassEnum
from plugins.raid.db.raid import Raid
from plugins.raid.db.raid_user_reaction import RaidUserReaction, ReactionEnum
from plugins.raid.render.renderer import Renderer
from plugins.raid.roles import RoleEnum


class RaidPluginConfig(Config):
    db_connect_str = "sqlite:///raid.db"
    bot_channel_id = "472469888158531585"
    raid_channel_id = "472081810499829768"
    locale = None
    timezone = "Europe/Berlin"
    calendar = {}


@Plugin.with_config(RaidPluginConfig)
class RaidPlugin(Plugin):

    def __init__(self, bot, config):
        super().__init__(bot, config)

        if self.config.locale:
            import locale
            locale.setlocale(locale.LC_TIME, self.config.locale)

        self.timezone = dateutil.tz.gettz(self.config.timezone)

        self.renderer = Renderer(self.timezone)
        self.bot_channel_id = to_snowflake(self.config.bot_channel_id)
        self.raid_channel_id = to_snowflake(self.config.raid_channel_id)
        self.bot_channel = None
        self.calendar_channel = None
        self.calendar = None

        engine = create_engine(self.config.db_connect_str)
        session_maker = sessionmaker()
        session_maker.configure(bind=engine)
        self.session = session_maker()

    @Plugin.listen("Ready")
    def on_ready(self, _):
        self.bot_channel = self.bot.client.api.channels_get(self.config.bot_channel_id)
        self.calendar_channel = self.bot.client.api.channels_get(self.config.raid_channel_id)
        self.calendar = Calendar(self.calendar_channel)
        self.register_schedule(self.cleanup, interval=60, repeat=True, init=True)
        self.register_schedule(self.remove_passed_raids, interval=60, repeat=True, init=True)

    def unload(self, ctx):
        super().unload(ctx)
        self.session.commit()

    @Plugin.command("create", parser=True)
    @Plugin.parser.add_argument("-h", "--help", action="store_true")
    @Plugin.parser.add_argument("at", type=str, nargs="?")
    @Plugin.parser.add_argument("--color", type=Color)
    @Plugin.parser.add_argument("--freq", type=str)
    @Plugin.parser.add_argument("--count", type=int, default=1)
    def on_create_command(self, event, args):
        def get_tz(tzname, tzoffset):
            if tzname:
                return dateutil.tz.gettz(tzname)
            else:
                return tzoffset

        if event.msg.channel.id != self.bot_channel.id:
            return

        if args.help or not args.at:
            event.msg.reply(
                "**Create a single or recurring raid.**\n\n"
                "Usage: `!create <datetime> [--color <color>] [--freq daily|weekly|monthly [--count <count>]]`"
            )
            return

        at = dateutil.parser.parse(args.at, tzinfos=get_tz)
        at = dateutil.utils.default_tzinfo(at, self.timezone)
        at = at.astimezone(dateutil.tz.UTC)
        at = at.replace(tzinfo=None)

        if args.freq:
            freq_map = {
                "monthly": rrule.MONTHLY,
                "weekly": rrule.WEEKLY,
                "daily": rrule.DAILY
            }
            occurrences = rrule.rrule(freq=freq_map[args.freq], count=args.count, dtstart=at)
        else:
            occurrences = (at,)

        for occurrence in occurrences:
            self._create_raid(occurrence, int(args.color.hex_l[1:], 16))

    @Plugin.command("delete", parser=True)
    @Plugin.parser.add_argument("-h", "--help", action="store_true")
    @Plugin.parser.add_argument("raid_ids", type=int, nargs="*")
    def on_delete_command(self, event, args):
        if event.msg.channel.id != self.bot_channel.id:
            return

        if args.help or not args.raid_ids:
            event.msg.reply(
                "**Delete one or more raids.**\n\n"
                "Usage: `!delete <raid_id> [<raid_id>...]`"
            )
            return

        for raid_id in args.raid_ids:
            self._delete_raid(raid_id)

    @Plugin.listen("MessageCreate")
    def on_message_create(self, event: MessageCreate):
        msg = event.message
        if msg.channel_id == self.calendar_channel.id:
            if msg.author != self.bot.client.state.me:
                msg.delete()

    @Plugin.listen("MessageReactionAdd")
    def on_message_reaction_add(self, event: MessageReactionAdd):
        if event.channel_id == self.calendar_channel.id:
            if event.user_id != self.bot.client.state.me.id:
                self._on_raid_channel_reaction(event.message_id, event.user_id, datetime.utcnow(), event.emoji)
                event.delete()

    @staticmethod
    @contextmanager
    def _transaction(session):
        try:
            yield
            session.commit()
        except Exception as e:
            session.rollback()
            raise e

    def format_datetime(self, dt):
        return dt\
            .replace(tzinfo=dateutil.tz.UTC)\
            .astimezone(self.timezone)\
            .strftime("%A %H:%M - %x")

    def cleanup(self):
        with self._transaction(self.session):
            raid_messages = []
            for batch in self.calendar_channel.messages_iter(bulk=True):
                unwanted_messages = []
                for message in batch:
                    if not self.session.query(exists().where(Raid.message_id == message.id)).scalar():
                        unwanted_messages.append(message)
                    else:
                        raid_messages.append(message)
                if len(unwanted_messages) > 0:
                    self.calendar_channel.delete_messages(unwanted_messages)
            for raid_message in raid_messages:
                for reaction in raid_message.reactions:
                    if reaction.emoji.name == "🤖":
                        continue
                    for reactor in raid_message.get_reactors(reaction.emoji):
                        self._on_raid_channel_reaction(raid_message.id, reactor.id, datetime.utcnow(), reaction.emoji)
                        raid_message.delete_reaction(reaction.emoji, reactor)

    def remove_passed_raids(self):
        with self._transaction(self.session):
            raids_to_remove = self.session \
                .query(Raid) \
                .filter(
                    Raid.date < datetime.utcnow() - timedelta(hours=8),
                    Raid.message_id != None
                ) \
                .all()
            self.calendar_channel.delete_messages([raid.message_id for raid in raids_to_remove])
            for raid in raids_to_remove:
                self.bot_channel.send_message("Raid removed from calendar: {}".format(self.format_datetime(raid.date)))
                raid.message_id = None

    def _on_raid_channel_reaction(self, message_id, user_id, at, emoji):
        emoji_to_method = {
            "👍": functools.partial(self._set_raid_invite_reaction, reaction=ReactionEnum.accepted),
            "👎": functools.partial(self._set_raid_invite_reaction, reaction=ReactionEnum.declined),
            "🕧": functools.partial(self._set_raid_invite_reaction, reaction=ReactionEnum.delayed, reason="+30m"),
            "🕐": functools.partial(self._set_raid_invite_reaction, reaction=ReactionEnum.delayed, reason="+1h"),
            "🕜": functools.partial(self._set_raid_invite_reaction, reaction=ReactionEnum.delayed, reason="+1h30m"),
            "🕑": functools.partial(self._set_raid_invite_reaction, reaction=ReactionEnum.delayed, reason="+2h"),
            "🕝": functools.partial(self._set_raid_invite_reaction, reaction=ReactionEnum.delayed, reason="+2h30m"),
            "🕒": functools.partial(self._set_raid_invite_reaction, reaction=ReactionEnum.delayed, reason="+3h"),
            "🕞": functools.partial(self._set_raid_invite_reaction, reaction=ReactionEnum.delayed, reason="+3h30m"),
            "🕓": functools.partial(self._set_raid_invite_reaction, reaction=ReactionEnum.delayed, reason="+4h"),
        }

        with self._transaction(self.session):
            raid = self._expect_raid_by_message_id(message_id)

            if emoji.name in emoji_to_method:
                emoji_to_method[emoji.name](raid=raid, user_id=user_id, at=at)
                self._update_calendar_message(raid)

    def _create_raid(self, at, color):
        with self._transaction(self.session):
            if at < datetime.utcnow():
                self.bot_channel.send_message("Can't create raids in the past.")
                return

            if self.session.query(Raid).filter_by(date=at).count() > 0:
                self.bot_channel.send_message("Raid already exists.")
                return

            raid = Raid(date=at, color=color)
            self.session.add(raid)
            self._add_raid_to_calendar(raid)
            self.bot_channel.send_message("Raid created: {}.".format(self.format_datetime(at)))

    def _delete_raid(self, raid_id):
        with self._transaction(self.session):
            raid = self.session.query(Raid).filter_by(id=raid_id).one_or_none()
            if raid:
                self._delete_calendar_message(raid)
                self.session.delete(raid)
                self.bot_channel.send_message("Raid deleted: {}.".format(self.format_datetime(raid.date)))
            else:
                self.bot_channel.send_message("Raid not found.")

    def _add_raid_to_calendar(self, raid):
        if raid.date.date() > date.today() + timedelta(days=14):
            return

        raid.message_id = self._create_calendar_message(raid).id
        self._reorder_calendar(raid.date)

    def _reorder_calendar(self, after):
        raids_to_reorder = self.session \
            .query(Raid) \
            .filter(Raid.date > after, Raid.message_id != None) \
            .order_by(Raid.date) \
            .all()

        if raids_to_reorder:
            self.calendar_channel.delete_messages([r.message_id for r in raids_to_reorder])

            for raid in raids_to_reorder:
                raid.message_id = self._create_calendar_message(raid).id

    def _create_calendar_message(self, raid):
        roster = self._get_roster_by_raid_and_guild(raid, self.calendar_channel.guild)
        return self.calendar_channel.send_message(embed=self.renderer.render_raid(raid, roster))

    def _update_calendar_message(self, raid):
        if raid.message_id:
            roster = self._get_roster_by_raid_and_guild(raid, self.calendar_channel.guild)
            raid_msg = self.calendar_channel.get_message(raid.message_id)
            raid_msg.edit(content=" ", embed=self.renderer.render_raid(raid, roster))

    def _delete_calendar_message(self, raid):
        if raid.message_id:
            self.calendar_channel.get_message(raid.message_id).delete()

    def _set_raid_invite_reaction(self, raid, user_id, at, reaction, reason=None):
        user_reaction = RaidUserReaction(
            raid_id=raid.id,
            user_id=user_id,
            at=at,
            reaction=reaction.value,
            reason=reason
        )
        self.session.add(user_reaction)

    @staticmethod
    def _is_raider(member: GuildMember):
        guild = member.guild
        for role_id in member.roles:
            if guild.roles[role_id].name in ("Mainraider", "Testraider"):
                return True
        return False

    @staticmethod
    def _get_class(member: GuildMember):
        for role_id in member.roles:
            role_name = member.guild.roles[role_id].name
            if role_name in [class_.value for class_ in ClassEnum]:
                return ClassEnum(role_name)
        return ClassEnum.unknown

    @staticmethod
    def _get_role(member: GuildMember):
        for role_id in member.roles:
            role_name = member.guild.roles[role_id].name
            if role_name in [role.value for role in RoleEnum]:
                return RoleEnum(role_name)
        return RoleEnum.unknown

    @staticmethod
    def _grouped_by(iterable, key, reverse=False):
        sorted_list = sorted(iterable, key=key, reverse=reverse)
        return itertools.groupby(sorted_list, key)

    def _get_roster_by_raid_and_guild(self, raid, guild: Guild):
        roster = {}

        for member in guild.members.values():
            if self._is_raider(member):
                roster[member.id] = {
                    "name": member.name,
                    "class": self._get_class(member),
                    "role": self._get_role(member),
                    "reaction": ReactionEnum.nothing
                }

        reactions = self._get_all_reactions_by_raid_id(raid.id)
        for reaction in reactions:
            member = guild.members.get(to_snowflake(reaction.user_id))
            if member is None:
                continue
            raider = roster.setdefault(member.id, {
                "name": member.name,
                "class": self._get_class(member),
                "role": self._get_role(member)
            })
            raider["reaction"] = ReactionEnum(reaction.reaction)
            raider["reaction_time"] = str(reaction.at)
            raider["reason"] = reaction.reason

        return roster

    def _expect_raid_by_message_id(self, message_id):
        return self.session.query(Raid).filter_by(message_id=message_id).one()

    def _get_all_reactions_by_raid_id(self, raid_id):
        return self.session \
            .query(RaidUserReaction) \
            .filter_by(raid_id=raid_id) \
            .order_by(RaidUserReaction.at) \
            .all()
