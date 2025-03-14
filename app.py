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

# Ensure storage folder exists
if not os.path.exists("stored_data"):
    os.makedirs("stored_data")

# Database setup
def create_database():
    """Creates the SQLite database and table if not exists"""
    conn = sqlite3.connect("events.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            city TEXT,  --
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

create_database()

# Fetch City ID from Resident Advisor
def fetch_city_id(city_name):
    """Fetch city ID from RA API"""
    query = {
        "query": """
        query GET_GLOBAL_SEARCH_RESULTS($searchTerm: String!) {
          search(searchTerm: $searchTerm, limit: 9, indices: [AREA], includeNonLive: false) {
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

# Fetch Events from RA API
def fetch_events(city_name, date):
    """Fetch events from Resident Advisor API"""
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

    if response.status_code == 200:
        data = response.json()
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
                "artists": [artist["name"] for artist in event.get("artists", [])],
                "city": city_name  # Store city name
            }
            events_list.append(event_info)

        save_events_to_db(events_list)
        return events_list
    else:
        print(f"❌ API Error: {response.status_code}, {response.text}")
        return {}

# Store Data in SQLite Database
def save_events_to_db(event_list):
    """Save event data to SQLite"""
    conn = sqlite3.connect("events.db")
    cursor = conn.cursor()

    for event in event_list:
        cursor.execute("""
            INSERT OR REPLACE INTO events (id, city, title, date, venue_name, venue_link, artists, event_link, flyer_image) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.get("event_id", "Unknown"),
            event.get("city", "Unknown"),  # Save the city name
            event.get("title", "No Title"),
            event.get("date", "No Date"),
            event.get("venue", {}).get("name", "Unknown"),
            event.get("venue", {}).get("url"),
            ", ".join(event.get("artists", [])),
            event.get("event_url"),
            event.get("flyer")
        ))

    conn.commit()
    conn.close()
    print("✅ Events saved in SQLite database")

# Flask Routes
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/get_events", methods=["POST"])
def get_events():
    city = request.form["city"]
    date = request.form["date"]
    events_response = fetch_events(city, date)
    return render_template("index.html", events=events_response)

if __name__ == "__main__":
    app.run(debug=True, port=5001)