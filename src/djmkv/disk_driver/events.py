import datetime
import enum


class BaseEvent:
    def __init__(self, *_):
        pass

    @classmethod
    def parse(cls, raw_string="") -> "BaseEvent":
        # remove stuff before the : if it's present
        raw_string = raw_string.split(":", maxsplit=1)[-1]
        raw_params = raw_string.split(",")
        # print(cls, raw_params, flush=True)
        return cls(*raw_params)


class UnknownEvent(BaseEvent):
    def __init__(self, *parameters):
        super().__init__()
        self.parameters = parameters


class StartEvent(BaseEvent):
    def __init__(self, command_number):
        super().__init__()
        self.command_number = command_number


class StopEvent(BaseEvent):
    def __init__(self, command_number):
        super().__init__()
        self.command_number = command_number


class MessageEvent(BaseEvent):
    def __init__(self, code, flags, count, message, format_code, *parameters):
        super().__init__()
        self.code = code
        self.flags = flags
        self.count = count
        self.message = message.strip('"')
        self.format_code = format_code.strip('"')
        self.parameters = [parameter.strip('"') for parameter in parameters]

    def __repr__(self):
        return f"{self.__class__.__name__}({self.code}, {self.flags}, {self.count}, {self.message}, {self.format_code})"


class ProgressCurrentEvent(BaseEvent):
    def __init__(self, code, operation_id, name):
        super().__init__()
        self.code = code
        self.operation_id = operation_id
        self.name = name.strip('"')


class ProgressTotalEvent(BaseEvent):
    def __init__(self, code, operation_id, name):
        super().__init__()
        self.code = code
        self.operation_id = operation_id
        self.name = name.strip('"')


class ProgressValueEvent(BaseEvent):
    def __init__(self, current, total, limit):
        super().__init__()
        self.current = int(current)
        self.total = int(total)
        self.limit = int(limit)
        self.current_fraction = self.current / self.limit
        self.total_fraction = self.total / self.limit

    def __repr__(self):
        return f"{self.__class__.__name__}({self.current}, {self.total}, {self.limit})"


class DriveScanEvent(BaseEvent):
    def __init__(
        self, index, visible, enabled, flags, drive_name, disc_name, unknown_string
    ):
        super().__init__()
        self.index = index
        self.visible = visible
        self.enabled = enabled
        self.flags = flags
        self.drive_name = drive_name
        self.disc_name = disc_name
        self.unknown_string = unknown_string


class TitleCountEvent(BaseEvent):
    def __init__(self, count):
        super().__init__()
        self.count = count


class ItemAttribute(enum.Enum):
    Unknown = 0
    Type = 1
    Name = 2
    LangCode = 3
    LangName = 4
    CodecId = 5
    CodecShort = 6
    CodecLong = 7
    ChapterCount = 8
    Duration = 9
    DiskSize = 10
    DiskSizeBytes = 11
    StreamTypeExtension = 12
    Bitrate = 13
    AudioChannelsCount = 14
    AngleInfo = 15
    SourceFileName = 16
    AudioSampleRate = 17
    AudioSampleSize = 18
    VideoSize = 19
    VideoAspectRatio = 20
    VideoFrameRate = 21
    StreamFlags = 22
    DateTime = 23
    OriginalTitleId = 24
    SegmentsCount = 25
    SegmentsMap = 26
    OutputFileName = 27
    MetadataLanguageCode = 28
    MetadataLanguageName = 29
    TreeInfo = 30
    PanelTitle = 31
    VolumeName = 32
    OrderWeight = 33
    OutputFormat = 34
    OutputFormatDescription = 35
    SeamlessInfo = 36
    PanelText = 37
    MkvFlags = 38
    MkvFlagsText = 39
    AudioChannelLayoutName = 40
    OutputCodecShort = 41
    OutputConversionType = 42
    OutputAudioSampleRate = 43
    OutputAudioSampleSize = 44
    OutputAudioChannelsCount = 45
    OutputAudioChannelLayoutName = 46
    OutputAudioChannelLayout = 47
    OutputAudioMixDescription = 48
    Comment = 49
    OffsetSequenceId = 50


class InfoEvent(BaseEvent):
    def __init__(self, item_id, code, *values):
        super().__init__()
        self.item_id = int(item_id)
        self.item_name = ItemAttribute(self.item_id).name
        self.code = int(code)
        self.values = [value.strip('"') for value in values]
        self.raw_value = (",".join(self.values)).strip('"')
        match ItemAttribute(self.item_id):
            case (
                ItemAttribute.OrderWeight
                | ItemAttribute.SegmentsCount
                | ItemAttribute.DiskSizeBytes
                | ItemAttribute.AudioChannelsCount
                | ItemAttribute.AudioSampleRate
                | ItemAttribute.AudioSampleSize
                | ItemAttribute.StreamFlags
                | ItemAttribute.ChapterCount
            ):
                self.value = int(self.raw_value)
            case ItemAttribute.Duration:
                hours, minutes, seconds = self.raw_value.split(":")
                hours, minutes, seconds = int(hours), int(minutes), float(seconds)
                self.value = datetime.timedelta(
                    hours=hours, minutes=minutes, seconds=seconds
                )
            case _:
                self.value = self.raw_value

    def __repr__(self):
        return f"{self.__class__.__name__}(ItemAttribute.{self.item_name}, {self.code}, {repr(self.value)})"


class DiscInfoEvent(InfoEvent):
    def __init__(self, item_id, code, *values):
        super().__init__(item_id, code, *values)


class TitleInfoEvent(InfoEvent):
    def __init__(self, title_number, item_id, code, *values):
        super().__init__(item_id, code, *values)
        self.title_number = int(title_number)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.title_number}, ItemAttribute.{self.item_name}, {self.code}, {repr(self.value)})"


class StreamInfoEvent(InfoEvent):
    def __init__(self, title_number, stream_number, item_id, code, *values):
        super().__init__(item_id, code, *values)
        self.title_number = int(title_number)
        self.stream_number = int(stream_number)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.title_number}, {self.stream_number}, ItemAttribute.{self.item_name}, {self.code}, {repr(self.value)})"


def get_event(raw_string) -> BaseEvent | None:
    message_type = raw_string.split(":", maxsplit=1)[0].upper().strip()
    match message_type:
        case "MSG":
            return MessageEvent.parse(raw_string)
        case "PRGC":
            return ProgressCurrentEvent.parse(raw_string)
        case "PRGT":
            return ProgressTotalEvent.parse(raw_string)
        case "PRGV":
            return ProgressValueEvent.parse(raw_string)
        case "DRV":
            return DriveScanEvent.parse(raw_string)
        case "TCOUT":
            return TitleCountEvent.parse(raw_string)
        case "CINFO":
            return DiscInfoEvent.parse(raw_string)
        case "TINFO":
            return TitleInfoEvent.parse(raw_string)
        case "SINFO":
            return StreamInfoEvent.parse(raw_string)
        case _:
            if len(raw_string.strip()) <= 0:
                return None
            return UnknownEvent.parse(raw_string)
