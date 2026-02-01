happy-english
=============

Локальный стек для голосового English‑coach: Ollama + Open WebUI + Speaches.

Быстрый старт (одна команда)
----------------------------
```
docker compose --profile bootstrap up -d
```

Открыть в браузере: http://localhost:3000

Преднастроенный UI
------------------
Создай `.env` в корне:
```
WEBUI_ADMIN_EMAIL=you@example.com
WEBUI_ADMIN_PASSWORD=strong-password
WEBUI_ADMIN_NAME=Admin
```

Это запустит:
- `ollama-pull` (скачает модель и выйдет),
- `speaches-pull` (скачает STT/TTS модели и выйдет),
- `webui-bootstrap` (создаст промпты/knowledge и выйдет).

При обычном `docker compose up -d` эти one-shot сервисы не стартуют.

При запуске бутстрапа сервис `webui-bootstrap` создаст:
- промпты (slash-команды),
- базы знаний `english_profile` и `error_log`,
- подсказки и дефолтную модель в UI.

Повторный запуск только для пересборки пресета:
```
docker compose --profile bootstrap up -d webui-bootstrap
```

Логи скачивания:
```
docker compose --profile bootstrap logs -f ollama-pull
docker compose --profile bootstrap logs -f speaches-pull
```

Обычный запуск без бутстрапа:
```
docker compose up -d
```

Скачивание других моделей
-------------------------
Ollama (LLM):
```
docker exec -it ollama ollama pull llama3.1
```

Автоскачивание модели при старте
--------------------------------
В `docker-compose.yml` есть сервис `ollama-pull`. Он скачает модель в общий volume `ollama` и не будет перекачивать при следующих запусках.

По умолчанию стоит:
```
OLLAMA_MODEL=qwen2.5:14b-instruct
```

Запуск один раз:
```
docker compose up -d ollama-pull
```

STT/TTS (Speaches):
- Добавь модели в `PRELOAD_MODELS` в `docker-compose.yml` и перезапусти:
  ```
  docker compose up -d --force-recreate
  ```
- Модели должны совпадать с `AUDIO_STT_MODEL` и `AUDIO_TTS_MODEL`.
