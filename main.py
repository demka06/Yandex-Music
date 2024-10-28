import asyncio
from re import findall
from typing import List
from os import mkdir
from os import listdir
from os.path import isdir

import eyed3
from loguru import logger
from telebot import apihelper
from telebot.async_telebot import AsyncTeleBot
from urllib.parse import urlparse
from yandex_music import ClientAsync
from yandex_music import exceptions
from yandex_music.track.track import Track
from yandex_music.tracks_list import TracksList

# Зависимости телеграм
TELEGRAM_ID = 0
TELEGRAM_TOKEN = ""

# Зависимости ЯМ
YANDEX_TOKEN = ""

# Константы
CODECS = ["mp3", "acc"]
BITRATES = [64, 128, 192, 320]

eyed3.log.setLevel("ERROR")


async def get_track_from_url(url: str) -> str:
    """
    Извлекает track_id из url типа https://music.yandex.ru/album/24985531/track/28676495

    Args:
        url (str): Ссылка на трек
    Return:
         str
    """

    return ":".join(findall(r'\d+', url)[::-1])

async def set_tags(track: Track,
                   file: str) -> None:
    """Добавление аудиофайлам исполнителя, названия, альбома, нумерации

    Args:
        track (yandex_music.track.track.Track): Объект трека
        file (str): Путь до сохраненного трека
    """

    logger.debug("Выгрузка тегов")
    audiofile = eyed3.load(path=file)  # Выгрузка тегов
    audiofile.initTag()  # Инициализация тегов

    # Присвоение новых значений тегам
    file_tag = audiofile.tag
    file_tag.title = track.title
    audiofile.tag.artist = ", ".join([i["name"] for i in track.artists])
    file_tag.album = track.albums[0].title
    file_tag.track_num = track.albums[0].track_count

    logger.debug("Сохранение тегов")
    file_tag.save()  # Сохранение тегов


async def get_downloaded_tracks(dir_name: str = "tracks",
                                codec: str = "mp3") -> List:
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


async def send_all_tracks_to_telegram(dir_name: str = "tracks",
                                      count: int = 10,
                                      offset: int = 0):
    """Отправка всех треков в телеграм

    Args:
            dir_name (str): Имя каталога, куда следует сохранять треки. Каталог может быть только в каталогом
            с этим файлом.
            count (int): Количество треков, которые нужно скачать
            offset (int): сдвиг
    """

    audio_files = await get_downloaded_tracks(dir_name)  # Список треков
    bot = Telegram()  # Инициализация бота

    # Отправление треков
    [await bot.send_audio_from_file(path=f"./{dir_name}/{file}") for file in audio_files[offset:count]]

    """
    counter = 0  # Управляющая переменная
    
    # Перебор и отправление треков
    for file in audio_files[offset:]:
    
        # Выход из цикла по счетчику
        if counter >= count:
            break
    
        await bot.send_audio_from_file(path=f"./{dir_name}/{file}")
    
        counter += 1  # Увеличение счетчика
    """


class YandexMusic:
    """Упрощение взаимодействия с модулем yandex_music.

    Args:
        token (str): Токен для авторизации в https://api.music.yandex.net
    """

    def __init__(self, token: str = YANDEX_TOKEN) -> None:
        try:
            logger.debug("Авторизация")
            self.client = ClientAsync(token)  # Авторизация
        except exceptions.UnauthorizedError:
            logger.error("Недействительный токен")

    async def __init_client(self):
        """Получение информацию об аккаунте использующихся в других запросах."""

        await self.client.init()

    async def get_tracks(self, track_ids: List[str] | List[int] | List[str | int] | int | str = 0,
                         count: int = 10,
                         offset: int = 0) -> list[Track] | TracksList | None:
        """
        Получение информации о треке.

        Args:
            track_ids (:obj:`str` | :obj:`int` | :obj:`list` из :obj:`str` | :obj:`list` из :obj:`int`): Уникальный
            идентификатор трека или треков. Если track_ids = 0, то отдаст все лайкнутые треки
            count (int): количество треков, которые нужно получить
            offset (int): сдвиг
        """

        await self.__init_client()

        logger.debug("Получение списка треков")
        return await self.client.tracks(track_ids=track_ids)[offset:count] if track_ids \
            else await self.client.users_likes_tracks()[offset:count]

    async def download_tracks(self, track_list: TracksList,
                              dir_name: str = "tracks",
                              codec: str = 'mp3',
                              bitrate: int = 192,
                              count: int = 10,
                              offset: int = 0,
                              repeats: bool = False) -> None:
        """Cохранение треков

        Args:
            dir_name (str): Имя каталога, куда следует сохранять треки. Каталог может быть только в каталогом
            с этим файлом.
            codec (str): Кодек скачиваемого трека. Известные значения  `mp3`, `aac`.
            bitrate (int): Битрейт скачиваемого трека. Известные значения 64`, `128`, `192`, `320`.
            count (int): Количество треков, которые нужно скачать. 0, если нужно вывести все треки.
            offset (int): Сдвиг.
            repeats (bool): Нужно ли проверять на наличие повторяющихся треков (для загрузки на пк).
            track_list (TracksList): объекты для загрузки.
        """

        await self.__init_client()

        # Управляющая переменная
        counter = 0

        # Уже сохраненные треки
        downloaded_tracks = await get_downloaded_tracks(dir_name, codec) if not repeats else None

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

        for track in track_list[offset:]:

            # Выход из цикла по счетчику
            if counter >= count and count:
                break

            logger.debug("Получение информации о треке")
            track: Track = await track.fetch_track_async()  # Получение информации о треке
            a = await track.get_specific_download_info_async(codec, bitrate)
            print(a)

            # Имя трека может состоять только из цифр и букв
            track_name = ''.join([i for i in track["title"] if i.isalnum() or i.isspace()])

            # Проверка на повторы
            if f"{track_name}.{codec}" in downloaded_tracks and not repeats:
                continue

            logger.debug("Сохранение трека")
            # Сохранение трека
            await track.download_async(filename=f"./{dir_name}/{track_name}.{codec}", codec=codec,
                                       bitrate_in_kbps=bitrate)

            # Присвоение тегов
            await set_tags(track=track, file=f"./{dir_name}/{track_name}.{codec}")

            if count:
                counter += 1  # Увеличение счетчика


class Telegram:
    """Упрощение взаимодействия с модулем telebot.

    Args:
        token (str): Токен для авторизации в telegram.
    """

    def __init__(self, token: str = TELEGRAM_TOKEN) -> None:
        try:
            self.bot = AsyncTeleBot(token)
            self.bot.get_me()
        except ValueError:
            logger.error("Указан неверный токен")
        except apihelper.ApiTelegramException:
            logger.error("Указан недействительный токен")

    async def send_audio_from_file(self, path, chat_id: int | str = TELEGRAM_ID) -> bool:
        """ Отправляет указанный трек в чат телеграм.

        Args:
            path (str): Путь до отправляемого файла.
            chat_id (int | str): id получателя.
        """

        try:
            await self.bot.send_audio(chat_id, open(path, 'rb'))
            logger.debug("Трек отправлен")
            return True
        except Exception as e:
            logger.error("Ошибка при отправке аудио: ")
            return False

    async def send_audio_from_link(self, track: Track, chat_id: int | str = TELEGRAM_ID) -> bool:
        """ Отправляет указанный трек в чат телеграм.

        Args:
            track (str): Обьект класса Track.
            chat_id (int | str): id получателя.
        """
        logger.debug("Получение загрузочной ссылки")
        download_info = await track.get_specific_download_info_async(codec="mp3", bitrate_in_kbps=192)
        direct_link = download_info.get_direct_link_async() if download_info.direct_link is None \
            else download_info.direct_link

        track_title = track.title
        track_artist = ", ".join([i["name"] for i in track.artists])
        track_cover = track.cover_uri

        try:
            await self.bot.send_audio(chat_id=chat_id, audio=direct_link,
                                      performer=track_artist,
                                      title=track_title,
                                      thumbnail=track_cover)
            logger.debug("Трек отправлен")
            return True
        except Exception as e:
            logger.error("Ошибка при отправке аудио: ")
            return False


async def main():
    a = YandexMusic()
    #await a.download_tracks(count=10)


asyncio.run(main())
