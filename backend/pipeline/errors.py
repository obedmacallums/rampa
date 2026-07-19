"""Stage failures carry a machine code that maps to an i18n message key."""

FAILURE_CODES = {
    "unsupported_format",
    "unreadable_file",
    "missing_crs",
    "internal_error",
}


class StageError(Exception):
    def __init__(self, code: str, detail: str = ""):
        assert code in FAILURE_CODES, code
        self.code = code
        self.message_key = f"errors.{code}"
        super().__init__(f"{code}: {detail}")
