from pathlib import Path
import re


RELEASE_VERSION_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9])$")


def validate_release_version(value: str) -> str:
    version = str(value or "").strip().removeprefix("v").removeprefix("V")
    if not RELEASE_VERSION_PATTERN.fullmatch(version):
        raise ValueError("Release version must use X.Y.Z and the final Z segment must be between 0 and 9")
    return version


def get_release_version() -> str:
    version_file = Path(__file__).resolve().parents[1] / "VERSION"
    try:
        return validate_release_version(version_file.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return "0.0.0"


APP_RELEASE = get_release_version()
