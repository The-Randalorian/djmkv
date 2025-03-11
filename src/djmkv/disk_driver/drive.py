import asyncio
import collections
import enum
import errno
import fcntl
import os
import pathlib
from contextlib import asynccontextmanager

try:
    from . import cdrom, sources
except ModuleNotFoundError:
    import cdrom, sources


DEFAULT_POLLING_PERIOD = 0.5


class Status(enum.IntEnum):
    CDS_NO_INFO = cdrom.CDS_NO_INFO
    CDS_NO_DISC = cdrom.CDS_NO_DISC
    CDS_TRAY_OPEN = cdrom.CDS_TRAY_OPEN
    CDS_DRIVE_NOT_READY = cdrom.CDS_DRIVE_NOT_READY
    CDS_DISC_OK = cdrom.CDS_DISC_OK


class Drive:
    def __init__(
        self, device_path: pathlib.Path, polling_period=DEFAULT_POLLING_PERIOD
    ):
        self.device_path = device_path
        self.polling_period = polling_period
        self.makemkv_source = sources.Device(self.device_path)
        self.lock = self.makemkv_source.lock  # use the same lock as the makemkv thing

    async def run_ioctl(self, request, arg=0, mutate_flag=True):
        result = -1
        async with self.lock:
            # try:
            fd = os.open(self.device_path, os.O_RDWR | os.O_EXCL | os.O_NONBLOCK)
            while True:
                try:
                    result = await asyncio.to_thread(
                        fcntl.ioctl,
                        fd,
                        request,
                        arg,
                        mutate_flag,
                    )
                    break
                except OSError as e:
                    if e.errno == errno.EBUSY:
                        await asyncio.sleep(0.1)
                        continue
                    raise e
            # except OSError as e:
            # finally:
            os.close(fd)
        return result

    async def get_status(self):
        return await self.run_ioctl(cdrom.CDROM_DRIVE_STATUS)

    async def get_uuid(self) -> str:
        await self.wait_disc_ok()
        process = await asyncio.create_subprocess_exec(
            "blkid",
            "-s",
            "UUID",
            "-o",
            "value",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, stderr = await process.communicate()
        return stdout.decode().strip()

    async def get_name(self) -> str:
        await self.wait_disc_ok()
        process = await asyncio.create_subprocess_exec(
            "blkid",
            "-s",
            "LABEL",
            "-o",
            "value",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, stderr = await process.communicate()
        return stdout.decode().strip()

    async def set_door_lock(self, locked: bool | int):
        if locked:
            locked = 1
        else:
            locked = 0
        await self.run_ioctl(cdrom.CDROM_LOCKDOOR, locked)

    async def lock_door(self):
        await self.set_door_lock(locked=1)

    async def unlock_door(self):
        await self.set_door_lock(locked=0)

    @asynccontextmanager
    async def locked_door(self):
        await self.lock_door()
        try:
            yield
        finally:
            await self.unlock_door()

    async def open_tray(self):
        await self.unlock_door()
        await self.run_ioctl(cdrom.CDROMEJECT)

    async def close_tray(self):
        await self.run_ioctl(cdrom.CDROMCLOSETRAY)

    async def wait_for_state(self, states: collections.abc.Set | int, invert=False):
        while True:
            if await self.is_in_state(states, invert):
                return
            await asyncio.sleep(self.polling_period)

    async def is_in_state(self, states: collections.abc.Set | int, invert=False):
        if not isinstance(
            states, collections.abc.Set
        ):  # make sure it's a set of states
            states = {states}  # if it's not, make it so number 1 :P
        status = await self.get_status()
        return (status in states) ^ invert

    async def is_disc_ok(self):
        return await self.is_in_state({Status.CDS_DISC_OK})

    async def wait_disc_ok(self):
        await self.wait_for_state({Status.CDS_DISC_OK})

    async def wait_disk_not_ok(self):
        await self.wait_for_state({Status.CDS_DISC_OK}, invert=True)

    async def is_tray_open(self):
        return await self.is_in_state({Status.CDS_TRAY_OPEN})

    async def wait_tray_opened(self):
        await self.wait_for_state({Status.CDS_TRAY_OPEN})

    async def wait_tray_closed(self):
        await self.wait_for_state({Status.CDS_TRAY_OPEN}, invert=True)

    async def is_disc_ready(self):
        return await self.is_in_state({Status.CDS_DISC_OK, Status.CDS_NO_DISC})

    async def wait_disc_ready(self):
        await self.wait_for_state({Status.CDS_DISC_OK, Status.CDS_NO_DISC})

    async def wait_disk_not_ready(self):
        await self.wait_for_state({Status.CDS_DISC_OK, Status.CDS_NO_DISC}, invert=True)

    async def wait_tray_cycle(self):
        await self.wait_tray_opened()
        await self.wait_tray_closed()

    async def cycle(self, autoclose=False):
        await self.open_tray()
        await self.wait_tray_opened()
        if autoclose:
            await self.close_tray()
        await self.wait_tray_closed()


if __name__ == "__main__":
    drive = Drive(pathlib.Path("/dev/cdrom/sr0"))
    asyncio.run(drive.cycle(True))
    print("Drive cycled")
