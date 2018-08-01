import enum

from sqlalchemy import Integer, Column, String, Enum, DateTime

from plugins.raid.db import Base


class ReactionEnum(enum.Enum):
    accepted = "Accepted"
    delayed = "Delayed"
    declined = "Declined"
    nothing = "Unknown"

    def __lt__(self, other):
        order = {
            ReactionEnum.accepted: 1,
            ReactionEnum.delayed: 2,
            ReactionEnum.declined: 3,
            ReactionEnum.nothing: 4
        }
        return order[self] < order[other]


class RaidUserReaction(Base):
    __tablename__ = "RAID_USER_REACTION"

    raid_id = Column(Integer, primary_key=True)
    user_id = Column(String(32), primary_key=True)
    at = Column(DateTime, primary_key=True)
    reaction = Column(String(32))
    reason = Column(String(1000))


reaction_to_icon = {
    ReactionEnum.accepted: "+",
    ReactionEnum.delayed: "!",
    ReactionEnum.declined: "-",
    ReactionEnum.nothing: " "
}
