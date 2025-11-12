# FlirtAI Backend

Telegram bot for Instagram profile analysis using Ollama and Kaspi payments.

## Setup
1. Copy `.env.example` to `.env` and fill values.
2. `pip install -r requirements.txt`
3. Run Ollama: `ollama serve` + `ollama pull llama2 llava`
4. Start Redis: `redis-server`
5. `python -m src.main`

## Structure
- `src/config/`: Env vars and constants.
- `src/handlers/`: Telegram event handlers.
- `src/services/`: Business logic (Ollama, Kaspi, etc.).
- `src/keyboards/`: UI keyboards.
- `src/states/`: FSM states.
- `src/core/`: Bot init.
- `src/utils/`: Helpers.

## Deployment
Use Docker: See `docker-compose.yml`.