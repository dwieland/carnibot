import enum


class RoleEnum(enum.Enum):
    tank = "Tank"
    heal = "Heal"
    melee = "Melee DD"
    ranged = "Range DD"
    unknown = "Unknown"

    def __lt__(self, other):
        order = {
            self.tank: 0,
            self.heal: 1,
            self.melee: 2,
            self.ranged: 3,
            self.unknown: 4
        }
        return order[self] < order[other]


role_to_plural = {
    RoleEnum.tank: "Tanks",
    RoleEnum.heal: "Healer",
    RoleEnum.melee: "Melee DDs",
    RoleEnum.ranged: "Ranged DDs",
    RoleEnum.unknown: "Unknown"
}
