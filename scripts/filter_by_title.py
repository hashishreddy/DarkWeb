import json
import os
from collections import defaultdict
from datetime import datetime


def group_links_by_title(fingerprint_file):
    """Group URLs by their title from the fingerprint JSON."""
    with open(fingerprint_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    title_to_urls = defaultdict(set)

    # Each key = content hash, value = dict with "records"
    for content_hash, content_data in data.items():
        records = content_data.get("records", [])
        for entry in records:
            title = entry.get("title", "").strip()
            url = entry.get("url", "").strip()
            if title and url:
                title_to_urls[title].add(url)

    # Keep only titles appearing in more than one URL
    filtered = {
        title: list(urls)
        for title, urls in title_to_urls.items()
        if len(urls) > 1
    }

    return filtered


def save_grouped_titles(grouped_links, output_folder="grouped_titles"):
    """Save grouped title data into a JSON file with date-based naming."""
    os.makedirs(output_folder, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    output_path = os.path.join(output_folder, f"grouped_titles_{today}.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(grouped_links, f, indent=4, ensure_ascii=False)

    print(f"[+] Grouped titles saved to {output_path}")
    return output_path
