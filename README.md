# Запуск АИС учета железнодорожных вагонов и составов на macOS

## 1. Установить Python

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

## 2. Установить Tesseract OCR

```bash
brew install tesseract
brew install tesseract-lang
```

Проверьте установку:

```bash
tesseract --version
```

## 3. Запустить проект

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

```text
http://127.0.0.1:8000/login/
```

## 4. Демо-пользователи

| Роль | Логин | Пароль |
| --- | --- | --- |
| Администратор | `admin` | `admin123` |
| Оператор | `operator` | `operator123` |
| Маневровый диспетчер | `dispatcher` | `dispatcher123` |

## 5. Проверка работы

После входа можно открыть:

```text
/dashboard/
/tracks/
/track-map/
/trains/create/
/wagons/create/
/documents/upload/
/reports/
/admin-panel/
```

## 6. PostgreSQL

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

