"""Internationalization API routes (zone translations etc.)."""

from fastapi import APIRouter

from titrack.data.zones import ZONE_NAMES_CN

router = APIRouter(prefix="/api/i18n", tags=["i18n"])


@router.get("/zones")
def get_zone_translations() -> dict[str, dict[str, str]]:
    """Return zone-name translation tables keyed by English display name.

    Shape: ``{"zh-CN": {"Hideout - Ember's Rest": "驻地 - 余烬避难所", ...}}``
    The web client looks up zone names using the English label it already
    receives from ``/api/runs`` and falls back to the English label if no
    translation exists.
    """
    return {"zh-CN": ZONE_NAMES_CN}
