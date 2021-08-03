"""Energosbyt Plus integration config and option flow handlers"""
import logging
from collections import OrderedDict
from datetime import timedelta
from typing import Any, ClassVar, Dict, Final, Mapping, Optional, Sequence

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_DEFAULT, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from custom_components.energosbyt_plus.api import (
    Account,
    EnergosbytPlusAPI,
    EnergosbytPlusException,
)
from custom_components.energosbyt_plus.const import CONF_ACCOUNTS, CONF_BRANCH, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_DISABLE_ENTITIES: Final = "disable_entities"


def _flatten(conf: Any):
    if isinstance(conf, timedelta):
        return conf.total_seconds()
    if isinstance(conf, Mapping):
        return dict(zip(conf.keys(), map(_flatten, conf.values())))
    if isinstance(conf, (list, tuple)):
        return list(map(_flatten, conf))
    return conf


class EnergosbytPlusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Energosbyt Plus config entries."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    CACHED_API_TYPE_NAMES: ClassVar[Optional[Dict[str, Any]]] = {}

    def __init__(self):
        """Instantiate config flow."""
        self._current_type = None
        self._current_config: Optional[ConfigType] = None
        self._devices_info = None
        self._accounts: Optional[Sequence["Account"]] = None

        self.schema_user = None

    async def _check_entry_exists(self, branch_code: str, username: str):
        current_entries = self._async_current_entries()

        for config_entry in current_entries:
            if (
                config_entry.data[CONF_BRANCH] == branch_code
                and config_entry.data[CONF_USERNAME] == username
            ):
                return True

        return False

    @staticmethod
    def make_entry_title(
        branch_code: str,
        username: str,
    ) -> str:
        return branch_code + " (" + username + ")"

    # Initial step for user interaction
    async def async_step_user(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow start."""
        if self.schema_user is None:
            schema_user = OrderedDict()

            try:
                branches = await EnergosbytPlusAPI.async_get_branches()
            except Exception as e:
                _LOGGER.warning(
                    f"Could not fetch branches list, falling back to text entry; error: {e}"
                )
                schema_user[CONF_BRANCH] = cv.string
            else:
                schema_user[CONF_BRANCH] = vol.In(
                    {branch.code: branch.title for branch in branches}
                )

            schema_user[vol.Required(CONF_USERNAME)] = str
            schema_user[vol.Required(CONF_PASSWORD)] = str
            self.schema_user = vol.Schema(schema_user)

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=self.schema_user)

        branch_code = user_input[CONF_BRANCH]
        username = user_input[CONF_USERNAME]

        if await self._check_entry_exists(branch_code, username):
            return self.async_abort(reason="already_configured_service")

        async with EnergosbytPlusAPI(
            branch_code=branch_code,
            username=username,
            password=user_input[CONF_PASSWORD],
        ) as api:
            try:
                await api.async_authenticate()

            except EnergosbytPlusException as e:
                _LOGGER.error(f"Authentication error: {repr(e)}")
                return self.async_show_form(
                    step_id="user",
                    data_schema=self.schema_user,
                    errors={"base": "authentication_error"},
                )

            try:
                self._accounts = await api.async_get_accounts()

            except EnergosbytPlusException as e:
                _LOGGER.error(f"Request error: {repr(e)}")
                return self.async_show_form(
                    step_id="user",
                    data_schema=self.schema_user,
                    errors={"base": "update_accounts_error"},
                )

        self._current_config = user_input

        return await self.async_step_select()

    async def async_step_select(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        accounts, current_config = self._accounts, self._current_config
        if user_input is None:
            if accounts is None or current_config is None:
                return await self.async_step_user()

            return self.async_show_form(
                step_id="select",
                data_schema=vol.Schema(
                    {
                        vol.Optional(CONF_ACCOUNTS): cv.multi_select(
                            {
                                account.number: account.number
                                for account in self._accounts
                            }
                        )
                    }
                ),
            )

        if user_input[CONF_ACCOUNTS]:
            current_config[CONF_DEFAULT] = False
            current_config[CONF_ACCOUNTS] = dict.fromkeys(
                user_input[CONF_ACCOUNTS], True
            )

        return self.async_create_entry(
            title=self.make_entry_title(
                current_config[CONF_BRANCH],
                current_config[CONF_USERNAME],
            ),
            data=_flatten(current_config),
        )

    async def async_step_import(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        if user_input is None:
            return self.async_abort(reason="unknown_error")

        username = user_input[CONF_USERNAME]
        branch_code = user_input[CONF_BRANCH]

        if await self._check_entry_exists(branch_code, username):
            return self.async_abort(reason="already_exists")

        return self.async_create_entry(
            title=self.make_entry_title(branch_code, username),
            data={CONF_USERNAME: username, CONF_BRANCH: branch_code},
        )
