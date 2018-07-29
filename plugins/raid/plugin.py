from datetime import datetime

import dateutil
from disco.bot import Plugin
from disco.bot.command import CommandEvent
from disco.gateway.events import MessageReactionAdd, MessageCreate
from disco.types import Message
from disco.types.base import snowflake
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from plugins.raid.db import Base
from plugins.raid.db.raid import Raid
from plugins.raid.db.raid_user_reaction import RaidUserReaction, ReactionEnum


class RaidPlugin(Plugin):
    def __init__(self, bot, config):
        super().__init__(bot, config)
        self.session = None
        self.raid_channel_id = snowflake("472081810499829768")

    def load(self, ctx):
        super().load(ctx)
        engine = create_engine("sqlite:///raid.db", echo=True)
        Base.metadata.create_all(engine)
        session_maker = sessionmaker()
        session_maker.configure(bind=engine)
        self.session = session_maker()

    def unload(self, ctx):
        super().unload(ctx)
        self.session.commit()

    @Plugin.command("create", parser=True)
    @Plugin.parser.add_argument("at", type=dateutil.parser.parse)
    def on_create_command(self, event: CommandEvent, args):
        event.msg.reply("[TBD] Created event at: {}".format(args.at))

    @Plugin.listen("MessageCreate")
    def on_message_create(self, event: MessageCreate):
        msg: Message = event.message
        if msg.channel_id == self.raid_channel_id:
            if msg.author != self.bot.client.state.me:
                msg.delete()

    @Plugin.listen("MessageReactionAdd")
    def on_message_reaction_add(self, event: MessageReactionAdd):
        if event.channel_id == self.raid_channel_id:
            if event.emoji.name == "👍":
                self._accept_raid_invite(event.message_id, event.user_id, datetime.utcnow())
            elif event.emoji.name == "👎":
                self._decline_raid_invite(event.message_id, event.user_id, datetime.utcnow())
            event.delete()

    def _accept_raid_invite(self, message_id, user_id, at):
        self._set_raid_invite_reaction(message_id, user_id, at, ReactionEnum.accepted)

    def _decline_raid_invite(self, message_id, user_id, at):
        self._set_raid_invite_reaction(message_id, user_id, at, ReactionEnum.declined)

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

    def _expect_raid_by_message_id(self, message_id):
        return self.session.query(Raid).filter_by(message_id=message_id).one()
