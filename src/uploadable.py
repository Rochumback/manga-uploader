import asyncio
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

import dotenv
from fastapi import UploadFile
from patoolib import extract_archive
from PIL import Image
from shutil import copyfileobj

from core.utils.constants import SUPPORTED_IMG_TYPES
from structs import ChapterMetadata, MangaMetadata

dotenv.load_dotenv()

ROOT: str = os.getenv("MANGAS_ABSOLUTE_PATH")  # type: ignore
BACKUP_ROOT: str = os.getenv("BACKUPS_PATH")  # type: ignore

MAKE_BACKUP = os.getenv("MAKE_BACKUP")
print(MAKE_BACKUP)

if ROOT is None:
    raise ValueError("root path missing")

if MAKE_BACKUP is not None:
    if BACKUP_ROOT is None:
        raise ValueError("backup path missing")


class Manga:
    __root_path: Path
    __manga_path: Path
    __image: UploadFile

    name: str

    def __init__(self, metadata: MangaMetadata) -> None:
        manga_name = metadata.manga_name
        root_path = Path(ROOT)
        self.name = manga_name.replace("/", " ")

        self.__root_path = Path(root_path)

    def set_image(self, image: UploadFile) -> None:
        self.__image = image

    def __validade_chapter(self):
        if self.__manga_path.exists():
            raise ValueError("Manga already exists")

    def build_tree(self) -> None:
        self.__create_manga_folder()
        self.__create_chapters_folder()
        self.__save_manga_image()

    def __create_manga_folder(self) -> None:
        manga_name = self.name
        manga_path = self.__root_path / "mangas" / manga_name
        manga_path.mkdir(parents=True)
        self.__manga_path = manga_path

    def __create_chapters_folder(self) -> None:
        manga_path = self.__manga_path
        chapters_folder = manga_path / "chapters"
        chapters_folder.mkdir(parents=True)

    def __save_manga_image(self) -> None:
        manga_path = self.__manga_path
        manga_image = manga_path / "image"


class MangaChapter:
    __file: UploadFile
    __manga_path: Path

    name: str
    chapter_number: float

    def __init__(self, chapter_metadata: ChapterMetadata) -> None:
        manga_name = chapter_metadata.manga_name.replace("/", " ")
        chapter_number = chapter_metadata.chapter_number

        root_path = Path(ROOT)
        manga_path = root_path / "mangas" / manga_name
        self.name = manga_name
        self.__manga_path = manga_path
        self.__chapter_path = manga_path / "chapters" / str(chapter_number)
        self.chapter_number = chapter_number

        self.__validade_chapter()

    def cleanup(self):
        self.__tmp.cleanup()

    def delete_chapter(self):
        if self.__chapter_path.exists():
            chapter_path = self.__chapter_path
            chapter_absolute = chapter_path.absolute().as_posix()
            shutil.rmtree(path=chapter_absolute)

    async def __make_backup(self):
        backup_path = Path(BACKUP_ROOT)
        manga_path = backup_path / str(self.name)
        file_path = manga_path / str(self.__file.filename)
        try:
            manga_path.mkdir(parents=True)
        except Exception as _:
            pass
        with file_path.open("wb") as file:
            copyfileobj(self.__file.file, file)

    def __validade_chapter(self):
        if not self.__manga_path.exists():
            raise ValueError("Manga doesn't exists")
        if self.__chapter_path.exists():
            raise ValueError("Chapter already exists")

    def set_file(self, file: UploadFile) -> None:
        self.__file = file

    async def save_chapter(self):
        self.__tmp = TemporaryDirectory()
        folder = await self.__extract_chapter()
        self.workdir = Path(self.__tmp.name) / folder
        await self.__save_pages()

        if MAKE_BACKUP:
            await self.__make_backup()
        self.cleanup()

    async def __save_pages(self):
        workdir = self.workdir
        files = list(workdir.rglob("*"))
        pages = filter(self.__filter_file, files)
        pages = self.__convert_images(list(pages))
        await self.__process_jpeg_images(pages)

    def __convert_images(self, pages: list[Path]):
        print(self.workdir)
        pages_path = self.workdir / "pages"
        print(pages_path)
        pages_path.mkdir(parents=True)
        for page in pages:
            page_absolute = page.absolute().as_posix()
            image = Image.open(page_absolute)
            name, _ = page.name.split(".", 1)
            image_new_path = pages_path / (name + ".jpg")
            image_new_absolute = image_new_path.absolute().as_posix()
            image.save(image_new_absolute, quality=100)
        return list(pages_path.rglob("*.jpg"))

    @staticmethod
    def __filter_file(file: Path):
        return file.suffix in SUPPORTED_IMG_TYPES

    async def __extract_chapter(self):
        workdir = Path(self.__tmp.name)
        packed_path = await self.__save_packed_file()
        extract_path = extract_archive(
            packed_path, outdir=workdir.absolute().as_posix()
        )
        return extract_path

    async def __save_packed_file(self):
        workdir = Path(self.__tmp.name)
        file = workdir / str(self.__file.filename)
        with file.open(mode="wb") as opened_file:
            copyfileobj(self.__file.file, opened_file)
        return file.absolute().as_posix()

    @staticmethod
    def __get_split_options(path: str):
        return {
            "input_folder": path,
            "split_height": 2500,
            "output_type": ".jpg",
            "custom_width": -1,
            "detection_type": "pixel",
            "detection_senstivity": 90,
            "lossy_quality": 100,
            "ignorable_pixels": 5,
            "scan_line_step": 5,
        }

    async def __process_jpeg_images(self, images: list[Path]):
        out_folder = self.__chapter_path / "pages"
        out_folder.mkdir(parents=True)
        for image in images:
            input = image.absolute().as_posix()
            out_path = self.__chapter_path / "pages" / image.name
            output = out_path.absolute().as_posix()

            process = await asyncio.create_subprocess_shell(
                f'./avif_converter "{input}" "{output}"',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
