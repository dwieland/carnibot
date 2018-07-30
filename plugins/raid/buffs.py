import enum

from plugins.raid.classes import ClassEnum


class BuffEnum(enum.Enum):
    ai = "Arcane Int"
    bs = "Battle Shout"
    cb = "Chaos Brand"
    mt = "Mystic Touch"
    pwf = "PW: Fortitude"


class_buffs = {
    ClassEnum.mage: BuffEnum.ai,
    ClassEnum.warrior: BuffEnum.bs,
    ClassEnum.demon_hunter: BuffEnum.cb,
    ClassEnum.monk: BuffEnum.mt,
    ClassEnum.priest: BuffEnum.pwf
}
