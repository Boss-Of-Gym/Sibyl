import re
from typing import Literal

from sibyl.dependency_analysis.domain.models import PackageChange

Severity = Literal["breaking", "non_breaking", "unknown"]

_LEADING_VERSION = re.compile(r"^v?(\d+)")


def _leading_major(version: str) -> int | None:
    match = _LEADING_VERSION.match(version)
    if match is None:
        return None
    return int(match.group(1))


def classify_version_change(old_version: str, new_version: str) -> Severity:
    old_major = _leading_major(old_version)
    new_major = _leading_major(new_version)
    if old_major is None or new_major is None:
        return "unknown"
    return "breaking" if old_major != new_major else "non_breaking"


def diff_packages(
    old_packages: list[dict[str, object]], new_packages: list[dict[str, object]]
) -> list[PackageChange]:
    old_by_name = {str(p["name"]): str(p["version"]) for p in old_packages}
    new_by_name = {str(p["name"]): str(p["version"]) for p in new_packages}

    changes: list[PackageChange] = []
    for name in sorted(set(old_by_name) | set(new_by_name)):
        old_version = old_by_name.get(name)
        new_version = new_by_name.get(name)

        if old_version is None:
            changes.append(
                PackageChange(
                    name=name,
                    change_type="added",
                    old_version=None,
                    new_version=new_version,
                    severity="non_breaking",
                )
            )
        elif new_version is None:
            changes.append(
                PackageChange(
                    name=name,
                    change_type="removed",
                    old_version=old_version,
                    new_version=None,
                    severity="breaking",
                )
            )
        elif old_version != new_version:
            changes.append(
                PackageChange(
                    name=name,
                    change_type="version_changed",
                    old_version=old_version,
                    new_version=new_version,
                    severity=classify_version_change(old_version, new_version),
                )
            )

    return changes
