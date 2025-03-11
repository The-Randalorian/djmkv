import asyncio
import datetime
import json
import os
import pathlib
import socket
from typing import Mapping, Any

import aiofiles
import aiomqtt
import sqlalchemy
from sqlalchemy import Engine
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

try:
    from .disk_driver import drive, events
except ModuleNotFoundError:
    from disk_driver import drive, events

try:
    from . import mqtt_wrapper
except ModuleNotFoundError:
    import mqtt_wrapper

try:
    from . import database
except ModuleNotFoundError:
    import database


TOPIC_ROOT: pathlib.Path = pathlib.Path(os.getenv("MQTT_TOPIC_ROOT", "djmkv/"))


class RipperServer:
    def __init__(self, name: str, drive_path: pathlib.Path | str):
        self.session_maker: async_sessionmaker | None = None
        self.db_engine: Engine | None = None
        self.root_topic: pathlib.Path | None = None
        self.drive_topic: pathlib.Path | None = None
        self.name = name
        if isinstance(drive_path, str):
            drive_path = pathlib.Path(drive_path)
        self.drive_path = drive_path
        self.mqtt_client: mqtt_wrapper.MQTTWrapper | None = None
        self.db: sqlalchemy.engine = None
        self.controller = drive.Drive(self.drive_path)
        self.processor = self.controller.makemkv_source

    async def setup_mqtt_client(
        self,
        hostname: str,
        port: int = 1883,
        username: str | None = None,
        password: str | None = None,
    ):
        self.root_topic = TOPIC_ROOT / self.name
        self.drive_topic = self.root_topic / str(self.drive_path).strip("/").replace(
            "/", "_"
        )

        self.mqtt_client = mqtt_wrapper.MQTTWrapper(
            aiomqtt.Client(
                hostname=hostname,
                port=port,
                username=username,
                password=password,
                identifier=socket.gethostname(),
            )
        )

    async def setup_database(self, connection_string: str):
        self.db_engine = await database.init_db(connection_string)
        self.session_maker = async_sessionmaker(self.db_engine, expire_on_commit=False)

    async def setup_makemkv(self, key: str | None = None):
        if key is not None:
            registration_process = await asyncio.create_subprocess_exec(
                "makemkvcon",
                "reg",
                key,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await registration_process.communicate()

        init_process = await asyncio.create_subprocess_exec(
            "makemkvcon",
            "info",
            "dev:/dev/null",  # null is fine, it just needs to start AT ALL and make the folder/files
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await init_process.communicate()

    async def mqtt_publish_progress(self, progress: dict):
        await self.mqtt_client.enqueue_message(
            self.drive_topic / "progress",
            payload=json.dumps(progress),
        )

    async def mqtt_publish_message(self, progress: dict):
        await self.mqtt_client.enqueue_message(
            self.drive_topic / "message",
            payload=json.dumps(progress),
        )

    async def scan_disc(self):
        # lock the door while we work with the disc
        async with self.controller.locked_door():
            print("scanning", flush=True)
            info_task = asyncio.create_task(self.processor.get_info())
            progress = {
                "current": {"progress": 0.0, "name": "Starting", "code": -1, "id": -1},
                "total": {"progress": 0.0, "name": "Starting", "code": -1, "id": -1},
            }
            await self.mqtt_publish_progress(progress)

            while True:
                event = await self.processor.get_event()

                # print(event, flush=True)
                match type(event):
                    case events.StopEvent:
                        print("stop event", flush=True)
                        await self.mqtt_publish_progress(
                            {
                                "current": {
                                    "progress": 1.0,
                                    "name": "Complete",
                                    "code": -2,
                                    "id": -2,
                                },
                                "total": {
                                    "progress": 1.0,
                                    "name": "Complete",
                                    "code": -2,
                                    "id": -2,
                                },
                            },
                        )
                        break  # we're done, stop here
                    case events.ProgressCurrentEvent:
                        progress["current"]["name"] = event.name
                        progress["current"]["code"] = event.code
                        progress["current"]["id"] = event.operation_id
                        progress["current"]["progress"] = 0.0
                    case events.ProgressTotalEvent:
                        progress["total"]["name"] = event.name
                        progress["total"]["code"] = event.code
                        progress["total"]["id"] = event.operation_id
                        progress["total"]["progress"] = 0.0
                    case events.MessageEvent:
                        print(event.message, flush=True)
                        await self.mqtt_publish_message(event.message)
                    case events.ProgressValueEvent:
                        progress["current"]["progress"] = event.current_fraction
                        progress["total"]["progress"] = event.total_fraction
                        await self.mqtt_publish_progress(progress)
                    # case events.MessageEvent:
            print("events handled", flush=True)
            return await info_task

    async def publish_disc_data(self, disc, disc_name, disc_data, session):
        async with aiofiles.open(f"out/{disc.disc_id}.json", "w") as f:
            await f.write(json.dumps(disc_data, indent=4, default=str))

        await self.update_disc(disc_data, disc_name, disc, session)

    async def drive_loop(self):
        while True:

            # assume the drive doesn't have the right disc in it. If it does, just make the user close the drive again
            await self.mqtt_publish_progress(
                {
                    "current": {
                        "progress": -1.0,
                        "name": "Awaiting disc",
                        "code": -3,
                        "id": -3,
                    },
                    "total": {
                        "progress": -1.0,
                        "name": "Awaiting disc",
                        "code": -3,
                        "id": -3,
                    },
                }
            )
            print("cycling", flush=True)
            await self.controller.cycle()

            print("waiting for disc to be ready", flush=True)
            await self.controller.wait_disc_ready()

            if not await self.controller.is_disc_ok():
                print("disc not ok", flush=True)
                continue

            # await asyncio.sleep(10)

            disc_id: int = int(await self.controller.get_uuid(), base=16)
            if (disc_id & (1 << 63)) != 0:
                disc_id = disc_id - (1 << 64)
            disc_name: str = await self.controller.get_name()

            async with self.session_maker() as session:
                disc_task = asyncio.create_task(
                    self.lookup_disc(disc_id, disc_name, session)
                )
                disc_data = await self.scan_disc()
                disc = await disc_task
                await self.publish_disc_data(disc, disc_name, disc_data, session)

    async def update_streams(self, title, title_data):
        existing_streams = await title.awaitable_attrs.streams
        for stream_number, stream_data in enumerate(title_data.get("Streams", [])):
            if stream_number >= len(existing_streams):
                stream = database.DiscStream(
                    disc_id=title.disc_id,
                    title_number=title.title_number,
                    stream_number=stream_number,
                    name=stream_data.get("Name", "Unknown"),
                )
                title.streams.append(stream)
            else:
                stream = existing_streams[stream_number]
                stream.name = stream_data.get("Name", "Unknown")

    async def update_titles(self, disc, disc_data):
        existing_titles = await disc.awaitable_attrs.titles
        for title_number, title_data in enumerate(disc_data.get("Titles", [])):
            if title_number >= len(existing_titles):
                title = database.DiscTitle(
                    disc_id=disc.disc_id,
                    title_number=title_number,
                    name=title_data.get("Name", "Unknown"),
                    chapter_count=title_data.get("ChapterCount", 1),
                    duration=title_data.get("Duration", datetime.timedelta(seconds=0)),
                    disc_size=title_data.get("DiscSize", "Unknown"),
                    disc_size_bytes=title_data.get("DiscSizeBytes", 0),
                    source_file_name=title_data.get("SourceFileName", "Unknown"),
                    segments_count=title_data.get("SegmentsCount", 1),
                    segments_map=title_data.get("SegmentsMap", ""),
                    output_file_name=title_data.get("OutputFileName", "Unknown"),
                    metadata_language_code=title_data.get(
                        "MetadataLanguageCode", "UNK"
                    ),
                    metadata_language_name=title_data.get(
                        "MetadataLanguageName", "Unknown"
                    ),
                    tree_info=title_data.get("TreeInfo", "Unknown"),
                    panel_title=title_data.get("PanelTitle", "Unknown"),
                    order_weight=title_data.get("OrderWeight", 0),
                )
                disc.titles.append(title)
            else:
                title = existing_titles[title_number]
                title.name = title_data.get("Name", "Unknown")
                title.chapter_count = title_data.get("ChapterCount", 1)
                title.duration = title_data.get(
                    "Duration", datetime.timedelta(seconds=0)
                )
                title.disc_size = title_data.get("DiscSize", "Unknown")
                title.disc_size_bytes = title_data.get("DiscSizeBytes", 0)
                title.source_file_name = title_data.get("SourceFileName", "Unknown")
                title.segments_count = title_data.get("SegmentsCount", 1)
                title.segments_map = title_data.get("SegmentsMap", "")
                title.output_file_name = title_data.get("OutputFileName", "Unknown")
                title.metadata_language_code = title_data.get(
                    "MetadataLanguageCode", "UNK"
                )
                title.metadata_language_name = title_data.get(
                    "MetadataLanguageName", "Unknown"
                )
                title.tree_info = title_data.get("TreeInfo", "Unknown")
                title.panel_title = title_data.get("PanelTitle", "Unknown")
                title.order_weight = title_data.get("OrderWeight", 0)

            await self.update_streams(title, title_data)

    async def update_disc(
        self,
        disc_data: Mapping[str, Any],
        disc_name: str,
        disc: database.Disc,
        session: AsyncSession,
    ):
        disc.type = disc_data.get("Type", "Unknown")
        disc.name = disc_data.get("Name", disc_name)
        disc.metadata_language_code = disc_data.get("MetadataLanguageCode", "UNK")
        disc.metadata_language_name = disc_data.get("MetadataLanguageName", "Unknown")
        disc.tree_info = disc_data.get("TreeInfo", "Unknown")
        disc.panel_title = disc_data.get("PanelTitle", "<b>Source information</b><br>")
        disc.volume_name = disc_data.get("VolumeName", "UNKNOWN")
        disc.order_weight = disc_data.get("OrderWeight", 0)

        # await session.commit()

        await self.update_titles(disc, disc_data)

        await session.commit()

    async def main_loop(self):
        async with asyncio.TaskGroup() as group:
            group.create_task(self.mqtt_client.send_loop())
            group.create_task(self.drive_loop())

    async def lookup_disc(self, disc_id: int, disc_name: str, session: AsyncSession):
        async with session.begin():
            disc = await session.get(
                database.Disc, {"disc_id": disc_id}, populate_existing=True
            )
            if disc is None:
                disc = database.Disc(disc_id=disc_id, name=disc_name)
                session.add(disc)
                print("disc added", flush=True)
            else:
                print("disc already exists", flush=True)
            return disc


async def main(drive_path: str):

    rs = RipperServer(socket.gethostname(), drive_path)

    print("initializing")
    setup_jobs = [
        rs.setup_mqtt_client(
            hostname=os.getenv("MQTT_HOSTNAME", None),
            username=os.getenv("MQTT_USERNAME", None),
            password=os.getenv("MQTT_PASSWORD", None),
        ),
        rs.setup_database(
            os.getenv("DB_STRING", "sqlite:///djmkv_database.db"),
        ),
        rs.setup_makemkv(os.getenv("MAKEMKV_KEY")),
    ]
    await asyncio.gather(*setup_jobs)

    print("starting drive loop")
    await rs.main_loop()


if __name__ == "__main__":
    dp = os.getenv("DRIVE_PATH", None)
    if dp is None:
        print("Drive not specified. Exiting.")
    asyncio.run(main(dp))
