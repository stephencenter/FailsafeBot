import math
import string
from html import unescape

import requests
from loguru import logger
from unidecode import unidecode

import common

TRIVIA_MEMORY_SIZE = 100
TRIVIA_NUM_QUESTIONS = 3

TRIVIA_DIFFICULTY_POINTS = {
    "easy": 10,
    "medium": 20,
    "hard": 30,
}


def fix_string(text: str) -> str:
    text = unescape(text)
    text = unidecode(text)
    return text.strip()


class TriviaQuestion:
    def __init__(self, question_dict: dict):
        self.type: str = question_dict['type']
        self.difficulty: str = question_dict['difficulty']
        self.category: str = fix_string(question_dict['category'].split(':')[-1])
        self.question: str = fix_string(question_dict['question'])
        self.correct_answer: str = fix_string(question_dict['correct_answer'])
        self.incorrect_answers = [fix_string(q) for q in question_dict['incorrect_answers']]

        # Sort answers alphabetically, unless it's a true/false question
        if self.type == 'boolean':
            self.answer_list = ['True', 'False']
        else:
            self.answer_list: list[str] = sorted([*self.incorrect_answers, self.correct_answer])

        self.guesses_left = len(self.answer_list) - 1

    def save_as_current_question(self, user_command: common.UserCommand) -> None:
        trivia_data = common.try_read_json(common.TRIVIA_CURRENT_PATH, {})
        trivia_data[user_command.get_chat_id()] = {
            'type': self.type,
            'difficulty': self.difficulty,
            'category': self.category,
            'question': self.question,
            'correct_answer': self.correct_answer,
            'incorrect_answers': self.incorrect_answers,
            'guesses_left': self.guesses_left,
        }
        common.write_json_to_file(common.TRIVIA_CURRENT_PATH, trivia_data)

    def get_question_string(self) -> str:
        alphabet = string.ascii_uppercase  # Should never need more than 4 letters
        answer_string = '\n'.join(f'    {alphabet[index]}. {answer}' for index, answer in enumerate(self.answer_list))

        question_string = f"""\
[Category: {self.category} — {self.difficulty.title()}]
Q. {self.question}
{answer_string}
Type /guess [your answer] to answer!
"""

        return question_string

    def score_question(self, user_command: common.UserCommand, *, was_correct: bool) -> int:
        if was_correct:
            potential_points = TRIVIA_DIFFICULTY_POINTS[self.difficulty]
            points_multiplier = self.guesses_left/(len(self.answer_list) - 1)
            points_gained = math.floor(potential_points*points_multiplier)

            points_dict = common.try_read_json(common.TRIVIA_POINTS_PATH, {})
            player_name = user_command.get_user_name()
            player_id = user_command.get_user_id()
            chat_id = user_command.get_chat_id()

            if chat_id not in points_dict:
                points_dict[chat_id] = {
                    player_id: {
                        'name': player_name,
                        'score': points_gained,
                    },
                }

            elif player_id not in points_dict[chat_id]:
                points_dict[chat_id][player_id] = {
                    'name': player_name,
                    'score': points_gained,
                }

            else:
                points_dict[chat_id][player_id]['name'] = player_name  # Update player name in case it's changed
                points_dict[chat_id][player_id]['score'] += points_gained

            common.write_json_to_file(common.TRIVIA_POINTS_PATH, points_dict)
            clear_current_question(user_command)

            return points_gained

        self.guesses_left -= 1

        if self.guesses_left > 0:
            self.save_as_current_question(user_command)
        else:
            clear_current_question(user_command)

        return 0

    def get_letter(self, guess: str) -> str | None:
        alphabet = string.ascii_lowercase  # Shouldn't need more than 4 letters
        for index, answer in enumerate(self.answer_list):
            if guess.lower() == answer.lower():
                return alphabet[index]

        return None

    def is_guess_correct(self, guess: str) -> bool:
        if len(guess) == 1 and guess.lower() == self.get_letter(self.correct_answer):
            return True

        return guess.lower() == self.correct_answer.lower()

    def is_guess_on_list(self, guess: str) -> bool:
        alphabet = string.ascii_lowercase[:len(self.answer_list)]
        if len(guess) == 1 and guess.lower() in alphabet:
            return True

        return guess.lower() in (x.lower() for x in self.answer_list)


def get_trivia_question(user_command: common.UserCommand) -> TriviaQuestion:
    current_question = get_current_question(user_command)
    if current_question is not None:
        return current_question

    response = requests.post(f"{common.TRIVIA_URL}{TRIVIA_NUM_QUESTIONS}", timeout=10).json()['results']

    # Check the list of the most recently asked trivia questions and attempt to pick a
    # question that isn't on the list
    previous_questions = common.try_read_lines_list(common.TRIVIA_MEMORY_PATH, [])

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
    common.write_lines_to_file(common.TRIVIA_MEMORY_PATH, previous_questions)

    current_question = TriviaQuestion(chosen)
    current_question.save_as_current_question(user_command)

    return current_question


def get_current_question(user_command: common.UserCommand) -> TriviaQuestion | None:
    trivia_data = common.try_read_json(common.TRIVIA_CURRENT_PATH, None)
    if trivia_data is None:
        return None

    chat_id = user_command.get_chat_id()
    if chat_id is None or chat_id not in trivia_data or trivia_data[chat_id] is None:
        return None

    current_question = TriviaQuestion(trivia_data[chat_id])
    current_question.guesses_left = trivia_data[chat_id]['guesses_left']

    return current_question


def clear_current_question(user_command: common.UserCommand) -> None:
    chat_id = user_command.get_chat_id()

    if chat_id is None:
        return

    trivia_data = common.try_read_json(common.TRIVIA_CURRENT_PATH, {})
    trivia_data[chat_id] = None

    common.write_json_to_file(common.TRIVIA_CURRENT_PATH, trivia_data)


def get_trivia_rankings(user_command: common.UserCommand) -> list[tuple[str, int]] | None:
    points_dict = common.try_read_json(common.TRIVIA_POINTS_PATH, {})
    if not points_dict:
        return None

    chat_id = user_command.get_chat_id()
    if chat_id not in points_dict:
        return None

    points_list = [(player['name'], player['score']) for player in points_dict[chat_id].values()]

    return sorted(points_list, key=lambda x: x[1], reverse=True)
