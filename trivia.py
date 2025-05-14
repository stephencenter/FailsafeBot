"""Trivia utilities.

This module contains constants, classes, and functions used by Trivia commands like
/trivia, /guess, and /triviarank.
"""

import math
import string

import aiohttp

import common

TRIVIA_DIFFICULTY_POINTS = {
    "easy": 10,
    "medium": 20,
    "hard": 30,
}


class TriviaQuestion:
    def __init__(self, question_dict: dict[str, str]) -> None:
        self.type: str = question_dict['type']
        self.difficulty: str = question_dict['difficulty']
        self.category: str = common.convert_to_ascii(question_dict['category'].split(':')[-1])
        self.question: str = common.convert_to_ascii(question_dict['question'])
        self.correct_answer: str = common.convert_to_ascii(question_dict['correct_answer'])
        self.incorrect_answers: list[str] = [common.convert_to_ascii(q) for q in question_dict['incorrect_answers']]

        # Sort answers alphabetically, unless it's a true/false question
        if self.type == 'boolean':
            self.answer_list: list[str] = ['True', 'False']
        else:
            self.answer_list: list[str] = sorted([*self.incorrect_answers, self.correct_answer])

        self.guesses_left: int = len(self.answer_list) - 1

    async def save_as_current_question(self, user_command: common.UserCommand) -> None:
        trivia_data = await common.try_read_json(common.PATH_CURRENT_TRIVIA, {})
        trivia_data[user_command.get_chat_id()] = {
            'type': self.type,
            'difficulty': self.difficulty,
            'category': self.category,
            'question': self.question,
            'correct_answer': self.correct_answer,
            'incorrect_answers': self.incorrect_answers,
            'guesses_left': self.guesses_left,
        }
        await common.write_json_to_file(common.PATH_CURRENT_TRIVIA, trivia_data)

    def get_question_string(self) -> str:
        alphabet = string.ascii_uppercase  # Should never need more than 4 letters
        answer_string = '\n'.join(f'    {alphabet[index]}. {answer}' for index, answer in enumerate(self.answer_list))

        question_string = f"""\
[Category: {self.category} — {self.difficulty.title()}]
Q. {self.question}
{answer_string}
Type /guess [your answer] to answer ({self.guesses_left} guess{'es' if self.guesses_left > 1 else ''} remaning)
"""

        return question_string

    async def score_question(self, user_command: common.UserCommand, *, was_correct: bool) -> int:
        if was_correct:
            potential_points = TRIVIA_DIFFICULTY_POINTS[self.difficulty]
            points_multiplier = self.guesses_left / (len(self.answer_list) - 1)
            points_gained = math.floor(potential_points * points_multiplier)

            points_dict = await common.try_read_json(common.PATH_TRIVIA_SCORES, {})
            player_name = await user_command.get_user_name()
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

            await common.write_json_to_file(common.PATH_TRIVIA_SCORES, points_dict)
            await clear_current_question(user_command)

            return points_gained

        self.guesses_left -= 1

        if self.guesses_left > 0:
            await self.save_as_current_question(user_command)
        else:
            await clear_current_question(user_command)

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


async def get_trivia_question(user_command: common.UserCommand) -> TriviaQuestion:
    current_question = await get_current_question(user_command)
    if current_question is not None:
        return current_question

    new_question = await get_new_trivia_question()
    await new_question.save_as_current_question(user_command)

    return new_question


async def get_new_trivia_question() -> TriviaQuestion:
    url = f"{common.URL_TRIVIA}1"
    async with (aiohttp.ClientSession() as session, session.post(url, timeout=aiohttp.ClientTimeout(total=10)) as response):
        response_data = (await response.json())['results']

    return TriviaQuestion(response_data[0])


async def get_current_question(user_command: common.UserCommand) -> TriviaQuestion | None:
    trivia_data = await common.try_read_json(common.PATH_CURRENT_TRIVIA, None)
    if trivia_data is None:
        return None

    chat_id = user_command.get_chat_id()
    if chat_id is None or chat_id not in trivia_data or trivia_data[chat_id] is None:
        return None

    current_question = TriviaQuestion(trivia_data[chat_id])
    current_question.guesses_left = trivia_data[chat_id]['guesses_left']

    return current_question


async def clear_current_question(user_command: common.UserCommand) -> None:
    chat_id = user_command.get_chat_id()

    if chat_id is None:
        return

    trivia_data = await common.try_read_json(common.PATH_CURRENT_TRIVIA, {})
    trivia_data[chat_id] = None

    await common.write_json_to_file(common.PATH_CURRENT_TRIVIA, trivia_data)


async def get_trivia_rankings(user_command: common.UserCommand) -> list[tuple[str, int]] | None:
    points_dict = await common.try_read_json(common.PATH_TRIVIA_SCORES, {})
    if not points_dict:
        return None

    chat_id = user_command.get_chat_id()
    if chat_id not in points_dict:
        return None

    points_list = [(player['name'], player['score']) for player in points_dict[chat_id].values()]

    return sorted(points_list, key=lambda x: x[1], reverse=True)
