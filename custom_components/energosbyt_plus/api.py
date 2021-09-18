import logging
from abc import abstractmethod
from datetime import date, datetime
from time import time
from typing import (
    Any,
    Callable,
    ClassVar,
    Final,
    Hashable,
    Iterable,
    Mapping,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

import aiohttp
import attr

_T = TypeVar("_T")
_TBaseDataItem = TypeVar("_TBaseDataItem", bound="_BaseDataItem")

_LOGGER = logging.getLogger(__name__)


def dash_or_converter(input_str: str, converter: Callable[[str], _T]) -> Optional[_T]:
    if input_str.strip() == "-":
        return None
    return converter(input_str)


def convert_date(date_str: str):
    return datetime.strptime(date_str, "%d.%m.%Y").date()


MIN_REQUEST_DATE = date(year=1900, month=1, day=1)


class EnergosbytPlusException(Exception):
    pass


class ObjectMissingData(EnergosbytPlusException):
    pass


class MethodRequiresAPI(ObjectMissingData):
    pass


class UnauthenticatedException(EnergosbytPlusException):
    pass


LOGIN_TYPE_CONTACT: Final = "contact"
LOGIN_TYPE_ACCOUNT: Final = "account"


class EnergosbytPlusAPI:
    BASE_LK_URL: ClassVar[str] = "https://lkm.esplus.ru"

    def __init__(
        self,
        branch_code: str,
        username: str,
        password: str,
        session: Optional[aiohttp.ClientSession] = None,
        login_type: Optional[str] = None,
    ) -> None:
        self._branch_code = branch_code
        self._username = username
        self._password = password
        self._session = session or aiohttp.ClientSession()
        self._login_type = login_type

        self._access_token: Optional[str] = None
        self._access_token_type: str = "Bearer"
        self._token_expires_at: float = -1.0
        self._refresh_token: Optional[str] = None

        self._request_counter: int = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._session.__aexit__(exc_type, exc_val, exc_tb)

    @property
    def branch_code(self) -> str:
        return self._branch_code

    @property
    def username(self) -> str:
        return self._username

    @property
    def password(self) -> str:
        return self._password

    @property
    def access_token(self) -> Optional[str]:
        return self._access_token

    @property
    def refresh_token(self) -> Optional[str]:
        return self._refresh_token

    @property
    def access_token_type(self) -> str:
        return self._access_token_type

    @property
    def token_expires_at(self) -> float:
        if self._access_token is None:
            return -1.0
        return self._token_expires_at

    @property
    def is_token_expired(self) -> bool:
        return time() > self._token_expires_at

    def _get_request_headers(
        self, authenticated: bool, headers: Optional[Mapping[str, Any]]
    ):
        headers = dict(headers or {})
        headers["x-requested-from"] = "esb-mobile-app"
        headers[aiohttp.hdrs.USER_AGENT] = "okhttp/3.12.1"

        if authenticated:
            if self.is_token_expired is None:
                # @TODO: add reauthentication
                raise UnauthenticatedException("account is not authenticated")

            headers[
                aiohttp.hdrs.AUTHORIZATION
            ] = f"{self._access_token_type} {self._access_token}"

        return headers

    async def _async_api_post_request(
        self,
        sub_url: str,
        authenticated: bool = True,
        headers: Optional[Mapping[str, Any]] = None,
        expected_status: int = 200,
        **kwargs,
    ) -> Any:
        request_counter = self._request_counter + 1
        self._request_counter = request_counter

        kwargs["headers"] = self._get_request_headers(authenticated, headers)
        _LOGGER.debug(f"[{request_counter}] POST:{sub_url} ({kwargs})")

        async with self._session.post(self.BASE_LK_URL + sub_url, **kwargs) as response:
            if response.status != expected_status:
                raise EnergosbytPlusException(
                    f"invalid response status ({response.status} != {expected_status})"
                )

            try:
                data = await response.json()
            except aiohttp.ContentTypeError:
                raise EnergosbytPlusException(
                    f"request failed (server did not provide a valid response)"
                )

            _LOGGER.debug(f"[{request_counter}] R:{data}")

            if data["error"] != 0:
                raise EnergosbytPlusException(f"request error {data['error']}")

            return data["content"]

    async def _async_api_get_request(
        self,
        sub_url: str,
        authenticated: bool = True,
        headers: Optional[Mapping[str, Any]] = None,
        **kwargs,
    ) -> Any:
        request_counter = self._request_counter + 1
        self._request_counter = request_counter

        kwargs["headers"] = self._get_request_headers(authenticated, headers)
        _LOGGER.debug(f"[{request_counter}] GET:{sub_url} ({kwargs})")

        async with self._session.get(self.BASE_LK_URL + sub_url, **kwargs) as response:
            data = await response.json()

            _LOGGER.debug(f"[{request_counter}] R:{data}")

            if data["error"] != 0:
                raise EnergosbytPlusException(f"request error {data['error']}")

            return data["content"]

    @classmethod
    async def async_get_branches(
        cls, session: Optional[aiohttp.ClientSession] = None
    ) -> Tuple["Branch", ...]:
        if session is None:
            async with aiohttp.ClientSession() as session:
                return await cls.async_get_branches(session)

        async with session.get(cls.BASE_LK_URL + "/api/v1/branches") as response:
            data = await response.json()
            if data["error"]:
                raise EnergosbytPlusException(
                    f"Could not fetch branches (error code: {data['error']})"
                )

            branches = data["content"]["branches"]  # @TODO: handle KeyError gracefully
            return tuple(
                Branch(
                    code=item["code"],
                    title=item["title"],
                    work_time=item["work_time"],
                    phone=item["phone"],
                    full_name=item["full_name"],
                )
                for item in branches
            )

    async def async_authenticate(self) -> None:
        username = self._username
        attempt_different_login_type = False

        login_type = self._login_type

        if login_type is None:
            if username.isnumeric():
                login_type = LOGIN_TYPE_ACCOUNT
                attempt_different_login_type = True
            else:
                login_type = LOGIN_TYPE_CONTACT

        request_url = "/api/v1/auth/login"
        request_json = {
            "login_type": login_type,
            "login": self._username,
            "password": self._password,
            "branch_code": self._branch_code,
        }

        try:
            content = await self._async_api_post_request(
                request_url,
                authenticated=False,
                json=request_json,
            )

        except BaseException as e:
            if attempt_different_login_type is False:
                _LOGGER.error(f"Error during authentication: {e}")
                raise EnergosbytPlusException(f"Error during authentication: {e}")

            _LOGGER.warning(
                f"Error during authentication with login_type={login_type}, "
                f"reattempting with login_type={LOGIN_TYPE_CONTACT}"
            )
            login_type = LOGIN_TYPE_CONTACT
            request_json["login_type"] = login_type
            content = await self._async_api_post_request(
                request_url,
                authenticated=False,
                json=request_json,
            )

        if self._login_type is None:
            self._login_type = login_type

        self._access_token = content["access_token"]
        self._access_token_type = content["token_type"]
        self._refresh_token = content["refresh_token"]
        self._token_expires_at = time() + content["expires_in"]

    async def async_get_residential_objects(self) -> Tuple["ResidentialObject", ...]:
        content = await self._async_api_get_request(
            "/api/v1/object/list", authenticated=True
        )
        return ResidentialObject.de_json_list(content["objects"], self)

    async def async_get_accounts(self) -> Tuple["Account", ...]:
        return tuple(
            account
            for object_ in await self.async_get_residential_objects()
            for account in object_.accounts
        )

    async def async_get_balance(self, account_id: str) -> "AccountBalance":
        content = await self._async_api_get_request(
            "/api/v1/account/balance",
            authenticated=True,
            params={"account_id": account_id},
        )
        return AccountBalance.de_json(content["balance"], self)

    async def async_get_charges(self, account_id: str) -> "AccountCharges":
        content = await self._async_api_get_request(
            "/api/v1/account/accruals",
            authenticated=True,
            params={"account_id": account_id},
        )
        return AccountCharges.de_json(content["accruals"], self)

    async def async_get_payments(
        self,
        account_id: str,
        period_start: Optional[date] = None,
        period_end: Optional[date] = None,
        limit: int = 10,
    ) -> Tuple["Payment", ...]:
        if period_end is None:
            period_end = date.today()

        if period_start is None:
            if period_end.month < 4:
                period_start = period_end.replace(
                    year=period_end.year - 1, month=12 + period_end.month - 3, day=1
                )
            else:
                period_start = period_end.replace(month=period_end.month - 3, day=1)

        content = await self._async_api_get_request(
            "/api/v1/statistics/payments",
            authenticated=True,
            params={
                "account_id": account_id,
                "period_from": f"{str(period_start.month).zfill(2)}.{str(period_start.year).zfill(4)}",
                "period_to": f"{str(period_end.month).zfill(2)}.{str(period_end.year).zfill(4)}",
                "limit": limit,
                "offset": 0,
            },
        )
        return Payment.de_json_list(content["payments"], self)

    async def async_get_last_payment(self, account_id: str) -> Optional["Payment"]:
        try:
            return (
                await self.async_get_payments(
                    account_id,
                    MIN_REQUEST_DATE,
                    date.today(),
                    1,
                )
            )[0]
        except IndexError:
            return None

    async def async_get_meters(self, account_id: str) -> Tuple["Meter", ...]:
        content = await self._async_api_get_request(
            "/api/v1/meter/list",
            authenticated=True,
            params={
                "account_id": account_id,
            },
        )

        return Meter.de_json_list(
            content["meters"].values(), self, account_id=account_id
        )

    async def async_get_meter_characteristics_per_residential_object(
        self,
    ) -> Tuple["ResidentialObjectMeters", ...]:
        content = await self._async_api_get_request(
            "/api/v1/settings/meters",
            authenticated=True,
        )

        meter_object_groups = content["objects"]

        if isinstance(meter_object_groups, Mapping):
            meter_object_groups = meter_object_groups.values()

        return ResidentialObjectMeters.de_json_list(meter_object_groups, self)

    async def async_get_meter_characteristics(
        self,
    ) -> Tuple["MeterCharacteristics", ...]:
        content = await self.async_get_meter_characteristics_per_residential_object()

        return tuple(
            characteristics
            for residential_holder in content
            for characteristics in residential_holder.meters
        )

    async def async_push_indications(
        self,
        account_id: str,
        meter_id: str,
        *args: Union[int, float],
        **kwargs: Union[int, float],
    ) -> None:
        if args:
            for t_index, arg in enumerate(args, start=1):
                assert (
                    t_index not in kwargs
                ), f"indication t{t_index} collision with named argument"
                kwargs["t" + str(t_index)] = arg

        assert kwargs, "at least one indication must be provided"

        await self._async_api_post_request(
            "/api/v1/meter/data/send",
            authenticated=True,
            json={
                **kwargs,
                "account_id": account_id,
                "meter_id": meter_id,
            },
        )


@attr.s(kw_only=True, frozen=True, slots=True)
class _BaseDataItem:
    api: Optional[EnergosbytPlusAPI] = attr.ib(default=None, repr=False)

    @classmethod
    @abstractmethod
    def de_json(
        cls: Type[_TBaseDataItem],
        data: Mapping[Hashable, Any],
        api: Optional[EnergosbytPlusAPI] = None,
    ) -> _TBaseDataItem:
        pass

    @classmethod
    def de_json_list(
        cls: Type[_TBaseDataItem],
        data: Iterable[Mapping[str, Any]],
        api: Optional[EnergosbytPlusAPI] = None,
        **kwargs,
    ) -> Tuple[_TBaseDataItem, ...]:
        # noinspection PyArgumentList
        return tuple(cls.de_json(item, api, **kwargs) for item in data)


@attr.s(kw_only=True, frozen=True, slots=True)
class MeterCharacteristicsZone:
    id: str = attr.ib()
    unit: str = attr.ib()


@attr.s(kw_only=True, frozen=True, slots=True)
class MeterCharacteristics(_BaseDataItem):
    id: str = attr.ib()
    code: str = attr.ib()
    name: str = attr.ib()
    number: str = attr.ib()
    manufacturer: Optional[str] = attr.ib()
    brand: Optional[str] = attr.ib()
    model: Optional[str] = attr.ib()
    type: Optional[str] = attr.ib()
    accuracy_class: Optional[str] = attr.ib()
    digits: Optional[int] = attr.ib()
    installation_date: Optional[date] = attr.ib()
    last_checkup_date: Optional[date] = attr.ib()
    next_checkup_date: Optional[date] = attr.ib()
    zones: Tuple[MeterCharacteristicsZone, ...] = attr.ib()
    residential_object_id: Optional[str] = attr.ib(
        default=None
    )  # this attribute is non-standard

    @classmethod
    def de_json(
        cls: Type[_TBaseDataItem],
        data: Mapping[Hashable, Any],
        api: Optional[EnergosbytPlusAPI] = None,
        residential_object_id: Optional[str] = None,
    ) -> _TBaseDataItem:
        return cls(
            api=api,
            id=data["id"],
            code=data["code"],
            name=data["name"],
            number=data["number"],
            manufacturer=dash_or_converter(data["manufacturer"], str),
            brand=dash_or_converter(data["mark"], str),
            model=dash_or_converter(data["model"], str),
            type=dash_or_converter(data["type"], str),
            accuracy_class=dash_or_converter(data["accuracy_class"], str),
            digits=dash_or_converter(data["digits"], int),
            installation_date=dash_or_converter(data["installed_date"], convert_date),
            last_checkup_date=dash_or_converter(
                data["verification_date"], convert_date
            ),
            next_checkup_date=dash_or_converter(
                data["verification_period"], convert_date
            ),
            zones=tuple(
                MeterCharacteristicsZone(id="t%d" % (i,), unit=data["tariff%d" % (i,)])
                for i in range(1, int(data["zoning"]) + 1)
            ),
            residential_object_id=residential_object_id,
        )

    @property
    def zone_ids(self) -> Tuple[str, ...]:
        return tuple(zone.id for zone in self.zones)


@attr.s(kw_only=True, frozen=True, slots=True)
class ResidentialObjectMeters(_BaseDataItem):
    id: str = attr.ib()
    address: str = attr.ib()
    meters: Tuple[MeterCharacteristics, ...] = attr.ib()

    @classmethod
    def de_json(
        cls: Type[_TBaseDataItem],
        data: Mapping[Hashable, Any],
        api: Optional[EnergosbytPlusAPI] = None,
    ) -> _TBaseDataItem:
        residential_object_id = data["id"]
        return cls(
            api=api,
            id=residential_object_id,
            address=data["address"],
            meters=MeterCharacteristics.de_json_list(
                data["meters"], api, residential_object_id=residential_object_id
            ),
        )


@attr.s(kw_only=True, frozen=True, slots=True)
class Service(_BaseDataItem):
    id: str = attr.ib()
    code: str = attr.ib()
    name: str = attr.ib()

    @classmethod
    def de_json(
        cls: Type[_TBaseDataItem],
        data: Mapping[Hashable, Any],
        api: Optional[EnergosbytPlusAPI] = None,
    ) -> _TBaseDataItem:
        return cls(
            api=api,
            id=data["id"],
            code=data["code"],
            name=data["name"],
        )


@attr.s(kw_only=True, frozen=True, slots=True)
class MeterZone:
    id: str = attr.ib()
    accepted: Optional[float] = attr.ib()
    last_submitted: Optional[float] = attr.ib()
    submitted: Optional[float] = attr.ib()
    accepted_date: Optional[date] = attr.ib()
    accepted_period: Optional[date] = attr.ib()
    last_submitted_date: Optional[date] = attr.ib()


_CAPITAL_MONTH_NAMES = (
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
)


@attr.s(kw_only=True, frozen=True, slots=True)
class Meter(_BaseDataItem):
    id: str = attr.ib()
    number: str = attr.ib()
    service: Service = attr.ib()
    # room: Any = ... @TODO: ?
    submission_period_start_day: int = attr.ib()
    submission_period_end_day: int = attr.ib()
    status: str = attr.ib()
    unit: str = attr.ib()
    zones: Tuple[MeterZone, ...] = attr.ib()
    account_id: Optional[str] = attr.ib(default=None)  # this attribute is non-standard

    @classmethod
    def de_json(
        cls: Type[_TBaseDataItem],
        data: Mapping[Hashable, Any],
        api: Optional[EnergosbytPlusAPI] = None,
        account_id: Optional[str] = None,
    ) -> _TBaseDataItem:
        accepted = data["accepted"]
        if accepted is None:
            accepted_date = None
            accepted_period = None
        else:
            accepted_date = convert_date(accepted["date"])
            period_month_name, _, period_year = accepted["period"].partition(" ")
            accepted_period = date(
                year=int(period_year),
                month=_CAPITAL_MONTH_NAMES.index(period_month_name),
                day=1,
            )

        last_submitted = data["sent"]
        if last_submitted is None:
            last_submitted_date = None
        else:
            last_submitted_date = convert_date(last_submitted["date"])

        submitted = data["current"]

        return cls(
            api=api,
            id=data["id"],
            number=data["number"],
            service=Service.de_json(data["service"], api),
            unit=data["unit"],
            status=data["status"],
            submission_period_start_day=int(data["period"]["from"]),
            submission_period_end_day=int(data["period"]["to"]),
            zones=tuple(
                MeterZone(
                    id=zone_index,
                    accepted=None if accepted is None else float(accepted[zone_index]),
                    accepted_date=accepted_date,
                    accepted_period=accepted_period,
                    last_submitted=(
                        None
                        if last_submitted is None
                        else float(last_submitted[zone_index])
                    ),
                    last_submitted_date=last_submitted_date,
                    submitted=(
                        None if submitted is None else float(submitted[zone_index])
                    ),
                )
                for zone_index in map("t%s".__mod__, range(1, int(data["zoning"]) + 1))
            ),
            account_id=account_id,
        )

    @property
    def submission_period_start_date(self) -> date:
        return date.today().replace(day=self.submission_period_start_day)

    @property
    def submission_period_end_date(self) -> date:
        return date.today().replace(day=self.submission_period_end_day)

    @property
    def is_submission_period_active(self) -> bool:
        return (
            self.submission_period_start_day
            <= date.today().day
            <= self.submission_period_end_day
        )

    @property
    def remaining_days_for_submission(self) -> Optional[int]:
        today_day = date.today().day
        if today_day < self.submission_period_start_day:
            return None
        end_day = self.submission_period_end_day
        if today_day > end_day:
            return None
        return end_day - today_day

    @property
    def remaining_days_until_submission(self) -> Optional[int]:
        today = date.today()

        start_date = self.submission_period_start_date
        if today < start_date:
            return (start_date - today).days

        if today < self.submission_period_end_date:
            return None

        if today.month == 12:
            next_date = today.replace(
                year=today.year + 1, month=1, day=self.submission_period_start_day
            )
        else:
            next_date = today.replace(
                month=today.month + 1, day=self.submission_period_start_day
            )

        return (next_date - today).days

    @property
    def zone_ids(self) -> Tuple[str, ...]:
        return tuple(zone.id for zone in self.zones)

    async def async_push_indications(
        self,
        *args: Union[int, float],
        ignore_periods: bool = False,
        ignore_values: bool = False,
        **kwargs: Union[int, float],
    ):
        if self.api is None:
            raise MethodRequiresAPI("bound api object is required to retrieve balance")

        account_id = self.account_id
        if account_id is None:
            raise ObjectMissingData("account id not set for meter")

        if args:
            for t_index, arg in enumerate(args, start=1):
                assert (
                    t_index not in kwargs
                ), f"indication t{t_index} collision with named argument"
                kwargs["t" + str(t_index)] = arg

        invalid_zone_ids = kwargs.keys() - self.zone_ids
        if invalid_zone_ids:
            raise EnergosbytPlusException(
                f"invalid zones provided: {','.join(invalid_zone_ids)}"
            )

        if not (ignore_periods or self.is_submission_period_active):
            raise EnergosbytPlusException("submission period is not active")

        if not ignore_values:
            for zone_id, zone_value in kwargs.items():
                for zone in self.zones:
                    if zone.id == zone_id:
                        max_value = max(
                            zone.submitted or 0.0,
                            zone.last_submitted or 0.0,
                            zone.accepted or 0.0,
                        )
                        if zone_value < max_value:
                            raise EnergosbytPlusException(
                                f"submitted value ({zone_value}) for zone {zone_id} "
                                f"is less than zone max value ({max_value})"
                            )

        await self.api.async_push_indications(account_id, self.id, *args, **kwargs)


@attr.s(kw_only=True, frozen=True, slots=True)
class PaymentService(Service):
    amount: float = attr.ib()

    @classmethod
    def de_json(
        cls: Type[_TBaseDataItem],
        data: Mapping[Hashable, Any],
        api: Optional[EnergosbytPlusAPI] = None,
    ) -> _TBaseDataItem:
        return cls(
            api=api,
            id=data["id"],
            code=data["code"],
            name=data["name"],
            amount=float(data["amount"]),
        )


@attr.s(kw_only=True, frozen=True, slots=True)
class Payment(_BaseDataItem):
    id: str = attr.ib()
    created_at: date = attr.ib()
    amount: float = attr.ib()
    is_accepted: bool = attr.ib()
    services: Tuple[PaymentService, ...] = attr.ib()

    @classmethod
    def de_json(
        cls: Type[_TBaseDataItem],
        data: Mapping[Hashable, Any],
        api: Optional[EnergosbytPlusAPI] = None,
    ) -> _TBaseDataItem:
        return cls(
            api=api,
            id=data["id"],
            created_at=convert_date(data["created_at"]),
            amount=float(data["amount"]),
            is_accepted=data["accepted"],
            services=PaymentService.de_json_list(data["services"], api),
        )


@attr.s(kw_only=True, frozen=True, slots=True)
class AccrualsServiceZoneValues(_BaseDataItem):
    """Values for zones"""

    t1: float = attr.ib()
    t2: float = attr.ib()
    t3: float = attr.ib()

    @classmethod
    def de_json(
        cls: Type[_TBaseDataItem],
        data: Mapping[Hashable, Any],
        api: Optional[EnergosbytPlusAPI] = None,
    ) -> _TBaseDataItem:
        return cls(
            api=api,
            t1=float(data["t1"]),
            t2=float(data["t2"]),
            t3=float(data["t3"]),
        )


@attr.s(kw_only=True, frozen=True, slots=True)
class AccrualsServiceZone:
    id: str = attr.ib()
    cost: float = attr.ib()
    current: float = attr.ib()
    previous: float = attr.ib()

    @property
    def consumption(self) -> float:
        return self.current - self.previous


@attr.s(kw_only=True, frozen=True, slots=True)
class ServiceCharge(_BaseDataItem):
    """Accruals -> Service member item

    Contains information about charges for service within parent period."""

    id: str = attr.ib()
    code: str = attr.ib()
    name: str = attr.ib()
    initial: float = attr.ib()
    paid: float = attr.ib()
    charged: float = attr.ib()
    unit: str = attr.ib()
    increase_ratio_value: Optional[float] = attr.ib()
    increase_ratio_amount: Optional[float] = attr.ib()
    recalculation: float = attr.ib()
    benefits: float = attr.ib()
    penalty: float = attr.ib()
    total: float = attr.ib()
    percent: float = attr.ib()
    percent_accrued: float = attr.ib()
    zones: Tuple[AccrualsServiceZone, ...] = attr.ib()

    @classmethod
    def de_json(
        cls: Type[_TBaseDataItem],
        data: Mapping[Hashable, Any],
        api: Optional[EnergosbytPlusAPI] = None,
    ) -> _TBaseDataItem:
        try:
            increase_ratio_value = float(data["increase_ratio_value"])
        except TypeError:
            increase_ratio_value = None

        return cls(
            api=api,
            id=data["id"],
            code=data["code"],
            name=data["name"],
            initial=-float(data["start_balance"]),  # this negation is necessary
            paid=float(data["payed"]),
            charged=float(data["accrued"]),
            unit=data["unit"],
            increase_ratio_value=increase_ratio_value,
            increase_ratio_amount=float(data["increase_ratio_amount"]),
            recalculation=float(data["recalculation"]),
            benefits=float(data["benefits"]),
            penalty=float(data["penalty"]),
            total=float(data["end_balance"]),  # this negation is not performed
            percent=float(data["percent"]),
            percent_accrued=float(data["percent_accrued"]),
            zones=tuple(
                AccrualsServiceZone(
                    id=zone_index,
                    cost=float(data["cost"][zone_index]),
                    previous=float(data["previous_data"][zone_index]),
                    current=float(data["current_data"][zone_index]),
                )
                for zone_index in map("t%d".__mod__, range(1, int(data["zoning"]) + 1))
            ),
        )


@attr.s(kw_only=True, frozen=True, slots=True)
class AccountCharges(_BaseDataItem):
    period: date = attr.ib()
    balance: float = attr.ib()
    charged: float = attr.ib()
    services: Tuple[ServiceCharge, ...] = attr.ib(converter=tuple)

    def __float__(self):
        return self.charged

    @classmethod
    def de_json(
        cls: Type[_TBaseDataItem],
        data: Mapping[Hashable, Any],
        api: Optional[EnergosbytPlusAPI] = None,
    ) -> _TBaseDataItem:
        month, _, year = data["period"].partition(".")
        return cls(
            api=api,
            period=date(year=int(year), month=int(month), day=1),
            balance=-float(data["balance"]),  # this negation is necessary
            charged=float(data["accrued"]),
            services=ServiceCharge.de_json_list(data["services"], api),
        )


@attr.s(kw_only=True, frozen=True, slots=True)
class Branch(_BaseDataItem):
    """Generic branch information"""

    work_time: str = attr.ib()
    phone: str = attr.ib()
    code: str = attr.ib()
    title: str = attr.ib()
    full_name: str = attr.ib()

    @classmethod
    def de_json(
        cls: Type[_TBaseDataItem],
        data: Mapping[Hashable, Any],
        api: Optional[EnergosbytPlusAPI] = None,
    ) -> _TBaseDataItem:
        return cls(
            api=api,
            work_time=data["work_time"],
            phone=data["phone"],
            code=data["code"],
            title=data["title"],
            full_name=data["full_name"],
        )


@attr.s(kw_only=True, frozen=True, slots=True)
class ObjectBranch(_BaseDataItem):
    """Branch information associated with object data"""

    work_time: str = attr.ib()
    phone: str = attr.ib()
    code: str = attr.ib()
    id: str = attr.ib()
    name: str = attr.ib()

    @classmethod
    def de_json(
        cls: Type[_TBaseDataItem],
        data: Mapping[Hashable, Any],
        api: Optional[EnergosbytPlusAPI] = None,
    ) -> _TBaseDataItem:
        return cls(
            api=api,
            work_time=data["work_time"],
            phone=data["phone"],
            code=data["code"],
            id=data["id"],
            name=data["name"],
        )


@attr.s(kw_only=True, frozen=True, slots=True)
class Account(_BaseDataItem):
    """Account information associated with object data"""

    id: str = attr.ib()
    number: str = attr.ib()
    balance: float = attr.ib()
    auto_payment_enabled: bool = attr.ib()
    digital_receipts_enabled: bool = attr.ib()
    indications_submission_available: bool = attr.ib()
    indications_submission_complete: bool = attr.ib()
    has_meters: bool = attr.ib()
    days_until_submission: int = attr.ib()
    services_text: str = attr.ib()
    services_count: int = attr.ib()
    owner_id: str = attr.ib()

    # this attribute is non-standard
    residential_object: Optional["ResidentialObject"] = attr.ib(default=None)

    @classmethod
    def de_json(
        cls: Type[_TBaseDataItem],
        data: Mapping[Hashable, Any],
        api: Optional[EnergosbytPlusAPI] = None,
        residential_object: Optional["ResidentialObject"] = None,
    ) -> _TBaseDataItem:
        try:
            days_until_submission = int(data["metrics_until_value"])
        except TypeError:
            days_until_submission = -1

        return cls(
            api=api,
            id=data["id"],
            number=data["number"],
            balance=-float(data["balance"]),  # this negation is necessary
            auto_payment_enabled=data["auto_payment_enabled"],
            digital_receipts_enabled=data["el_receipt_subscribed"],
            indications_submission_available=data["metrics_send_available"],
            indications_submission_complete=data["all_meters_sent"],
            has_meters=data["has_meters"],
            days_until_submission=days_until_submission,
            services_text=data["services"],
            services_count=int(data["services_count"]),
            owner_id=data["owner_id"],
            residential_object=residential_object,
        )

    @property
    def services(self) -> Tuple[str, ...]:
        return tuple(map(str.strip, self.services_text.split(";")))

    async def async_get_balance(self):
        if self.api is None:
            raise MethodRequiresAPI("bound api object is required to retrieve balance")
        return await self.api.async_get_balance(self.id)

    async def async_get_charges(self):
        if self.api is None:
            raise MethodRequiresAPI("bound api object is required to retrieve charges")
        return await self.api.async_get_charges(self.id)

    async def async_get_payments(self):
        if self.api is None:
            raise MethodRequiresAPI("bound api object is required to retrieve payments")
        return await self.api.async_get_payments(self.id)

    async def async_get_last_payment(self):
        if self.api is None:
            raise MethodRequiresAPI(
                "bound api object is required to retrieve last payment"
            )
        return await self.api.async_get_last_payment(self.id)

    async def async_get_meters(self):
        if self.api is None:
            raise MethodRequiresAPI("bound api object is required to retrieve meters")
        return await self.api.async_get_meters(self.id)


@attr.s(kw_only=True, frozen=True, slots=True)
class ResidentialObject(_BaseDataItem):
    id: str = attr.ib()
    address: str = attr.ib()
    branch: ObjectBranch = attr.ib()
    is_object_head: bool = attr.ib()
    accounts: Tuple[Account, ...] = attr.ib(converter=tuple)

    @classmethod
    def de_json(
        cls: Type[_TBaseDataItem],
        data: Mapping[Hashable, Any],
        api: Optional[EnergosbytPlusAPI] = None,
    ) -> _TBaseDataItem:
        obj = cls(
            api=api,
            id=data["id"],
            address=data["address"],
            branch=ObjectBranch.de_json(data["branch"], api),
            is_object_head=data[
                "is_object_head"
            ],  # @TODO: is this parameter interesting?
            accounts=(),
        )

        object.__setattr__(
            obj,
            "accounts",
            tuple(Account.de_json_list(data["accounts"], api, residential_object=obj)),
        )

        return obj


@attr.s(kw_only=True, frozen=True, slots=True)
class BalanceService(_BaseDataItem):
    id: str = attr.ib()
    group: str = attr.ib()
    code: str = attr.ib()
    name: str = attr.ib()
    total: float = attr.ib()
    paid: float = attr.ib()
    balance_actual: float = attr.ib()
    accrued: float = attr.ib()
    commission_percent: float = attr.ib()
    commission_value: float = attr.ib()
    commission_actual_balance: float = attr.ib()
    # recalculation: List[...]

    @classmethod
    def de_json(
        cls: Type[_TBaseDataItem],
        data: Mapping[Hashable, Any],
        api: Optional[EnergosbytPlusAPI] = None,
    ) -> _TBaseDataItem:
        return cls(
            api=api,
            id=data["id"],
            group=data["group"],
            code=data["code"],
            name=data["name"],
            total=float(data["end_balance"]),  # this negation is not performed
            balance_actual=-float(data["actual_balance"]),
            accrued=float(data["accrued"]),
            commission_percent=float(data["commission_percent"]),
            commission_value=float(data["commission_value"]),
            commission_actual_balance=float(data["commission_actual_balance"]),
            paid=float(data["payed_in_period"]),
        )


@attr.s(kw_only=True, frozen=True, slots=True)
class AccountBalance(_BaseDataItem):
    period: date = attr.ib()
    balance: float = attr.ib()
    accrued: float = attr.ib()
    commission_balance: float = attr.ib()
    services: Tuple[BalanceService, ...] = attr.ib(converter=tuple)

    def __float__(self):
        return self.balance

    @classmethod
    def de_json(
        cls: Type[_TBaseDataItem],
        data: Mapping[Hashable, Any],
        api: Optional[EnergosbytPlusAPI] = None,
    ) -> _TBaseDataItem:
        month, _, year = data["period"].partition(".")
        return cls(
            api=api,
            period=date(year=int(year), month=int(month), day=1),
            balance=-float(data["balance"]),
            accrued=float(data["accrued"]),
            commission_balance=float(data["commission_balance"]),  # @TODO: ?
            services=BalanceService.de_json_list(data["services"], api),
        )
