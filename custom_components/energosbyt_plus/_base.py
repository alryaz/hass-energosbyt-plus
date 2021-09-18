__all__ = (
    "make_common_async_setup_entry",
    "EnergosbytPlusEntity",
    "async_refresh_api_data",
    "async_register_update_delegator",
    "UpdateDelegatorsDataType",
    "EntitiesDataType",
    "SupportedServicesType",
)

import asyncio
import logging
from abc import abstractmethod
from datetime import timedelta
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Hashable,
    Iterable,
    List,
    Mapping,
    Optional,
    Set,
    SupportsInt,
    TYPE_CHECKING,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_DEFAULT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, HomeAssistantType, StateType
from homeassistant.util import as_local, utcnow

from custom_components.energosbyt_plus._util import (
    IS_IN_RUSSIA,
    dev_presentation_replacer,
    mask_username,
    with_auto_auth,
)
from custom_components.energosbyt_plus.api import Account, EnergosbytPlusAPI
from custom_components.energosbyt_plus.const import (
    ATTRIBUTION_EN,
    ATTRIBUTION_RU,
    ATTR_ACCOUNT_CODE,
    ATTR_ACCOUNT_ID,
    CONF_ACCOUNTS,
    CONF_BRANCH,
    CONF_DEV_PRESENTATION,
    CONF_NAME_FORMAT,
    DATA_API_OBJECTS,
    DATA_ENTITIES,
    DATA_FINAL_CONFIG,
    DATA_UPDATE_DELEGATORS,
    DOMAIN,
    FORMAT_VAR_ACCOUNT_CODE,
    FORMAT_VAR_ACCOUNT_CODE_SHORT,
    FORMAT_VAR_ACCOUNT_ID,
    FORMAT_VAR_CODE,
    FORMAT_VAR_ID,
    SUPPORTED_PLATFORMS,
)

if TYPE_CHECKING:
    from homeassistant.helpers.entity_registry import RegistryEntry

_LOGGER = logging.getLogger(__name__)

_TEnergosbytPlusEntity = TypeVar("_TEnergosbytPlusEntity", bound="EnergosbytPlusEntity")

AddEntitiesCallType = Callable[[List["MESEntity"], bool], Any]
UpdateDelegatorsDataType = Dict[str, Tuple[AddEntitiesCallType, Set[Type["MESEntity"]]]]
EntitiesDataType = Dict[
    Type["EnergosbytPlusEntity"], Dict[Hashable, "EnergosbytPlusEntity"]
]


def make_common_async_setup_entry(
    entity_cls: Type["EnergosbytPlusEntity"], *args: Type["EnergosbytPlusEntity"]
):
    async def _async_setup_entry(
        hass: HomeAssistantType,
        config_entry: ConfigEntry,
        async_add_devices,
    ):
        current_entity_platform = entity_platform.current_platform.get()

        log_prefix = (
            f"[{config_entry.data[CONF_BRANCH]}/"
            f"{mask_username(config_entry.data[CONF_USERNAME])}]"
            f"[{current_entity_platform.domain}][setup] "
        )
        _LOGGER.debug(
            log_prefix
            + (
                "Регистрация делегата обновлений"
                if IS_IN_RUSSIA
                else "Registering update delegator"
            )
        )

        await async_register_update_delegator(
            hass,
            config_entry,
            current_entity_platform.domain,
            async_add_devices,
            entity_cls,
            *args,
        )

    _async_setup_entry.__name__ = "async_setup_entry"

    return _async_setup_entry


async def async_register_update_delegator(
    hass: HomeAssistantType,
    config_entry: ConfigEntry,
    platform: str,
    async_add_entities: AddEntitiesCallType,
    entity_cls: Type["EnergosbytPlusEntity"],
    *args: Type["EnergosbytPlusEntity"],
    update_after_complete: bool = True,
):
    entry_id = config_entry.entry_id

    update_delegators: UpdateDelegatorsDataType = hass.data[DATA_UPDATE_DELEGATORS][
        entry_id
    ]
    update_delegators[platform] = (async_add_entities, {entity_cls, *args})

    if update_after_complete:
        if len(update_delegators) != len(SUPPORTED_PLATFORMS):
            return

        await async_refresh_api_data(hass, config_entry)


async def async_refresh_api_data(hass: HomeAssistantType, config_entry: ConfigEntry):
    entry_id = config_entry.entry_id
    api: "EnergosbytPlusAPI" = hass.data[DATA_API_OBJECTS][entry_id]

    residential_objects = await with_auto_auth(api, api.async_get_residential_objects)

    update_delegators: UpdateDelegatorsDataType = hass.data[DATA_UPDATE_DELEGATORS][
        entry_id
    ]

    log_prefix_base = (
        f"[{config_entry.data[CONF_BRANCH]}/"
        f"{mask_username(config_entry.data[CONF_USERNAME])}] "
    )
    refresh_log_prefix = log_prefix_base + "[refresh] "

    _LOGGER.info(
        refresh_log_prefix
        + (
            "Запуск обновления связанных с профилем данных"
            if IS_IN_RUSSIA
            else "Beginning profile-related data update"
        )
    )

    if not update_delegators:
        return

    entities: EntitiesDataType = hass.data[DATA_ENTITIES][entry_id]
    final_config: ConfigType = dict(hass.data[DATA_FINAL_CONFIG][entry_id])

    dev_presentation = final_config.get(CONF_DEV_PRESENTATION)
    dev_log_prefix = log_prefix_base + "[dev] "

    if dev_presentation:
        from pprint import pformat

        _LOGGER.debug(
            dev_log_prefix
            + ("Конечная конфигурация:" if IS_IN_RUSSIA else "Final configuration:")
            + "\n"
            + pformat(final_config)
        )

    platform_tasks = {}

    accounts_config = final_config.get(CONF_ACCOUNTS) or {}
    account_default_config = final_config[CONF_DEFAULT]

    for residential_object in residential_objects:
        for account in residential_object.accounts:
            account_code = account.number
            account_config = accounts_config.get(account_code)
            account_log_prefix_base = (
                refresh_log_prefix + f"[{mask_username(account_code)}]"
            )

            if account_config is None:
                account_config = account_default_config

            if account_config is False:
                continue

            for platform, (_, entity_classes) in update_delegators.items():
                platform_log_prefix_base = account_log_prefix_base + f"[{platform}]"
                add_update_tasks = platform_tasks.setdefault(platform, [])
                for entity_cls in entity_classes:
                    cls_log_prefix_base = (
                        platform_log_prefix_base + f"[{entity_cls.__name__}]"
                    )
                    if account_config[entity_cls.config_key] is False:
                        _LOGGER.debug(
                            log_prefix_base
                            + " "
                            + (
                                f"Лицевой счёт пропущен согласно фильтрации"
                                if IS_IN_RUSSIA
                                else f"Account skipped due to filtering"
                            )
                        )
                        continue

                    current_entities = entities.setdefault(entity_cls, {})

                    _LOGGER.debug(
                        cls_log_prefix_base
                        + "[update] "
                        + (
                            "Планирование процедуры обновления"
                            if IS_IN_RUSSIA
                            else "Planning update procedure"
                        )
                    )

                    add_update_tasks.append(
                        entity_cls.async_refresh_account(
                            hass,
                            current_entities,
                            account,
                            config_entry,
                            account_config,
                        )
                    )

    if platform_tasks:

        async def _wrap_update_task(update_task):
            try:
                return await update_task
            except BaseException as task_exception:
                _LOGGER.exception(
                    f"Error occurred during task execution: {repr(task_exception)}",
                    exc_info=task_exception,
                )
                return None

        all_updates_count = sum(map(len, platform_tasks.values()))
        _LOGGER.info(
            refresh_log_prefix
            + (
                f"Выполнение процедур обновления ({all_updates_count}) для платформ: "
                f"{', '.join(platform_tasks.keys())}"
                if IS_IN_RUSSIA
                else f"Performing update procedures ({all_updates_count}) for platforms: "
                f"{', '.join(platform_tasks.keys())}"
            )
        )
        for platform, tasks in zip(
            platform_tasks.keys(),
            await asyncio.gather(
                *map(
                    lambda x: asyncio.gather(*map(_wrap_update_task, x)),
                    platform_tasks.values(),
                )
            ),
        ):
            all_new_entities = []
            for results in tasks:
                if results is None:
                    continue
                all_new_entities.extend(results)

            if all_new_entities:
                update_delegators[platform][0](all_new_entities, True)
    else:
        _LOGGER.warning(
            refresh_log_prefix
            + (
                "Отсутствуют подходящие платформы для конфигурации"
                if IS_IN_RUSSIA
                else "Missing suitable platforms for configuration"
            )
        )


class NameFormatDict(dict):
    def __missing__(self, key: str):
        if key.endswith("_upper") and key[:-6] in self:
            return str(self[key[:-6]]).upper()
        if key.endswith("_cap") and key[:-4] in self:
            return str(self[key[:-4]]).capitalize()
        if key.endswith("_title") and key[:-6] in self:
            return str(self[key[:-6]]).title()
        return "{{" + str(key) + "}}"


_TData = TypeVar("_TData")


SupportedServicesType = Mapping[
    Optional[Tuple[type, SupportsInt]],
    Mapping[str, Union[dict, Callable[[dict], dict]]],
]


class EnergosbytPlusEntity(Entity):
    config_key: ClassVar[str] = NotImplemented

    _supported_services: ClassVar[SupportedServicesType] = {}

    def __init__(
        self,
        account: Account,
        account_config: ConfigType,
    ) -> None:
        self._account: Account = account
        self._account_config: ConfigType = account_config
        self._entity_updater = None

    @property
    def device_info(self) -> Dict[str, Any]:
        account_object = self._account
        branch_code = account_object.api.branch_code

        device_info = {
            "name": f"№ {account_object.number}",
            "identifiers": {(DOMAIN, f"{branch_code}__{account_object.id}")},
            "manufacturer": "EnergosbyT.Plus",
            "model": branch_code,
        }

        residential_object = account_object.residential_object
        if residential_object is not None:
            device_info["suggested_area"] = residential_object.address

        return device_info

    @property
    def is_dev_presentation_enabled(self) -> bool:
        return bool(self._account_config.get(CONF_DEV_PRESENTATION))

    #################################################################################
    # Config getter helpers
    #################################################################################

    @property
    def scan_interval(self) -> timedelta:
        return self._account_config[CONF_SCAN_INTERVAL][self.config_key]

    @property
    def name_format(self) -> str:
        return self._account_config[CONF_NAME_FORMAT][self.config_key]

    #################################################################################
    # Base overrides
    #################################################################################

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return False

    @property
    def device_state_attributes(self):
        """Return the attribute(s) of the sensor"""

        attributes = dict(self.sensor_related_attributes or {})

        if ATTR_ACCOUNT_ID not in attributes:
            attributes[ATTR_ACCOUNT_ID] = self._account.id

        if ATTR_ACCOUNT_CODE not in attributes:
            attributes[ATTR_ACCOUNT_CODE] = self._account.number

        attributes[ATTR_ATTRIBUTION] = (
            ATTRIBUTION_RU if IS_IN_RUSSIA else ATTRIBUTION_EN
        )

        if self.is_dev_presentation_enabled:
            dev_presentation_replacer(attributes, (ATTR_ACCOUNT_CODE, ATTR_ACCOUNT_ID))

        return attributes

    @property
    def name(self) -> Optional[str]:
        name_format_values = {
            key: ("" if value is None else str(value))
            for key, value in self.name_format_values.items()
        }

        if FORMAT_VAR_CODE not in name_format_values:
            name_format_values[FORMAT_VAR_CODE] = self.code

        if FORMAT_VAR_ACCOUNT_CODE not in name_format_values:
            name_format_values[FORMAT_VAR_ACCOUNT_CODE] = self._account.number

        if FORMAT_VAR_ACCOUNT_CODE_SHORT not in name_format_values:
            name_format_values[FORMAT_VAR_ACCOUNT_CODE_SHORT] = (
                "#" + self._account.number[-4:]
            )

        if FORMAT_VAR_ACCOUNT_ID not in name_format_values:
            name_format_values[FORMAT_VAR_ACCOUNT_ID] = str(self._account.id)

        if self.is_dev_presentation_enabled:
            dev_presentation_replacer(
                name_format_values,
                (
                    FORMAT_VAR_CODE,
                    FORMAT_VAR_ACCOUNT_CODE,
                    FORMAT_VAR_ACCOUNT_CODE_SHORT,
                ),
                (FORMAT_VAR_ACCOUNT_ID, FORMAT_VAR_ID),
            )

        return self.name_format.format_map(NameFormatDict(name_format_values))

    #################################################################################
    # Hooks for adding entity to internal registry
    #################################################################################

    async def async_added_to_hass(self) -> None:
        _LOGGER.info(self.log_prefix + "Adding to HomeAssistant")
        self.updater_restart()

    async def async_will_remove_from_hass(self) -> None:
        _LOGGER.info(self.log_prefix + "Removing from HomeAssistant")
        self.updater_stop()

        registry_entry: Optional["RegistryEntry"] = self.registry_entry
        if registry_entry:
            entry_id: Optional[str] = registry_entry.config_entry_id
            if entry_id:
                data_entities: EntitiesDataType = self.hass.data[DATA_ENTITIES][
                    entry_id
                ]
                cls_entities = data_entities.get(self.__class__)
                if cls_entities:
                    remove_indices = []
                    for idx, entity in enumerate(cls_entities):
                        if self is entity:
                            remove_indices.append(idx)
                    for idx in remove_indices:
                        cls_entities.pop(idx)

    #################################################################################
    # Updater management API
    #################################################################################

    @property
    def log_prefix(self) -> str:
        return f"[{self.config_key}][{self.entity_id or '<no entity ID>'}] "

    def updater_stop(self) -> None:
        if self._entity_updater is not None:
            _LOGGER.debug(self.log_prefix + "Stopping updater")
            self._entity_updater()
            self._entity_updater = None

    def updater_restart(self) -> None:
        log_prefix = self.log_prefix
        scan_interval = self.scan_interval

        self.updater_stop()

        async def _update_entity(*_):
            nonlocal self
            _LOGGER.debug(log_prefix + f"Executing updater on interval")
            await self.async_update_ha_state(force_refresh=True)

        _LOGGER.debug(
            log_prefix + f"Starting updater "
            f"(interval: {scan_interval.total_seconds()} seconds, "
            f"next call: {as_local(utcnow()) + scan_interval})"
        )
        self._entity_updater = async_track_time_interval(
            self.hass,
            _update_entity,
            scan_interval,
        )

    async def updater_execute(self) -> None:
        self.updater_stop()
        try:
            await self.async_update_ha_state(force_refresh=True)
        finally:
            self.updater_restart()

    async def async_update(self) -> None:
        # @TODO: more sophisticated error handling
        await with_auto_auth(self._account.api, self.async_update_internal)

    #################################################################################
    # Functional base for inherent classes
    #################################################################################

    @classmethod
    @abstractmethod
    async def async_refresh_account(
        cls: Type[_TEnergosbytPlusEntity],
        hass: HomeAssistantType,
        entities: Dict[Hashable, _TEnergosbytPlusEntity],
        account: "Account",
        config_entry: ConfigEntry,
        account_config: ConfigType,
    ) -> Optional[Iterable[_TEnergosbytPlusEntity]]:
        raise NotImplementedError

    #################################################################################
    # Data-oriented base for inherent classes
    #################################################################################

    @abstractmethod
    async def async_update_internal(self) -> None:
        raise NotImplementedError

    @property
    @abstractmethod
    def code(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def state(self) -> StateType:
        raise NotImplementedError

    @property
    @abstractmethod
    def icon(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def sensor_related_attributes(self) -> Optional[Mapping[str, Any]]:
        raise NotImplementedError

    @property
    @abstractmethod
    def name_format_values(self) -> Mapping[str, Any]:
        raise NotImplementedError

    @property
    @abstractmethod
    def unique_id(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def device_class(self) -> Optional[str]:
        raise NotImplementedError

    def register_supported_services(self, for_object: Optional[Any] = None) -> None:
        for type_feature, services in self._supported_services.items():
            result, features = (
                (True, None)
                if type_feature is None
                else (isinstance(for_object, type_feature[0]), (int(type_feature[1]),))
            )

            if result:
                for service, schema in services.items():
                    self.platform.async_register_entity_service(
                        service, schema, "async_service_" + service, features
                    )
