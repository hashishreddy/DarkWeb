# scrape_data.py
import requests
from bs4 import BeautifulSoup
import json
import os
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from langdetect import detect, DetectorFactory
from textblob import TextBlob
from rake_nltk import Rake
import re
import hashlib

# Ensure deterministic language detection
DetectorFactory.seed = 0

DATA_FOLDER = os.path.join("data")
PROXIES = {
    'http': 'socks5h://127.0.0.1:9050',
    'https': 'socks5h://127.0.0.1:9050'
}

os.makedirs(DATA_FOLDER, exist_ok=True)

# Patterns
PGP_KEY_PATTERN = re.compile(r'-----BEGIN PGP PUBLIC KEY BLOCK-----.*?-----END PGP PUBLIC KEY BLOCK-----', re.DOTALL)
BITCOIN_WALLET_PATTERN = re.compile(r'\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b')
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
ONION_LINK_PATTERN = re.compile(r'\b[a-z2-7]{16}\.onion\b|\b[a-z2-7]{56}\.onion\b')

def html_sha256(html_text):
    return hashlib.sha256(html_text.encode('utf-8')).hexdigest()

def text_sha256(text):
    normalized = " ".join(text.lower().split())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

def extract_metadata_from_text(text):
    pgp_keys = PGP_KEY_PATTERN.findall(text)
    btc_wallets = BITCOIN_WALLET_PATTERN.findall(text)
    emails = EMAIL_PATTERN.findall(text)
    return {"pgp_keys": pgp_keys, "btc_wallets": btc_wallets, "emails": emails}

def extract_onion_links(html_text):
    # extract anchored .onion hrefs plus raw occurrences
    soup = BeautifulSoup(html_text, "html.parser")
    links = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        if ".onion" in href:
            links.add(href)
    # raw matches
    for match in ONION_LINK_PATTERN.findall(html_text):
        links.add(match)
    return list(links)

def extract_handles_and_social(html_text):
    # simple heuristics for Telegram/X/Discord handles
    handles = {"telegram": [], "x": [], "discord": []}
    # telegram t.me links or @handles
    for t in re.findall(r'(?:t\.me\/[A-Za-z0-9_]+)|@([A-Za-z0-9_]{4,})', html_text):
        if t:
            handles["telegram"].append(t if t.startswith("t.me") else f"@{t}")
    # x/twitter
    for t in re.findall(r'(?:twitter\.com\/[A-Za-z0-9_]+)|@([A-Za-z0-9_]{4,})', html_text):
        if t:
            handles["x"].append(t if t.startswith("twitter.com") else f"@{t}")
    # discord invite
    for d in re.findall(r'(?:discord\.gg\/[A-Za-z0-9]+)|discord(app)?\.com\/invite\/[A-Za-z0-9]+', html_text):
        handles["discord"].append(d)
    return handles

def rake_keywords(text, max_words=10):
    r = Rake()
    r.extract_keywords_from_text(text)
    return r.get_ranked_phrases()[:max_words]

def simple_keyword_summary(text, top_n=10):
    # very naive: split and count
    words = re.findall(r'\w{4,}', text.lower())
    freq = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    top = sorted(freq.items(), key=lambda x: -x[1])[:top_n]
    return [w for w, _ in top]

def scrape_single(url, timeout=90):
    try:
        start = time.time()
        response = requests.get(url, proxies=PROXIES, timeout=timeout)
        elapsed = time.time() - start
        status = response.status_code

        if response.status_code != 200:
            return None, f"Failed ({status}) {url}"

        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else "No Title"
        text_content = " ".join(soup.stripped_strings)
        snippet = text_content[:2000]  # save a snippet cap to keep JSON size reasonable
        word_count = len(re.findall(r'\w+', text_content))

        # language detection (safe)
        try:
            language = detect(text_content) if text_content.strip() else "unknown"
        except Exception:
            language = "unknown"

        # sentiment via TextBlob (polarity [-1,1], subjectivity [0,1])
        try:
            tb = TextBlob(snippet)
            sentiment = {"polarity": round(tb.sentiment.polarity, 4), "subjectivity": round(tb.sentiment.subjectivity, 4)}
        except Exception:
            sentiment = {"polarity": 0.0, "subjectivity": 0.0}

        # keywords
        try:
            keywords_rake = rake_keywords(text_content, max_words=12)
        except Exception:
            keywords_rake = simple_keyword_summary(text_content, top_n=12)

        # metadata extraction
        metadata = extract_metadata_from_text(text_content)
        handles = extract_handles_and_social(html)

        # onion outbound links
        onion_links_outbound = extract_onion_links(html)

        # sizes and hashes
        page_size_kb = round(len(response.content) / 1024.0, 2)
        html_hash = html_sha256(html)
        text_hash = text_sha256(text_content)

        record = {
            "url": url,
            "collected_at": datetime.utcnow().isoformat() + "Z",
            "title": title,
            "status_code": status,
            "load_time_s": round(elapsed, 3),
            "page_size_kb": page_size_kb,
            "word_count": word_count,
            "language": language,
            "sentiment": sentiment,
            "keywords": keywords_rake,
            "snippet": snippet,
            "raw_text": text_content,     # WARNING: may be large; kept for analysis
            "html_hash": html_hash,
            "text_hash": text_hash,
            "metadata": metadata,
            "social_handles": handles,
            "onion_links_outbound": onion_links_outbound
        }
        return record, None

    except Exception as e:
        return None, f"Error {url}: {e}"

def scrape_data(links_file, max_workers=5):
    start_time = time.time()

    with open(links_file, "r", encoding="utf-8") as infile:
        links_data = json.load(infile)

    scraped_data = {}
    total_links = 0
    success_count = 0
    fail_count = 0
    failures = []

    for term, urls in links_data.items():
        scraped_data[term] = []
        candidate_urls = urls
        total_links += len(candidate_urls)
        print(f"[*] Preparing to scrape {len(candidate_urls)} links for '{term}'...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(scrape_single, url): url for url in candidate_urls}
            for i, future in enumerate(as_completed(futures), 1):
                print(f"    -> Progress: {i}/{len(candidate_urls)}", end='\r')
                result, error = future.result()
                if result:
                    scraped_data[term].append(result)
                    success_count += 1
                else:
                    failures.append(error)
                    fail_count += 1
        print("\n")

    today = datetime.now().strftime("%Y-%m-%d")
    filename = os.path.join(DATA_FOLDER, f"scraped_{today}.json")
    with open(filename, "w", encoding="utf-8") as outfile:
        json.dump(scraped_data, outfile, indent=4, ensure_ascii=False)
    print(f"[+] Scraped data saved to {filename}")

    if failures:
        failed_file = os.path.join(DATA_FOLDER, f"failed_{today}.json")
        with open(failed_file, "w", encoding="utf-8") as f:
            json.dump(failures, f, indent=4, ensure_ascii=False)
        print(f"[!] Failed links saved to {failed_file}")

    end_time = time.time()
    elapsed = end_time - start_time
    print("\n==== SCRAPING STATISTICS ====")
    print(f"Total candidate links considered: {total_links}")
    print(f"Successfully scraped: {success_count}")
    print(f"Failed to scrape: {fail_count}")
    print(f"Total runtime: {elapsed:.2f} seconds")

    return filename

# allow running this script standalone
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python scrape_data.py path/to/links_file.json")
        sys.exit(1)
    links_file = sys.argv[1]
    scrape_data(links_file)
