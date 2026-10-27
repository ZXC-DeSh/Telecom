# API — AntiFraude

REST API системы анализа телефонных вызовов и выявления подозрительной активности.

**Base URL:** `https://fraud-egg.onthewifi.com`  
**Версия API:** `v1`  
**Формат обмена:** JSON  
**OpenAPI / Swagger UI:** [https://fraud-egg.onthewifi.com/docs](https://fraud-egg.onthewifi.com/docs)  
**OpenAPI JSON:** [https://fraud-egg.onthewifi.com/openapi.json](https://fraud-egg.onthewifi.com/openapi.json)

Все прикладные маршруты находятся под префиксом `/api/v1`.

## Общий формат ответа

Успешные ответы обёрнуты в общий объект:

```json
{
  "status_code": 200,
  "message": "OK",
  "data": {}
}
```

- `status_code` — HTTP-код результата.
- `message` — текстовое сообщение.
- `data` — объект результата или `null`.

Содержимое `data` зависит от эндпоинта. Для списков используются поля пагинации `items`, `page`, `page_size`, `total` и `pages`.

## Эндпоинты

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/api/v1/health` | Проверка состояния API, PostgreSQL и ML-модели |
| `GET` | `/api/v1/model/info` | Информация о модели и её метриках |
| `POST` | `/api/v1/predict` | Скоринг одного вызова или пакета CDR |
| `GET` | `/api/v1/calls` | Поиск и постраничный просмотр вызовов |
| `GET` | `/api/v1/calls/{call_id}` | Подробная информация о вызове и последняя оценка риска |
| `GET` | `/api/v1/fraud-alerts` | Список подозрительных вызовов |
| `GET` | `/api/v1/subscribers/{msisdn_a}` | Профиль абонента, статистика, контакты и активность |
| `GET` | `/api/v1/dashboard/summary` | Сводная статистика и временная динамика |
| `GET` | `/api/v1/dashboard/refresh-status` | Состояние обновления статистики дашборда |
| `POST` | `/api/v1/analysis/run` | Создание задания анализа CDR за период |
| `GET` | `/api/v1/analysis/{job_id}` | Состояние и прогресс задания анализа |
| `GET` | `/api/v1/analysis/current` | Активные, ожидающие и последние завершённые задания |

## Форматы данных

### Тип вызова

Поле `call_type` принимает одно из значений:

| Значение | Значение вызова |
|---|---|
| `01` | Входящий |
| `02` | Исходящий |
| `03` | Переадресация |

### Уровень риска

Поле `risk_level` может принимать значения `low`, `medium`, `high`, `critical`.

`risk_score` — число в диапазоне от `0` до `1`. Это оценка риска, а не процент в диапазоне 0–100. Для отображения в процентах значение можно умножить на 100.

### Сценарий фрода

`fraud_scenario` может содержать код `S1`–`S7` либо `null`, если сценарий не определён.

### Рекомендация оператору

Поле `recommendation` принимает значения:

- `monitor` — наблюдать;
- `manual_review` — направить на ручную проверку;
- `escalate` — эскалировать.

`auto_blocked` показывает состояние автоблокировки. Скоринговый результат сам по себе не означает, что вызов был заблокирован.

### Формат CDR

Объект `CDRCreate` используется для скоринга переданной записи:

| Поле | Тип | Обязательное | Ограничения |
|---|---|---|---|
| `call_type` | `string` | Да | `01`, `02` или `03` |
| `imsi_a` | `string \| null` | Нет | Если задано, длина 1–32 символа |
| `msisdn_a` | `string` | Да | Ровно 10 цифр |
| `msisdn_b` | `string` | Да | Ровно 10 цифр |
| `call_time` | `string` | Да | Дата и время в формате RFC 3339 / ISO 8601 |
| `duration_seconds` | `number` | Да | Неотрицательное значение |
| `msisdn_c` | `string \| null` | Нет | `null` либо ровно 10 цифр |

Пример `call_time`: `2026-10-14T11:42:00+03:00`. Номера передаются без знака `+`, пробелов и разделителей.

## Проверка состояния сервиса

### `GET /api/v1/health`

Возвращает общее состояние сервиса и состояние зависимостей.

Пример запроса:

```bash
curl https://fraud-egg.onthewifi.com/api/v1/health
```

Пример ответа:

```json
{
  "status_code": 200,
  "message": "OK",
  "data": {
    "status": "ok",
    "database": {
      "status": "ok",
      "message": null
    },
    "model": {
      "status": "ok",
      "message": null
    }
  }
}
```

Поля `status`, `database.status` и `model.status` могут принимать значения `ok`, `degraded` или `unavailable`. Для зависимостей также может возвращаться поясняющее поле `message`.

### `GET /api/v1/model/info`

Возвращает сведения о загруженной модели.

```bash
curl https://fraud-egg.onthewifi.com/api/v1/model/info
```

Структура `data`:

```json
{
  "name": "antifraud-catboost",
  "version": "1.0.0",
  "algorithm": "CatBoost",
  "trained_at": null,
  "feature_names": [],
  "metrics": {
    "precision": null,
    "recall": null,
    "f1_score": null,
    "pr_auc": null,
    "false_positive_rate": null
  },
  "is_loaded": true
}
```

Пример иллюстрирует структуру ответа; фактические значения `name`, `version`, `feature_names` и метрик определяются развёрнутой моделью. Метрики могут быть `null`, если они не заданы.

## Скоринг вызовов

### `POST /api/v1/predict`

Выполняет оценку риска для одного вызова либо пакета вызовов. `Content-Type: application/json`.

#### Скоринг одного вызова

Передайте объект `call` с данными CDR. Необязательное поле `call_id` связывает оценку с существующим вызовом, если это предусмотрено сценарием обработки.

```bash
curl -X POST \
  https://fraud-egg.onthewifi.com/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{
    "call": {
      "call_type": "02",
      "imsi_a": "250010123456789",
      "msisdn_a": "8991234567",
      "msisdn_b": "8107654321",
      "call_time": "2026-10-14T11:42:00",
      "duration_seconds": 6,
      "msisdn_c": null
    }
  }'
```

Пример ответа:

```json
{
  "status_code": 200,
  "message": "Prediction completed",
  "data": {
    "call_id": null,
    "risk_score": 0.91,
    "risk_level": "critical",
    "is_fraud": true,
    "fraud_scenario": "S1",
    "reasons": [
      {
        "feature": "short_call_ratio",
        "value": 0.94,
        "impact": "positive",
        "contribution": 0.31,
        "description": "Высокая доля коротких вызовов"
      }
    ],
    "recommendation": "manual_review",
    "operator_message": "Вызов имеет высокий риск мошеннической активности. Требуется проверка оператором.",
    "auto_blocked": false
  }
}
```

Числа и тексты в примере демонстрационные; реальный результат зависит от входной записи, доступной истории и загруженной модели.

#### Пакетный скоринг

Передайте массив `calls`. Размер пакета — от 1 до 1000 записей.

```json
{
  "calls": [
    {
      "call_type": "02",
      "imsi_a": "250010123456789",
      "msisdn_a": "8991234567",
      "msisdn_b": "8107654321",
      "call_time": "2026-10-14T11:42:00+03:00",
      "duration_seconds": 6,
      "msisdn_c": null
    },
    {
      "call_type": "01",
      "imsi_a": null,
      "msisdn_a": "8107654321",
      "msisdn_b": "8991234567",
      "call_time": "2026-10-14T11:45:00+03:00",
      "duration_seconds": 125,
      "msisdn_c": null
    }
  ]
}
```

Ответ содержит `items` с результатами по отдельным вызовам, `total` — количество переданных записей и `processed` — количество обработанных записей:

```json
{
  "status_code": 200,
  "message": "Batch prediction completed",
  "data": {
    "items": [
      {
        "call_id": null,
        "risk_score": 0.91,
        "risk_level": "critical",
        "is_fraud": true,
        "fraud_scenario": "S1",
        "reasons": [],
        "recommendation": "manual_review",
        "operator_message": "Требуется проверка оператором.",
        "auto_blocked": false
      }
    ],
    "total": 2,
    "processed": 2
  }
}
```

В сокращённом примере показан один элемент `items`; в полном ответе массив содержит результаты всех обработанных вызовов.

#### Интерпретация результата

- `risk_score` — оценка в диапазоне `0.0–1.0`; чем выше значение, тем выше рассчитанный риск.
- `risk_level` — категория риска: `low`, `medium`, `high` или `critical`.
- `is_fraud` — классификационный результат модели/сервиса.
- `fraud_scenario` — код предполагаемого сценария `S1`–`S7`, если он определён.
- `reasons` — список факторов. Каждый элемент содержит обязательные `feature` и `impact`, а также необязательные `value`, `contribution` и `description`.
- `recommendation` — рекомендуемое действие для оператора.
- `operator_message` — текстовое пояснение результата.
- `auto_blocked` — признак фактической автоблокировки; по умолчанию `false`.

Для `reasons[].impact` API задаёт строковый тип, но закрытый перечень допустимых значений схемой не установлен. Не следует интерпретировать `contribution` как вероятность: это отдельное числовое поле объяснения.

## Вызовы и поиск

### `GET /api/v1/calls`

Возвращает постраничный список вызовов. Все параметры необязательные.

| Параметр | Тип | Ограничения |
|---|---|---|
| `date_from` | `date-time` | Нижняя граница времени |
| `date_to` | `date-time` | Верхняя граница времени |
| `call_type` | `string` | `01`, `02`, `03` |
| `msisdn` | `string` | Ровно 10 цифр |
| `risk_level` | `string` | `low`, `medium`, `high`, `critical` |
| `page` | `integer` | От 1, по умолчанию `1` |
| `page_size` | `integer` | От 1 до 100, по умолчанию `20` |

Пример:

```bash
curl "https://fraud-egg.onthewifi.com/api/v1/calls?risk_level=high&page=1&page_size=20"
```

Структура ответа:

```json
{
  "status_code": 200,
  "message": "OK",
  "data": {
    "items": [],
    "page": 1,
    "page_size": 20,
    "total": 0,
    "pages": 0
  }
}
```

Элемент `items` содержит идентификатор вызова, поля CDR и доступные поля оценки риска: `risk_score`, `risk_level`, `is_fraud`, `fraud_scenario`.

### `GET /api/v1/calls/{call_id}`

Возвращает подробности одного вызова. `call_id` должен быть UUID.

```bash
curl "https://fraud-egg.onthewifi.com/api/v1/calls/2aab44d0-7c0b-4f0e-9f65-6b8a5d74a100"
```

В `data` возвращаются поля CDR, идентификатор, оценка риска, сценарий, операторы A/B/C, `reasons`, `recommendation` и `operator_message`. Поля оценки могут быть `null`, если оценка для вызова отсутствует.

## Подозрительные вызовы

### `GET /api/v1/fraud-alerts`

Возвращает постраничный список подозрительных вызовов.

| Параметр | Тип | Ограничения |
|---|---|---|
| `risk_level` | `string` | `low`, `medium`, `high`, `critical` |
| `fraud_scenario` | `string` | `S1`–`S7` |
| `msisdn` | `string` | Ровно 10 цифр |
| `date_from` | `date-time` | Нижняя граница времени |
| `date_to` | `date-time` | Верхняя граница времени |
| `page` | `integer` | От 1, по умолчанию `1` |
| `page_size` | `integer` | От 1 до 100, по умолчанию `20` |

Пример:

```bash
curl "https://fraud-egg.onthewifi.com/api/v1/fraud-alerts?risk_level=critical&fraud_scenario=S1"
```

Элемент `items` содержит `alert_id`, `call_id`, время вызова, номера A/B, длительность, `risk_score`, `risk_level`, `fraud_scenario`, `reasons`, `recommendation`, `operator_message` и `auto_blocked`.

## Профиль абонента

### `GET /api/v1/subscribers/{msisdn_a}`

Возвращает профиль абонента. Номер должен содержать ровно 10 цифр.

```bash
curl "https://fraud-egg.onthewifi.com/api/v1/subscribers/8991234567"
```

Структура `data` включает:

- `msisdn`, `first_seen_at`, `last_seen_at`;
- `risk_score`, `risk_level`;
- `statistics` — количество входящих, исходящих и переадресованных вызовов, уникальных контактов, коротких и неотвеченных вызовов, их доли;
- `contacts` — контакты, число вызовов и доступные оценки риска;
- `activity` — временные точки активности;
- `related_suspicious_numbers` — связанные подозрительные номера.

Пример сокращённого ответа:

```json
{
  "status_code": 200,
  "message": "OK",
  "data": {
    "msisdn": "8991234567",
    "first_seen_at": "2026-10-01T08:00:00",
    "last_seen_at": "2026-10-14T11:42:00",
    "risk_score": 0.82,
    "risk_level": "high",
    "statistics": {
      "total_calls": 150,
      "incoming_calls": 20,
      "outgoing_calls": 120,
      "forwarded_calls": 10,
      "unique_contacts": 98,
      "short_calls": 70,
      "unanswered_calls": 35,
      "short_calls_ratio": 0.4667,
      "unanswered_calls_ratio": 0.2333
    },
    "contacts": [],
    "activity": [],
    "related_suspicious_numbers": []
  }
}
```

## Дашборд

### `GET /api/v1/dashboard/summary`

Возвращает сводную статистику:

- `period_from`, `period_to` — границы периода;
- `total_calls` — общее число вызовов;
- `analyzed_calls` — число вызовов с оценкой;
- `suspicious_calls` — число подозрительных вызовов;
- `suspicious_subscribers` — число подозрительных абонентов;
- `risk_distribution` — количество вызовов по уровням `low`, `medium`, `high`, `critical`;
- `timeline` — временные точки с общим числом и количеством подозрительных вызовов.

```bash
curl https://fraud-egg.onthewifi.com/api/v1/dashboard/summary
```

### `GET /api/v1/dashboard/refresh-status`

Возвращает состояние обновления статистики.

```bash
curl https://fraud-egg.onthewifi.com/api/v1/dashboard/refresh-status
```

Формат `data`:

```json
{
  "status_code": 200,
  "message": "OK",
  "data": {
    "status": "ready"
  }
}
```

Значение `status` — строка; возможные значения определяются реализацией сервиса.

## Анализ CDR за период

### `POST /api/v1/analysis/run`

Создаёт задание анализа за временной диапазон. Ответ при успешном принятии задания — `202 Accepted`.

Тело запроса:

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `date_from` | `date-time` | Да | Начало периода |
| `date_to` | `date-time` | Да | Конец периода; не раньше `date_from` |
| `force_recalculate` | `boolean` | Нет | Принудительно пересчитать результаты; по умолчанию `false` |

Пример:

```bash
curl -X POST \
  https://fraud-egg.onthewifi.com/api/v1/analysis/run \
  -H "Content-Type: application/json" \
  -d '{
    "date_from": "2026-10-14T00:00:00+03:00",
    "date_to": "2026-10-15T00:00:00+03:00",
    "force_recalculate": false
  }'
```

Пример ответа `202 Accepted`:

```json
{
  "status_code": 202,
  "message": "Analysis job accepted",
  "data": {
    "job_id": "5f32db50-11b1-4e11-9f0e-bd81e7b34e6d",
    "status": "queued",
    "date_from": "2026-10-14T00:00:00",
    "date_to": "2026-10-15T00:00:00",
    "created_at": "2026-10-16T12:00:00"
  }
}
```

### `GET /api/v1/analysis/{job_id}`

Возвращает статус задания по UUID.

```bash
curl "https://fraud-egg.onthewifi.com/api/v1/analysis/5f32db50-11b1-4e11-9f0e-bd81e7b34e6d"
```

Поле `status` принимает `queued`, `running`, `completed`, `failed` или `cancelled`. Ответ содержит `progress_percent` от 0 до 100, период, временные отметки, `metrics` и `error`.

`metrics`, если доступны, содержит:

- `total_calls`;
- `processed_calls`;
- `fraud_calls`;
- `low_risk_calls`;
- `medium_risk_calls`;
- `high_risk_calls`;
- `critical_risk_calls`.

### `GET /api/v1/analysis/current`

Возвращает текущее состояние очереди и последние задания:

- `active_job` — активное задание либо `null`;
- `queued_jobs` — очередь заданий;
- `last_failed_job` — последнее неуспешное задание либо `null`;
- `last_successful_job` — последнее успешно завершённое задание либо `null`.

```bash
curl https://fraud-egg.onthewifi.com/api/v1/analysis/current
```

## Ошибки и валидация

### `422 Unprocessable Entity`

Возвращается при ошибке валидации параметров пути, query-параметров или JSON-тела. Например, если номер не содержит ровно 10 цифр, `page_size` выходит за диапазон `1–100`, `call_type` не входит в допустимый набор или поле даты имеет неверный формат.

Пример структуры:

```json
{
  "detail": [
    {
      "loc": ["query", "page_size"],
      "msg": "Input should be less than or equal to 100",
      "type": "less_than_equal",
      "input": 200
    }
  ]
}
```

`loc` указывает расположение ошибочного поля, `msg` — описание, `type` — машинный тип ошибки. Поле `input` может содержать исходное значение.

### Другие HTTP-ошибки

- `404 Not Found` — запрошенный ресурс не найден, если соответствующий обработчик возвращает этот статус.
- `500 Internal Server Error` — необработанная серверная ошибка.
- `503 Service Unavailable` — сервис или зависимость недоступны, если это предусмотрено обработчиком.

Фактический статус и тело ошибки определяются конкретным эндпоинтом. Полный список ответов и схем доступен в Swagger UI.

## Дополнительная документация

Полные JSON-схемы запросов и ответов, интерактивная отправка запросов и актуальный контракт API доступны в [Swagger UI](https://fraud-egg.onthewifi.com/docs). Спецификация OpenAPI доступна по адресу [openapi.json](https://fraud-egg.onthewifi.com/openapi.json).
