from __future__ import annotations

from datetime import date
from typing import Annotated

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, UrlConstraints

HttpsUrl = Annotated[AnyUrl, UrlConstraints(allowed_schemes=["https"], host_required=True)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class MarketplaceOwner(StrictModel):
    name: str = Field(min_length=1)
    email: str = Field(min_length=1)


class MarketplaceMetadata(StrictModel):
    name: str = Field(min_length=1)
    display_name: str = Field(alias="displayName", min_length=1)
    owner: MarketplaceOwner
    description: str = Field(min_length=1)
    version: str = Field(min_length=1)


class CatalogPlugin(StrictModel):
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    codex_compatibility: bool = Field(alias="codexCompatibility")


class Catalog(StrictModel):
    marketplace: MarketplaceMetadata
    plugins: list[CatalogPlugin]


class LicenseEvidence(StrictModel):
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ProvenanceRecord(StrictModel):
    skill: str = Field(min_length=1)
    origin: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    source_subpath: str = Field(alias="sourceSubpath", min_length=1)
    imported_at: date = Field(alias="importedAt")
    license: str = Field(min_length=1)
    license_evidence: LicenseEvidence = Field(alias="licenseEvidence")
    content_sha256: str = Field(alias="contentSha256", pattern=r"^[0-9a-f]{64}$")
    files: dict[str, str]
    transformations: list[str]


class CodexAuthor(StrictModel):
    name: str = Field(min_length=1)
    email: str | None = None
    url: HttpsUrl | None = None


class CodexInterface(StrictModel):
    display_name: str = Field(alias="displayName", min_length=1)
    short_description: str = Field(alias="shortDescription", min_length=1)
    long_description: str = Field(alias="longDescription", min_length=1)
    developer_name: str = Field(alias="developerName", min_length=1)
    category: str = Field(min_length=1)
    capabilities: list[str] = Field(min_length=1)
    default_prompt: list[str] = Field(alias="defaultPrompt", min_length=1)
    website_url: HttpsUrl | None = Field(default=None, alias="websiteURL")


class CodexManifest(StrictModel):
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    author: CodexAuthor
    homepage: HttpsUrl | None = None
    repository: HttpsUrl | None = None
    license: str | None = None
    keywords: list[str] | None = None
    skills: str
    interface: CodexInterface
