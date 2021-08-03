import datetime
import re
from datetime import timedelta
from typing import (
    Any,
    Callable,
    Coroutine,
    Iterable,
    MutableMapping,
    Optional,
    TypeVar,
    Union,
)

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.typing import HomeAssistantType

from custom_components.energosbyt_plus.api import (
    EnergosbytPlusAPI,
    EnergosbytPlusException,
)
from custom_components.energosbyt_plus.const import CONF_BRANCH, DOMAIN


def _make_log_prefix(
    config_entry: Union[Any, ConfigEntry], domain: Union[Any, EntityPlatform], *args
):
    join_args = [
        (
            config_entry.entry_id[-6:]
            if isinstance(config_entry, ConfigEntry)
            else str(config_entry)
        ),
        (domain.domain if isinstance(domain, EntityPlatform) else str(domain)),
    ]
    if args:
        join_args.extend(map(str, args))

    return "[" + "][".join(join_args) + "] "


@callback
def _find_existing_entry(
    hass: HomeAssistantType, type_: str, username: str
) -> Optional[config_entries.ConfigEntry]:
    existing_entries = hass.config_entries.async_entries(DOMAIN)
    for config_entry in existing_entries:
        if (
            config_entry.data[CONF_BRANCH] == type_
            and config_entry.data[CONF_USERNAME] == username
        ):
            return config_entry


_RE_USERNAME_MASK = re.compile(r"^(\W*)(.).*(.)$")


def dev_presentation_replacer(
    mapping: MutableMapping[str, Any],
    filter_vars: Iterable[str],
    blackout_vars: Optional[Iterable[str]] = None,
):
    filter_vars = set(filter_vars)
    if blackout_vars is not None:
        blackout_vars = set(blackout_vars)
        filter_vars.difference_update(blackout_vars)

        for attr in blackout_vars:
            value = mapping.get(attr)
            if value is not None:
                if isinstance(value, float):
                    value = "#####.###"
                elif isinstance(value, int):
                    value = "#####"
                elif isinstance(value, str):
                    value = "XXXXX"
                else:
                    value = "*****"
                mapping[attr] = value

    for attr in filter_vars:
        value = mapping.get(attr)
        if value is not None:
            value = re.sub(r"[A-Za-z]", "X", str(value))
            value = re.sub(r"[0-9]", "#", value)
            value = re.sub(r"\w+", "*", value)
            mapping[attr] = value


def mask_username(username: str):
    parts = username.split("@")
    return "@".join(map(lambda x: _RE_USERNAME_MASK.sub(r"\1\2***\3", x), parts))


LOCAL_TIMEZONE = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo

# Kaliningrad is excluded as it is not supported
IS_IN_RUSSIA = (
    timedelta(hours=3) <= LOCAL_TIMEZONE.utcoffset(None) <= timedelta(hours=12)
)
_T = TypeVar("_T")
_RT = TypeVar("_RT")


async def with_auto_auth(
    api: "EnergosbytPlusAPI",
    async_getter: Callable[..., Coroutine[Any, Any, _RT]],
    *args,
    **kwargs
) -> _RT:
    try:
        return await async_getter(*args, **kwargs)
    except EnergosbytPlusException:
        await api.async_authenticate()
        return await async_getter(*args, **kwargs)
