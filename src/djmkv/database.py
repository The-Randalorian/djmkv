import enum
import os
import datetime
from typing import List
from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    ForeignKeyConstraint,
    UniqueConstraint,
    BigInteger,
    Interval,
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from sqlalchemy import create_engine


class DiscType(enum.Enum):
    DVD = 0
    HD_DVD = 1
    BLU_RAY = 2
    UHD_BLU_RAY = 3


class StreamType(enum.Enum):
    VIDEO = 0
    AUDIO = 1
    SUBTITLES = 2


class SeriesType(enum.Enum):
    MOVIE = 0
    SHOW = 1


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Disc(Base):
    __tablename__ = "discs"

    disc_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=True)
    name: Mapped[str] = mapped_column(String(64), nullable=True)
    metadata_language_code: Mapped[str] = mapped_column(String(16), nullable=True)
    metadata_language_name: Mapped[str] = mapped_column(String(64), nullable=True)
    tree_info: Mapped[str] = mapped_column(String(64), nullable=True)
    panel_title: Mapped[str] = mapped_column(String(64), nullable=True)
    volume_name: Mapped[str] = mapped_column(String(64), nullable=True)
    order_weight: Mapped[int] = mapped_column(Integer, nullable=True)

    titles: Mapped[List["DiscTitle"]] = relationship(
        back_populates="disc", cascade="all, delete-orphan"
    )


class DiscTitle(Base):
    __tablename__ = "disc_titles"

    disc_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("discs.disc_id"),
        primary_key=True,
        nullable=False,
    )
    title_number: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=True)
    chapter_count: Mapped[int] = mapped_column(Integer, default=1)
    duration: Mapped[datetime.timedelta] = mapped_column(
        Interval, default=datetime.timedelta(seconds=0)
    )
    disc_size: Mapped[str] = mapped_column(String(32), nullable=True)
    disc_size_bytes: Mapped[int] = mapped_column(Integer, nullable=True)
    source_file_name: Mapped[str] = mapped_column(String(128), nullable=True)
    segments_count: Mapped[int] = mapped_column(Integer, default=1)
    segments_map: Mapped[str] = mapped_column(String(256), nullable=True)
    output_file_name: Mapped[str] = mapped_column(String(128), nullable=True)
    metadata_language_code: Mapped[str] = mapped_column(String(16), nullable=True)
    metadata_language_name: Mapped[str] = mapped_column(String(64), nullable=True)
    tree_info: Mapped[str] = mapped_column(String(128), nullable=True)
    panel_title: Mapped[str] = mapped_column(String(64), nullable=True)
    order_weight: Mapped[int] = mapped_column(Integer, default=0)

    disc: Mapped["Disc"] = relationship(back_populates="titles")
    streams: Mapped[List["DiscStream"]] = relationship(
        back_populates="title", cascade="all, delete-orphan"
    )


class DiscStream(Base):
    __tablename__ = "disc_streams"

    disc_id: Mapped[int] = mapped_column(BigInteger, nullable=False, primary_key=True)
    title_number: Mapped[int] = mapped_column(Integer, nullable=False, primary_key=True)
    stream_number: Mapped[int] = mapped_column(
        Integer, nullable=False, primary_key=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False, primary_key=True)

    title: Mapped["DiscTitle"] = relationship(back_populates="streams")

    __table_args__ = (
        ForeignKeyConstraint(
            ["disc_id", "title_number"],
            [
                "disc_titles.disc_id",
                "disc_titles.title_number",
            ],
        ),
    )


class Series(Base):
    __tablename__ = "series"

    series_id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, nullable=False
    )
    series_name: Mapped[str] = mapped_column(String(64), nullable=True)
    series_year: Mapped[int] = mapped_column(Integer, nullable=True)

    titles: Mapped[List["SeriesTitle"]] = relationship(
        back_populates="series", cascade="all, delete-orphan"
    )


class SeriesTitle(Base):
    __tablename__ = "series_titles"

    series_id: Mapped[int] = mapped_column(
        ForeignKey("series.series_id"), primary_key=True, nullable=False
    )
    season: Mapped[int] = mapped_column(primary_key=True, nullable=True, default=None)
    episode: Mapped[int] = mapped_column(primary_key=True, nullable=True, default=None)
    version: Mapped[str] = mapped_column(primary_key=True, default="")

    series: Mapped["Series"] = relationship(back_populates="titles")


class SeriesStream(Base):
    __tablename__ = "series_streams"
    series_id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    season: Mapped[int] = mapped_column(primary_key=True, nullable=True, default=None)
    episode: Mapped[int] = mapped_column(primary_key=True, nullable=True, default=None)
    version: Mapped[str] = mapped_column(primary_key=True, default="")
    stream_number: Mapped[int] = mapped_column(primary_key=True, default=0)

    __table_args__ = (
        ForeignKeyConstraint(
            ["series_id", "season", "episode", "version"],
            [
                "series_titles.series_id",
                "series_titles.season",
                "series_titles.episode",
                "series_titles.version",
            ],
        ),
    )


class TitleMapping(Base):
    __tablename__ = "title_mappings"

    # series title
    series_id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    season: Mapped[int] = mapped_column(
        primary_key=True,
        nullable=True,
        default=None,
    )
    episode: Mapped[int] = mapped_column(
        primary_key=True,
        nullable=True,
        default=None,
    )
    version: Mapped[str] = mapped_column(primary_key=True, default="")

    # order
    order: Mapped[int] = mapped_column(primary_key=True, nullable=False, default=0)

    # disc title
    disc_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title_number: Mapped[int] = mapped_column(nullable=False)

    # other mapping information
    first_chapter: Mapped[int] = mapped_column(nullable=False, default=0)
    last_chapter: Mapped[int] = mapped_column(nullable=False, default=-1)

    __table_args__ = (
        ForeignKeyConstraint(
            ["series_id", "season", "episode", "version"],
            [
                "series_titles.series_id",
                "series_titles.season",
                "series_titles.episode",
                "series_titles.version",
            ],
        ),
        ForeignKeyConstraint(
            ["disc_id", "title_number"],
            [
                "disc_titles.disc_id",
                "disc_titles.title_number",
            ],
        ),
        # in addition to the above constraints, no two mappings for the same series title can have the same order
        UniqueConstraint("series_id", "season", "episode", "version", "order"),
    )


class StreamMapping(Base):
    __tablename__ = "stream_mappings"

    # series title
    series_id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    season: Mapped[int] = mapped_column(
        primary_key=True,
        nullable=True,
        default=None,
    )
    episode: Mapped[int] = mapped_column(
        primary_key=True,
        nullable=True,
        default=None,
    )
    version: Mapped[str] = mapped_column(primary_key=True, default="")

    # order
    order: Mapped[int] = mapped_column(primary_key=True, nullable=False, default=0)

    series_stream_number: Mapped[int] = mapped_column(primary_key=True, default=0)
    disc_stream_number: Mapped[int] = mapped_column(default=0)

    __table_args__ = (
        ForeignKeyConstraint(
            ["series_id", "season", "episode", "version", "series_stream_number"],
            [
                "series_streams.series_id",
                "series_streams.season",
                "series_streams.episode",
                "series_streams.version",
                "series_streams.stream_number",
            ],
        ),
        ForeignKeyConstraint(
            ["series_id", "season", "episode", "version", "order"],
            [
                "title_mappings.series_id",
                "title_mappings.season",
                "title_mappings.episode",
                "title_mappings.version",
                "title_mappings.order",
            ],
        ),
    )


async def init_db(connection_string: str):
    engine = create_async_engine(connection_string)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


if __name__ == "__main__":
    path = "../../test/test_database.db"
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    engine = create_engine(f"sqlite:///{path}", echo=True)
    Base.metadata.create_all(engine)
