"""RSS feed validation for Apple Podcasts and Spotify compliance."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from podflow.utils.logging import get_logger

log = get_logger(__name__)

ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ATOM_NS = "http://www.w3.org/2005/Atom"


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        lines = []
        if self.errors:
            lines.append(f"ERRORS ({len(self.errors)}):")
            for e in self.errors:
                lines.append(f"  - {e}")
        if self.warnings:
            lines.append(f"WARNINGS ({len(self.warnings)}):")
            for w in self.warnings:
                lines.append(f"  - {w}")
        if self.is_valid:
            lines.append("Feed is valid.")
        return "\n".join(lines)


def validate_feed(feed_path: Path) -> ValidationResult:
    """Validate a podcast RSS feed for Apple/Spotify compliance."""
    result = ValidationResult()
    feed_path = Path(feed_path)

    if not feed_path.exists():
        result.errors.append(f"Feed file not found: {feed_path}")
        return result

    try:
        tree = ET.parse(str(feed_path))
    except ET.ParseError as e:
        result.errors.append(f"XML parse error: {e}")
        return result

    root = tree.getroot()

    # Must be RSS 2.0
    if root.tag != "rss":
        result.errors.append(f"Root element must be <rss>, got <{root.tag}>")
        return result

    version = root.get("version", "")
    if version != "2.0":
        result.errors.append(f"RSS version must be 2.0, got '{version}'")

    channel = root.find("channel")
    if channel is None:
        result.errors.append("Missing <channel> element")
        return result

    # Required channel elements
    _require_element(channel, "title", result)
    _require_element(channel, "description", result)
    _require_element(channel, "link", result)

    # iTunes required elements
    _require_element(channel, f"{{{ITUNES_NS}}}author", result, "itunes:author")
    _require_element(channel, f"{{{ITUNES_NS}}}owner", result, "itunes:owner")
    _require_element(channel, f"{{{ITUNES_NS}}}explicit", result, "itunes:explicit")

    # iTunes recommended elements
    image = channel.find(f"{{{ITUNES_NS}}}image")
    if image is None:
        result.warnings.append("Missing itunes:image — required by Apple Podcasts")
    else:
        href = image.get("href", "")
        if not href:
            result.warnings.append("itunes:image has no href attribute")
        elif not href.startswith("https://"):
            result.warnings.append("itunes:image should use HTTPS URL")

    category = channel.find(f"{{{ITUNES_NS}}}category")
    if category is None:
        result.warnings.append("Missing itunes:category — recommended for discoverability")

    # Validate items (episodes)
    items = channel.findall("item")
    if not items:
        result.warnings.append("Feed has no episodes")

    for i, item in enumerate(items, 1):
        prefix = f"Episode {i}"
        _require_element(item, "title", result, f"{prefix}: title")
        _require_element(item, "description", result, f"{prefix}: description")

        enclosure = item.find("enclosure")
        if enclosure is None:
            result.errors.append(f"{prefix}: Missing <enclosure> element")
        else:
            url = enclosure.get("url", "")
            if not url:
                result.errors.append(f"{prefix}: enclosure missing 'url' attribute")
            elif not url.startswith("https://") and not url.startswith("http://"):
                result.warnings.append(f"{prefix}: enclosure URL should be HTTPS")

            enc_type = enclosure.get("type", "")
            if enc_type not in ("audio/mpeg", "audio/x-m4a", "audio/mp4", "video/mp4"):
                result.warnings.append(
                    f"{prefix}: enclosure type '{enc_type}' may not be supported"
                )

            length = enclosure.get("length", "0")
            if length == "0":
                result.warnings.append(f"{prefix}: enclosure length is 0")

        guid = item.find("guid")
        if guid is None:
            result.warnings.append(f"{prefix}: Missing <guid> — recommended for deduplication")

    log.info("Validation complete: %d errors, %d warnings", len(result.errors), len(result.warnings))
    return result


def _require_element(
    parent: ET.Element,
    tag: str,
    result: ValidationResult,
    display_name: str | None = None,
) -> ET.Element | None:
    el = parent.find(tag)
    name = display_name or tag
    if el is None:
        result.errors.append(f"Missing required element: {name}")
        return None
    if not (el.text or "").strip() and not el.attrib:
        result.warnings.append(f"Element {name} is empty")
    return el
