__all__ = ("CONFIG_ENTRY_SCHEMA",)

from datetime import timedelta

import voluptuous as vol
from homeassistant.const import (
    CONF_DEFAULT,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.helpers import config_validation as cv

from custom_components.energosbyt_plus._util import IS_IN_RUSSIA
from custom_components.energosbyt_plus.const import (
    CONF_ACCOUNTS,
    CONF_CHARGES,
    CONF_BRANCH,
    CONF_DEV_PRESENTATION,
    CONF_LAST_PAYMENT,
    CONF_METERS,
    CONF_NAME_FORMAT,
    CONF_SERVICE_CHARGES,
    DEFAULT_NAME_FORMAT_EN_ACCOUNTS,
    DEFAULT_NAME_FORMAT_EN_CHARGES,
    DEFAULT_NAME_FORMAT_EN_LAST_PAYMENT,
    DEFAULT_NAME_FORMAT_EN_METERS,
    DEFAULT_NAME_FORMAT_EN_SERVICE_CHARGES,
    DEFAULT_NAME_FORMAT_RU_ACCOUNTS,
    DEFAULT_NAME_FORMAT_RU_CHARGES,
    DEFAULT_NAME_FORMAT_RU_LAST_PAYMENT,
    DEFAULT_NAME_FORMAT_RU_METERS,
    DEFAULT_NAME_FORMAT_RU_SERVICE_CHARGES,
    DEFAULT_SCAN_INTERVAL,
)

MIN_SCAN_INTERVAL = timedelta(seconds=60)


(
    default_name_format_accounts,
    default_name_format_charges,
    default_name_format_meters,
    default_name_format_last_payment,
    default_name_format_service_accruals,
) = (
    (
        DEFAULT_NAME_FORMAT_RU_ACCOUNTS,
        DEFAULT_NAME_FORMAT_RU_CHARGES,
        DEFAULT_NAME_FORMAT_RU_METERS,
        DEFAULT_NAME_FORMAT_RU_LAST_PAYMENT,
        DEFAULT_NAME_FORMAT_RU_SERVICE_CHARGES,
    )
    if IS_IN_RUSSIA
    else (
        DEFAULT_NAME_FORMAT_EN_ACCOUNTS,
        DEFAULT_NAME_FORMAT_EN_CHARGES,
        DEFAULT_NAME_FORMAT_EN_METERS,
        DEFAULT_NAME_FORMAT_EN_LAST_PAYMENT,
        DEFAULT_NAME_FORMAT_EN_SERVICE_CHARGES,
    )
)


NAME_FORMAT_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ACCOUNTS, default=default_name_format_accounts): cv.string,
        vol.Optional(CONF_CHARGES, default=default_name_format_charges): cv.string,
        vol.Optional(CONF_METERS, default=default_name_format_meters): cv.string,
        vol.Optional(
            CONF_LAST_PAYMENT, default=default_name_format_last_payment
        ): cv.string,
        vol.Optional(
            CONF_SERVICE_CHARGES,
            default=default_name_format_service_accruals,
        ): cv.string,
    },
    extra=vol.PREVENT_EXTRA,
)


SCAN_INTERVAL_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_ACCOUNTS, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_time_period,
        vol.Optional(
            CONF_CHARGES, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_time_period,
        vol.Optional(
            CONF_METERS, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_time_period,
        vol.Optional(
            CONF_LAST_PAYMENT, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_time_period,
        vol.Optional(
            CONF_SERVICE_CHARGES, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_time_period,
    }
)


def _validator_name_format_schema(schema):
    return vol.Any(
        vol.All(cv.string, lambda x: {CONF_ACCOUNTS: x}, schema),
        schema,
    )


GENERIC_ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ACCOUNTS, default=True): cv.boolean,
        vol.Optional(CONF_CHARGES, default=True): cv.boolean,
        vol.Optional(CONF_SERVICE_CHARGES, default=True): cv.boolean,
        vol.Optional(CONF_METERS, default=True): cv.boolean,
        vol.Optional(CONF_LAST_PAYMENT, default=True): cv.boolean,
        vol.Optional(CONF_DEV_PRESENTATION, default=False): cv.boolean,
        vol.Optional(CONF_NAME_FORMAT, default=lambda: NAME_FORMAT_SCHEMA({})): vol.Any(
            vol.All(cv.string, lambda x: {CONF_ACCOUNTS: x}, NAME_FORMAT_SCHEMA),
            NAME_FORMAT_SCHEMA,
        ),
        vol.Optional(
            CONF_SCAN_INTERVAL, default=lambda: SCAN_INTERVAL_SCHEMA({})
        ): vol.Any(
            vol.All(
                cv.positive_time_period,
                lambda x: dict.fromkeys(
                    (
                        CONF_ACCOUNTS,
                        CONF_CHARGES,
                        CONF_METERS,
                        CONF_LAST_PAYMENT,
                        CONF_SERVICE_CHARGES,
                    ),
                    x,
                ),
                SCAN_INTERVAL_SCHEMA,
            ),
            SCAN_INTERVAL_SCHEMA,
        ),
    },
    extra=vol.PREVENT_EXTRA,
)


GENERIC_ACCOUNT_VALIDATOR = vol.Any(
    vol.Equal(False),  # For disabling
    vol.All(vol.Equal(True), lambda _: GENERIC_ACCOUNT_SCHEMA({})),  # For default
    GENERIC_ACCOUNT_SCHEMA,  # For custom
)


CONFIG_ENTRY_SCHEMA = vol.Schema(
    {
        # Primary API configuration
        vol.Required(CONF_BRANCH): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        # Additional API configuration
        vol.Optional(
            CONF_DEFAULT,
            default=lambda: GENERIC_ACCOUNT_SCHEMA({}),
        ): GENERIC_ACCOUNT_VALIDATOR,
        vol.Optional(CONF_ACCOUNTS): vol.Any(
            vol.All(
                cv.ensure_list,
                [cv.string],
                lambda x: {y: GENERIC_ACCOUNT_SCHEMA({}) for y in x},
            ),
            vol.Schema({cv.string: GENERIC_ACCOUNT_VALIDATOR}),
        ),
    },
    extra=vol.PREVENT_EXTRA,
)
