_ЛК &#xab;ЭнергосбыТ Плюс&#xbb;_ для _Home Assistant_
==================================================

<img src="https://raw.githubusercontent.com/alryaz/hass-energosbyt-plus/master/images/header.png" alt="Логотип интеграции">

> Предоставление информации о текущем состоянии ваших лицевых счетов в ЛК ЭнергосбыТ Плюс.
> Передача показаний по счётчикам.
>
> EnergosbyT Plus personal cabinet information and status retrieval, with meter indications submission capabilities.
>
> [![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
> [![Лицензия](https://img.shields.io/badge/%D0%9B%D0%B8%D1%86%D0%B5%D0%BD%D0%B7%D0%B8%D1%8F-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
> [![Поддержка](https://img.shields.io/badge/%D0%9F%D0%BE%D0%B4%D0%B4%D0%B5%D1%80%D0%B6%D0%B8%D0%B2%D0%B0%D0%B5%D1%82%D1%81%D1%8F%3F-%D0%B8%D0%B7%D1%80%D0%B5%D0%B4%D0%BA%D0%B0-green.svg?style=for-the-badge)](https://github.com/alryaz/hass-energosbyt-plus/graphs/commit-activity)

> 💵 **Пожертвование на развитие проекта**  
> [![Пожертвование YooMoney](https://img.shields.io/badge/YooMoney-8B3FFD.svg?style=for-the-badge)](https://yoomoney.ru/to/410012369233217)
> [![Пожертвование Тинькофф](https://img.shields.io/badge/Tinkoff-F8D81C.svg?style=for-the-badge)](https://www.tinkoff.ru/cf/3g8f1RTkf5G)
> [![Пожертвование PayPal](https://img.shields.io/badge/PayPal-159BD7.svg?style=for-the-badge)](https://www.paypal.me/alryaz)
> [![Пожертвование Cбербанк](https://img.shields.io/badge/Сбербанк-green.svg?style=for-the-badge)](https://www.sberbank.com/ru/person/dl/jc?linkname=3pDgknI7FY3z7tJnN)
>
> 💬 **Техническая поддержка**  
> [![Группа в Telegram](https://img.shields.io/endpoint?url=https%3A%2F%2Ftg.sumanjay.workers.dev%2Falryaz_ha_addons&style=for-the-badge)](https://telegram.dog/alryaz_ha_addons)


## Скриншоты

<details>
  <summary>Информация о лицевом счёте</summary> 
  <img src="https://raw.githubusercontent.com/alryaz/hass-energosbyt-plus/main/images/account.png" alt="Скриншот: Информация о лицевом счёте">
</details>
<details>
  <summary>Общие начисления</summary> 
  <img src="https://raw.githubusercontent.com/alryaz/hass-energosbyt-plus/main/images/charges.png" alt="Скриншот: Общие начисления">
</details>
<details>
  <summary>Начисления по услуге</summary> 
  <img src="https://raw.githubusercontent.com/alryaz/hass-energosbyt-plus/main/images/service_charges.png" alt="Скриншот: Начисления по услуге">
</details>
<details>
  <summary>Последний зарегистрированный платёж</summary> 
  <img src="https://raw.githubusercontent.com/alryaz/hass-energosbyt-plus/main/images/last_payment.png" alt="Скриншот: Последний зарегистрированный платёж">
</details>
<details>
  <summary>Счётчик коммунальных услуг</summary> 
  <img src="https://raw.githubusercontent.com/alryaz/hass-energosbyt-plus/main/images/meter.png" alt="Скриншот: Счётчик коммунальных услуг">
</details>
<details>
  <summary>Служба отправки показаний</summary> 
  <img src="https://raw.githubusercontent.com/alryaz/hass-energosbyt-plus/main/images/push_indications_service.png" alt="Скриншот: Служба отправки показаний">
</details>

## Установка

1. Установите
   HACS ([инструкция по установке на оф. сайте](https://hacs.xyz/docs/installation/installation/))
1. Найдите `EnergosbyT Plus` (`ЭнергосбыТ Плюс`) в поиске по интеграциям <sup>1</sup>
1. Установите последнюю версию компонента, нажав на кнопку `Установить` (`Install`)
1. Перезапустите Home Assistant

## Конфигурация компонента:
- Вариант А: Через _Интеграции_ (в поиске - "ЭнергосбыТ Плюс" или "EnergosbyT Plus")
- Вариант Б: YAML

### Пример конфигурации YAML
```yaml
...
energosbyt_plus:
  # Выбран филиал в г. Киров
  branch: kirov
  username: 1234567890
  password: super_password
```


### Описание конфигурационной схемы
```yaml
...
energosbyt_plus:
  
  # Филиал / регион
  # Доступные филиалы на момент релиза:
  # - vladimir: Владимирский филиал
  # - ivanovo: Ивановский филиал
  # - kirov: Кировский филиал
  # - chuvashia: Филиал Марий Эл и Чувашии
  # - oren: Оренбургский филиал
  # - samara: Самарский филиал
  # - saratov: Саратовский филиал
  # - ekb: Свердловский филиал (Екатеринбург)
  # - udm: Удмуртский филиал
  # - ulyanov: Ульяновский филиал
  branch: "..."

  # Имя пользователя (номер лицевого счёта)
  # Обязательный параметр
  username: "..."

  # Пароль
  # Обязательный параметр
  password: "..."

  # Конфигурация по умолчанию для лицевых счетов
  # Необязательный параметр
  #  # Данная конфигурация применяется, если отсутствует  # конкретизация, указанная в разделе `accounts`.
  default:

    # Добавлять ли объект(-ы): Информация о лицевом счёте
    # Значение по умолчанию: истина (true)
    accounts: true | false

    # Добавлять ли объект(-ы): Счётчик коммунальных услуг
    # Значение по умолчанию: истина (true)
    meters: true | false

    # Добавлять ли объект(-ы): Последний зарегистрированный платёж
    # Значение по умолчанию: истина (true)
    last_payment: true | false
    
    # Добавлять ли объект(-ы): Общие начисления
    # Значение по умолчанию: истина (true)
    charges: true | false
    
    # Добавлять ли объект(-ы): Начисления по услугам
    # Значение по умолчанию: истина (true)
    service_charges: true | false
    
    # Скрытие персональных данных
    #
    # Внимание! Данный параметр является техническим, и используется исключительно для
    # разработки и создания скриншотов (например, для тикетов). Его использование не
    # рекомендовано! Данный параметр не скрывает Ваши личные данные из логов.
    #
    # Значение по умолчанию: ложь (false)
    dev_presentation: true | false

  # Настройки для отдельных лицевых счетов
  # Необязательный параметр
  accounts:

    # Номер лицевого счёта
    "...":

      # Конфигурация по конкретным лицевым счетам выполняется аналогично
      # конфигурации по умолчанию для лицевых счетов (раздел `default`).
      ...
```

### Вариант конфигурации "Чёрный список"

Для реализации белого списка, конфигурация выполняется следующим образом:
```yaml
...
energosbyt_plus:
  ...
  # Выборочное исключение лицевых счетов
  accounts:
    # Все указанные ниже лицевые счета будут добавлены
    "123123123000": false
    "321321321000": false
    "333222111001": false
```

### Вариант конфигурации "Белый список"

Для реализации белого списка, конфигурация выполняется следующим образом:
```yaml
...
energosbyt_plus:
  ...
  # Отключение добавление лицевых счетов по умолчанию
  default: false

  # Выборочное включение лицевых сченов
  accounts:
    # Все указанные ниже лицевые счета будут добавлены
    "123123123000": true
    "321321321000": true
    "333222111001": true
```

Также возможно использовать укороченную запись:
```yaml
...
energosbyt_plus:
  ...
  # Данный пример функционально эквивалентен предыдущему примеру
  default: false
  accounts: ["123123123000", "321321321000", "333222111001"]
```

## Использование

### Служба передачи показаний - `energosbyt_plus.push_indications`

Служба передачи показаний позволяет отправлять показания по счётчикам в личный кабинет, и
имеет следующий набор параметров:

| Название | Описание |
| --- | --- |
| `target` | Выборка целевых объектов, для которых требуется передавать показания |
| `data`.`indications` | Список / именованный массив показаний, передаваемых в ЛК |
| `data`.`incremental` | Суммирование текущих показаний с передаваемыми |
| `data`.`ignore_period` | Игнорировать период передачи показаний |
| `data`.`ignore_indications` | Игнорировать ограничения по значениям |

#### Примеры вызова службы

##### 1. Обычная передача показаний

- Например, если передача показаний активна с 15 по 25 число, а сегодня 11, то показания
  <font color="red">**не будут**</font> отправлены<sup>1</sup>.
- Например, если текущие, последние или принятые значения по счётчику &ndash; 321, 654 и 987 по зонам
  _Т1_, _Т2_ и _Т3_ соответственно, то показания <font color="red">**не будут**</font>
  отправлены<sup>1</sup>.
  
```yaml
service: energosbyt_plus.push_indications
data:
  indications: "123, 456, 789"
target:
  entity_id: sensor.1243145122_meter_123456789
```

... или, с помощью именованного массива:

```yaml
service: energosbyt_plus.push_indications
data:
  indications:
    t1: 123
    t2: 456
    t3: 789
target:
  entity_id: sensor.1243145122_meter_123456789
```

... или, с помощью списка:

```yaml
service: energosbyt_plus.push_indications
data:
  indications: [123, 456, 789]
target:
  entity_id: sensor.1243145122_meter_123456789
```

##### 2. Форсированная передача показаний

Отключение всех ограничений по показаниям.

- Например, если передача показаний активна с 15 по 25 число, а сегодня 11, то показания
  <font color="green">**будут**</font> отправлены<sup>1</sup>.
- Например, если текущие, последние или принятые значения по счётчику &ndash; 321, 654 и 987 по зонам
  _Т1_, _Т2_ и _Т3_ соответственно, то показания <font color="green">**будут**</font>
  отправлены<sup>1</sup>.
  
```yaml
service: energosbyt_plus.push_indications
data_template:
  indications: [123, 456, 789]
  ignore_indications: true
  ignore_periods: true
target:
  entity_id: sensor.1243145122_meter_123456789
```

##### 3. Сложение показаний

- Например, если передача показаний активна с 15 по 25 число, а сегодня 11, то показания
  <font color="red">**не будут**</font> отправлены<sup>1</sup>.
- Например, если текущие, последние или принятые значения по счётчику &ndash; 321, 654 и 987 по зонам
  _Т1_, _Т2_ и _Т3_ соответственно, то показания <font color="green">**будут**</font>
  отправлены<sup>1</sup>.
  
**Внимание:** в данном примере будут отправлены показания _444_, _1110_ и _1776_,
а не _123_, _456_ и _789_. 
  
```yaml
service: energosbyt_plus.push_indications
data_template:
  indications: [123, 456, 789]
  incremental: true
target:
  entity_id: sensor.1243145122_meter_123456789
```
