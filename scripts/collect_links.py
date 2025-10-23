import requests
from bs4 import BeautifulSoup
import json
import os
from urllib.parse import urlparse, parse_qs, unquote
from datetime import datetime

SEARCH_TERMS = ["drugs forum"]
LINKS_FOLDER = os.path.join("links")

os.makedirs(LINKS_FOLDER, exist_ok=True)

def collect_links():
    results = {}
    for term in SEARCH_TERMS:
        url = f"https://ahmia.fi/search/?q={term.replace(' ', '+')}"
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        onion_links = []
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if "/search/redirect?" in href:
                parsed = urlparse(href)
                query_params = parse_qs(parsed.query)
                if 'redirect_url' in query_params:
                    onion_url = unquote(query_params['redirect_url'][0])
                    if ".onion" in onion_url:
                        onion_links.append(onion_url)
            elif ".onion" in href:
                onion_links.append(href)
        results[term] = list(set(onion_links))

    today = datetime.now().strftime("%Y-%m-%d")
    filename = os.path.join(LINKS_FOLDER, f"links_{today}.json")
    with open(filename, 'w') as outfile:
        json.dump(results, outfile, indent=4)
    print(f"[+] Saved onion links to {filename}")
    return filename
