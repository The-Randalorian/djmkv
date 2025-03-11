import re
import enum

# This is just a hacky script to find the various constant values from the appropriate linux header file. The better way
# to do this would be to make a small C file with all of those defines available as python variables, but figuring out
# how to set that up would take me way longer than this.

# first a few defaults from the kernel (loading from the specific h file is better, but this is a fallback)
CDROMEJECT = 21257
CDROMCLOSETRAY = 21273
CDROM_DRIVE_STATUS = 21286
CDROM_DISC_STATUS = 21287
CDROM_LOCKDOOR = 21289
CDS_NO_INFO = 0
CDS_NO_DISC = 1
CDS_TRAY_OPEN = 2
CDS_DRIVE_NOT_READY = 3
CDS_DISC_OK = 4

# We'll use a few different patterns to make sure we get them all.
hex_pattern = re.compile(r"#define\W+(?P<key>\w+)\W+0x(?P<value>[\da-fA-F]+)")
binary_pattern = re.compile(r"#define\W+(?P<key>\w+)\W+0b(?P<value>[\da-fA-F]+)")
decimal_pattern = re.compile(r"#define\W+(?P<key>\w+)\W+(?P<value>\d+)")

# We'll toss them in a few different data structures depending on what we want to use.
ioctl_values = {
    "CDROMEJECT": CDROMEJECT,
    "CDROMCLOSETRAY": CDROMCLOSETRAY,
    "CDROM_DRIVE_STATUS": CDROM_DRIVE_STATUS,
    "CDROM_DISC_STATUS": CDROM_DISC_STATUS,
    "CDROM_LOCKDOOR": CDROM_LOCKDOOR,
    "CDS_NO_INFO": CDS_NO_INFO,
    "CDS_NO_DISC": CDS_NO_DISC,
    "CDS_TRAY_OPEN": CDS_TRAY_OPEN,
    "CDS_DRIVE_NOT_READY": CDS_DRIVE_NOT_READY,
    "CDS_DISC_OK": CDS_DISC_OK,
}
ioctl: enum.IntEnum = enum.IntEnum(
    "IOCTL", ((key, value) for key, value in ioctl_values.items())
)


def add_ioctl(key, value):
    ioctl_values[key] = value
    globals()[key] = value


def load_ioctl(path: str):
    global ioctl_values, ioctl
    ioctl_values = {}
    with open(path) as f:
        for line in f:
            match = hex_pattern.match(line)
            if match:
                add_ioctl(match.group("key"), int(match.group("value"), 16))
                continue
            match = binary_pattern.match(line)
            if match:
                add_ioctl(match.group("key"), int(match.group("value"), 2))
                continue
            match = decimal_pattern.match(line)
            if match:
                add_ioctl(match.group("key"), int(match.group("value"), 10))
                continue
    ioctl = enum.IntEnum("IOCTL", ((key, value) for key, value in ioctl_values.items()))


load_ioctl("/usr/include/linux/cdrom.h")  # We'll auto generate them

if __name__ == "__main__":
    for key, value in ioctl_values.items():
        print(key, value)
