happy-english
=============

Минимальный стартовый проект для локального запуска.

Запуск
------
```
docker compose up -d
```

Открыть в браузере
------------------
http://localhost:3000

Скачивание других моделей
-------------------------
Ollama (LLM):
```
docker exec -it ollama ollama pull llama3.1
```

STT/TTS (Speaches):
- Добавь модели в `PRELOAD_MODELS` в `docker-compose.yml` и перезапусти:
  ```
  docker compose up -d --force-recreate
  ```
- Модели должны совпадать с `AUDIO_STT_MODEL` и `AUDIO_TTS_MODEL`.
