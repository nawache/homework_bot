import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telebot
from dotenv import load_dotenv

from custom_exceptions import (
    APIRequestError, APIResponseError, HomeworkStatusUnknown
)


load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens() -> bool:
    """Проверяет доступность переменных окружения.

    Returns:
        bool: True, если все токены доступны, иначе вызывает исключение.
    """
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }

    missing_tokens = [
        token_name for token_name, token_value in tokens.items()
        if not token_value
    ]

    if missing_tokens:
        logger.critical(
            f'Отсутствуют обязательные переменные окружения: {missing_tokens}'
        )
        return False

    return True


def send_message(bot: telebot.TeleBot, message: str) -> None:
    """Отправляет сообщение в Telegram чат.

    Args:
        bot (telebot.TeleBot): Экземпляр бота Telegram.
        message (str): Текст сообщения для отправки.
    """
    try:
        logger.debug('Бот начал отправку сообщения')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(f'Бот успешно отправил сообщение: {message}')
    except Exception as error:
        logger.error(f'Сбой при отправке сообщения в Telegram: {error}')


def get_api_answer(timestamp: int) -> dict:
    """Делает запрос к API сервиса.

    Args:
        timestamp (int): Временная метка для получения статусов после неё.

    Returns:
        dict: Ответ API, преобразованный из JSON в Python-словарь.
    """
    REQUEST_PARAMS = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp}
    }

    try:
        logger.info(
            f'Попытка отправки GET-запроса к эндпоинту {ENDPOINT} '
            f'с параметрами {REQUEST_PARAMS["params"]}')
        response = requests.get(**REQUEST_PARAMS)
        if response.status_code != HTTPStatus.OK:
            raise APIRequestError(
                f'Эндпоинт {ENDPOINT} недоступен. '
                f'Код ответа API: {response.status_code}'
            )
        logger.info('Ответ на запрос к API получен')
        return response.json()

    except requests.exceptions.RequestException as error:
        raise APIRequestError(f'Ошибка при запросе к API: {error}')


def check_response(response: dict) -> list:
    """Проверяет ответ API на соответствие документации.

    Args:
        response (dict): Ответ API, преобразованный в Python-словарь.

    Returns:
        list: Список домашних работ.
    """
    if not isinstance(response, dict):
        raise TypeError('Ответ API должен быть словарем')

    if 'homeworks' not in response:
        raise APIResponseError('В ответе API отсутствует ключ "homeworks"')

    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Значение ключа "homeworks" должно быть списком')

    logger.info('Ответ API соответствует документации')
    return homeworks


def parse_status(homework: dict) -> str:
    """Извлекает статус домашней работы.

    Args:
        homework (dict): Словарь с информацией о домашней работе.

    Returns:
        str: Строка с информацией об изменении статуса работы.
    """
    if not isinstance(homework, dict):
        raise TypeError('Homework должен быть словарем')

    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if not homework_name:
        raise KeyError('В ответе API отсутствует ключ "homework_name"')

    if not homework_status:
        raise KeyError('В ответе API отсутствует ключ "status"')

    if homework_status not in HOMEWORK_VERDICTS:
        raise HomeworkStatusUnknown(
            f'Неизвестный статус работы: {homework_status}'
        )

    verdict = HOMEWORK_VERDICTS.get(homework_status)

    logger.info(f'Изменение статуса работы "{homework_name}"')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main() -> None:
    """Основная логика работы бота.

    Returns:
        None
    """
    logger.info('Бот начал работу')

    if not check_tokens():
        logger.critical('Программа принудительно остановлена')
        sys.exit()

    bot = telebot.TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    last_error = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
                logger.info('Статус обновлен')
            else:
                logger.debug('Нет новых статусов')

            timestamp = response.get('current_date', int(time.time()))

        except Exception as error:
            error_message = f'Сбой в работе программы: {error}'
            logger.error(error_message)

            if str(error) != str(last_error):
                send_message(bot, error_message)
                last_error = error

        finally:
            logger.info(f'Следующий запрос через {RETRY_PERIOD} секунд')
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
