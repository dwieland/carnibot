import enum
import itertools
import os
from datetime import datetime

from dateutil import parser
from discord import Member
from discord.ext.commands import Bot, Context
from sqlalchemy import Column, DateTime, Enum, String, create_engine, Integer, func, and_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class ClassEnum(enum.Enum):
    death_knight = "Death Knight"
    druid = "Druid"
    demon_hunter = "Demon Hunter"
    hunter = "Hunter"
    mage = "Mage"
    monk = "Monk"
    paladin = "Paladin"
    priest = "Priest"
    rogue = "Rogue"
    shaman = "Shaman"
    warlock = "Warlock"
    warrior = "Warrior"
    unknown = "Unknown"


class RoleEnum(enum.Enum):
    tank = "Tank"
    heal = "Heal"
    dd = "DD"
    unknown = "Unknown"

    def __lt__(self, other):
        order = {
            self.tank: 0,
            self.heal: 1,
            self.dd: 2,
            self.unknown: 3
        }
        return order[self] < order[other]


class ReactionEnum(enum.IntEnum):
    accepted = 1
    declined = 2
    nothing = 8


class Raid(Base):
    __tablename__ = "RAID"

    id = Column(Integer, primary_key=True)
    date = Column(DateTime, unique=True)
    message_id = Column(String)


class RaidUserReaction(Base):
    __tablename__ = "RAID_USER_REACTION"

    raid_id = Column(Integer, primary_key=True)
    user_id = Column(String, primary_key=True)
    at = Column(DateTime, primary_key=True)
    reaction = Column(Enum(ReactionEnum))
    reason = Column(String)


reaction_to_icon = {
    ReactionEnum.nothing: " ",
    ReactionEnum.accepted: "+",
    ReactionEnum.declined: "-"
}
raid_buffs = {
    "Arcane Intellect": ClassEnum.mage,
    "Battle Shout": ClassEnum.warrior,
    "Chaos Brand": ClassEnum.demon_hunter,
    "Mystic Touch": ClassEnum.monk,
    "Power Word: Fortitude": ClassEnum.priest
}


class Delimiter:
    pass


def render_row(row_template, delimiter, row):
    if isinstance(row, Delimiter):
        return delimiter
    else:
        return row_template.format(*row)


def render_table(table, columns):
    column_widths = [0] * (columns - 1)
    for row in table:
        if isinstance(row, Delimiter):
            continue
        for column in range(1, columns):
            column_widths[column - 1] = max(column_widths[column - 1], len(row[column]))
    header = "  ┌" + "┬".join("─" * (w+2) for w in column_widths) + "┐"
    footer = "  └" + "┴".join("─" * (w+2) for w in column_widths) + "┘"
    delim = "  ├" + "┼".join("─" * (w+2) for w in column_widths) + "┤"
    row_tmpl = "{} │ " + " │ ".join("{{: <{}}}".format(w) for w in column_widths) + " │"

    return "{}\n{}\n{}\n".format(
        header,
        "\n".join(render_row(row_tmpl, delim, row) for row in table),
        footer
    )


def grouped_by(iterable, key, reverse=False):
    sorted_list = sorted(iterable, key=key, reverse=reverse)
    return itertools.groupby(sorted_list, key)


def render_raid(raid_id, timestamp, roster):
    accepted = sum(1 for _ in filter(lambda x: x["reaction"] == ReactionEnum.accepted, roster.values()))
    declined = sum(1 for _ in filter(lambda x: x["reaction"] == ReactionEnum.declined, roster.values()))
    unknown = sum(1 for _ in filter(lambda x: x["reaction"] == ReactionEnum.nothing, roster.values()))

    table = []
    for role, role_group in grouped_by(roster.values(), lambda r: r["role"]):
        for reaction, reaction_group in grouped_by(role_group, lambda r: r["reaction"]):
            reaction_group = list(reaction_group)
            table.append([
                reaction_to_icon[reaction],
                "{} ({})".format(role.value, len(reaction_group)),
                ", ".join(raider["name"] for raider in reaction_group)
            ])
        table.append(Delimiter())

    buffs = {
        True: [],
        False: []
    }
    for buff, class_ in raid_buffs.items():
        buff_available = any(
            map(lambda x: x["class"] == class_ and x["reaction"] == ReactionEnum.accepted, roster.values())
        )
        buffs[buff_available].append(buff)

    table.append([
        "+",
        "Buffs ({})".format(len(buffs[True])),
        ", ".join(buffs[True])
    ])

    table.append([
        "-",
        "Buffs ({})".format(len(buffs[False])),
        ", ".join(buffs[False])
    ])

    return """
   Raid ID: {}   Start: {}
+  Accepted: {}
-  Declined: {}
   Unknown: {}
{}
""".format(raid_id, timestamp, accepted, declined, unknown, render_table(table, 3))


def is_raider(member: Member):
    for role in member.roles:
        if role.name in ("Mainraider", "Testraider"):
            return True
    return False


def get_class(member: Member):
    for role in member.roles:
        if role.name in [class_.value for class_ in ClassEnum]:
            return ClassEnum(role.name)
    return ClassEnum.unknown


def get_role(member: Member):
    for role in member.roles:
        if role.name in [role.value for role in RoleEnum]:
            return RoleEnum(role.name)
    return RoleEnum.unknown


def get_nickname(member: Member):
    return member.nick or member.name


def associate_by(iterable, key):
    associated = {}
    for el in iterable:
        associated[key(el)] = el
    return associated


def create_carni_bot(bot, session):

    class CarniBot:
        @staticmethod
        def run(token):
            bot.run(token)

        @staticmethod
        @bot.event
        async def on_ready():
            print('Logged in as')
            print(bot.user.name)
            print(bot.user.id)
            print('------')

        @staticmethod
        @bot.event
        async def on_command_error(exc, ctx):
            await bot.send_message(ctx.message.channel, str(exc))

        @staticmethod
        @bot.command(pass_context=True)
        async def create(ctx: Context, at: str):
            """foo bar documentation"""
            at = parser.parse(at)

            raid = Raid(date=at)
            session.add(raid)
            session.commit()

            await bot.say("Created new raid with id `{}`".format(raid.id))

        @staticmethod
        @bot.command(pass_context=True)
        async def next(ctx: Context):
            raid = session.query(Raid).order_by(Raid.date).filter(Raid.date > datetime.now()).first()
            if raid is None:
                session.commit()
                await bot.say("No raid scheduled.")
                return

            roster = {}
            for raider in filter(is_raider, ctx.message.channel.server.members):
                roster[raider.id] = {
                    "name": get_nickname(raider),
                    "class": get_class(raider),
                    "role": get_role(raider),
                    "reaction": ReactionEnum.nothing,
                }

            reactions = session.query(RaidUserReaction).filter_by(raid_id=raid.id).order_by(RaidUserReaction.at).all()
            for reaction in reactions:
                member = ctx.message.channel.server.get_member(reaction.user_id)
                if member is None:
                    continue
                raider = roster.setdefault(member.id, {
                    "name": get_nickname(member),
                    "class": get_class(member),
                    "role": get_role(member)
                })
                raider["reaction"] = reaction.reaction
                raider["reaction_time"] = str(reaction.at)

            text = "```diff\n{}\n```".format(render_raid(raid.id, raid.date, roster))
            session.commit()
            await bot.say(text)

        @staticmethod
        @bot.command(pass_context=True)
        async def accept(ctx: Context, raid_id: int, *, reason: str = None):
            raid = session.query(Raid).filter_by(id=raid_id).first()
            if raid is None:
                session.commit()
                await bot.say("No raid with id {} found.".format(raid_id))
                return

            reaction = RaidUserReaction(
                raid_id=raid_id,
                user_id=ctx.message.author.id,
                at=ctx.message.timestamp,
                reaction=ReactionEnum.accepted,
                reason=reason
            )

            session.add(reaction)
            session.commit()
            await bot.say("Accepted raid with id {}.".format(raid_id))

        @staticmethod
        @bot.command(pass_context=True)
        async def decline(ctx: Context, raid_id: int, *, reason: str):
            raid = session.query(Raid).filter_by(id=raid_id).first()
            if raid is None:
                session.commit()
                await bot.say("No raid with id {} found.".format(raid_id))
                return

            reaction = RaidUserReaction(
                raid_id=raid_id,
                user_id=ctx.message.author.id,
                at=ctx.message.timestamp,
                reaction=ReactionEnum.declined,
                reason=reason
            )

            session.add(reaction)
            session.commit()
            await bot.say("Declined raid with id {}.".format(raid_id))

        @staticmethod
        @bot.command(pass_context=True)
        async def reasons(ctx: Context, raid_id: int):
            raid = session.query(Raid).filter_by(id=raid_id).first()
            if raid is None:
                session.commit()
                await bot.say("No raid with id {} found.".format(raid_id))
                return

            max_reaction_at = session.\
                query(
                    RaidUserReaction.raid_id,
                    RaidUserReaction.user_id,
                    func.max(RaidUserReaction.at).label("max_at")
                ).\
                select_from(RaidUserReaction).\
                filter_by(raid_id=raid.id).\
                group_by(RaidUserReaction.raid_id, RaidUserReaction.user_id).\
                subquery("max_reaction_at")

            # noinspection PyPep8
            last_reactions = session.\
                query(RaidUserReaction).\
                filter(and_(
                    RaidUserReaction.raid_id == max_reaction_at.c.raid_id,
                    RaidUserReaction.user_id == max_reaction_at.c.user_id,
                    RaidUserReaction.at == max_reaction_at.c.max_at,
                    RaidUserReaction.reason != None
                )).\
                order_by(RaidUserReaction.at).\
                all()

            session.commit()

            if len(last_reactions) == 0:
                await bot.say("Nobody has declined the raid invite.")
                return

            table = [[
                reaction_to_icon[reaction.reaction],
                get_nickname(ctx.message.channel.server.get_member(reaction.user_id)),
                str(reaction.at),
                reaction.reason or ""
            ] for reaction in last_reactions]

            await bot.say("```diff\n{}\n```".format(render_table(table, 4)))

        @staticmethod
        @bot.command(pass_context=True)
        async def log(ctx: Context, raid_id: int):
            raid = session.query(Raid).filter_by(id=raid_id).first()
            if raid is None:
                session.commit()
                await bot.say("No raid with id {} found.".format(raid_id))
                return

            reactions = session.\
                query(RaidUserReaction).\
                filter_by(raid_id=raid.id).\
                order_by(RaidUserReaction.at).\
                all()
            session.commit()

            table = [[
                reaction_to_icon[reaction.reaction],
                get_nickname(ctx.message.channel.server.get_member(reaction.user_id)),
                str(reaction.at),
                reaction.reason or ""
            ] for reaction in reactions]

            await bot.say("```diff\n{}\n```".format(render_table(table, 4)))

    return CarniBot()


def main():
    engine = create_engine("sqlite:///carnibot.db", echo=True)
    Base.metadata.create_all(engine)
    session_maker = sessionmaker()
    session_maker.configure(bind=engine)
    carni_bot = create_carni_bot(Bot(command_prefix="!"), session_maker())
    carni_bot.run(os.getenv("BOT_TOKEN"))


if __name__ == '__main__':
    main()
