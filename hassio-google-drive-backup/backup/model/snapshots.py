
from datetime import datetime, timedelta
from typing import Dict, Optional
from dateutil.tz import tzutc
from ..util import Estimator

from ..const import SOURCE_GOOGLE_DRIVE, SOURCE_HA
from ..logger import getLogger

logger = getLogger(__name__)

PROP_KEY_SLUG = "snapshot_slug"
PROP_KEY_DATE = "snapshot_date"
PROP_KEY_NAME = "snapshot_name"
PROP_TYPE = "type"
PROP_VERSION = "version"
PROP_PROTECTED = "protected"
PROP_RETAINED = "retained"

DRIVE_KEY_TEXT = "Google Drive's snapshot metadata"
HA_KEY_TEXT = "Home Assistant's snapshot metadata"


class AbstractSnapshot():
    def __init__(self, name: str, slug: str, source: str, date: str, size: int, version: str, snapshotType: str, protected: bool, retained: bool = False, uploadable: bool = False, details={}):
        self._options = None
        self._name = name
        self._slug = slug
        self._source = source
        self._date = date
        self._size = size
        self._retained = retained
        self._uploadable = uploadable
        self._details = details
        self._version = version
        self._snapshotType = snapshotType
        self._protected = protected

    def setOptions(self, options):
        self._options = options

    def getOptions(self):
        return self._options

    def name(self) -> str:
        return self._name

    def slug(self) -> str:
        return self._slug

    def size(self) -> int:
        return self._size

    def sizeInt(self) -> int:
        try:
            return int(self.size())
        except ValueError:
            return 0

    def date(self) -> datetime:
        return self._date

    def source(self) -> str:
        return self._source

    def retained(self) -> str:
        return self._retained

    def version(self):
        return self._version

    def snapshotType(self):
        return self._snapshotType

    def protected(self):
        return self._protected

    def setRetained(self, retained):
        self._retained = retained

    def uploadable(self) -> bool:
        return self._uploadable

    def considerForPurge(self) -> bool:
        return not self.retained()

    def setUploadable(self, uploadable):
        self._uploadable = uploadable

    def details(self):
        return self._details

    def status(self):
        return None


class Snapshot(object):
    """
    Represents a Home Assistant snapshot stored on Google Drive, locally in
    Home Assistant, or a pending snapshot we expect to see show up later
    """

    def __init__(self, snapshot: Optional[AbstractSnapshot] = None):
        self.sources: Dict[str, AbstractSnapshot] = {}
        self._purgeNext: Dict[str, bool] = {}
        self._options = None
        self._status_override = None
        self._status_override_args = None
        self._state_detail = None
        self._upload_source = None
        self._upload_source_name = None
        self._upload_fail_info = None
        if snapshot is not None:
            self.addSource(snapshot)

    def setOptions(self, options):
        self._options = options

    def getOptions(self):
        return self._options

    def updatePurge(self, source: str, purge: bool):
        self._purgeNext[source] = purge

    def addSource(self, snapshot: AbstractSnapshot):
        self.sources[snapshot.source()] = snapshot
        if snapshot.getOptions() and not self.getOptions():
            self.setOptions(snapshot.getOptions())

    def getStatusDetail(self):
        return self._state_detail

    def setStatusDetail(self, info):
        self._state_detail = info

    def removeSource(self, source):
        if source in self.sources:
            del self.sources[source]
        if source in self._purgeNext:
            del self._purgeNext[source]

    def getPurges(self):
        return self._purgeNext

    def uploadInfo(self):
        if not self._upload_source:
            return {}
        elif self._upload_source.progress() == 100:
            return {}
        else:
            return {
                'progress': self._upload_source.progress()
            }

    def getSource(self, source: str):
        return self.sources.get(source, None)

    def name(self):
        for snapshot in self.sources.values():
            return snapshot.name()
        return "error"

    def slug(self) -> str:
        for snapshot in self.sources.values():
            return snapshot.slug()
        return "error"

    def size(self) -> int:
        for snapshot in self.sources.values():
            return snapshot.size()
        return 0

    def sizeInt(self) -> int:
        for snapshot in self.sources.values():
            return snapshot.sizeInt()
        return 0

    def snapshotType(self) -> str:
        for snapshot in self.sources.values():
            return snapshot.snapshotType()
        return "error"

    def version(self) -> str:
        for snapshot in self.sources.values():
            if snapshot.version() is not None:
                return snapshot.version()
        return None

    def details(self):
        for snapshot in self.sources.values():
            if snapshot.details() is not None:
                return snapshot.details()
        return {}

    def getUploadInfo(self, time):
        if self._upload_source_name is None:
            return None
        ret = {
            'name': self._upload_source_name
        }
        if self._upload_fail_info:
            ret['failure'] = self._upload_fail_info
        elif self._upload_source is not None:
            ret['progress'] = self._upload_source.progress()
            ret['speed'] = self._upload_source.speed(timedelta(seconds=20))
            ret['total'] = self._upload_source.position()
            ret['started'] = time.formatDelta(self._upload_source.startTime())
        return ret

    def protected(self) -> bool:
        for snapshot in self.sources.values():
            return snapshot.protected()
        return False

    def date(self) -> datetime:
        for snapshot in self.sources.values():
            return snapshot.date()
        return datetime.now(tzutc())

    def sizeString(self) -> str:
        size_string = self.size()
        if type(size_string) == str:
            return size_string
        return Estimator.asSizeString(size_string)

    def status(self) -> str:
        if self._status_override is not None:
            return self._status_override.format(*self._status_override_args)

        for snapshot in self.sources.values():
            status = snapshot.status()
            if status:
                return status

        inDrive = self.getSource(SOURCE_GOOGLE_DRIVE) is not None
        inHa = self.getSource(SOURCE_HA) is not None

        if inDrive and inHa:
            return "Backed Up"
        if inDrive:
            return "Drive Only"
        if inHa:
            return "HA Only"
        return "Deleted"

    def isDeleted(self) -> bool:
        return len(self.sources) == 0

    def overrideStatus(self, format, *args) -> None:
        self._status_override = format
        self._status_override_args = args

    def setUploadSource(self, source_name: str, source):
        self._upload_source = source
        self._upload_source_name = source_name
        self._upload_fail_info = None

    def clearUploadSource(self):
        self._upload_source = None
        self._upload_source_name = None
        self._upload_fail_info = None

    def uploadFailure(self, info):
        self._upload_source = None
        self._upload_fail_info = info

    def clearStatus(self):
        self._status_override = None
        self._status_override_args = None

    def __str__(self) -> str:
        return "<Slug: {0} {1} {2}>".format(self.slug(), " ".join(self.sources), self.date().isoformat())

    def __format__(self, format_spec: str) -> str:
        return self.__str__()

    def __repr__(self) -> str:
        return self.__str__()
