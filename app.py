from flask import Flask, render_template, request
import os
import requests
import json
import sqlite3
from datetime import datetime

app = Flask(__name__)

# Resident Advisor API Endpoint
RA_GRAPHQL_URL = "https://ra.co/graphql"
HEADERS = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
    "Content-Type": "application/json"
}

# 🔹 Ensure storage folder exists
if not os.path.exists("stored_data"):
    os.makedirs("stored_data")


# 🔹 Database setup
def create_database():
    """Creates the SQLite database and table if not exists"""
    conn = sqlite3.connect("events.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            title TEXT,
            date TEXT,
            venue_name TEXT,
            venue_link TEXT,
            artists TEXT,
            event_link TEXT,
            flyer_image TEXT
        )
    """)
    conn.commit()
    conn.close()


create_database()  # Run database setup on start


# 🔍 Fetch City ID from Resident Advisor
def fetch_city_id(city_name):
    """Fetch city ID from RA API"""
    query = {
        "query": """
        query GET_GLOBAL_SEARCH_RESULTS($searchTerm: String!) {
          search(searchTerm: $searchTerm, limit: 5, indices: [AREA], includeNonLive: false) {
            id
            value
          }
        }
        """,
        "variables": {"searchTerm": city_name}
    }

    response = requests.post(RA_GRAPHQL_URL, headers=HEADERS, json=query)

    if response.status_code == 200:
        data = response.json()
        locations = data.get("data", {}).get("search", [])
        if locations:
            return locations[0]["id"]
    return None


# 🔍 Fetch Events from RA API
def fetch_events(city_name, date):
    """Fetch events from Resident Advisor API and store them properly"""
    city_id = fetch_city_id(city_name)
    if city_id is None:
        print("❌ Could not retrieve city ID.")
        return {}

    try:
        city_id = int(city_id)
    except ValueError:
        print(f"❌ Error: City ID '{city_id}' is not a valid integer.")
        return {}

    query = {
        "query": """
        query GET_POPULAR_EVENTS(
            $filters: FilterInputDtoInput, 
            $pageSize: Int, 
            $sort: SortInputDtoInput
        ) {
            eventListings(filters: $filters, pageSize: $pageSize, page: 1, sort: $sort) {
                data {
                    id
                    listingDate
                    event {
                        id
                        title
                        date
                        contentUrl
                        flyerFront
                        venue {
                            id
                            name
                            contentUrl
                        }
                        artists {
                            id
                            name
                        }
                    }
                }
            }
        }
        """,
        "variables": {
            "filters": {
                "areas": {"eq": city_id},
                "listingDate": {"gte": date, "lte": date}
            },
            "pageSize": 20,
            "sort": {
                "score": {"order": "DESCENDING"},
                "titleKeyword": {"order": "ASCENDING"}
            }
        }
    }

    response = requests.post(RA_GRAPHQL_URL, headers=HEADERS, json=query)

    print(f"🔹 API Response Status Code: {response.status_code}")
    print(f"📋 API Response JSON: {response.text}")

    if response.status_code == 200:
        data = response.json()

        if not isinstance(data, dict):  # ✅ Ensure it's a dictionary
            print("❌ API response is not a dictionary!")
            return {}

        event_listings = data.get("data", {}).get("eventListings", {}).get("data", [])

        events_list = []
        for item in event_listings:
            event = item.get("event", {})
            venue = event.get("venue", {})

            event_info = {
                "event_id": event.get("id", "Unknown"),
                "title": event.get("title", "No Title"),
                "date": event.get("date", "No Date"),
                "event_url": f"https://ra.co{event.get('contentUrl', '')}" if event.get("contentUrl") else None,
                "flyer": event.get("flyerFront"),
                "venue": {
                    "name": venue.get("name", "Unknown"),
                    "url": f"https://ra.co{venue.get('contentUrl', '')}" if venue.get("contentUrl") else None
                },
                "artists": [artist["name"] for artist in event.get("artists", [])] if "artists" in event else []
            }
            events_list.append(event_info)
            print(f"🟢 Event URL: {event_info['event_url']}")  # Debugging print
            print(f"🟢 Venue URL: {event_info['venue']['url']}")  # Debugging print

        save_events_to_json(city_name, date, events_list)  # ✅ Save data to JSON file
        save_events_to_db(events_list)  # ✅ Store in database

        return events_list  # ✅ Return cleaned event list

    else:
        print(f"❌ API Error: {response.status_code}, {response.text}")
        return {}


# 📂 Save JSON File
def save_events_to_json(city_name, date, events_response):
    """Save event data to JSON file"""
    filename = f"events_{city_name}_{date}.json"
    filepath = f"./stored_data/{filename}"

    with open(filepath, "w", encoding="utf-8") as json_file:
        json.dump(events_response, json_file, indent=4, ensure_ascii=False)

    print(f"✅ Data saved to {filepath}")
    return filepath


# 🗄 Store Data in SQLite Database
def save_events_to_db(event_list):
    """Save event data to SQLite"""
    conn = sqlite3.connect("events.db")
    cursor = conn.cursor()

    for event in event_list:
        cursor.execute("""
            INSERT OR REPLACE INTO events (id, title, date, venue_name, venue_link, artists, event_link, flyer_image) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.get("event_id", "Unknown"),  # ✅ Avoid KeyError, use 'Unknown' if missing
            event.get("title", "No Title"),  # ✅ Default to 'No Title' if missing
            event.get("date", "No Date"),  # ✅ Default to 'No Date' if missing
            event.get("venue", {}).get("name", "Unknown"),  # ✅ Check nested dict
            event.get("venue", {}).get("url"),  # ✅ Handle missing venue URL
            ", ".join(event.get("artists", [])),  # ✅ Convert list to string safely
            event.get("event_url"),  # ✅ Handle missing event URL
            event.get("flyer")  # ✅ Handle missing flyer image
        ))

    conn.commit()
    conn.close()
    print("✅ Events saved in SQLite database")

# 🏡 Flask Routes
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/get_events", methods=["POST"])
def get_events():
    city = request.form["city"]
    date = request.form["date"]

    print(f"🔍 Fetching events for: City={city}, Date={date}")

    events_response = fetch_events(city, date)

    if not events_response:  # ✅ Handle invalid response
        print("❌ Invalid API response format")
        return render_template("index.html", events=[], error="Invalid API response format.")

    event_list = []
    for event in events_response:
        event_details = {
            "Event ID": event["event_id"],
            "Event Name": event["title"],
            "Date": event["date"],
            "Venue Name": event["venue"]["name"],
            "Venue Link": event["venue"]["url"],
            "Artists": event["artists"],
            "Event Link": event["event_url"],
            "Flyer Image": event["flyer"]
        }
        event_list.append(event_details)

    # ✅ Save to database
    filepath = save_events_to_json(city, date, event_list)
    save_events_to_db(event_list)

    return render_template("index.html", events=event_list, json_file=filepath)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
