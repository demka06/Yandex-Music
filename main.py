from os import mkdir
from os import listdir
from os.path import isdir
from typing import List

import eyed3
from loguru import logger
from telebot import TeleBot
from telebot import apihelper
from yandex_music import Client
from yandex_music import exceptions
from yandex_music.track.track import Track

# Зависимости телеграм
TELEGRAM_ID = 0
TELEGRAM_TOKEN = ""

# Зависимости ЯМ
YANDEX_TOKEN = ""

# Константы
CODECS = ["mp3", "acc"]
BITRATES = [64, 128, 192, 320]

eyed3.log.setLevel("ERROR")


def set_tags(track: Track, file: str) -> None:
    """Добавление аудиофайлам исполнителя, названия, альбома, нумерации

    Args:
        track (yandex_music.track.track.Track): Объект трека
        file (str): Путь до сохраненного трека
    """

    # Извлечение необхордимых переменных
    track_name = track["title"]
    track_artists = ", ".join([i["name"] for i in track["artists"]])
    album = track["albums"][0]["title"]
    track_count = track["albums"][0]["track_count"]

    logger.debug("Выгрузка тегов")
    audiofile = eyed3.load(path=file)  # Выгрузка тегов
    audiofile.initTag()  # Инициализация тегов

    # Присвоение новых значений тегам
    file_tag = audiofile.tag
    file_tag.title = track_name
    audiofile.tag.artist = track_artists
    file_tag.album = album
    file_tag.track_num = track_count

    logger.debug("Сохранение тегов")
    file_tag.save()  # Сохранение тегов


def get_downloaded_tracks(dir_name: str = "tracks", codec: str = "mp3") -> List:
    """Получение уже загруженных треков

    Args:
            dir_name (str): Имя каталога, куда следует сохранять треки. Каталог может быть только в каталогом
            с этим файлом.
            codec (str): Кодек скачиваемого трека. Известные значения  `mp3`, `aac`.
    """

    # Имя папки может состоять только из цифр и букв
    dir_name = ''.join([i for i in dir_name if i.isalnum() or i.isspace()]) if dir_name != "tracks" else dir_name
    if not dir_name or not isdir(dir_name):
        logger.error("Указан неверный путь")
        return []

    # Получение получение только аудиофайлов
    files = listdir(f"./{dir_name}/")
    return [file for file in files if file.endswith(codec)] if files is not None else []


def send_all_tracks_to_telegram(dir_name: str = "tracks", count: int = 10, offset: int = 0):
    """Отправка всех треков в телеграм

    Args:
            dir_name (str): Имя каталога, куда следует сохранять треки. Каталог может быть только в каталогом
            с этим файлом.
            count (int): Количество треков, которые нужно скачать
            offset (int): сдвиг
    """

    audio_files = get_downloaded_tracks(dir_name)  # Список треков
    bot = Telegram()  # Инициализация бота
    counter = 0  # Управляющая переменная

    # Перебор и отправление треков
    for file in audio_files[offset:]:

        # Выход из цикла по счетчику
        if counter >= count:
            break

        bot.send_audio(f"./{dir_name}/{file}")

        counter += 1  # Увеличение счетчика


class YandexMusic:
    """Упрощение взаимодействия с модулем yandex_music

    Args:
        token (str): Токен для авторизации в https://api.music.yandex.net
    """

    def __init__(self, token: str = YANDEX_TOKEN):
        try:
            logger.debug("Авторизация")
            self.client = Client(token).init()  # Авторизация
        except exceptions.UnauthorizedError:
            logger.error("Недействительный токен")

    def download_tracks(self, dir_name: str = "tracks", codec: str = 'mp3', bitrate: int = 192,
                        count: int = 10, offset: int = 0) -> None:
        """Получение и сохранение понравившихся треков

        Args:
            dir_name (str): Имя каталога, куда следует сохранять треки. Каталог может быть только в каталогом
            с этим файлом.
            codec (str): Кодек скачиваемого трека. Известные значения  `mp3`, `aac`.
            bitrate (int): Битрейт скачиваемого трека. Известные значения 64`, `128`, `192`, `320`.
            count (int): Количество треков, которые нужно скачать
            offset (int): сдвиг
        """

        # Управляющая переменная
        counter = 0

        # Уже сохраненные треки
        downloaded_tracks = get_downloaded_tracks(dir_name, codec)

        # Имя папки может состоять только из цифр и букв
        dir_name = ''.join([i for i in dir_name if i.isalnum() or i.isspace()]) if dir_name != "tracks" else dir_name
        if not dir_name:
            logger.error("Указан неверный путь")
            return None

        # Создает папку с указанным именем, если такой нет
        if not isdir(dir_name):
            mkdir(dir_name)

        if codec not in CODECS:
            logger.error("Указан неверный формат для сохранения")
            return None

        if bitrate not in BITRATES:
            logger.error("Указан неверный битрейт")
            return None

        logger.debug("Получение списка понравившихся треков")
        track_list = self.client.users_likes_tracks()  # Получение списка понравившихся треков

        for track in track_list[offset:]:

            # Выход из цикла по счетчику
            if counter >= count:
                break

            logger.debug("Получение информации о треке")
            track = track.fetch_track()  # Получение информации о треке

            # Имя трека может состоять только из цифр и букв
            track_name = ''.join([i for i in track["title"] if i.isalnum() or i.isspace()])

            # Проверка на повторы
            if f"{track_name}.{codec}" in downloaded_tracks:
                continue

            logger.debug("Сохранение трека")
            # Сохранение трека
            track.download(filename=f"./{dir_name}/{track_name}.{codec}", codec=codec, bitrate_in_kbps=bitrate)

            # Присвоение тегов
            set_tags(track=track, file=f"./{dir_name}/{track_name}.{codec}")

            counter += 1  # Увеличение счетчика


class Telegram:
    """Упрощение взаимодействия с модулем yandex_music

    Args:
        token (str): Токен для авторизации в telegram
        your_id (int): ID телеграм чата для отправки сообщений
    """

    def __init__(self, token: str = TELEGRAM_TOKEN, your_id: int = TELEGRAM_ID):
        try:
            self.your_id = your_id
            self.bot = TeleBot(token)
            self.bot.get_me()
        except ValueError:
            logger.error("Указан неверный токен")
        except apihelper.ApiTelegramException:
            logger.error("Указан недействительный токен")

    def send_audio(self, path):
        """ Отправляет указанный трек в чат телеграм

        Args:
            path (str): Путь до отправляемого файла
        """
        try:
            self.bot.send_audio(self.your_id, open(path, 'rb'))
            logger.debug("Трек отправлен")
            return True
        except Exception as e:
            logger.error("Ошибка при отправке аудио: ")
            return False
