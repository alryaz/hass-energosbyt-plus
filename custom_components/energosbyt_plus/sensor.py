"""
Sensor for Energosbyt Plus cabinet.
Retrieves indications regarding current state of accounts.
"""
import asyncio
import logging
import re
from abc import abstractmethod
from typing import (
    Any,
    ClassVar,
    Dict,
    Final,
    Hashable,
    Iterable,
    Mapping,
    Optional,
    Type,
    TypeVar,
    Union,
)

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    ATTR_ID,
    ATTR_NAME,
    STATE_OK,
    STATE_UNKNOWN,
)
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.util import slugify

from custom_components.energosbyt_plus._base import (
    EnergosbytPlusEntity,
    SupportedServicesType,
    make_common_async_setup_entry,
)
from custom_components.energosbyt_plus._util import (
    dev_presentation_replacer,
    with_auto_auth,
)
from custom_components.energosbyt_plus.api import (
    Account,
    AccountBalance,
    AccountCharges,
    EnergosbytPlusException,
    Meter,
    MeterCharacteristics,
    ServiceCharge,
)
from custom_components.energosbyt_plus.const import (
    ATTR_ACCEPTED,
    ATTR_ACCOUNT_CODE,
    ATTR_ACCURACY,
    ATTR_BENEFITS,
    ATTR_BRAND,
    ATTR_CALL_PARAMS,
    ATTR_CHARGED,
    ATTR_COMMENT,
    ATTR_COST,
    ATTR_CURRENT,
    ATTR_DIGITS,
    ATTR_END,
    ATTR_IGNORE_INDICATIONS,
    ATTR_IGNORE_PERIOD,
    ATTR_INCREASE_AMOUNT,
    ATTR_INCREASE_RATIO,
    ATTR_INCREMENTAL,
    ATTR_INDICATIONS,
    ATTR_INITIAL,
    ATTR_INSTALL_DATE,
    ATTR_LAST_CHECKUP_DATE,
    ATTR_LAST_INDICATIONS_DATE,
    ATTR_LAST_SUBMITTED,
    ATTR_MANUFACTURER,
    ATTR_METER_CODE,
    ATTR_MODEL,
    ATTR_NEXT_CHECKUP_DATE,
    ATTR_NOTIFICATION,
    ATTR_PAID,
    ATTR_PENALTY,
    ATTR_PERIOD,
    ATTR_PREVIOUS,
    ATTR_RECALCULATIONS,
    ATTR_REMAINING_DAYS,
    ATTR_SERVICES,
    ATTR_SERVICE_NAME,
    ATTR_SERVICE_TYPE,
    ATTR_START,
    ATTR_SUBMITTED,
    ATTR_SUBMIT_PERIOD_ACTIVE,
    ATTR_SUBMIT_PERIOD_END,
    ATTR_SUBMIT_PERIOD_START,
    ATTR_SUCCESS,
    ATTR_TOTAL,
    ATTR_TYPE,
    ATTR_UNIT,
    ATTR_ZONES,
    CONF_ACCOUNTS,
    CONF_CHARGES,
    CONF_DEV_PRESENTATION,
    CONF_METERS,
    CONF_SERVICE_CHARGES,
    DOMAIN,
    FORMAT_VAR_ID,
    FORMAT_VAR_TYPE_EN,
    FORMAT_VAR_TYPE_RU,
)

_LOGGER = logging.getLogger(__name__)

RE_HTML_TAGS = re.compile(r"<[^<]+?>")
RE_MULTI_SPACES = re.compile(r"\s{2,}")

INDICATIONS_MAPPING_SCHEMA = vol.Schema(
    {
        vol.Required(vol.Match(r"t\d+")): cv.positive_float,
    }
)

INDICATIONS_SEQUENCE_SCHEMA = vol.All(
    vol.Any(vol.All(cv.positive_float, cv.ensure_list), [cv.positive_float]),
    lambda x: dict(map(lambda y: ("t" + str(y[0]), y[1]), enumerate(x, start=1))),
)

SERVICE_PUSH_INDICATIONS: Final = "push_indications"
SERVICE_PUSH_INDICATIONS_SCHEMA: Final = {
    vol.Required(ATTR_INDICATIONS): vol.Any(
        vol.All(
            cv.string,
            lambda x: list(map(str.strip, x.split(","))),
            INDICATIONS_SEQUENCE_SCHEMA,
        ),
        INDICATIONS_MAPPING_SCHEMA,
        INDICATIONS_SEQUENCE_SCHEMA,
    ),
    vol.Optional(ATTR_IGNORE_PERIOD, default=False): cv.boolean,
    vol.Optional(ATTR_IGNORE_INDICATIONS, default=False): cv.boolean,
    vol.Optional(ATTR_INCREMENTAL, default=False): cv.boolean,
    vol.Optional(ATTR_NOTIFICATION, default=False): vol.Any(
        cv.boolean,
        persistent_notification.SCHEMA_SERVICE_CREATE,
    ),
}

_SERVICE_SCHEMA_BASE_DATED: Final = {
    vol.Optional(ATTR_START, default=None): vol.Any(vol.Equal(None), cv.datetime),
    vol.Optional(ATTR_END, default=None): vol.Any(vol.Equal(None), cv.datetime),
}

SERVICE_GET_PAYMENTS: Final = "get_payments"
SERVICE_GET_INVOICES: Final = "get_invoices"

_TEnergosbytPlusEntity = TypeVar("_TEnergosbytPlusEntity", bound=EnergosbytPlusEntity)


def get_supported_features(
    from_services: SupportedServicesType, for_object: Any
) -> int:
    features = 0
    for type_feature, services in from_services.items():
        if type_feature is None:
            continue
        check_cls, feature = type_feature
        if isinstance(for_object, check_cls):
            features |= feature

    return features


class EnergosbytPlusAccount(EnergosbytPlusEntity):
    """The class for this sensor"""

    config_key: ClassVar[str] = CONF_ACCOUNTS

    _supported_services: ClassVar[SupportedServicesType] = {
        None: {
            "get_payments": _SERVICE_SCHEMA_BASE_DATED,
        },
    }

    def __init__(
        self, *args, balance: Optional[AccountBalance] = None, **kwargs
    ) -> None:
        super().__init__(*args, *kwargs)
        self._balance = balance

        self.entity_id: Optional[str] = f"sensor." + slugify(
            f"{self._account.number}_account"
        )

    @property
    def code(self) -> str:
        return self._account.number

    @property
    def device_class(self) -> Optional[str]:
        return DOMAIN + "_account"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor"""
        acc = self._account
        return f"account_{acc.id}_account"

    @property
    def state(self) -> Union[str, float]:
        balance = self._balance
        if balance is not None:
            if self._account_config[CONF_DEV_PRESENTATION]:
                return ("-" if (balance.balance or 0.0) < 0.0 else "") + "#####.###"
            return round(balance.balance or 0.0, 2)  # fixes -0.0 issues
        return STATE_UNKNOWN

    @property
    def icon(self) -> str:
        return "mdi:flash-circle"

    @property
    def unit_of_measurement(self) -> Optional[str]:
        return "руб."

    @property
    def sensor_related_attributes(self) -> Optional[Mapping[str, Any]]:
        account = self._account

        attributes = {
            "auto_payment_enabled": account.auto_payment_enabled,
            "digital_receipts_enabled": account.digital_receipts_enabled,
            "indications_submission_available": account.indications_submission_available,
            "indications_submission_complete": account.indications_submission_complete,
            "has_meters": account.has_meters,
            "days_until_submission": account.days_until_submission,
            ATTR_SERVICES: account.services,
        }

        return attributes

    @property
    def name_format_values(self) -> Mapping[str, Any]:
        """Return the name of the sensor"""
        account = self._account
        return {
            FORMAT_VAR_ID: str(account.id),
            FORMAT_VAR_TYPE_EN: "account",
            FORMAT_VAR_TYPE_RU: "лицевой счёт",
        }

    #################################################################################
    # Functional implementation of inherent class
    #################################################################################

    @classmethod
    async def async_refresh_account(
        cls,
        hass: HomeAssistantType,
        entities: Dict[Hashable, _TEnergosbytPlusEntity],
        account: "Account",
        config_entry: ConfigEntry,
        account_config: ConfigType,
    ):
        entity_key = account.id
        try:
            entity = entities[entity_key]
        except KeyError:
            entity = cls(account, account_config)
            entities[entity_key] = entity

            return [entity]
        else:
            if entity.enabled:
                entity.async_schedule_update_ha_state(force_refresh=True)

    async def async_update_internal(self) -> None:
        account = self._account
        self._balance = await account.async_get_balance()
        self.register_supported_services(account)

    #################################################################################
    # Services callbacks
    #################################################################################

    @property
    def supported_features(self) -> int:
        return get_supported_features(
            self._supported_services,
            self._account,
        )


class EnergosbytPlusMeter(EnergosbytPlusEntity):
    """The class for this sensor"""

    config_key: ClassVar[str] = CONF_METERS

    _collective_update_futures: ClassVar[Dict[str, asyncio.Future]] = {}

    _supported_services: ClassVar[SupportedServicesType] = {
        None: {
            SERVICE_PUSH_INDICATIONS: SERVICE_PUSH_INDICATIONS_SCHEMA,
        },
    }

    def __init__(
        self,
        *args,
        meter: Meter,
        characteristics: Optional[MeterCharacteristics] = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._meter = meter
        self._characteristics = characteristics

        self.entity_id: Optional[str] = f"sensor." + slugify(
            f"{self._account.number}_meter_{self.code}"
        )

    #################################################################################
    # Implementation base of inherent class
    #################################################################################

    @classmethod
    async def _collective_get_meter_data_for_account(
        cls, hass: HomeAssistantType, account: Account
    ):
        account_id = account.id

        try:
            collective_update_future = cls._collective_update_futures[account_id]
        except KeyError:
            collective_update_future = hass.loop.create_future()
            cls._collective_update_futures[account_id] = collective_update_future
            try:
                meters = await account.async_get_meters()
            except BaseException as e:
                collective_update_future.set_exception(e)
                raise
            else:
                collective_update_future.set_result(meters)
                return meters
            finally:
                del cls._collective_update_futures[account_id]
        else:
            return await collective_update_future

    @classmethod
    async def async_refresh_account(
        cls,
        hass: HomeAssistantType,
        entities: Dict[Hashable, Optional[_TEnergosbytPlusEntity]],
        account: "Account",
        config_entry: ConfigEntry,
        account_config: ConfigType,
    ):
        new_meter_entities = []

        residential_object = account.residential_object

        if residential_object and account.has_meters:
            residential_object_id = residential_object.id
            
            meters, characteristics = await asyncio.gather(
                cls._collective_get_meter_data_for_account(hass, account),
                account.api.async_get_meter_characteristics(),
            )

            for meter in meters:
                entity_key = (account.id, meter.id)

                this_characteristic = None
                for characteristic in characteristics:
                    if characteristic.id == meter.id:
                        this_characteristic = characteristic
                        break

                try:
                    entity = entities[entity_key]
                except KeyError:
                    entity = cls(
                        account,
                        account_config,
                        meter=meter,
                        characteristics=this_characteristic,
                    )
                    entities[entity_key] = entity
                    new_meter_entities.append(entity)
                else:
                    if entity.enabled:
                        entity.async_schedule_update_ha_state(force_refresh=False)
                    entity._meter = meter

                if this_characteristic is None:
                    _LOGGER.warning(
                        f"Did not find characteristic for meter with ID: {meter.id}"
                    )
                else:
                    entity._characteristics = this_characteristic

        return new_meter_entities if new_meter_entities else None

    async def async_update_internal(self) -> None:
        """Internal update method.

        For meters, this method is only called during entity updates.
        """

        meter_id = self._meter.id

        for meter in await self._collective_get_meter_data_for_account(
            self.hass, self._account
        ):
            if meter.id == meter_id:
                self.register_supported_services(meter)
                self._meter = meter
                return

        self.hass.async_create_task(self.async_remove())

    #################################################################################
    # Data-oriented implementation of inherent class
    #################################################################################

    @property
    def code(self) -> str:
        return self._meter.number

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor"""
        return f"account_{self._account.id}_meter_{self._meter.id}"

    @property
    def state(self) -> str:
        meter = self._meter
        if meter is None:
            return STATE_UNKNOWN
        return meter.status or STATE_OK

    @property
    def icon(self) -> str:
        return "mdi:counter"

    @property
    def device_class(self) -> Optional[str]:
        return DOMAIN + "_meter"

    @property
    def sensor_related_attributes(self) -> Optional[Mapping[str, Any]]:
        meter = self._meter
        characteristics = self._characteristics

        dev_presentation_enabled = self.is_dev_presentation_enabled
        service = meter.service
        submit_period_active = meter.is_submission_period_active

        attributes = {}

        if characteristics:
            attributes[ATTR_NAME] = characteristics.name

        attributes.update(
            {
                ATTR_METER_CODE: characteristics.number,
                ATTR_SERVICE_NAME: service.name,
                ATTR_SERVICE_TYPE: service.code,
                ATTR_SUBMIT_PERIOD_START: meter.submission_period_start_date.isoformat(),
                ATTR_SUBMIT_PERIOD_END: meter.submission_period_end_date.isoformat(),
                ATTR_SUBMIT_PERIOD_ACTIVE: submit_period_active,
                ATTR_REMAINING_DAYS: (
                    meter.remaining_days_for_submission
                    if submit_period_active
                    else meter.remaining_days_until_submission
                ),
            }
        )

        zones_data = meter.zones
        if zones_data:
            last_indications_date = zones_data[0].last_submitted_date
            attributes[ATTR_LAST_INDICATIONS_DATE] = (
                None
                if last_indications_date is None
                else last_indications_date.isoformat()
            )

            # Add zone information
            zones = []
            for zone_data, zone_characteristics in zip(
                zones_data, characteristics.zones
            ):
                zone_attributes = {
                    ATTR_ID: zone_data.id,
                    ATTR_LAST_SUBMITTED: zone_data.last_submitted,
                    ATTR_SUBMITTED: zone_data.submitted,
                    ATTR_ACCEPTED: zone_data.accepted,
                }

                if dev_presentation_enabled:
                    dev_presentation_replacer(
                        zone_attributes,
                        (),
                        (
                            ATTR_SUBMITTED,
                            ATTR_ACCEPTED,
                            ATTR_LAST_SUBMITTED,
                        ),
                    )

                zones.append(zone_attributes)

            attributes[ATTR_ZONES] = zones

        if characteristics:
            installation_date = characteristics.installation_date
            last_checkup_date = characteristics.last_checkup_date
            next_checkup_date = characteristics.next_checkup_date

            attributes.update(
                {
                    ATTR_MANUFACTURER: characteristics.manufacturer,
                    ATTR_BRAND: characteristics.brand,
                    ATTR_MODEL: characteristics.model,
                    ATTR_TYPE: characteristics.type,
                    ATTR_ACCURACY: characteristics.accuracy_class,
                    ATTR_DIGITS: characteristics.digits,
                    ATTR_INSTALL_DATE: (
                        None
                        if installation_date is None
                        else installation_date.isoformat()
                    ),
                    ATTR_LAST_CHECKUP_DATE: (
                        None
                        if last_checkup_date is None
                        else last_checkup_date.isoformat()
                    ),
                    ATTR_NEXT_CHECKUP_DATE: (
                        None
                        if next_checkup_date is None
                        else next_checkup_date.isoformat()
                    ),
                }
            )

        if dev_presentation_enabled:
            dev_presentation_replacer(
                attributes,
                (),
                (
                    ATTR_ACCOUNT_CODE,
                    ATTR_METER_CODE,
                    ATTR_INSTALL_DATE,
                    ATTR_LAST_INDICATIONS_DATE,
                    ATTR_LAST_CHECKUP_DATE,
                    ATTR_NEXT_CHECKUP_DATE,
                ),
            )

        return attributes

    @property
    def name_format_values(self) -> Mapping[str, Any]:
        meter = self._meter
        service = meter.service
        return {
            FORMAT_VAR_ID: meter.id,
            FORMAT_VAR_TYPE_EN: "meter",
            FORMAT_VAR_TYPE_RU: "счётчик",
            ATTR_SERVICE_NAME: service.name,
            ATTR_SERVICE_TYPE: service.code,
        }

    #################################################################################
    # Additional functionality
    #################################################################################

    def _fire_callback_event(
        self,
        call_data: Mapping[str, Any],
        event_data: Mapping[str, Any],
        event_id: str,
        title: str,
    ):
        hass = self.hass
        comment = event_data.get(ATTR_COMMENT)

        if comment is not None:
            message = str(comment)
            comment = "Response comment: " + str(comment)
        else:
            comment = "Response comment not provided"
            message = comment

        _LOGGER.log(
            logging.INFO if event_data.get(ATTR_SUCCESS) else logging.ERROR,
            RE_MULTI_SPACES.sub(" ", RE_HTML_TAGS.sub("", comment)),
        )

        meter_code = self.code

        event_data = {
            ATTR_ENTITY_ID: self.entity_id,
            ATTR_METER_CODE: meter_code,
            ATTR_CALL_PARAMS: dict(call_data),
            ATTR_SUCCESS: False,
            ATTR_INDICATIONS: None,
            ATTR_COMMENT: None,
            **event_data,
        }

        _LOGGER.debug("Firing event '%s' with post_fields: %s" % (event_id, event_data))

        hass.bus.async_fire(event_type=event_id, event_data=event_data)

        notification_content: Union[bool, Mapping[str, str]] = call_data[
            ATTR_NOTIFICATION
        ]

        if notification_content is not False:
            payload = {
                persistent_notification.ATTR_TITLE: title + " - №" + meter_code,
                persistent_notification.ATTR_NOTIFICATION_ID: event_id
                + "_"
                + meter_code,
                persistent_notification.ATTR_MESSAGE: message,
            }

            if isinstance(notification_content, Mapping):
                for key, value in notification_content.items():
                    payload[key] = str(value).format_map(event_data)

            hass.async_create_task(
                hass.services.async_call(
                    persistent_notification.DOMAIN,
                    persistent_notification.SERVICE_CREATE,
                    payload,
                )
            )

    @staticmethod
    def _get_real_indications(
        meter: Meter, call_data: Mapping
    ) -> Mapping[str, Union[int, float]]:
        indications: Dict[str, Union[int, float]] = dict(call_data[ATTR_INDICATIONS])
        meter_zones = meter.zones
        is_incremental = call_data[ATTR_INCREMENTAL]

        for zone_id in indications.keys():
            zone_found = False
            for zone in meter_zones:
                if zone.id == zone_id:
                    zone_found = True
                    if is_incremental:
                        indications[zone_id] += zone.submitted or zone.accepted or 0.0
                    break

            if not zone_found:
                raise ValueError(f"meter zone {zone_id} does not exist")

        return indications

    async def async_service_push_indications(self, **call_data):
        """
        Push indications entity service.
        :param call_data: Parameters for service call
        :return:
        """
        _LOGGER.info(self.log_prefix + "Begin handling indications submission")

        meter = self._meter

        if meter is None:
            raise Exception("Meter is unavailable")

        event_data = {}

        try:
            indications = self._get_real_indications(meter, call_data)

            event_data[ATTR_INDICATIONS] = dict(indications)

            await with_auto_auth(
                meter.api,
                meter.async_push_indications,
                **indications,
                ignore_periods=call_data[ATTR_IGNORE_PERIOD],
                ignore_values=call_data[ATTR_IGNORE_INDICATIONS],
            )

        except EnergosbytPlusException as e:
            event_data[ATTR_COMMENT] = "API error: %s" % e
            raise

        except BaseException as e:
            event_data[ATTR_COMMENT] = "Unknown error: %r" % e
            _LOGGER.error(event_data[ATTR_COMMENT])
            raise

        else:
            event_data[ATTR_COMMENT] = "Indications submitted successfully"
            event_data[ATTR_SUCCESS] = True
            self.async_schedule_update_ha_state(force_refresh=True)

        finally:
            self._fire_callback_event(
                call_data,
                event_data,
                DOMAIN + "_" + SERVICE_PUSH_INDICATIONS,
                "Передача показаний",
            )

            _LOGGER.info(self.log_prefix + "End handling indications submission")


class _EnergosbytPlusChargesEntityBase(EnergosbytPlusEntity):
    _collective_update_futures: ClassVar[Dict[str, asyncio.Future]] = {}

    @property
    def code(self) -> str:
        return self._account.number

    @property
    def device_class(self) -> Optional[str]:
        return DOMAIN + "_charges"

    @property
    def icon(self) -> str:
        return "mdi:receipt"

    @property
    def unit_of_measurement(self) -> str:
        return "руб."

    @property
    @abstractmethod
    def _total_charges(self) -> float:
        raise NotImplementedError

    @property
    def state(self) -> Union[float, str]:
        if self.is_dev_presentation_enabled:
            return ("-" if self._total_charges < 0.0 else "") + "#####.###"
        return round(self._total_charges, 2)

    @classmethod
    async def _collective_get_charges_data_for_account(
        cls, hass: HomeAssistantType, account: Account
    ):
        account_id = account.id

        try:
            collective_update_future = cls._collective_update_futures[account_id]
        except KeyError:
            collective_update_future = hass.loop.create_future()
            cls._collective_update_futures[account_id] = collective_update_future
            try:
                charges = await account.async_get_charges()
            except BaseException as e:
                collective_update_future.set_exception(e)
                raise
            else:
                collective_update_future.set_result(charges)
                return charges
            finally:
                del cls._collective_update_futures[account_id]
        else:
            return await collective_update_future


class EnergosbytPlusCharges(_EnergosbytPlusChargesEntityBase):
    config_key: ClassVar[str] = CONF_CHARGES

    def __init__(
        self, *args, charges: Optional["AccountCharges"] = None, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self._charges = charges

        self.entity_id: Optional[str] = "sensor." + slugify(
            f"{self._account.number}_{self.config_key}"
        )

    @property
    def code(self) -> str:
        return self._account.number

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor"""
        return f"account_{self._account.id}_charges"

    @property
    def _total_charges(self) -> float:
        return self._charges.charged

    @property
    def sensor_related_attributes(self):
        charges = self._charges

        if not charges:
            return None

        dev_presentation_enabled = self.is_dev_presentation_enabled

        paid = 0.0
        initial = 0.0
        total = 0.0
        benefits = 0.0
        penalty = 0.0
        recalculations = 0.0
        increase_amount = 0.0

        for service in charges.services:
            paid += service.paid
            initial += service.initial
            total += service.total
            benefits += service.benefits
            penalty += service.penalty
            recalculations += service.recalculation
            increase_amount += service.increase_ratio_amount

        attributes = {
            ATTR_PERIOD: charges.period.isoformat(),
            ATTR_TOTAL: round(total, 2),
            ATTR_PAID: round(paid, 2),
            ATTR_INITIAL: round(initial, 2),
            ATTR_CHARGED: round(charges.charged, 2),
            ATTR_BENEFITS: round(benefits, 2),
            ATTR_PENALTY: round(penalty, 2),
            ATTR_RECALCULATIONS: round(recalculations, 2),
        }

        if dev_presentation_enabled:
            dev_presentation_replacer(
                attributes,
                (ATTR_PERIOD,),
                (
                    ATTR_BENEFITS,
                    ATTR_CHARGED,
                    ATTR_INITIAL,
                    ATTR_PAID,
                    ATTR_PENALTY,
                    ATTR_RECALCULATIONS,
                    ATTR_RECALCULATIONS,
                    ATTR_TOTAL,
                    ATTR_INCREASE_AMOUNT,
                    ATTR_INCREASE_RATIO,
                ),
            )

        return attributes

    @property
    def name_format_values(self) -> Mapping[str, Any]:
        return {
            FORMAT_VAR_ID: self._account.id,
            FORMAT_VAR_TYPE_EN: "charges",
            FORMAT_VAR_TYPE_RU: "начисления",
        }

    @classmethod
    async def async_refresh_account(
        cls: Type[_TEnergosbytPlusEntity],
        hass: HomeAssistantType,
        entities: Dict[Hashable, _TEnergosbytPlusEntity],
        account: "Account",
        config_entry: ConfigEntry,
        account_config: ConfigType,
    ) -> Optional[Iterable[_TEnergosbytPlusEntity]]:
        entity_key = account.id

        try:
            entity = entities[entity_key]
        except KeyError:
            entity = cls(account, account_config)
            entities[entity_key] = entity
            return [entity]

        else:
            if entity.enabled:
                entity.async_schedule_update_ha_state(force_refresh=True)

        return None

    async def async_update_internal(self) -> None:
        self._charges = await self._collective_get_charges_data_for_account(
            self.hass, self._account
        )


class EnergosbytPlusServiceCharges(_EnergosbytPlusChargesEntityBase):
    config_key: ClassVar[str] = CONF_SERVICE_CHARGES

    def __init__(self, *args, service_charge: "ServiceCharge", **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._service_charge = service_charge

        self.entity_id: Optional[str] = "sensor." + slugify(
            f"{self._account.number}_charges_{service_charge.code}"
        )

    @property
    def _total_charges(self) -> float:
        return self._service_charge.charged

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor"""
        return f"account_{self._account.id}_servicecharges_{self._service_charge.id}"

    @property
    def sensor_related_attributes(self):
        service_charges = self._service_charge
        dev_presentation_enabled = self.is_dev_presentation_enabled

        attributes = {
            ATTR_ID: service_charges.id,
            ATTR_CODE: service_charges.code,
            ATTR_NAME: service_charges.name,
            ATTR_UNIT: service_charges.unit,
            ATTR_TOTAL: round(service_charges.total, 2),
            ATTR_INITIAL: round(service_charges.initial, 2),
            ATTR_PAID: round(service_charges.paid, 2),
            ATTR_CHARGED: round(service_charges.charged, 2),
            ATTR_RECALCULATIONS: round(service_charges.recalculation, 2),
            ATTR_BENEFITS: round(service_charges.benefits, 2),
            ATTR_PENALTY: round(service_charges.penalty, 2),
            ATTR_INCREASE_RATIO: round(service_charges.increase_ratio_value or 0.0, 2),
            ATTR_INCREASE_AMOUNT: round(service_charges.increase_ratio_amount, 2),
        }

        zones_data = service_charges.zones
        if zones_data:
            zones_attribute = []
            for zone in service_charges.zones:
                current = zone.current

                zone_attributes = {
                    ATTR_ID: zone.id,
                    ATTR_COST: round(zone.cost, 2),
                    ATTR_CURRENT: (None if current is None else round(current, 2)),
                    ATTR_PREVIOUS: zone.previous,
                }

                if dev_presentation_enabled:
                    dev_presentation_replacer(
                        zone_attributes,
                        (),
                        (ATTR_COST, ATTR_CURRENT, ATTR_PREVIOUS),
                    )

                zones_attribute.append(zone_attributes)

            attributes[ATTR_ZONES] = zones_attribute

        if dev_presentation_enabled:
            dev_presentation_replacer(
                attributes,
                (ATTR_ID,),
                (
                    ATTR_BENEFITS,
                    ATTR_CHARGED,
                    ATTR_INITIAL,
                    ATTR_PAID,
                    ATTR_PENALTY,
                    ATTR_RECALCULATIONS,
                    ATTR_RECALCULATIONS,
                    ATTR_TOTAL,
                    ATTR_INCREASE_AMOUNT,
                    ATTR_INCREASE_RATIO,
                ),
            )

        return attributes

    @property
    def name_format_values(self) -> Mapping[str, Any]:
        service_charges = self._service_charge
        return {
            FORMAT_VAR_ID: self._account.id,
            FORMAT_VAR_TYPE_EN: "charges",
            FORMAT_VAR_TYPE_RU: "начисления",
            "service_name": service_charges.name,
            "service_id": service_charges.id,
            "service_type": service_charges.code,
        }

    @classmethod
    async def async_refresh_account(
        cls: Type[_TEnergosbytPlusEntity],
        hass: HomeAssistantType,
        entities: Dict[Hashable, _TEnergosbytPlusEntity],
        account: "Account",
        config_entry: ConfigEntry,
        account_config: ConfigType,
    ) -> Optional[Iterable[_TEnergosbytPlusEntity]]:
        account_id = account.id
        charges = await cls._collective_get_charges_data_for_account(hass, account)
        new_entities = []

        for service_charge in charges.services:
            entity_key = (account_id, service_charge.id)

            try:
                entity = entities[entity_key]
            except KeyError:
                entity = cls(account, account_config, service_charge=service_charge)
                entities[entity_key] = entity
                new_entities.append(entity)

            else:
                if entity.enabled:
                    entity.service_charge = service_charge
                    entity.async_schedule_update_ha_state(force_refresh=False)

        return new_entities or None

    async def async_update_internal(self) -> None:
        charges = await self._collective_get_charges_data_for_account(
            self.hass, self._account
        )
        service_charge_id = self._service_charge.id

        for service_charge in charges.services:
            if service_charge.id == service_charge_id:
                self._service_charge = service_charge
                break


async_setup_entry = make_common_async_setup_entry(
    EnergosbytPlusAccount,
    EnergosbytPlusCharges,
    EnergosbytPlusServiceCharges,
    EnergosbytPlusMeter,
)
