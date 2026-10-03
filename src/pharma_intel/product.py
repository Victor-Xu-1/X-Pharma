"""Public product identity; operational protocols keep their stable identifiers."""

from pharma_intel import __version__

PRODUCT_NAME = "X-Pharma"
PRODUCT_VERSION = __version__
PRODUCT_RELEASE = f"v{PRODUCT_VERSION}"
PACKAGE_NAME = "x-pharma"
PROJECT_URL = "https://github.com/Victor-Xu-1/X-Pharma"
SOURCE_USER_AGENT = f"{PACKAGE_NAME}/{PRODUCT_VERSION} (+{PROJECT_URL})"
