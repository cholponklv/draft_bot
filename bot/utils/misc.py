import json

def load_json(file_path: str) -> dict:
    """Загружает JSON-файл и возвращает словарь."""
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)
