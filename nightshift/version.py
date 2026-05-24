"""NightShift version metadata."""

from __future__ import annotations


PACKAGE_VERSION = "0.3.0"
RELEASE_CHANNEL = "alpha"
hotdog_version = "chicago"
topping_version = "onions"

HOTDOG_VERSIONS = (
    "bratwurst",
    "italian-sausage",
    "footlong",
    "new-york",
    "chicago",
    "coney",
    "corn-dog",
    "kielbasa",
    "vienna",
    "andouille",
    "chorizo",
    "frankfurter",
)

TOPPING_VERSIONS = (
    "relish",
    "mustard",
    "mayo",
    "onions",
    "sauerkraut",
    "jalapenos",
    "pickles",
    "chili",
    "cheese",
    "sport-peppers",
    "ketchup",
    "slaw",
)


def display_version() -> str:
    return f"{PACKAGE_VERSION}-{RELEASE_CHANNEL}-{hotdog_version}-{topping_version}"


__version__ = PACKAGE_VERSION
