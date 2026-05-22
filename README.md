# Запуск АИС учета железнодорожных вагонов и составов

---

## Windows

### 1. Установить Python

Скачайте установщик с [python.org](https://www.python.org/downloads/) и запустите его.

> **Важно:** при установке обязательно поставьте галочку **"Add Python to PATH"**.

Проверьте установку в командной строке (cmd или PowerShell):

```bat
python --version
pip --version
```

### 2. Установить Tesseract OCR

Скачайте установщик с [github.com/UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) и запустите его.

При установке выберите дополнительные языки (русский)

### 3. Запустить проект

Перейдите в папку проекта:

```bat
cd путь\к\проекту
```

Создайте виртуальное окружение:

```bat
python -m venv .venv
```

Активируйте его:

```bat
.venv\Scripts\activate
```

Установите зависимости:

```bat
pip install -r requirements.txt
```

Примените миграции:

```bat
python manage.py migrate
```

Загрузите демо-данные:

```bat
python manage.py seed_demo
```

Запустите сервер:

```bat
python manage.py runserver
```

Откройте в браузере:

```
http://127.0.0.1:8000/login/
```

### 4. PostgreSQL (Windows)

По умолчанию проект запускается на SQLite.

Для запуска с PostgreSQL задайте переменные окружения в PowerShell:

```powershell
$env:POSTGRES_DB="aisdip"
$env:POSTGRES_USER="postgres"
$env:POSTGRES_PASSWORD="postgres"
$env:POSTGRES_HOST="localhost"
$env:POSTGRES_PORT="5432"
```

Или в командной строке (cmd):

```bat
set POSTGRES_DB=aisdip
set POSTGRES_USER=postgres
set POSTGRES_PASSWORD=postgres
set POSTGRES_HOST=localhost
set POSTGRES_PORT=5432
```

Затем выполните:

```bat
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

---

## macOS

### 1. Установить Python

Установите Homebrew, если его нет:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Установите Python:

```bash
brew install python
```

Проверьте установку:

```bash
python3 --version
pip3 --version
```

### 2. Установить Tesseract OCR

```bash
brew install tesseract
brew install tesseract-lang
```

Проверьте установку:

```bash
tesseract --version
```

### 3. Запустить проект

Перейдите в папку проекта:

```bash
cd путь/к/проекту
```

Создайте виртуальное окружение:

```bash
python3 -m venv .venv
```

Активируйте его:

```bash
source .venv/bin/activate
```

Установите зависимости:

```bash
pip install -r requirements.txt
```

Примените миграции:

```bash
python manage.py migrate
```

Загрузите демо-данные:

```bash
python manage.py seed_demo
```

Запустите сервер:

```bash
python manage.py runserver
```

Откройте в браузере:

```
http://127.0.0.1:8000/login/
```

### 4. PostgreSQL (macOS)

По умолчанию проект запускается на SQLite.

Для запуска с PostgreSQL задайте переменные окружения:

```bash
export POSTGRES_DB=aisdip
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=postgres
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
```

Затем выполните:

```bash
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

---

## Демо-пользователи

| Роль | Логин | Пароль |
| --- | --- | --- |
| Администратор | `admin` | `admin123` |
| Оператор | `operator` | `operator123` |
| Маневровый диспетчер | `dispatcher` | `dispatcher123` |

## Проверка работы

После входа можно открыть:

```
/dashboard/
/tracks/
/track-map/
/trains/create/
/wagons/create/
/documents/upload/
/reports/
/admin-panel/
```

---

## Описание системы

### Что это за система

Это веб-приложение на Django для учёта железнодорожных составов и вагонов. Система позволяет отслеживать:

- кто вошёл в систему и с какой ролью;
- какие есть составы и вагоны;
- где они стоят на путях и участках;
- как и когда их перемещали;
- какие документы загружены и что распознал OCR;
- какие отчёты и уведомления сформированы.

### Архитектура проекта

Проект разделён на два уровня:

- `aisdip/` — «каркас» проекта: настройки, подключение БД, общие URL.
- `rail/` — вся бизнес-логика предметной области:
  - `models.py` — таблицы/сущности (Состав, Вагон, Путь, Документ и т.д.)
  - `views.py` — обработка страниц и действий пользователя
  - `forms.py` — формы и валидация
  - `services.py` — отдельные бизнес-операции (перемещение, OCR, логирование, уведомления)
  - `templates/` + `static/` — интерфейс

Поток данных: **Пользователь в UI → View/Form → Service → Model/DB → ответ в UI**

### Ключевые сущности и связи

Основные модели:

- `Role` + `UserProfile` — роли (админ, оператор, диспетчер).
- `RailwayTrack` + `TrackSection` — путь и его участки.
- `Train` + `Wagon` — состав и его вагоны.
- `MovementHistory` — история перемещений (кто, откуда, куда, когда).
- `Document` + `OCRResult` — файл документа и результат распознавания.
- `OperationLog` — аудит действий.
- `Notification` — уведомления пользователю.

Связи:

- у состава много вагонов;
- у пути много участков;
- у документа один OCR-результат;
- перемещения и логи привязаны к пользователю.

### Бизнес-сценарий

Типовой демонстрационный процесс:

1. Логин под нужной ролью.
2. Создание/редактирование состава и вагонов.
3. Размещение на участке пути (через форму или drag&drop на схеме).
4. При перемещении:
   - проверяется занятость участка;
   - создаётся запись в `MovementHistory`;
   - обновляется текущая позиция;
   - обновляется признак занятости участков;
   - создаётся запись в `OperationLog`.
5. Загрузка документа и запуск OCR:
   - документ получает статус обработки;
   - извлекаются поля (номер состава, вагоны, груз, дата);
   - результат можно подтвердить оператором.
6. Формирование отчётов и экспорт CSV.
7. Просмотр уведомлений и админ-журнала операций.

### Ключевые особенности

- **Ролевая модель доступа** — разграничение прав между администратором, оператором и диспетчером.
- **Трассируемость операций** — полная история перемещений и журнал действий.
- **Устойчивость к ошибкам OCR** — система не падает при сбое распознавания.
- **Визуализация** — схема путей с поддержкой drag&drop.
- **Демо-наполнение** — команда `seed_demo` позволяет быстро показать работу системы end-to-end.
