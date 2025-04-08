import random
import re
import common

D10000_LIST_PATH = "Data/d10000_list.txt"
ACTIVE_EFFECTS_PATH = "Data/active_effects.json"

def parse_diceroll(dice_roll) -> tuple[int, int, int] | None:
    try:
        if dice_roll[0].startswith("d"):
            dice_roll[0] = f"1{dice_roll[0]}"

    except IndexError:
        return None

    roll_data = re.split(r"d|(\+)|(-)", "".join(dice_roll), flags=re.IGNORECASE)
    roll_data = [x for x in roll_data if x is not None]

    try:
        num_dice = int(roll_data[0])
        num_faces = int(roll_data[1])

    except (IndexError, ValueError):
        return None

    if num_faces < 1 or num_dice < 1:
        return None

    modifier = 0

    try:
        if roll_data[2] == '+':
            modifier = int(roll_data[3])

        if roll_data[2] == '-':
            modifier = -int(roll_data[3])

    except (IndexError, ValueError) as e:
        if len(roll_data) != 2 or e is ValueError:
            return None

    return num_dice, num_faces, modifier

def get_coc_roll() -> str:
    roll_string = ""
    for stat in ["STR", "CON", "DEX", "APP", "POW"]:
        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        d3 = random.randint(1, 6)

        roll_string = "\n".join([roll_string, f"{stat}: {5*(d1 + d2 + d3)}"])

    for stat in ["SIZ", "INT", "EDU", "LUC"]:
        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)

        roll_string = "\n".join([roll_string, f"{stat}: {5*(d1 + d2 + 6)}"])

    roll_string = "\n".join([roll_string, f"Bonus: {random.randint(1, 10)}"])
    return roll_string

def get_dnd_roll() -> str:
    roll_string = ""
    for stat in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
        four_rolls = [random.randint(1, 6) for _ in range(4)]
        del four_rolls[four_rolls.index(min(four_rolls))]
        roll_string = "\n".join([roll_string, f"{stat}: {sum(four_rolls)}"])

    return roll_string

def get_mythras_roll() -> str:
    roll_string = ""
    for stat in ["STR", "CON", "DEX", "POW", "CHA"]:
        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        d3 = random.randint(1, 6)

        roll_string = "\n".join([roll_string, f"{stat}: {d1 + d2 + d3}"])

    for stat in ["INT", "SIZ"]:
        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)

        roll_string = "\n".join([roll_string, f"{stat}: {d1 + d2 + 6}"])

    return roll_string

def get_d10000_roll(username) -> str:
    try:
        with open(D10000_LIST_PATH, 'r', encoding='utf-8') as f:
            effects = f.readlines()
    except FileNotFoundError:
        return "The d10000 file couldn't be found!"

    chosen_effect = random.choice(effects).strip()

    effects_dict = common.try_read_json(ACTIVE_EFFECTS_PATH, dict())

    try:
        effects_dict[username].append(chosen_effect)
        effects_dict[username] = sorted(set(effects_dict[username]))
    except KeyError:
        effects_dict[username] = [chosen_effect]

    common.write_json_to_file(ACTIVE_EFFECTS_PATH, effects_dict)

    return chosen_effect

def get_active_effects(username) -> list:
    effects_dict = common.try_read_json(ACTIVE_EFFECTS_PATH, dict())

    try:
        active_effects = effects_dict[username]
    except KeyError:
        return []

    return active_effects

def reset_active_effects(username):
    effects_dict = common.try_read_json(ACTIVE_EFFECTS_PATH, dict())
    effects_dict[username] = []

    common.write_json_to_file(ACTIVE_EFFECTS_PATH, effects_dict)
