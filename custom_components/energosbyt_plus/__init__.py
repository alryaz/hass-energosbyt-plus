"""Energosbyt API"""
__all__ = (
    "CONFIG_SCHEMA",
    "async_unload_entry",
    "async_reload_entry",
    "async_setup",
    "async_setup_entry",
    "config_flow",
    "const",
    "sensor",
    "DOMAIN",
)

import asyncio
import logging
from typing import Any, Dict, List, Mapping, Optional, TYPE_CHECKING, Tuple

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from custom_components.energosbyt_plus._base import UpdateDelegatorsDataType
from custom_components.energosbyt_plus._schema import CONFIG_ENTRY_SCHEMA
from custom_components.energosbyt_plus._util import (
    IS_IN_RUSSIA,
    _find_existing_entry,
    _make_log_prefix,
    mask_username,
)
from custom_components.energosbyt_plus.api import EnergosbytPlusAPI
from custom_components.energosbyt_plus.const import (
    CONF_ACCOUNTS,
    CONF_CHARGES,
    CONF_BRANCH,
    CONF_METERS,
    CONF_NAME_FORMAT,
    CONF_USER_AGENT,
    DATA_API_OBJECTS,
    DATA_ENTITIES,
    DATA_FINAL_CONFIG,
    DATA_UPDATE_DELEGATORS,
    DATA_UPDATE_LISTENERS,
    DATA_YAML_CONFIG,
    DEFAULT_NAME_FORMAT_EN_ACCOUNTS,
    DEFAULT_NAME_FORMAT_EN_CHARGES,
    DEFAULT_NAME_FORMAT_EN_METERS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

if TYPE_CHECKING:
    from custom_components.energosbyt_plus.sensor import EnergosbytPlusAccount

_LOGGER = logging.getLogger(__name__)


def _unique_entries(value: List[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    pairs: Dict[Tuple[str, str], Optional[int]] = {}

    errors = []
    for i, config in enumerate(value):
        unique_key = (config[CONF_BRANCH], config[CONF_USERNAME])
        if unique_key in pairs:
            if pairs[unique_key] is not None:
                errors.append(
                    vol.Invalid(
                        "duplicate unique key, first encounter",
                        path=[pairs[unique_key]],
                    )
                )
                pairs[unique_key] = None
            errors.append(
                vol.Invalid("duplicate unique key, subsequent encounter", path=[i])
            )
        else:
            pairs[unique_key] = i

    if errors:
        if len(errors) > 1:
            raise vol.MultipleInvalid(errors)
        raise next(iter(errors))

    return value


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Any(
            vol.Equal({}),
            vol.All(
                cv.ensure_list,
                vol.Length(min=1),
                [CONFIG_ENTRY_SCHEMA],
                _unique_entries,
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up the Energosbyt Plus component."""
    domain_config = config.get(DOMAIN)
    if not domain_config:
        return True

    domain_data = {}
    hass.data[DOMAIN] = domain_data

    yaml_config = {}
    hass.data[DATA_YAML_CONFIG] = yaml_config

    for user_cfg in domain_config:
        if not user_cfg:
            continue

        region: str = user_cfg[CONF_BRANCH]
        username: str = user_cfg[CONF_USERNAME]

        key = (region, username)
        log_prefix = f"[{region}/{mask_username(username)}] "

        _LOGGER.debug(
            log_prefix
            + (
                "Получена конфигурация из YAML"
                if IS_IN_RUSSIA
                else "YAML configuration encountered"
            )
        )

        existing_entry = _find_existing_entry(hass, region, username)
        if existing_entry:
            if existing_entry.source == config_entries.SOURCE_IMPORT:
                yaml_config[key] = user_cfg
                _LOGGER.debug(
                    log_prefix
                    + (
                        "Соответствующая конфигурационная запись существует"
                        if IS_IN_RUSSIA
                        else "Matching config entry exists"
                    )
                )
            else:
                _LOGGER.warning(
                    log_prefix
                    + (
                        "Конфигурация из YAML переопределена другой конфигурацией!"
                        if IS_IN_RUSSIA
                        else "YAML config is overridden by another entry!"
                    )
                )
            continue

        # Save YAML configuration
        yaml_config[key] = user_cfg

        _LOGGER.warning(
            log_prefix
            + (
                "Создание новой конфигурационной записи"
                if IS_IN_RUSSIA
                else "Creating new config entry"
            )
        )

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data={
                    CONF_BRANCH: region,
                    CONF_USERNAME: username,
                },
            )
        )

    if not yaml_config:
        _LOGGER.debug(
            "Конфигурация из YAML не обнаружена"
            if IS_IN_RUSSIA
            else "YAML configuration not found"
        )

    return True


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: config_entries.ConfigEntry
):
    branch_code = config_entry.data[CONF_BRANCH]
    username = config_entry.data[CONF_USERNAME]

    unique_key = (branch_code, username)
    entry_id = config_entry.entry_id

    log_prefix = f"[{branch_code}/{mask_username(username)}] "
    hass_data = hass.data

    # Source full configuration
    if config_entry.source == config_entries.SOURCE_IMPORT:
        # Source configuration from YAML
        yaml_config = hass_data.get(DATA_YAML_CONFIG)

        if not yaml_config or unique_key not in yaml_config:
            _LOGGER.info(
                log_prefix
                + (
                    f"Удаление записи {entry_id} после удаления из конфигурации YAML"
                    if IS_IN_RUSSIA
                    else f"Removing entry {entry_id} after removal from YAML configuration"
                )
            )
            hass.async_create_task(hass.config_entries.async_remove(entry_id))
            return False

        user_cfg = yaml_config[unique_key]

    else:
        # Source and convert configuration from input post_fields
        all_cfg = {**config_entry.data}

        if config_entry.options:
            all_cfg.update(config_entry.options)

        try:
            user_cfg = CONFIG_ENTRY_SCHEMA(all_cfg)
        except vol.Invalid as e:
            _LOGGER.error(
                log_prefix
                + (
                    "Сохранённая конфигурация повреждена"
                    if IS_IN_RUSSIA
                    else "Configuration invalid"
                )
                + ": "
                + repr(e)
            )
            return False

    _LOGGER.info(
        log_prefix
        + (
            "Применение конфигурационной записи"
            if IS_IN_RUSSIA
            else "Applying configuration entry"
        )
    )

    from custom_components.energosbyt_plus.api import EnergosbytPlusException

    try:
        api_object = EnergosbytPlusAPI(
            branch_code=branch_code,
            username=username,
            password=user_cfg[CONF_PASSWORD],
        )

        await api_object.async_authenticate()

        # Fetch all accounts
        residential_objects = await api_object.async_get_residential_objects()

    except EnergosbytPlusException as e:
        desc_text = (
            "Невозможно выполнить авторизацию"
            if IS_IN_RUSSIA
            else "Error authenticating"
        ) + ": "
        _LOGGER.error(log_prefix + desc_text + repr(e))
        raise ConfigEntryNotReady(desc_text + str(e))

    accounts_count = sum(
        len(residential_object.accounts) for residential_object in residential_objects
    )

    if not accounts_count:
        # Cancel setup because no accounts provided
        _LOGGER.warning(
            log_prefix
            + ("Лицевые счета не найдены" if IS_IN_RUSSIA else "No accounts found")
        )
        return False

    _LOGGER.debug(
        log_prefix
        + (
            f"Найдено {accounts_count} лицевых счетов"
            if IS_IN_RUSSIA
            else f"Found {accounts_count} accounts"
        )
    )

    api_objects: Dict[str, "EnergosbytPlusAPI"] = hass_data.setdefault(
        DATA_API_OBJECTS, {}
    )

    # Create placeholders
    api_objects[entry_id] = api_object
    hass_data.setdefault(DATA_ENTITIES, {})[entry_id] = {}
    hass_data.setdefault(DATA_FINAL_CONFIG, {})[entry_id] = user_cfg
    hass.data.setdefault(DATA_UPDATE_DELEGATORS, {})[entry_id] = {}

    # Forward entry setup to sensor platform
    for domain in (SENSOR_DOMAIN, BINARY_SENSOR_DOMAIN):
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(
                config_entry,
                domain,
            )
        )

    # Create options update listener
    update_listener = config_entry.add_update_listener(async_reload_entry)
    hass_data.setdefault(DATA_UPDATE_LISTENERS, {})[entry_id] = update_listener

    _LOGGER.debug(
        log_prefix
        + ("Применение конфигурации успешно" if IS_IN_RUSSIA else "Setup successful")
    )
    return True


async def async_reload_entry(
    hass: HomeAssistantType,
    config_entry: config_entries.ConfigEntry,
) -> None:
    """Reload Energosbyt Plus entry"""
    log_prefix = _make_log_prefix(config_entry, "setup")
    _LOGGER.info(
        log_prefix
        + (
            "Перезагрузка интеграции"
            if IS_IN_RUSSIA
            else "Reloading configuration entry"
        )
    )
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistantType,
    config_entry: config_entries.ConfigEntry,
) -> bool:
    """Unload Energosbyt Plus entry"""
    log_prefix = _make_log_prefix(config_entry, "setup")
    entry_id = config_entry.entry_id

    update_delegators: UpdateDelegatorsDataType = hass.data[DATA_UPDATE_DELEGATORS].pop(
        entry_id
    )

    tasks = [
        hass.config_entries.async_forward_entry_unload(config_entry, domain)
        for domain in update_delegators.keys()
    ]

    unload_ok = all(await asyncio.gather(*tasks))

    if unload_ok:
        hass.data[DATA_API_OBJECTS].pop(entry_id)
        hass.data[DATA_FINAL_CONFIG].pop(entry_id)

        cancel_listener = hass.data[DATA_UPDATE_LISTENERS].pop(entry_id)
        cancel_listener()

        _LOGGER.info(
            log_prefix
            + (
                "Интеграция выгружена"
                if IS_IN_RUSSIA
                else "Unloaded configuration entry"
            )
        )

    else:
        _LOGGER.warning(
            log_prefix
            + (
                "При выгрузке конфигурации произошла ошибка"
                if IS_IN_RUSSIA
                else "Failed to unload configuration entry"
            )
        )

    return unload_ok
