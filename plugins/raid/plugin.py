import itertools
from datetime import datetime

import dateutil.parser
from disco.bot import Plugin
from disco.gateway.events import MessageReactionAdd, MessageCreate
from disco.types import Message, Channel, Guild, GuildMember
from disco.util.snowflake import to_snowflake
from sqlalchemy import create_engine, exists
from sqlalchemy.orm import sessionmaker

from plugins.raid.classes import ClassEnum
from plugins.raid.db import Base
from plugins.raid.db.raid import Raid
from plugins.raid.db.raid_user_reaction import RaidUserReaction, ReactionEnum, reaction_to_icon
from plugins.raid.roles import RoleEnum


class RaidPlugin(Plugin):
    def __init__(self, bot, config):
        super().__init__(bot, config)
        self.session = None
        self.raid_channel_id = to_snowflake("472081810499829768")
        self.__raid_channel: Channel = None

    @property
    def raid_channel(self):
        if self.__raid_channel is None:
            self.__raid_channel = self.bot.client.api.channels_get(self.raid_channel_id)
        return self.__raid_channel

    def load(self, ctx):
        super().load(ctx)
        engine = create_engine("sqlite:///raid.db")
        Base.metadata.create_all(engine)
        session_maker = sessionmaker()
        session_maker.configure(bind=engine)
        self.session = session_maker()

    def unload(self, ctx):
        super().unload(ctx)
        self.session.commit()

    @Plugin.schedule(interval=5, init=False, repeat=False)
    def on_cleanup(self):
        raid_messages = []
        for batch in self.raid_channel.messages_iter(bulk=True):
            unwanted_messages = []
            for message in batch:
                if not self.session.query(exists().where(Raid.message_id == message.id)).scalar():
                    unwanted_messages.append(message)
                else:
                    raid_messages.append(message)
            if len(unwanted_messages) > 0:
                self.raid_channel.delete_messages(unwanted_messages)
        for raid_message in raid_messages:
            for reaction in raid_message.reactions:
                for reactor in raid_message.get_reactors(reaction.emoji):
                    if reactor == self.bot.client.state.me:
                        continue
                    self._on_raid_channel_reaction(raid_message.id, reactor.id, datetime.utcnow(), reaction.emoji)
                    raid_message.delete_reaction(reaction.emoji, reactor)
        self.session.commit()

    @Plugin.command("create", parser=True)
    @Plugin.parser.add_argument("at", type=dateutil.parser.parse)
    def on_create_command(self, _, args):
        self._create_raid(args.at)

    @Plugin.listen("MessageCreate")
    def on_message_create(self, event: MessageCreate):
        msg: Message = event.message
        if msg.channel_id == self.raid_channel_id:
            if msg.author != self.bot.client.state.me:
                msg.delete()

    @Plugin.listen("MessageReactionAdd")
    def on_message_reaction_add(self, event: MessageReactionAdd):
        if event.channel_id == self.raid_channel_id:
            if event.user_id != self.bot.client.state.me.id:
                self._on_raid_channel_reaction(event.message_id, event.user_id, datetime.utcnow(), event.emoji)
                event.delete()

    def _on_raid_channel_reaction(self, message_id, user_id, at, emoji):
        if emoji.name == "👍":
            self._accept_raid_invite(message_id, user_id, at)
        elif emoji.name == "👎":
            self._decline_raid_invite(message_id, user_id, at)
        self._update_raid_message(message_id)

    def _create_raid(self, at):
        raid_msg = self._create_placeholder_message()
        raid = Raid(date=at, message_id=raid_msg.id)
        self.session.add(raid)
        self.session.commit()
        self._update_raid_message(raid.message_id)

    def _create_placeholder_message(self):
        channel: Channel = self.bot.client.state.channels[self.raid_channel_id]
        msg = channel.send_message("Placeholder. Raid will appear shortly.")
        msg.add_reaction("🤖")
        return msg

    def _update_raid_message(self, raid_message_id):
        raid = self._expect_raid_by_message_id(raid_message_id)
        roster = self._get_roster_by_raid_and_guild(raid, self.raid_channel.guild)
        self.session.commit()

        raid_msg: Message = self.raid_channel.get_message(raid.message_id)
        raid_msg.edit(self._render_raid(raid, roster))

    def _accept_raid_invite(self, message_id, user_id, at):
        self._set_raid_invite_reaction(message_id, user_id, at, ReactionEnum.accepted)
        self.session.commit()

    def _decline_raid_invite(self, message_id, user_id, at):
        self._set_raid_invite_reaction(message_id, user_id, at, ReactionEnum.declined)
        self.session.commit()

    def _set_raid_invite_reaction(self, message_id, user_id, at, reaction, reason=None):
        raid = self._expect_raid_by_message_id(message_id)
        reaction = RaidUserReaction(
            raid_id=raid.id,
            user_id=user_id,
            at=at,
            reaction=reaction,
            reason=reason
        )
        self.session.add(reaction)

    @staticmethod
    def _is_raider(member: GuildMember):
        guild: Guild = member.guild
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

    @staticmethod
    def _count_if(iterable, condition):
        return sum(1 for _ in filter(condition, iterable))

    def _render_raid(self, raid, roster):
        total_accepted = self._count_if(roster.values(), lambda x: x["reaction"] == ReactionEnum.accepted)
        total_declined = self._count_if(roster.values(), lambda x: x["reaction"] == ReactionEnum.declined)
        total_unknown = self._count_if(roster.values(), lambda x: x["reaction"] == ReactionEnum.nothing)

        text_lines = []
        for role, role_group in self._grouped_by(roster.values(), lambda r: r["role"]):
            role_group = list(role_group)
            role_accepted = self._count_if(role_group, lambda r: r["reaction"] == ReactionEnum.accepted)
            role_declined = self._count_if(role_group, lambda r: r["reaction"] == ReactionEnum.declined)
            text_lines.append("")
            text_lines.append("{} (+{} -{}):".format(role.value, role_accepted, role_declined))
            for reaction, reaction_group in self._grouped_by(role_group, lambda r: r["reaction"]):
                text_lines.append("{}  {}".format(
                    reaction_to_icon[reaction],
                    ", ".join(raider["name"] for raider in reaction_group)
                ))

        return """```diff
Raid ID: {}
   Start: {}
+  Accepted: {}
-  Declined: {}
   Unknown: {}
{}
```""".format(raid.id, raid.date, total_accepted, total_declined, total_unknown, "\n".join(text_lines))

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
                print("Reaction from non-member user found: {}".format(reaction.user_id))
                continue
            raider = roster.setdefault(member.id, {
                "name": member.name,
                "class": self._get_class(member),
                "role": self._get_role(member)
            })
            raider["reaction"] = reaction.reaction
            raider["reaction_time"] = str(reaction.at)

        return roster

    def _expect_raid_by_message_id(self, message_id):
        return self.session.query(Raid).filter_by(message_id=message_id).one()

    def _get_all_reactions_by_raid_id(self, raid_id):
        return self.session\
            .query(RaidUserReaction)\
            .filter_by(raid_id=raid_id)\
            .order_by(RaidUserReaction.at)\
            .all()
