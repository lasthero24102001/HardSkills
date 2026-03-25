# 🛠 Project: HardSkills (Enterprise Architecture & DevOps)

Репозиторий, демонстрирующий применение принципов чистой архитектуры, автоматизированного тестирования и современных CI/CD процессов.

## 🏛 Архитектурные паттерны
Проект построен по принципам **Layered Architecture (Слоистая архитектура)** для обеспечения слабой связанности компонентов:
*   **Domain Layer:** Чистая бизнес-логика (сущности, модели данных).
*   **Service/Use Case Layer:** Оркестрация логики, работа с репозиториями.
*   **Infrastructure/Repository Layer:** Взаимодействие с внешними API, базой данных и Redis.
*   **Presentation/API Layer:** Входные точки (FastAPI/Flask/Django), валидация схем.

## 🧪 Качество кода и Тестирование
- **Unit Testing:** Покрытие критических модулей юнит-тестами с использованием `pytest`.
- **Mocking:** Изоляция тестов от внешних зависимостей (БД, API) через моки.
- **TDD:** Разработка через тестирование для минимизации багов в продакшене.

## 🚀 CI/CD & DevOps
Проект включает настроенные конвейеры автоматизации (GitHub Actions / GitLab CI):
- **Linter & Formatter:** Автоматическая проверка кода (Ruff, Flake8, Black).
- **Test Automation:** Прогон всех тестов при каждом Push или Pull Request.
- **Container Registry:** Сборка Docker-образа при успешном прохождении тестов.

## 🛠 Технологический стек
*   **Core:** Python 3.10+
*   **Web Framework:** (укажи свой, например FastAPI)
*   **Testing:** Pytest, Mockito
*   **CI/CD:** GitHub Actions
*   **DevOps:** Docker, Docker Compose, Multi-stage builds

## 📦 Запуск проекта

### 🐳 Использование Docker (Рекомендуется)
Сборка образа и запуск всех слоев приложения:
```bash
git clone https://github.com/lasthero24102001/HardSkills
cd HardSkills
pip install -r requirements.txt
docker-compose up --build
uvicorn main:app --reload

