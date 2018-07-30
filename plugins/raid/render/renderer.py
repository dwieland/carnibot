from disco.types.message import MessageEmbedField, MessageEmbed

from plugins.raid.buffs import class_buffs, BuffEnum
from plugins.raid.db.raid_user_reaction import ReactionEnum, reaction_to_icon
from plugins.raid.render.bold import Bold
from plugins.raid.render.diff import Diff
from plugins.raid.roles import role_to_plural, RoleEnum


class Renderer:

    def render_attendance(self, roster):
        total_accepted = self._count_if(roster.values(), lambda x: x["reaction"] == ReactionEnum.accepted)
        total_declined = self._count_if(roster.values(), lambda x: x["reaction"] == ReactionEnum.declined)
        total_unknown = self._count_if(roster.values(), lambda x: x["reaction"] == ReactionEnum.nothing)

        return MessageEmbedField(
            name="Attendance",
            value=Diff("+ Accepted: {}\n- Declined: {}\n  Unknown: {}".format(
                total_accepted,
                total_declined,
                total_unknown
            )),
            inline=True
        )

    @staticmethod
    def render_buffs(roster):
        buffs = {buff: "-" for buff in BuffEnum}
        for raider in roster.values():
            if raider["reaction"] == ReactionEnum.accepted and raider["class"] in class_buffs:
                buffs[class_buffs[raider["class"]]] = "+"

        return MessageEmbedField(
            name="Raid Buffs",
            value=Diff("\n".join(
                "{} {}".format(got_it, buff.value)
                for buff, got_it in sorted(buffs.items(), key=lambda i: (i[1], i[0].value))
            )),
            inline=True
        )

    @staticmethod
    def render_role(roster, role):
        role_roster = list(filter(lambda x: x["role"] == role, roster.values()))
        if len(role_roster) == 0:
            return

        role_roster = sorted(role_roster, key=lambda x: (x["reaction"], x["name"]))

        return MessageEmbedField(
            name=Bold(role_to_plural[role]),
            value=Diff("\n".join("{} {}".format(reaction_to_icon[x["reaction"]], x["name"]) for x in role_roster)),
            inline=True
        )

    def render_raid(self, raid, roster):
        weekday_to_url = {
            0: "https://s3.eu-central-1.amazonaws.com/weekday-thumbnails/icons8-montag-50.png",
            1: "https://s3.eu-central-1.amazonaws.com/weekday-thumbnails/icons8-dienstag-50.png",
            2: "https://s3.eu-central-1.amazonaws.com/weekday-thumbnails/icons8-mittwoch-50.png",
            3: "https://s3.eu-central-1.amazonaws.com/weekday-thumbnails/icons8-donnerstag-50.png",
            4: "https://s3.eu-central-1.amazonaws.com/weekday-thumbnails/icons8-freitag-50.png",
            5: "https://s3.eu-central-1.amazonaws.com/weekday-thumbnails/icons8-samstag-50.png",
            6: "https://s3.eu-central-1.amazonaws.com/weekday-thumbnails/icons8-sonntag-50.png",
        }
        embed = MessageEmbed(
            title=raid.date.strftime("%A %H:%M - %x"),
            thumbnail={
                "url": weekday_to_url[raid.date.weekday()]
            }
        )
        embed.fields.append(self.render_attendance(roster))
        embed.fields.append(self.render_buffs(roster))
        embed.fields.extend([self.render_role(roster, role) for role in RoleEnum])
        for _ in range(embed.fields.count(None)):
            embed.fields.remove(None)
        return embed

    @staticmethod
    def _count_if(iterable, condition):
        return sum(1 for _ in filter(condition, iterable))
