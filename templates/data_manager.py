import json
import os

# Define data directory and file path
DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

JSON_FILE_PATH = os.path.join(DATA_DIR, "events_data.json")


def save_data_to_json(event_data):
    """ Save events data to a JSON file in a structured format. """
    structured_data = {"events": event_data}  # Wrap in 'events' key for clarity

    with open(JSON_FILE_PATH, "w", encoding="utf-8") as file:
        json.dump(structured_data, file, indent=4, ensure_ascii=False)

    print(f"📂 Data saved to {JSON_FILE_PATH}")


def load_data_from_json():
    """ Load stored event data from the JSON file. """
    if os.path.exists(JSON_FILE_PATH):
        with open(JSON_FILE_PATH, "r", encoding="utf-8") as file:
            return json.load(file)
    return {"events": []}  # Return empty structure if no file exists
