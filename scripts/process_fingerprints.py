# process_fingerprints.py
import json
import hashlib
import re
import os
from datetime import datetime
from collections import defaultdict
from pathlib import Path

# ML components
from transformers import pipeline


# fallback
import warnings

# paths
OUTPUT_FOLDER = "fingerprints"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# helpers
def sha256_of_text(text):
    normalized = " ".join(text.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def build_index_from_scraped(scraped_data):
    """
    Build an index grouping by text_hash (content fingerprint) while keeping
    metadata and useful fields for analysis.
    """
    index = {}
    for term, entries in scraped_data.items():
        for entry in entries:
            text_hash = entry.get("text_hash") or sha256_of_text(entry.get("raw_text", ""))
            html_hash = entry.get("html_hash") or sha256_of_text(entry.get("snippet", ""))
            url = entry.get("url")
            title = entry.get("title", "")
            metadata = entry.get("metadata", {})
            # store record
            record = {
                "url": url,
                "title": title,
                "collected_at": entry.get("collected_at"),
                "status_code": entry.get("status_code"),
                "load_time_s": entry.get("load_time_s"),
                "page_size_kb": entry.get("page_size_kb"),
                "language": entry.get("language"),
                "sentiment": entry.get("sentiment"),
                "keywords": entry.get("keywords"),
                "onion_links_outbound": entry.get("onion_links_outbound", []),
                "html_hash": html_hash,
                "text_hash": text_hash,
                "metadata": metadata
            }
            index.setdefault(text_hash, []).append(record)
    return index

# Topic classification: try to load a zero-shot pipeline; fallback to simple keyword rules
def get_zero_shot_classifier():
    try:
        classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
        return classifier
    except Exception as e:
        warnings.warn(f"Zero-shot model unavailable: {e}. Falling back to keyword classifier.")
        return None

# Define candidate topics/labels relevant to your domain
DEFAULT_LABELS = [
    "Illicit marketplace", "Drugs", "Weapons", "Fraud", "Hacking", "Exploit", "Leak",
    "Stolen data", "Counterfeit", "Scam", "Services", "Financial services", "Guides",
    "Forum discussion", "Carding", "Malware", "Security", "Vendor advertisement"
]

def classify_text_with_model(classifier, text, labels=DEFAULT_LABELS, multi_label=True):
    try:
        result = classifier(text, labels, multi_label=multi_label)
        # return labels with score > 0.3 (adjust threshold as needed)
        out = [(lab, sc) for lab, sc in zip(result['labels'], result['scores']) if sc >= 0.30]
        return out
    except Exception:
        return []

def simple_keyword_classify(text):
    txt = text.lower()
    ranking = {}
    # small manual lexicon -> label mapping
    lex = {
        "drugs": ["drug", "fentanyl", "heroin", "cocaine", "meth", "weed", "opiate"],
        "weapons": ["weapon", "gun", "firearm", "explosive", "silencer"],
        "fraud": ["fraud", "scam", "phishing", "carding", "ccv"],
        "hacking": ["exploit", "vulnerability", "rce", "sql injection", "xss", "dox"],
        "leak": ["leak", "leaked", "dumps", "credentials", "database"],
        "malware": ["malware", "trojan", "ransomware", "botnet"],
        "stolen data": ["stolen", "dump", "credit card", "ssn", "credentials"],
        "marketplace": ["vendor", "market", "purchase", "escrow", "vendor fee"]
    }
    for label, toks in lex.items():
        for t in toks:
            if t in txt:
                ranking[label] = ranking.get(label, 0) + txt.count(t)
    # convert to labels with scores
    items = sorted(ranking.items(), key=lambda x: -x[1])
    return [(k, float(v)/max(1,sum(ranking.values()))) for k, v in items]

def process_scraped_file(scraped_file):
    with open(scraped_file, "r", encoding="utf-8") as f:
        scraped = json.load(f)

    print("[*] Building fingerprint index...")
    index = build_index_from_scraped(scraped)

    print("[*] Attempting to load zero-shot classifier (this may download a model)...")
    classifier = None
    try:
        classifier = get_zero_shot_classifier()
    except Exception:
        classifier = None

    print("[*] Classifying content and aggregating actor signals...")
    # actor maps
    pgp_map = defaultdict(list)
    btc_map = defaultdict(list)
    email_map = defaultdict(list)

    enriched_index = {}

    for text_hash, records in index.items():
        # pick representative text to classify (first record's snippet)
        sample_text = ""
        if records:
            url = records[0].get("url", "")
            # try to load raw_text from original scraped file if present
            # we don't keep raw_text in index, so look into scraped payload
            # fallback: use title + keywords
            sample_text = records[0].get("title", "") + " " + " ".join(records[0].get("keywords", []) )

        # try classification
        labels_scores = []
        if classifier:
            labels_scores = classify_text_with_model(classifier, sample_text)
        if not labels_scores:
            labels_scores = simple_keyword_classify(sample_text)

        # aggregate metadata
        agg_pgp = []
        agg_btc = []
        agg_emails = []
        for r in records:
            md = r.get("metadata", {})
            for k in md.get("pgp_keys", []):
                agg_pgp.append(k)
                pgp_map[k].append(r.get("url"))
            for b in md.get("btc_wallets", []):
                agg_btc.append(b)
                btc_map[b].append(r.get("url"))
            for e in md.get("emails", []):
                agg_emails.append(e)
                email_map[e].append(r.get("url"))

        enriched_index[text_hash] = {
            "text_hash": text_hash,
            "records": records,
            "classification": labels_scores,
            "pgp_keys": list(set(agg_pgp)),
            "btc_wallets": list(set(agg_btc)),
            "emails": list(set(agg_emails)),
            "first_seen": min(r.get("collected_at") for r in records if r.get("collected_at")),
            "last_seen": max(r.get("collected_at") for r in records if r.get("collected_at"))
        }

    # save the fingerprint index
    today = datetime.now().strftime("%Y-%m-%d")
    output_path = os.path.join(OUTPUT_FOLDER, f"fingerprints_{today}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(enriched_index, f, indent=4, ensure_ascii=False)

    # save actor maps too for quick actor-tracking
    actor_folder = "actors"
    os.makedirs(actor_folder, exist_ok=True)
    with open(os.path.join(actor_folder, f"pgp_map_{today}.json"), "w", encoding="utf-8") as f:
        json.dump({k: list(set(v)) for k, v in pgp_map.items()}, f, indent=4, ensure_ascii=False)
    with open(os.path.join(actor_folder, f"btc_map_{today}.json"), "w", encoding="utf-8") as f:
        json.dump({k: list(set(v)) for k, v in btc_map.items()}, f, indent=4, ensure_ascii=False)
    with open(os.path.join(actor_folder, f"email_map_{today}.json"), "w", encoding="utf-8") as f:
        json.dump({k: list(set(v)) for k, v in email_map.items()}, f, indent=4, ensure_ascii=False)

    print(f"[+] Fingerprints saved to {output_path}")
    print(f"[+] Actor maps saved in {actor_folder}/")

    return output_path

# allow standalone run
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python process_fingerprints.py path/to/scraped_file.json")
        sys.exit(1)
    scraped_file = sys.argv[1]
    process_scraped_file(scraped_file)
