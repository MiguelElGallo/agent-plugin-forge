from __future__ import annotations

import ipaddress
import re
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from .common import parse_semver, validate_name, validate_spdx_expression

MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
HTTP_FIELD_NAME_RE = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IMMUTABLE_REVISION_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64}|sha256:[0-9a-f]{64})$")

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
OpaqueNonEmptyStr = Annotated[str, StringConstraints(min_length=1)]
MarketplaceDescription = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1024)
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, validate_default=True)


class MarketplaceOwner(StrictModel):
    name: NonEmptyStr
    email: NonEmptyStr


class MarketplaceMetadata(StrictModel):
    name: NonEmptyStr
    display_name: NonEmptyStr = Field(alias="displayName")
    owner: MarketplaceOwner
    description: MarketplaceDescription
    version: NonEmptyStr

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        validate_name(value, kind="skill")
        return value

    @field_validator("version")
    @classmethod
    def version_is_semver(cls, value: str) -> str:
        parse_semver(value, label="Marketplace version")
        return value


class CatalogPlugin(StrictModel):
    name: NonEmptyStr
    category: NonEmptyStr
    codex_compatibility: bool = Field(alias="codexCompatibility")

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        validate_name(value, kind="plugin")
        return value


class Catalog(StrictModel):
    marketplace: MarketplaceMetadata
    plugins: list[CatalogPlugin]

    @model_validator(mode="after")
    def unique_plugins(self) -> Catalog:
        names = [plugin.name for plugin in self.plugins]
        duplicate = next((name for name in names if names.count(name) > 1), None)
        if duplicate is not None:
            raise ValueError(f"duplicate catalog plugin: {duplicate}")
        return self


class CopilotMarketplaceMetadata(StrictModel):
    description: MarketplaceDescription
    version: NonEmptyStr


class CopilotMarketplacePlugin(StrictModel):
    name: NonEmptyStr
    description: MarketplaceDescription
    version: NonEmptyStr
    source: NonEmptyStr

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        validate_name(value, kind="plugin")
        return value


class CopilotMarketplace(StrictModel):
    name: NonEmptyStr
    owner: MarketplaceOwner
    metadata: CopilotMarketplaceMetadata
    plugins: list[CopilotMarketplacePlugin]

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        validate_name(value, kind="skill")
        return value


class CodexMarketplaceSource(StrictModel):
    source: Literal["local"]
    path: NonEmptyStr


class CodexMarketplacePolicy(StrictModel):
    installation: Literal["AVAILABLE"]
    authentication: Literal["ON_INSTALL"]


class CodexMarketplacePlugin(StrictModel):
    name: NonEmptyStr
    source: CodexMarketplaceSource
    policy: CodexMarketplacePolicy
    category: NonEmptyStr

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        validate_name(value, kind="plugin")
        return value


class CodexMarketplaceInterface(StrictModel):
    display_name: NonEmptyStr = Field(alias="displayName")


class CodexMarketplace(StrictModel):
    name: NonEmptyStr
    interface: CodexMarketplaceInterface
    plugins: list[CodexMarketplacePlugin]

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        validate_name(value, kind="skill")
        return value


class PortableAuthor(StrictModel):
    name: str | None = None
    email: str | None = None
    url: str | None = None


class PortableManifest(StrictModel):
    schema_: Literal["https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"] = Field(
        alias="$schema"
    )
    name: NonEmptyStr
    version: str | None = None
    description: str | None = None
    author: PortableAuthor | None = None
    homepage: str | None = None
    repository: str | None = None
    license: str | None = None
    keywords: list[str] | None = None
    extensions: dict[str, dict[str, Any]] | None = None

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        validate_name(value, kind="plugin")
        return value

    @field_validator("version")
    @classmethod
    def valid_version(cls, value: str | None) -> str | None:
        if value is not None:
            parse_semver(value, label="Plugin version")
        return value

    @field_validator("license")
    @classmethod
    def valid_license(cls, value: str | None) -> str | None:
        if value is not None:
            validate_spdx_expression(value, label="Plugin license")
        return value


def _safe_relative_parts(value: str, *, prefix: str) -> bool:
    suffix = value.removeprefix(prefix)
    if not suffix:
        return True
    if suffix.startswith("/"):
        suffix = suffix[1:]
    path = PurePosixPath(suffix)
    return not path.is_absolute() and ".." not in path.parts and "\\" not in suffix


class StdioServer(StrictModel):
    type: Literal["stdio"]
    command: OpaqueNonEmptyStr
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: str | None = None

    @field_validator("command")
    @classmethod
    def command_is_one_safe_token(cls, value: str) -> str:
        if "\x00" in value or "\n" in value or "\r" in value:
            raise ValueError("command must be one executable token")
        if value.startswith("./"):
            if not _safe_relative_parts(value, prefix="./") or value in {"./", "./."}:
                raise ValueError("plugin-relative command must remain inside the plugin root")
            return value
        if (
            "/" in value
            or "\\" in value
            or value in {".", ".."}
            or any(character.isspace() for character in value)
        ):
            raise ValueError("command must be a bare executable name or start with './'")
        return value

    @field_validator("env")
    @classmethod
    def environment_does_not_override_roots(cls, value: dict[str, str]) -> dict[str, str]:
        reserved = {"plugin_root", "plugin_data"}
        invalid = sorted(name for name in value if name.casefold() in reserved)
        if invalid:
            raise ValueError(f"environment cannot override client variables: {invalid}")
        return value

    @field_validator("cwd")
    @classmethod
    def cwd_is_contained(cls, value: str | None) -> str | None:
        if value is None:
            return value
        prefixes = ("./", "${PLUGIN_ROOT}", "${PLUGIN_DATA}")
        prefix = next(
            (item for item in prefixes if value == item or value.startswith(f"{item}/")),
            None,
        )
        if prefix is None or not _safe_relative_parts(value, prefix=prefix):
            raise ValueError("cwd must stay under './', '${PLUGIN_ROOT}', or '${PLUGIN_DATA}'")
        return value


def _validate_remote_url(value: str) -> str:
    if any(
        character.isspace() or ord(character) < 0x20 or ord(character) == 0x7F
        for character in value
    ):
        raise ValueError("url must not contain whitespace or control characters")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.hostname is None:
        raise ValueError("url must be an absolute HTTP or HTTPS URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("url must not contain user information")
    if parsed.fragment:
        raise ValueError("url must not contain a fragment")
    try:
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("url must contain a valid TCP port") from exc
    if parsed.scheme == "http":
        host = parsed.hostname
        loopback = host == "localhost"
        if not loopback:
            try:
                loopback = ipaddress.ip_address(host).is_loopback
            except ValueError:
                loopback = False
        if not loopback:
            raise ValueError("non-loopback MCP endpoints must use HTTPS")
    return value


def _validate_headers(value: dict[str, str]) -> dict[str, str]:
    folded: dict[str, str] = {}
    credential_headers = {"authorization", "proxy-authorization", "cookie", "x-api-key"}
    for name, item in value.items():
        if not HTTP_FIELD_NAME_RE.fullmatch(name):
            raise ValueError(f"invalid HTTP header name: {name!r}")
        normalized = name.casefold()
        if normalized in folded:
            raise ValueError(
                f"duplicate case-insensitive HTTP header: {folded[normalized]!r}/{name!r}"
            )
        if normalized in credential_headers:
            raise ValueError(f"credentials must not be embedded in MCP header {name!r}")
        if any(character in item for character in ("\x00", "\r", "\n")) or any(
            (ord(character) < 0x20 and character != "\t") or ord(character) == 0x7F
            for character in item
        ):
            raise ValueError(f"invalid HTTP header value for {name!r}")
        folded[normalized] = name
    return value


class StreamableHttpServer(StrictModel):
    type: Literal["streamable-http"]
    url: OpaqueNonEmptyStr
    headers: dict[str, str] = Field(default_factory=dict)

    _url_validator = field_validator("url")(_validate_remote_url)
    _headers_validator = field_validator("headers")(_validate_headers)


class SseServer(StrictModel):
    type: Literal["sse"]
    url: OpaqueNonEmptyStr
    headers: dict[str, str] = Field(default_factory=dict)

    _url_validator = field_validator("url")(_validate_remote_url)
    _headers_validator = field_validator("headers")(_validate_headers)


McpServer = Annotated[StdioServer | StreamableHttpServer | SseServer, Field(discriminator="type")]


class McpConfiguration(StrictModel):
    schema_: Literal["https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"] = Field(
        alias="$schema"
    )
    mcp_servers: dict[str, McpServer] = Field(alias="mcpServers")


class LicenseEvidence(StrictModel):
    path: NonEmptyStr
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("path")
    @classmethod
    def contained_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "\\" in value:
            raise ValueError("license evidence path must stay inside the plugin")
        return value


class ProvenanceRecord(StrictModel):
    skill: NonEmptyStr
    origin: NonEmptyStr
    revision: NonEmptyStr
    source_subpath: NonEmptyStr = Field(alias="sourceSubpath")
    imported_at: date = Field(alias="importedAt")
    license: NonEmptyStr
    license_evidence: LicenseEvidence = Field(alias="licenseEvidence")
    content_sha256: str = Field(alias="contentSha256", pattern=r"^[0-9a-f]{64}$")
    files: dict[str, str]
    file_modes: dict[str, bool] = Field(default_factory=dict, alias="fileModes")
    transformations: list[str]

    @field_validator("skill")
    @classmethod
    def valid_skill_name(cls, value: str) -> str:
        validate_name(value, kind="skill")
        return value

    @field_validator("revision")
    @classmethod
    def immutable_revision(cls, value: str) -> str:
        if IMMUTABLE_REVISION_RE.fullmatch(value) is None:
            raise ValueError("revision must be a full commit/tree ID or sha256:<digest>")
        return value

    @field_validator("source_subpath")
    @classmethod
    def contained_source_subpath(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "\\" in value:
            raise ValueError("sourceSubpath must be a contained POSIX path")
        return value

    @model_validator(mode="after")
    def valid_file_hashes(self) -> ProvenanceRecord:
        for path_text, digest in self.files.items():
            path = PurePosixPath(path_text)
            if path.is_absolute() or ".." in path.parts or "\\" in path_text:
                raise ValueError(f"provenance file path escapes the skill: {path_text}")
            if SHA256_RE.fullmatch(digest) is None:
                raise ValueError(f"invalid provenance SHA-256 for {path_text}")
        if self.file_modes and set(self.file_modes) != set(self.files):
            raise ValueError("provenance fileModes keys must match files keys")
        validate_spdx_expression(self.license, label="Provenance license")
        return self


class ImportRequest(StrictModel):
    plugin: NonEmptyStr
    source: Path
    source_skill: str | None = None
    origin: NonEmptyStr
    revision: NonEmptyStr
    source_subpath: NonEmptyStr
    license_id: NonEmptyStr
    license_file: Path
    imported_at: date
    category: NonEmptyStr | None = None
    version: str | None = None
    description: NonEmptyStr | None = None
    author: NonEmptyStr | None = None
    transformations: tuple[str, ...] = ()
    expected_sha256: str | None = None

    @field_validator("plugin")
    @classmethod
    def valid_plugin_name(cls, value: str) -> str:
        validate_name(value, kind="plugin")
        return value

    @field_validator("source_skill")
    @classmethod
    def valid_source_skill(cls, value: str | None) -> str | None:
        if value is not None:
            validate_name(value, kind="skill")
        return value

    @field_validator("revision")
    @classmethod
    def immutable_revision(cls, value: str) -> str:
        if IMMUTABLE_REVISION_RE.fullmatch(value) is None:
            raise ValueError("revision must be a full commit/tree ID or sha256:<digest>")
        return value

    @field_validator("source_subpath")
    @classmethod
    def contained_source_subpath(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "\\" in value:
            raise ValueError("source_subpath must be a contained POSIX path")
        return value

    @field_validator("license_id")
    @classmethod
    def valid_license(cls, value: str) -> str:
        return validate_spdx_expression(value, label="Imported license")

    @field_validator("version")
    @classmethod
    def valid_version(cls, value: str | None) -> str | None:
        if value is not None:
            parse_semver(value, label="Requested plugin version")
        return value


class ImportPlan(StrictModel):
    plugin: NonEmptyStr
    skill: NonEmptyStr
    source_kind: Literal["skill-directory", "skill-file", "plugin-skill"]
    destination: Path
    creates_plugin: bool
    file_count: int = Field(ge=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    license_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    license_destination: NonEmptyStr
    plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    files: dict[str, str]
    file_modes: dict[str, bool]
