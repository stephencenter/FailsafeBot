import random
import re
import helpers

# Stat Roll command
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

async def statroll_command(context, update=None):
    valid_games = ["dnd", "coc", "mythras"]
    try:
        game = (await helpers.get_args_list(context, update))[0].lower()
        if game not in valid_games:
            raise IndexError

    except IndexError:
        return f"Please supply a valid game name. Options are {', '.join(valid_games)}"

    roll_string = "this should not appear"
    if game == "dnd":
        roll_string = get_dnd_roll()

    if game == "coc":
        roll_string = get_coc_roll()

    if game == "mythras":
        roll_string = get_mythras_roll()

    return roll_string

# Dice Roll commmand
def parse_diceroll(dice_roll) -> list:
    try:
        if dice_roll[0].startswith("d"):
            dice_roll[0] = f"1{dice_roll[0]}"

    except IndexError:
        return []

    roll_data = re.split(r"d|(\+)|(-)", "".join(dice_roll), flags=re.IGNORECASE)
    roll_data = [x for x in roll_data if x is not None]

    try:
        num_dice = int(roll_data[0])
        num_faces = int(roll_data[1])

    except (IndexError, ValueError):
        return []

    if num_faces < 1 or num_dice < 1:
        return []

    modifier = 0

    try:
        if roll_data[2] == '+':
            modifier = int(roll_data[3])

        if roll_data[2] == '-':
            modifier = -int(roll_data[3])

    except (IndexError, ValueError) as e:
        if len(roll_data) != 2 or e is ValueError:
            return []

    return [num_dice, num_faces, modifier]

async def roll_command(context, update=None):
    dice_roll = parse_diceroll(await helpers.get_args_list(context, update))

    if not dice_roll:
        return 'Please use dice notation like a civilized humanoid, e.g. "3d6 + 2"'

    num_dice, num_faces, modifier = dice_roll

    if num_dice > 50:
        return "Keep it to 50 dice or fewer please, I'm not a god."

    if num_faces > 10000:
        return "Keep it to 10,000 sides or fewer please, I'm not a god."

    rolls = []
    for _ in range(num_dice):
        this_roll = random.randint(1, num_faces)
        rolls.append(this_roll)

    if modifier != 0 or num_dice > 1:
        dice_text = ', '.join(str(x) for x in rolls)
        dice_text = f"({dice_text})"

    else:
        dice_text = ""

    sender = await helpers.get_sender(context, update)
    return f"{sender} rolled a {sum(rolls) + modifier} {dice_text}"
