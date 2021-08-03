_ЛК &#xab;ЭнергосбыТ Плюс&#xbb;_ для _Home Assistant_
==================================================

> Предоставление информации о текущем состоянии ваших лицевых счетов в ЛК ЭнергосбыТ Плюс.
> Передача показаний по счётчикам.
>
> TNS Energo personal cabinet information and status retrieval, with meter indications submission capabilities.
> 
>[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
> [![Лицензия](https://img.shields.io/badge/%D0%9B%D0%B8%D1%86%D0%B5%D0%BD%D0%B7%D0%B8%D1%8F-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
> [![Поддержка](https://img.shields.io/badge/%D0%9F%D0%BE%D0%B4%D0%B4%D0%B5%D1%80%D0%B6%D0%B8%D0%B2%D0%B0%D0%B5%D1%82%D1%81%D1%8F%3F-%D0%B4%D0%B0-green.svg)](https://github.com/alryaz/hass-energosbyt-plus/graphs/commit-activity)
>
>[![Пожертвование Yandex](https://img.shields.io/badge/%D0%9F%D0%BE%D0%B6%D0%B5%D1%80%D1%82%D0%B2%D0%BE%D0%B2%D0%B0%D0%BD%D0%B8%D0%B5-Yandex-red.svg)](https://money.yandex.ru/to/410012369233217)
> [![Пожертвование PayPal](https://img.shields.io/badge/%D0%9F%D0%BE%D0%B6%D0%B5%D1%80%D1%82%D0%B2%D0%BE%D0%B2%D0%B0%D0%BD%D0%B8%D0%B5-Paypal-blueviolet.svg)](https://www.paypal.me/alryaz)

> ❗ **ВНИМАНИЕ** ❗ На данный момент интеграция не поддерживает отправку показаний. Для участия в
> тестировании данного функционала, пожалуйста, свяжитесь с разработчиком, или
> [откройте issue](https://github.com/alryaz/hass-energosbyt-plus/issues/new).

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

## Установка

### Посредством HACS

> **✔️️ Рекомендуемый метод**

1. Установите
   HACS ([инструкция по установке на оф. сайте](https://hacs.xyz/docs/installation/installation/))
2. Добавьте репозиторий в список дополнительных
3. Найдите `EnergosbyT Plus` (`ЭнергосбыТ Плюс`) в поиске по интеграциям <sup>1</sup>
4. Установите последнюю версию компонента, нажав на кнопку `Установить` (`Install`)
5. Перезапустите Home Assistant


### Вручную

> **⚠️ Не рекомендуется**

## Конфигурация компонента:
- Вариант А: Через _Интеграции_ (в поиске - "ЭнергосбыТ Плюс" или "TNS Energo")
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

