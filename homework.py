import logging
import os
import time
from http import HTTPStatus
from logging import StreamHandler
from urllib.error import HTTPError

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='sys.stdout',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = StreamHandler()
logger.addHandler(handler)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

homework_status_cache = None


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Сообщение отправлено')
    except Exception as error:
        logger.error(f'сбой при отправке сообщения в Telegram {error}')


def get_api_answer(current_timestamp):
    """Запрос к эндпоинту."""
    try:
        timestamp = current_timestamp or int(time.time())
        params = {'from_date': timestamp}
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        assert response.status_code == HTTPStatus.OK
    except HTTPError:
        logger.error('недоступность эндпоинта')
    return response.json()


def check_response(response):
    """Проверка API на корректность."""
    homework = response['homeworks']
    if not isinstance(homework, list):
        logger.error('не корректный тип API')
        raise ValueError
    else:
        for item in response['homeworks']:
            return item


def parse_status(homework):
    """Определяет статус домашней работы."""
    if not homework:
        return None
    if 'homework_name' not in homework:
        logger.error('отсутствие ожидаемых ключей в ответе API')
        raise KeyError
    homework_name = homework['homework_name']
    homework_status = homework['status']
    global homework_status_cache
    if homework_status_cache == homework_status:
        logger.debug('отсутствие в ответе новых статусов')
        return None
    if HOMEWORK_STATUSES[homework_status]:
        verdict = HOMEWORK_STATUSES[homework_status]
        homework_status_cache = homework_status
        return (f'Изменился статус проверки работы '
                f'"{homework_name}". {verdict}')
    else:
        logger.error('отсутствие ожидаемых ключей в ответе API')


def check_tokens():
    """Проверка доступности переменных."""
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        return True
    else:
        logger.critical('не хватает глобальных переменных')


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            check_tokens()
            response = get_api_answer(current_timestamp - RETRY_TIME)
            check = check_response(response)
            par_stat = parse_status(check)
            if par_stat is not None:
                send_message(bot, par_stat)
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
