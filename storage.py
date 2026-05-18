import json
import os
from typing import Optional
from models import Prediction, UserSettings
import config

os.makedirs(config.DATA_DIR, exist_ok=True)
PREDICTIONS_FILE = os.path.join(config.DATA_DIR, "predictions.json")
SETTINGS_FILE    = os.path.join(config.DATA_DIR, "settings.json")


def _read_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_json(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Predictions ──────────────────────────────────────────────────────────────

def load_predictions(chat_id: int) -> list[Prediction]:
    data = _read_json(PREDICTIONS_FILE)
    return [Prediction.from_dict(p) for p in data.get(str(chat_id), [])]


def save_predictions(chat_id: int, predictions: list[Prediction]):
    data = _read_json(PREDICTIONS_FILE)
    predictions = sorted(predictions, key=lambda p: p.match_time)
    data[str(chat_id)] = [p.to_dict() for p in predictions]
    _write_json(PREDICTIONS_FILE, data)


def add_predictions(chat_id: int, new_preds: list[Prediction]) -> int:
    """Добавляет прогнозы, пропускает дубликаты по тексту. Возвращает кол-во добавленных."""
    existing = load_predictions(chat_id)
    existing_texts = {p.text.strip().lower() for p in existing}

    added = []
    for p in new_preds:
        if p.text.strip().lower() not in existing_texts:
            added.append(p)
            existing_texts.add(p.text.strip().lower())

    if added:
        save_predictions(chat_id, existing + added)
    return len(added)


def update_prediction(chat_id: int, pred_id: str, **kwargs):
    preds = load_predictions(chat_id)
    for p in preds:
        if p.id == pred_id:
            for k, v in kwargs.items():
                setattr(p, k, v)
    save_predictions(chat_id, preds)


def delete_prediction(chat_id: int, pred_id: str) -> bool:
    preds = load_predictions(chat_id)
    new_preds = [p for p in preds if p.id != pred_id]
    if len(new_preds) == len(preds):
        return False
    save_predictions(chat_id, new_preds)
    return True


def clear_predictions(chat_id: int):
    save_predictions(chat_id, [])


def get_all_chat_ids() -> list[int]:
    data = _read_json(PREDICTIONS_FILE)
    return [int(k) for k in data.keys()]


# ── Settings ─────────────────────────────────────────────────────────────────

def load_settings(chat_id: int) -> UserSettings:
    data = _read_json(SETTINGS_FILE)
    raw = data.get(str(chat_id))
    if raw:
        return UserSettings.from_dict(raw)
    return UserSettings(chat_id=chat_id, timezone_offset=config.DEFAULT_TZ_OFFSET)


def save_settings(settings: UserSettings):
    data = _read_json(SETTINGS_FILE)
    data[str(settings.chat_id)] = settings.to_dict()
    _write_json(SETTINGS_FILE, data)
