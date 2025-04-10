import math
from html import unescape

import requests
from loguru import logger
from unidecode import unidecode

import common

TRIVIA_URL = "https://opentdb.com/api.php?amount="
TRIVIA_POINTS_PATH = "Data/trivia_points.json"
TRIVIA_MEMORY_PATH = "Data/trivia_memory.txt"

TRIVIA_MEMORY_SIZE = 100
TRIVIA_NUM_QUESTIONS = 3

TRIVIA_DIFFICULTY_POINTS = {
    "easy": 10,
    "medium": 20,
    "hard": 30
}

current_question = None

def fix_string(string: str) -> str:
    string = unescape(string)
    string = unidecode(string)
    return string.strip()

class TriviaQuestion:
    def __init__(self, question_dict: dict):
        self.type: str = question_dict['type']
        self.difficulty: str = question_dict['difficulty']
        self.category: str = fix_string(question_dict['category'].split(':')[-1])
        self.question: str = fix_string(question_dict['question'])
        self.correct_answer: str = fix_string(question_dict['correct_answer'])

        # Sort answers alphabetically, unless it's a true/false question
        if self.type == 'boolean':
            self.answer_list = ['True', 'False']
        else:
            self.answer_list: list[str] = [fix_string(q) for q in question_dict['incorrect_answers']]
            self.answer_list = sorted([*self.answer_list, self.correct_answer])

        self.guesses_left = len(self.answer_list) - 1

    def get_question_string(self) -> str:
        alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'  # Should never need more than 4 letters
        answer_string = '\n'.join(f'    {alphabet[index]}. {answer}' for index, answer in enumerate(self.answer_list))

        question_string = f"""\
[Category: {self.category} — {self.difficulty.title()}]
Q. {self.question}
{answer_string}
Type /guess [your answer] to answer!
"""

        return question_string

    def score_question(self, user_command: common.UserCommand, *, was_correct: bool) -> int:
        global current_question

        points_gained = 0
        if was_correct:
            potential_points = TRIVIA_DIFFICULTY_POINTS[self.difficulty]
            points_multiplier = self.guesses_left/(len(self.answer_list) - 1)
            points_gained = math.floor(potential_points*points_multiplier)
            current_question = None

        else:
            self.guesses_left -= 1

        if self.guesses_left == 0:
            current_question = None

        if points_gained > 0:
            points_dict = common.try_read_json(TRIVIA_POINTS_PATH, {})
            player_name = user_command.get_author()

            try:
                points_dict[player_name] += points_gained
            except KeyError:
                points_dict[player_name] = points_gained

            common.write_json_to_file(TRIVIA_POINTS_PATH, points_dict)

        return points_gained

    def get_letter(self, guess: str) -> str | None:
        alphabet = 'abcdefghijklmnopqrstuvwxyz'  # Shouldn't need more than 4 letters
        for index, answer in enumerate(self.answer_list):
            if guess.lower() == answer.lower():
                return alphabet[index]

        return None

    def is_guess_correct(self, guess: str) -> bool:
        if len(guess) == 1 and guess.lower() == self.get_letter(self.correct_answer):
            return True

        return guess.lower() == self.correct_answer.lower()

    def is_guess_on_list(self, guess: str) -> bool:
        alphabet = 'abcdefghijklmnopqrstuvwxyz'[:len(self.answer_list)]
        if len(guess) == 1 and guess.lower() in alphabet:
            return True

        return guess.lower() in (x.lower() for x in self.answer_list)

def get_trivia_question() -> TriviaQuestion:
    global current_question

    if current_question is not None:
        return current_question

    response = requests.post(f"{TRIVIA_URL}{TRIVIA_NUM_QUESTIONS}", timeout=10).json()['results']

    # Check the list of the most recently asked trivia questions and attempt to pick a
    # question that isn't on the list
    previous_questions = common.try_read_lines_list(TRIVIA_MEMORY_PATH, [])

    # We ask the trivia API for a few trivia questions and pick the first one that isn't
    # in the trivia memory
    for item in response:
        if item["question"] not in previous_questions:
            chosen = item
            break
        logger.info(f"skipped duplicate question: {item['question']}")
    else:
        chosen = response[0]

    previous_questions.append(chosen["question"])
    if (size := len(previous_questions)) > TRIVIA_MEMORY_SIZE:
        previous_questions = previous_questions[size - TRIVIA_MEMORY_SIZE:]

    # Keep track of which trivia questions have already been asked recently
    common.write_lines_to_file(TRIVIA_MEMORY_PATH, previous_questions)

    current_question = TriviaQuestion(chosen)

    return current_question

def get_current_question() -> TriviaQuestion | None:
    return current_question
