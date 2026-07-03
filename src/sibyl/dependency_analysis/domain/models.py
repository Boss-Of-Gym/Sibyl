from typing import Literal

from pydantic import BaseModel


class DependencyPackage(BaseModel):
    name: str
    version: str
    direct: bool


class DependencyManifestReport(BaseModel):
    repository: str
    commit_sha: str
    ecosystem: str
    packages: list[DependencyPackage]


class PackageChange(BaseModel):
    name: str
    change_type: Literal["added", "removed", "version_changed"]
    old_version: str | None
    new_version: str | None
    severity: Literal["breaking", "non_breaking", "unknown"]
