"""Define validated models for packages, marketplaces, provenance, and MCP."""

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
PROVENANCE_LOCAL_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
SCP_GIT_ORIGIN_RE = re.compile(r"(?:(?P<user>[^@/:]+)@)?(?P<host>[^/:]+):(?P<path>.+)")

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
OpaqueNonEmptyStr = Annotated[str, StringConstraints(min_length=1)]
MarketplaceDescription = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1024)
]


def normalize_provenance_origin(value: str) -> str:
    """Normalize and validate a credential-free immutable-source origin."""

    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("origin must not contain control characters")
    if "::" in value:
        raise ValueError("Git remote-helper origins are not supported")

    local = Path(value).expanduser()
    if local.is_absolute():
        return local.resolve().as_uri()

    if "://" not in value:
        scp = SCP_GIT_ORIGIN_RE.fullmatch(value)
        if scp:
            if "?" in value or "#" in value:
                raise ValueError("origin must not include a query or fragment")
            user = f"{scp.group('user')}@" if scp.group("user") else ""
            path = scp.group("path").lstrip("/")
            return f"ssh://{user}{scp.group('host')}/{path}"
        if PROVENANCE_LOCAL_ID_RE.fullmatch(value):
            return value
        raise ValueError("local origin must be an absolute path or a simple identifier")

    parsed = urlsplit(value)
    if parsed.scheme not in {"https", "ssh", "file"}:
        raise ValueError("origin must use HTTPS, SSH, scp-style SSH, file, or local identity")
    if parsed.password is not None or (
        parsed.scheme in {"https", "file"} and parsed.username is not None
    ):
        raise ValueError("origin URL must not embed credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("origin URL must not include a query or fragment")
    if parsed.scheme in {"https", "ssh"} and not parsed.hostname:
        raise ValueError("network origin must include a host")
    return value


class StrictModel(BaseModel):
    """Provide the closed, alias-aware base configuration for forge models."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, validate_default=True)


class MarketplaceOwner(StrictModel):
    """Describe the named owner of a generated marketplace."""

    name: NonEmptyStr
    email: NonEmptyStr


class MarketplaceMetadata(StrictModel):
    """Represent canonical metadata shared by generated marketplaces."""

    name: NonEmptyStr
    display_name: NonEmptyStr = Field(alias="displayName")
    owner: MarketplaceOwner
    description: MarketplaceDescription
    version: NonEmptyStr

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        """Validate the marketplace name against the skill-name form."""

        validate_name(value, kind="skill")
        return value

    @field_validator("version")
    @classmethod
    def version_is_semver(cls, value: str) -> str:
        """Require the marketplace version to use strict semantic versioning."""

        parse_semver(value, label="Marketplace version")
        return value


class CatalogPlugin(StrictModel):
    """Describe one portable plugin entry in the canonical catalog."""

    name: NonEmptyStr
    category: NonEmptyStr
    codex_compatibility: bool = Field(alias="codexCompatibility")

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        """Validate the catalog entry's portable plugin name."""

        validate_name(value, kind="plugin")
        return value


class Catalog(StrictModel):
    """Represent the canonical marketplace metadata and plugin entries."""

    marketplace: MarketplaceMetadata
    plugins: list[CatalogPlugin]

    @model_validator(mode="after")
    def unique_plugins(self) -> Catalog:
        """Reject duplicate plugin names in the canonical catalog."""

        names = [plugin.name for plugin in self.plugins]
        duplicate = next((name for name in names if names.count(name) > 1), None)
        if duplicate is not None:
            raise ValueError(f"duplicate catalog plugin: {duplicate}")
        return self


class CopilotMarketplaceMetadata(StrictModel):
    """Represent metadata emitted in the Copilot marketplace wrapper."""

    description: MarketplaceDescription
    version: NonEmptyStr


class CopilotMarketplacePlugin(StrictModel):
    """Represent one plugin entry in the generated Copilot marketplace."""

    name: NonEmptyStr
    description: MarketplaceDescription
    version: NonEmptyStr
    source: NonEmptyStr

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        """Validate the Copilot entry's portable plugin name."""

        validate_name(value, kind="plugin")
        return value


class CopilotMarketplace(StrictModel):
    """Represent the generated Copilot marketplace document."""

    name: NonEmptyStr
    owner: MarketplaceOwner
    metadata: CopilotMarketplaceMetadata
    plugins: list[CopilotMarketplacePlugin]

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        """Validate the Copilot marketplace name against the skill-name form."""

        validate_name(value, kind="skill")
        return value


class CodexMarketplaceSource(StrictModel):
    """Describe a local package source in a Codex marketplace entry."""

    source: Literal["local"]
    path: NonEmptyStr


class CodexMarketplacePolicy(StrictModel):
    """Describe Codex installation and authentication policy defaults."""

    installation: Literal["AVAILABLE"]
    authentication: Literal["ON_INSTALL"]


class CodexMarketplacePlugin(StrictModel):
    """Represent one plugin entry in the generated Codex marketplace."""

    name: NonEmptyStr
    source: CodexMarketplaceSource
    policy: CodexMarketplacePolicy
    category: NonEmptyStr

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        """Validate the Codex entry's portable plugin name."""

        validate_name(value, kind="plugin")
        return value


class CodexMarketplaceInterface(StrictModel):
    """Describe user-facing metadata for a Codex marketplace."""

    display_name: NonEmptyStr = Field(alias="displayName")


class CodexMarketplace(StrictModel):
    """Represent the generated Codex marketplace document."""

    name: NonEmptyStr
    interface: CodexMarketplaceInterface
    plugins: list[CodexMarketplacePlugin]

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        """Validate the Codex marketplace name against the skill-name form."""

        validate_name(value, kind="skill")
        return value


class PortableAuthor(StrictModel):
    """Describe optional author metadata in a portable plugin manifest."""

    name: str | None = None
    email: str | None = None
    url: str | None = None


class PortableManifest(StrictModel):
    """Represent the closed Agent Plugins 1.0 portable manifest."""

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
        """Validate the manifest's portable plugin name."""

        validate_name(value, kind="plugin")
        return value

    @field_validator("version")
    @classmethod
    def valid_version(cls, value: str | None) -> str | None:
        """Validate an optional manifest version as strict semantic versioning."""

        if value is not None:
            parse_semver(value, label="Plugin version")
        return value

    @field_validator("license")
    @classmethod
    def valid_license(cls, value: str | None) -> str | None:
        """Validate an optional manifest license as an SPDX expression."""

        if value is not None:
            validate_spdx_expression(value, label="Plugin license")
        return value


def _safe_relative_parts(value: str, *, prefix: str) -> bool:
    """Return whether a prefixed portable path stays beneath its root."""

    suffix = value.removeprefix(prefix)
    if not suffix:
        return True
    if suffix.startswith("/"):
        suffix = suffix[1:]
    path = PurePosixPath(suffix)
    return not path.is_absolute() and ".." not in path.parts and "\\" not in suffix


class StdioServer(StrictModel):
    """Represent a portable standard-input/output MCP server definition."""

    type: Literal["stdio"]
    command: OpaqueNonEmptyStr
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: str | None = None

    @field_validator("command")
    @classmethod
    def command_is_one_safe_token(cls, value: str) -> str:
        """Require a bare command or a contained plugin-relative executable."""

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
        """Reject environment variables that override client-provided roots."""

        reserved = {"plugin_root", "plugin_data"}
        invalid = sorted(name for name in value if name.casefold() in reserved)
        if invalid:
            raise ValueError(f"environment cannot override client variables: {invalid}")
        return value

    @field_validator("cwd")
    @classmethod
    def cwd_is_contained(cls, value: str | None) -> str | None:
        """Require an optional working directory to stay under a client root."""

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
    """Validate a credential-free remote MCP URL with loopback HTTP support."""

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
    """Validate MCP HTTP headers and reject embedded credentials or controls."""

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
    """Represent a streamable HTTP MCP server definition."""

    type: Literal["streamable-http"]
    url: OpaqueNonEmptyStr
    headers: dict[str, str] = Field(default_factory=dict)

    _url_validator = field_validator("url")(_validate_remote_url)
    _headers_validator = field_validator("headers")(_validate_headers)


class SseServer(StrictModel):
    """Represent a legacy server-sent-events MCP server definition."""

    type: Literal["sse"]
    url: OpaqueNonEmptyStr
    headers: dict[str, str] = Field(default_factory=dict)

    _url_validator = field_validator("url")(_validate_remote_url)
    _headers_validator = field_validator("headers")(_validate_headers)


McpServer = Annotated[StdioServer | StreamableHttpServer | SseServer, Field(discriminator="type")]


class McpConfiguration(StrictModel):
    """Represent a portable Agent Plugins 1.0 MCP configuration."""

    schema_: Literal["https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"] = Field(
        alias="$schema"
    )
    mcp_servers: dict[str, McpServer] = Field(alias="mcpServers")


class LicenseEvidence(StrictModel):
    """Bind distributed license evidence to its contained path and digest."""

    path: NonEmptyStr
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("path")
    @classmethod
    def contained_path(cls, value: str) -> str:
        """Require the license evidence path to remain inside its plugin."""

        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "\\" in value:
            raise ValueError("license evidence path must stay inside the plugin")
        return value


class ProvenanceRecord(StrictModel):
    """Record immutable origin, licensing, hashes, and modes for one skill."""

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
        """Validate the provenance record's Agent Skill name."""

        validate_name(value, kind="skill")
        return value

    @field_validator("origin")
    @classmethod
    def safe_origin(cls, value: str) -> str:
        """Normalize and validate the provenance source origin."""

        return normalize_provenance_origin(value)

    @field_validator("revision")
    @classmethod
    def immutable_revision(cls, value: str) -> str:
        """Require an immutable commit, tree, or content revision identifier."""

        if IMMUTABLE_REVISION_RE.fullmatch(value) is None:
            raise ValueError("revision must be a full commit/tree ID or sha256:<digest>")
        return value

    @field_validator("source_subpath")
    @classmethod
    def contained_source_subpath(cls, value: str) -> str:
        """Require the source subpath to remain relative and contained."""

        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "\\" in value:
            raise ValueError("sourceSubpath must be a contained POSIX path")
        return value

    @model_validator(mode="after")
    def valid_file_hashes(self) -> ProvenanceRecord:
        """Validate provenance file paths, digests, modes, and license syntax."""

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
    """Describe a validated request to plan or apply one skill import."""

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
        """Validate the destination portable plugin name."""

        validate_name(value, kind="plugin")
        return value

    @field_validator("origin")
    @classmethod
    def safe_origin(cls, value: str) -> str:
        """Normalize and validate the requested source origin."""

        return normalize_provenance_origin(value)

    @field_validator("source_skill")
    @classmethod
    def valid_source_skill(cls, value: str | None) -> str | None:
        """Validate an optional selected source skill name."""

        if value is not None:
            validate_name(value, kind="skill")
        return value

    @field_validator("revision")
    @classmethod
    def immutable_revision(cls, value: str) -> str:
        """Require an immutable source revision identifier."""

        if IMMUTABLE_REVISION_RE.fullmatch(value) is None:
            raise ValueError("revision must be a full commit/tree ID or sha256:<digest>")
        return value

    @field_validator("source_subpath")
    @classmethod
    def contained_source_subpath(cls, value: str) -> str:
        """Require the requested source subpath to remain contained."""

        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "\\" in value:
            raise ValueError("source_subpath must be a contained POSIX path")
        return value

    @field_validator("license_id")
    @classmethod
    def valid_license(cls, value: str) -> str:
        """Validate the imported skill's SPDX license expression."""

        return validate_spdx_expression(value, label="Imported license")

    @field_validator("version")
    @classmethod
    def valid_version(cls, value: str | None) -> str | None:
        """Validate an optional requested plugin version."""

        if value is not None:
            parse_semver(value, label="Requested plugin version")
        return value


class ImportPlan(StrictModel):
    """Bind a reviewed import plan to destinations, hashes, and file modes."""

    plugin: NonEmptyStr
    skill: NonEmptyStr
    source_kind: Literal["skill-directory", "skill-file", "plugin-skill"]
    destination: Path
    repository_url: NonEmptyStr
    catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    creates_plugin: bool
    file_count: int = Field(ge=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    license_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    license_destination: NonEmptyStr
    plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    files: dict[str, str]
    file_modes: dict[str, bool]
