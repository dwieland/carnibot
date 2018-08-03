from sqlalchemy import Column, Integer, DateTime, String

from plugins.raid.db import Base


class Raid(Base):
    __tablename__ = "RAID"

    id = Column(Integer, primary_key=True)
    date = Column(DateTime, unique=True)
    message_id = Column(String(32))
    color = Column(Integer)
