from datetime import datetime, timedelta, timezone


class Clock:
    _offset = timedelta(0)

    @classmethod
    def now(cls):
        # naive UTC, so it compares cleanly with MySQL DATETIME columns
        return datetime.now(timezone.utc).replace(tzinfo=None) + cls._offset

    @classmethod
    def advance(cls, **kwargs):
        """Tests only. Example: Clock.advance(minutes=16)"""
        cls._offset += timedelta(**kwargs)

    @classmethod
    def reset(cls):
        cls._offset = timedelta(0)