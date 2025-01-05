"""Handler for capabilities data."""
import atexit
import logging
import pickle
import platform
import re
import time
from contextlib import ExitStack
from os import environ, path
from tempfile import mkdtemp
from typing import Any, Dict, Optional, Type

import importlib_resources
import yaml

if environ.get("ESCPOS_CAPABILITIES_DEBUG", 0):
    logging.basicConfig()

logger = logging.getLogger(__name__)
pickle_dir = environ.get("ESCPOS_CAPABILITIES_PICKLE_DIR", mkdtemp())
pickle_path = path.join(pickle_dir, f"{platform.python_version()}.capabilities.pickle")
# get a temporary file from importlib_resources if no file is specified in env
file_manager = ExitStack()
atexit.register(file_manager.close)
ref = importlib_resources.files(__name__) / "capabilities.json"
capabilities_path = environ.get(
    "ESCPOS_CAPABILITIES_FILE",
    file_manager.enter_context(importlib_resources.as_file(ref)),
)

# Load external printer database
t0 = time.time()
logger.debug("Using capabilities from file: %s", capabilities_path)
if path.exists(pickle_path):
    if path.getmtime(capabilities_path) > path.getmtime(pickle_path):
        logger.debug("Found a more recent capabilities file")
        full_load = True
    else:
        full_load = False
        logger.debug("Loading capabilities from pickle in %s", pickle_path)
        with open(pickle_path, "rb") as cf:
            CAPABILITIES = pickle.load(cf)
else:
    logger.debug("Capabilities pickle file not found: %s", pickle_path)
    full_load = True

if full_load:
    logger.debug("Loading and pickling capabilities")
    with open(capabilities_path) as cp, open(pickle_path, "wb") as pp:
        CAPABILITIES = yaml.safe_load(cp)
        if not CAPABILITIES:
            # yaml could not be loaded
            print(
                f"Capabilities yaml from {capabilities_path} could not be loaded.\n"
                "This python package seems to be broken. If it has been installed "
                "from official sources, please report an issue on GitHub.\n"
                "Currently loaded capabilities:\n"
                f"{CAPABILITIES}"
            )
            CAPABILITIES = {
                "profiles": {
                    "default": {
                        "name": "BrokenDefault",
                        "notes": "The integrated capabilities file could not be found and has been replaced.",
                        "codePages": {"0": "Broken"},
                        "features": {},
                    },
                },
                "encodings": {
                    "Broken": {
                        "name": "Broken",
                        "notes": "The configuration is broken.",
                    }
                },
            }
            print(
                "Created a minimal backup profile, "
                "many functionalities of the library will not work:\n"
                f"{CAPABILITIES}"
            )
        pickle.dump(CAPABILITIES, pp, protocol=2)

logger.debug("Finished loading capabilities took %.2fs", time.time() - t0)


class NotSupported(Exception):
    """Raised if a requested feature is not supported by the printer profile."""

    pass


BARCODE_B = "barcodeB"


class BaseProfile:
    """This represents a printer profile.

    A printer profile knows about the number of columns, supported
    features, colors and more.
    """

    profile_data: Dict[str, Any] = {}

    def __getattr__(self, name):
        """Get a data element from the profile."""
        return self.profile_data[name]

    def get_font(self, font) -> int:
        """Return the escpos index for `font`.

        Makes sure that the requested `font` is valid.
        """
        font = {"a": 0, "b": 1}.get(font, font)
        if not str(font) in self.fonts:
            raise NotSupported(f'"{font}" is not a valid font in the current profile')
        return font

    def get_columns(self, font) -> int:
        """Return the number of columns for the given font."""
        font = self.get_font(font)
        columns = self.fonts[str(font)]["columns"]
        assert type(columns) is int
        return columns

    def supports(self, feature) -> bool:
        """Return true/false for the given feature."""
        return self.features.get(feature)

    def get_code_pages(self) -> Dict[str, int]:
        """Return the support code pages as a ``{name: index}`` dict."""
        return {v: k for k, v in self.codePages.items()}


def get_profile(name: Optional[str] = None, **kwargs):
    """Get a profile by name.

    If no name is given, return the default profile.
    """
    if isinstance(name, Profile):
        return name

    clazz = get_profile_class(name or "default")
    return clazz(**kwargs)


CLASS_CACHE = {}


def get_profile_class(name: str) -> Type[BaseProfile]:
    """Load a profile class.

    For the given profile name, load the data from the external
    database, then generate dynamically a class.
    """
    if name not in CLASS_CACHE:
        profiles: Dict[str, Any] = CAPABILITIES["profiles"]
        profile_data = profiles[name]
        profile_name = clean(name)
        class_name = f"{profile_name[0].upper()}{profile_name[1:]}Profile"
        new_class = type(class_name, (BaseProfile,), {"profile_data": profile_data})
        CLASS_CACHE[name] = new_class

    return CLASS_CACHE[name]


def clean(s: str) -> str:
    """Clean profile name."""
    # Remove invalid characters
    s = re.sub("[^0-9a-zA-Z_]", "", s)
    # Remove leading characters until we find a letter or underscore
    s = re.sub("^[^a-zA-Z_]+", "", s)
    return str(s)


# mute the mypy type issue with this dynamic base class function for now (: Any)
ProfileBaseClass: Any = get_profile_class("default")


class Profile(ProfileBaseClass):
    """Profile class for user usage.

    For users, who want to provide their own profile.
    """

    def __init__(self, columns: Optional[int] = None, features=None) -> None:
        """Initialize profile."""
        super(Profile, self).__init__()

        self.columns = columns
        self.features = features or {}

    def get_columns(self, font) -> int:
        """Get column count of printer."""
        if self.columns is not None:
            return self.columns

        return super(Profile, self).get_columns(font)
