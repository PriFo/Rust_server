# BattleMetrics API Documentation

> **Примечание:** Это справочная документация по BattleMetrics API, используемому ботом для получения данных о серверах и игроках Rust. Полная документация API доступна на [battlemetrics.com/developers](https://www.battlemetrics.com/developers).
> 
> **Статус:** API находится в состоянии разработки и может быть изменен. Обсуждения следует вести в [Discord канале #api](https://discord.gg/battlemetrics).

## Использование в проекте

Бот использует следующие endpoints BattleMetrics API:
- `GET /servers/` - получение информации о серверах
- `GET /players/` - получение информации об игроках
- `GET /games/` - получение информации об играх

Для работы с API требуется API ключ, который настраивается в файле `.env` как `BM_API_KEY`.

---

## Содержание

1. [Авторизация](#авторизация)
2. [Rate Limiting](#rate-limiting)
3. [Общие концепции](#общие-концепции)
4. [API Endpoints](#api-endpoints)
   - [Ban (Баны)](#ban)
   - [Ban List (Список банов)](#ban-list)
   - [Ban List Exemption (Исключения из банов)](#ban-list-exemption)
   - [Ban List Invite (Приглашение в список банов)](#ban-list-invite)

---

## Авторизация

API BattleMetrics использует **OAuth 2.0 Bearer токены** для авторизации.

### Создание токена

Персональные токены доступа можно создать в разделе разработчика.

### Использование токена

Все запросы должны включать заголовок `Authorization`:

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbiI6IjM5NzE4MDE2ZjZlYjY1NmMiLCJpYXQiOjE0NzgwMzc1MjQsIm5iZiI6MTQ3ODAzNzUyNCwiaXNzIjoiaHR0cHM6Ly93d3cuYmF0dGxlbWV0cmljcy5jb20iLCJzdWIiOiJ1cm46dXNlcjoxIn0.iwwHt2lvBxlBqcEm7HrX1b1Rb9MXcMghUY5xspluWgw
```

### Scopes (Области доступа)

Scopes ограничивают, но не предоставляют разрешения. Используйте только необходимые scopes.

**Формат:** `<resource>:<action>(:additional-restriction)`

**Пример:** 
- `ban` — доступ ко всем операциям с банами
- `ban:export:server:1` — экспорт банов только для сервера с ID `1`

---

## Rate Limiting

Глобальный лимит применяется ко всем API endpoints.

### Лимиты токена

| Параметр | Значение |
|----------|----------|
| **Для неавторизованных запросов** | 60 запросов/мин, 15 запросов/сек (burst) |
| **Для авторизованных запросов** | 300 запросов/мин, 45 запросов/сек |

### HTTP заголовки

Лимиты информация предоставляется в заголовках ответа:

```http
X-Rate-Limit-Limit: 60
X-Rate-Limit-Remaining: 60
```

> **Примечание:** Лимиты имеют скользящее окно (rolling window).

---

## Общие концепции

### Сортировка

Некоторые endpoints поддерживают сортировку. По умолчанию сортировка по возрастанию.

**Изменить порядок на убывание:**

```
-<attribute>
```

**Несколько атрибутов:**

```
-timestamp,player
```

### Sparse Fieldsets

Запрашивайте только необходимые атрибуты:

```http
GET /bans?fields[ban]=uid,reason
```

> **Примечание:** Атрибуты `type` и `id` всегда включаются в ответ.

---

## API Endpoints

### Ban

**Статус:** `prototype`

Система банов BattleMetrics. Применяйте баны к серверам или всей организации.

> ⚠️ **Важно:** Баны **не добавляют** баны в нативную систему бана игры.

#### Scopes

- `ban` — все операции
- `ban:create` — создание
- `ban:read` — чтение
- `ban:update` — обновление
- `ban:delete` — удаление
- `ban:export` — экспорт

Scopes можно ограничить сервером или организацией:
- `ban:create:server:<id>`
- `ban:create:org:<id>`

#### Шаблоны для reason

Динамические поля в причине бана:

| Поле | Описание |
|------|---------|
| `{{uid}}` | Уникальный ID бана |
| `{{admin}}` | Никнейм администратора |
| `{{duration}}` | Длительность (Perm, 24h, 7d) |
| `{{timeLeft}}` | Оставшееся время (обновляется динамически) |
| `{{banned}}` | Когда был выдан бан |
| `{{expires}}` | Когда истекает бан (Perm для перманентных) |

#### Атрибуты Ban

| Атрибут | Тип | Описание | Пример |
|---------|-----|---------|--------|
| `id` | string | ID бана | `"42"` |
| `uid` | string | Уникальный ID бана (5-14 символов) | `"41opA0OgW"` |
| `timestamp` | date-time | Время создания бана | `"2016-10-05T14:35:51.962Z"` |
| `reason` | string | Причина бана (1-255 символов) | `"41opA0OgW - Scammer"` |
| `note` | string (nullable) | Приватная заметка | `"Video: https://..."` |
| `expires` | date-time (nullable) | Время истечения (null = перманент) | `"2016-11-05T14:35:51.962Z"` |
| `identifiers` | array | Массив идентификаторов для бана | `[1000, {...}]` |
| `orgWide` | boolean | Применить на все серверы организации | `true` |
| `autoAddEnabled` | boolean | Автоматически банить новые идентификаторы | `true` |
| `nativeEnabled` | boolean (nullable) | Использовать нативные баны | `null` |

#### Отношения (Relationships)

| Отношение | Тип | Описание |
|-----------|-----|---------|
| `banList` | banList | Список банов |
| `organization` | organization | Организация |
| `player` | player | Игрок |
| `server` | server | Сервер |
| `user` | user | Пользователь |

---

### Ban Create

**POST /bans**

Создать новый бан. BattleMetrics автоматически сканирует серверы и кикает совпадающих игроков.

**Требуемый scope:** `ban:create`

#### Параметры

Смотрите раздел [Атрибуты Ban](#атрибуты-ban)

#### Пример запроса

```bash
curl -n -X POST https://api.battlemetrics.com/bans \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "type": "ban",
      "attributes": {
        "uid": "41opA0OgW",
        "timestamp": "2016-10-05T14:35:51.962Z",
        "reason": "41opA0OgW - Scammer (Sisko)",
        "note": "Reported with video evidence",
        "expires": "2016-11-05T14:35:51.962Z",
        "identifiers": [
          1000,
          {"type": "steamID", "identifier": "1111111111111111", "manual": true}
        ],
        "orgWide": true,
        "autoAddEnabled": true,
        "nativeEnabled": null
      },
      "relationships": {
        "organization": {
          "data": {"type": "organization", "id": "42"}
        }
      }
    }
  }'
```

#### Ответ

```http
HTTP/2.0 201 Created
```

```json
{
  "data": {
    "type": "ban",
    "id": "42",
    "attributes": {
      "id": "42",
      "uid": "41opA0OgW",
      "timestamp": "2016-10-05T14:35:51.962Z",
      "reason": "41opA0OgW - Scammer (Sisko)",
      "note": "Reported with video evidence",
      "expires": "2016-11-05T14:35:51.962Z",
      "identifiers": [1000, {...}],
      "orgWide": true,
      "autoAddEnabled": true,
      "nativeEnabled": null
    }
  }
}
```

---

### Ban Import

**POST /bans/import**

Импортировать несколько банов одновременно.

**Ограничения:**
- Не кикает уже онлайн игроков
- Не логирует каждый бан в активность сервера
- Баны не сразу доступны в поиске

**Требуемый scope:** `ban:import`

#### Параметры

Аналогичны `Ban Create`, но в массиве.

#### Пример запроса

```bash
curl -n -X POST https://api.battlemetrics.com/bans/import \
  -H "Content-Type: application/json" \
  -d '{
    "data": [
      {
        "type": "ban",
        "attributes": {
          "uid": "41opA0OgW",
          "reason": "Scammer",
          "identifiers": [1000],
          "orgWide": true
        },
        "relationships": {
          "organization": {
            "data": {"type": "organization", "id": "42"}
          }
        }
      }
    ]
  }'
```

#### Ответ

```http
HTTP/2.0 201 Created
```

---

### Ban Export

**GET /bans/export**

Экспортировать баны в различные игровые форматы.

**Требуемый scope:** `ban:export`

#### Поддерживаемые форматы

| Формат | Поддерживаемые идентификаторы |
|--------|-------------------------------|
| `arma2/bans.txt` | IP, BE GUID |
| `arma3/bans.txt` | IP, BE GUID |
| `squad/Bans.cfg` | Steam ID |
| `ark/banlist.txt` | Steam ID |
| `rust/bans.cfg` | Steam ID |
| `rust/bansip_SERVER.ini` | IP |

#### Параметры

| Параметр | Тип | Описание | Обязательный |
|----------|-----|---------|-------------|
| `format` | string | Формат экспорта | ✓ |
| `filter[organization]` | string | ID организации |  |
| `filter[server]` | string | ID сервера |  |

#### Пример запроса

```bash
curl -n https://api.battlemetrics.com/bans/export \
  -G \
  -d "filter[server]=42" \
  -d "filter[organization]=42" \
  -d "format=arma2%2Fbans.txt"
```

#### Ответ

```
aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa -1 gWopA0OgW
127.0.0.1 -1 gWopA0OgW
```

---

### Ban Info

**GET /bans/{ban_id}**

Получить информацию о конкретном бане.

**Требуемый scope:** `ban:read`

#### Параметры

| Параметр | Описание |
|----------|---------|
| `fields:ban` | Атрибуты бана для возврата |
| `fields:player` | Атрибуты игрока |
| `fields:server` | Атрибуты сервера |
| `include` | Отношения для включения (organization, player, server, user, banList, banExemption) |

#### Пример запроса

```bash
curl -n https://api.battlemetrics.com/bans/42 \
  -G \
  -d "include=server%2Cplayer" \
  -d "fields[ban]=uid%2Creason"
```

#### Ответ

```http
HTTP/2.0 200 OK
```

---

### Ban List

**GET /bans**

Список, поиск и фильтрация банов.

**Требуемый scope:** `ban:read`

#### Параметры

| Параметр | Тип | Описание |
|----------|-----|---------|
| `filter:banList` | uuid | UUID списка банов |
| `filter:exempt` | boolean | Показать баны с исключениями |
| `filter:expired` | boolean | Показать истекшие баны |
| `filter:organization` | string | ID организации |
| `filter:player` | string | ID игрока |
| `filter:search` | string | Поисковой запрос |
| `filter:server` | string | ID сервера |
| `filter:users` | string | Список ID пользователей (через запятую) |
| `page:size` | integer | Размер страницы (1-100, по умолчанию 10) |
| `page:key` | string | Ключ страницы для пагинации |
| `page:rel` | string | Направление (next, prev) |
| `sort` | string | Сортировка (по умолчанию `-timestamp`) |

#### Пример запроса

```bash
curl -n https://api.battlemetrics.com/bans \
  -G \
  -d "filter[server]=42" \
  -d "filter[expired]=false" \
  -d "page[size]=20" \
  -d "sort=-timestamp"
```

#### Ответ

```json
{
  "meta": {
    "active": 50,
    "expired": 50,
    "total": 100
  },
  "data": [
    {
      "type": "ban",
      "id": "42",
      "attributes": {
        "uid": "41opA0OgW",
        "timestamp": "2016-10-05T14:35:51.962Z",
        "reason": "41opA0OgW - Scammer (Sisko)"
      }
    }
  ],
  "links": {
    "next": "https://api.battlemetrics.com/bans?page[size]=10&key=2016-10-05T14:35:51.962Z",
    "prev": "https://api.battlemetrics.com/bans?page[size]=10&key=2015-10-05T14:35:51.962Z"
  }
}
```

---

### Ban Update

**PATCH /bans/{ban_id}**

Обновить существующий бан.

**Требуемый scope:** `ban:update` (и `ban:create` для смены сервера/организации)

#### Параметры

| Параметр | Обязательный |
|----------|-------------|
| `data:type` | ✓ |
| Все остальные (как в Ban Create) | Опционально |

#### Пример запроса

```bash
curl -n -X PATCH https://api.battlemetrics.com/bans/42 \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "type": "ban",
      "id": "42",
      "attributes": {
        "reason": "Updated reason",
        "expires": "2016-12-05T14:35:51.962Z"
      }
    }
  }'
```

#### Ответ

```http
HTTP/2.0 200 OK
```

---

### Ban Delete

**DELETE /bans/{ban_id}**

Удалить существующий бан.

**Требуемый scope:** `ban:delete`

#### Пример запроса

```bash
curl -n -X DELETE https://api.battlemetrics.com/bans/42 \
  -H "Content-Type: application/json"
```

#### Ответ

```http
HTTP/2.0 204 No Content
```

---

## Ban List

**Статус:** `prototype`

Управление списками банов BattleMetrics.

### Атрибуты Ban List

| Атрибут | Тип | Описание |
|---------|-----|---------|
| `id` | uuid | ID списка банов |
| `name` | string | Название |
| `action` | string | Действие при присоединении (none, log, kick) |
| `defaultAutoAddEnabled` | boolean | Auto add по умолчанию |
| `defaultIdentifiers` | array | Идентификаторы по умолчанию |
| `defaultNativeEnabled` | boolean (nullable) | Нативные баны по умолчанию |
| `defaultReasons` | array | Причины по умолчанию |
| `nativeBanTTL` | integer (nullable) | Минуты для удаления бана из системы |
| `permCreate` | boolean | Разрешение создавать баны |
| `permDelete` | boolean | Разрешение удалять баны |
| `permManage` | boolean | Разрешение управлять подписками |
| `permUpdate` | boolean | Разрешение обновлять баны |

---

### Ban List Read

**GET /ban-lists/{banList_id}**

Получить информацию о списке банов.

#### Пример запроса

```bash
curl -n https://api.battlemetrics.com/ban-lists/01234567-89ab-cdef-0123-456789abcdef \
  -G \
  -d "include=owner"
```

#### Ответ

```http
HTTP/2.0 200 OK
```

---

## Ban List Exemption

**Статус:** `prototype`

Исключения из списков банов.

### Атрибуты

| Атрибут | Тип | Описание |
|---------|-----|---------|
| `id` | uuid | ID исключения |
| `reason` | string (nullable) | Причина исключения |

### Ban List Exemption Create

**POST /bans/{ban_id}/relationships/exemptions**

Создать исключение из бана.

#### Параметры

| Параметр | Обязательный |
|----------|-------------|
| `data:type` | ✓ |
| `data:relationships:organization:data:id` | ✓ |
| `data:relationships:organization:data:type` | ✓ |
| `data:attributes:reason` |  |

#### Пример запроса

```bash
curl -n -X POST https://api.battlemetrics.com/bans/42/relationships/exemptions \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "type": "banExemption",
      "attributes": {
        "reason": "Exception reason"
      },
      "relationships": {
        "organization": {
          "data": {
            "type": "organization",
            "id": "42"
          }
        }
      }
    }
  }'
```

#### Ответ

```http
HTTP/2.0 201 Created
```

---

### Ban List Exemption Update

**PATCH /bans/{ban_id}/relationships/exemptions**

Обновить исключение.

#### Пример запроса

```bash
curl -n -X PATCH https://api.battlemetrics.com/bans/42/relationships/exemptions \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "type": "banExemption",
      "id": "01234567-89ab-cdef-0123-456789abcdef",
      "attributes": {
        "reason": "Updated reason"
      }
    }
  }'
```

#### Ответ

```http
HTTP/2.0 204 No Content
```

---

### Ban List Exemption Delete

**DELETE /bans/{ban_id}/relationships/exemptions**

Удалить исключение.

#### Пример запроса

```bash
curl -n -X DELETE https://api.battlemetrics.com/bans/42/relationships/exemptions \
  -H "Content-Type: application/json"
```

#### Ответ

```http
HTTP/2.0 204 No Content
```

---

## Ban List Invite

**Статус:** `prototype`

Приглашения в список банов.

### Атрибуты

| Атрибут | Тип | Описание |
|---------|-----|---------|
| `id` | string | ID приглашения (7-14 символов) |
| `limit` | integer (nullable) | Лимит использования (null = неограниченно) |
| `uses` | integer | Количество использований |
| `permCreate` | boolean | Разрешение создавать |
| `permDelete` | boolean | Разрешение удалять |
| `permManage` | boolean | Разрешение управлять |
| `permUpdate` | boolean | Разрешение обновлять |

---

## Ссылки на спецификации

API BattleMetrics использует открытые спецификации JSON:API.

---

## Поддержка

Для вопросов и обсуждений посетите [Discord канал #api](https://discord.gg/battlemetrics).
