import random
import re
import helpers
import settings

# Stat Roll command
async def statroll_command(context, update=None) -> helpers.CommandResponse:
    game_functions = {"dnd": get_dnd_roll, "coc": get_coc_roll, "mythras": get_mythras_roll}
    error_response = f"Please supply a valid game name. Options are {', '.join(game_functions.keys())}"

    try:
        game = (await helpers.get_args_list(context, update))[0].lower()
        roll_string = game_functions[game]()

    except IndexError:
        return helpers.CommandResponse("Can you roll me a tabletop character?", error_response)

    user_prompt = f"Can you roll me a character for {game}?"

    try:
        roll_string = game_functions[game]()

    except KeyError:
        return helpers.CommandResponse(user_prompt, error_response)

    return helpers.CommandResponse(user_prompt, roll_string)

# Dice Roll commmand
async def roll_command(context, update=None) -> helpers.CommandResponse:
    parsed_roll = parse_diceroll(await helpers.get_args_list(context, update))

    if parsed_roll is None:
        return helpers.CommandResponse("Can you roll some dice for me?", "Please use dice notation like a civilized humanoid, e.g. '3d6 + 2'")

    num_dice, num_faces, modifier = parsed_roll

    if modifier > 0:
        roll_text = f"{num_dice}d{num_faces} + {modifier}"
    elif modifier < 0:
        roll_text = f"{num_dice}d{num_faces} - {abs(modifier)}"
    else:
        roll_text = f"{num_dice}d{num_faces}"

    user_prompt = f"Can you roll a {roll_text} for me?"

    config = settings.get_config()
    if num_dice > config.main.maxdice:
        return helpers.CommandResponse(user_prompt, f"Keep it to {config.main.maxdice:,} dice or fewer please, I'm not a god.")

    if num_faces > config.main.maxfaces:
        return helpers.CommandResponse(user_prompt, f"Keep it to {config.main.maxfaces:,} sides or fewer please, I'm not a god.")

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

    return helpers.CommandResponse(user_prompt, f"{sender} rolled a {sum(rolls) + modifier:,} {dice_text}")

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
