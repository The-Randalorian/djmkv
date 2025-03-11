import pathlib
import asyncio
from typing import List

try:
    from . import events
except ModuleNotFoundError:
    import events

PROGRAM = "makemkvcon"
DEFAULT_ARGS = ["-r", "--messages=-stdout", "--progress=-stdout", "--minlength=0"]
EVENT_QUEUE_SIZE = 0


class Source:
    def __init__(self, source_type: str, source_string: str):
        self.source_id = f"{source_type}:{source_string}"
        self.source_type = source_type
        self.source_string = source_string
        self.lock = (
            asyncio.Lock()
        )  # prevent multiple things from using the same makemkv drive
        self.process: asyncio.subprocess = None
        self.event_queue = asyncio.Queue(EVENT_QUEUE_SIZE)
        self.command_counter = 0

    async def run_command(self, args: List[str], wait_for_queue=True):
        async with self.lock:
            command_number = self.command_counter
            self.command_counter += 1
            history = []

            event = events.StartEvent(command_number)
            await self.event_queue.put(event)
            history.append(event)

            self.process = await asyncio.create_subprocess_exec(
                PROGRAM,
                *args,
                bufsize=0,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )

            while self.process.returncode is None:
                try:
                    byte_line = await asyncio.wait_for(
                        self.process.stdout.readline(), timeout=1.0
                    )
                    line = byte_line.decode("utf-8")

                    if len(line) <= 0:
                        # A weird deadlock happens sometimes (only in docker?) where the event loop isn't released
                        # (despite the above await), causing the system handling the return code to fail to update, in
                        # turn causing our loop to never exit. We could probably just break here, but for safety we just
                        # sleep and let the subprocess handler thing get a cycle or two in.
                        await asyncio.sleep(0.01)

                    line = line.rstrip("\r\n")
                    event = events.get_event(line)
                    if event is None:
                        # This is another (more negatively impacting) way to fix the docker bug.
                        # await asyncio.sleep(0)
                        continue
                    await self.event_queue.put(event)
                    history.append(event)
                except TimeoutError:
                    # print("timeout", flush=True)
                    pass  # silent timeout while polling

            # print("waiting for communicate", flush=True)
            stdout, stderr = await self.process.communicate()
            # print("done communicating", flush=True)
            for line in stdout.decode("utf-8").splitlines():
                line = line.rstrip("\r\n")
                event = events.get_event(line)
                await self.event_queue.put(event)
                history.append(event)

            event = events.StopEvent(command_number)
            await self.event_queue.put(event)
            history.append(event)

            # don't release the lock until all events are processed
            if wait_for_queue:
                await self.event_queue.join()
        return command_number, history

    async def get_event(self):
        event = await self.event_queue.get()
        self.event_queue.task_done()
        return event

    async def run_info(self, wait_for_queue=True):
        args = list(DEFAULT_ARGS)  # make a shallow copy
        args.append("info")
        args.append(self.source_id)
        return await self.run_command(args, wait_for_queue=wait_for_queue)

    async def get_info(self):
        command_number, history = await self.run_info()
        return self.history_to_dict(history)

    @staticmethod
    def history_to_dict(history):
        info = {"Titles": {}}
        for event in history:
            if isinstance(event, events.DiscInfoEvent):
                # print("D", event)
                info[event.item_name] = event.value
            elif isinstance(event, events.TitleInfoEvent):
                title = info["Titles"].get(event.title_number, {"Streams": {}})
                title[event.item_name] = event.value
                info["Titles"][event.title_number] = title
                # print("T", event)
            elif isinstance(event, events.StreamInfoEvent):
                title = info["Titles"].get(event.title_number, {"Streams": {}})
                info["Titles"][event.title_number] = title
                stream = title["Streams"].get(event.stream_number, {})
                stream[event.item_name] = event.value
                title["Streams"][event.stream_number] = stream
                # print("S", event)

        # now that we have everything, convert it to lists
        titles = []
        for t_index in sorted(info["Titles"].keys()):
            title = info["Titles"][t_index]
            streams = []
            for s_index in sorted(title["Streams"].keys()):
                stream = title["Streams"][s_index]
                streams.append(stream)
            title["Streams"] = streams
            titles.append(title)
        info["Titles"] = titles

        return info


class Device(Source):
    def __init__(self, path="/dev/cdrom/sr0"):
        self.device_path = pathlib.Path(path)
        super().__init__("dev", str(path))


class Iso(Source):
    def __init__(self, path):
        self.device_path = pathlib.Path(path)
        super().__init__("iso", str(path))


class File(Source):
    def __init__(self, path):
        self.device_path = pathlib.Path(path)
        super().__init__("file", str(path))


class Disc(Source):
    def __init__(self, disc_id):
        super().__init__("disc", disc_id)


Image = Iso  # Because I think the name Image (the file type) makes more sense than Iso (the specific file extension)
