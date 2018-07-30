import enum

from sqlalchemy import Integer, Column, String, Enum, DateTime

from plugins.raid.db import Base


class ReactionEnum(enum.IntEnum):
    accepted = 1
    declined = 2
    nothing = 8


class RaidUserReaction(Base):
    __tablename__ = "RAID_USER_REACTION"

    raid_id = Column(Integer, primary_key=True)
    user_id = Column(String(32), primary_key=True)
    at = Column(DateTime, primary_key=True)
    reaction = Column(Enum(ReactionEnum))
    reason = Column(String(1000))


reaction_to_icon = {
    ReactionEnum.nothing: " ",
    ReactionEnum.accepted: "+",
    ReactionEnum.declined: "-"
}
