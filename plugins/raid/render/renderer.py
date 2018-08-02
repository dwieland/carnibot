import dateutil.utils
from dateutil import tz
from disco.types.message import MessageEmbedField, MessageEmbed

from plugins.raid.buffs import class_buffs, BuffEnum
from plugins.raid.db.raid_user_reaction import ReactionEnum, reaction_to_icon
from plugins.raid.render.bold import Bold
from plugins.raid.render.diff import Diff
from plugins.raid.roles import role_to_plural, RoleEnum


class Renderer:

    def __init__(self, timezone):
        self.timezone = timezone

    def render_attendance(self, roster):
        totals = [
            (reaction, self._count_if(roster.values(), lambda x: x["reaction"] == reaction))
                for reaction in ReactionEnum
        ]

        return MessageEmbedField(
            name="Attendance",
            value=Diff("\n".join("{} {}: {}".format(
                reaction_to_icon[reaction],
                reaction.value,
                total
            ) for (reaction, total) in totals)),
            inline=True
        )

    @staticmethod
    def render_buffs(roster):
        buffs = {buff: ReactionEnum.declined for buff in BuffEnum}
        for raider in roster.values():
            if raider["class"] in class_buffs:
                cur_reaction = buffs[class_buffs[raider["class"]]]
                buffs[class_buffs[raider["class"]]] = min(cur_reaction, raider["reaction"])

        return MessageEmbedField(
            name="Raid Buffs",
            value=Diff("\n".join(
                "{} {}".format(reaction_to_icon[reaction], buff.value)
                for buff, reaction in sorted(buffs.items(), key=lambda i: (i[1], i[0].value))
            )),
            inline=True
        )

    @staticmethod
    def render_raider(raider):
        if raider["reaction"] == ReactionEnum.delayed and raider.get("reason"):
            return "{} {} ({})".format(
                reaction_to_icon[raider["reaction"]],
                raider["name"],
                raider["reason"]
            )
        else:
            return "{} {}".format(
                reaction_to_icon[raider["reaction"]],
                raider["name"]
            )

    def render_role(self, roster, role):
        role_roster = list(filter(lambda x: x["role"] == role, roster.values()))
        if len(role_roster) == 0:
            return

        role_roster = sorted(role_roster, key=lambda x: (x["reaction"], x["name"]))

        return MessageEmbedField(
            name=Bold(role_to_plural[role]),
            value=Diff("\n".join(self.render_raider(raider) for raider in role_roster)),
            inline=True
        )

    def render_raid(self, raid, roster):
        pic_url_template = "https://s3.eu-central-1.amazonaws.com/weekday-thumbnails/icons8-{}-{}.png"
        pic_width = 100
        weekday_to_url = {
            0: pic_url_template.format("montag", pic_width),
            1: pic_url_template.format("dienstag", pic_width),
            2: pic_url_template.format("mittwoch", pic_width),
            3: pic_url_template.format("donnerstag", pic_width),
            4: pic_url_template.format("freitag", pic_width),
            5: pic_url_template.format("samstag", pic_width),
            6: pic_url_template.format("sonntag", pic_width),
        }
        at = dateutil.utils.default_tzinfo(raid.date, tz.UTC)
        embed = MessageEmbed(
            title=at.astimezone(self.timezone).strftime("%A %H:%M - %x"),
            description="Raid ID: {}".format(raid.id),
            thumbnail={
                "url": weekday_to_url[raid.date.weekday()]
            }
        )
        embed.fields.append(self.render_attendance(roster))
        embed.fields.append(self.render_buffs(roster))
        for role in RoleEnum:
            embed.fields.append(self.render_role(roster, role))
        for _ in range(embed.fields.count(None)):
            embed.fields.remove(None)
        return embed

    @staticmethod
    def _count_if(iterable, condition):
        return sum(1 for _ in filter(condition, iterable))
