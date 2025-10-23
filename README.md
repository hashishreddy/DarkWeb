# 🕵️‍♂️ Dark Web Data Pipeline

This project is a **modular data processing pipeline** designed to collect, scrape, and analyze `.onion` (dark web) URLs. It automates the entire process — from link collection to content grouping — for efficient monitoring, research, and analysis of the dark web ecosystem.

---

## 🚀 Pipeline Overview

The pipeline runs in **four main stages**, orchestrated by `run.py`:

1.  **🔗 Collect Onion Links**
    * **Script:** `collect_links.py`
    * **Description:** Crawls and gathers `.onion` URLs from predefined sources or seed lists.
    * **Output:** `links_<date>.json` inside the `links/` folder.

2.  **🧠 Scrape Onion Data**
    * **Script:** `scrape_data.py`
    * **Description:** Extracts titles, descriptions, and metadata from collected links.
    * **Output:** `scraped_<date>.json` inside the `scraped/` folder.

3.  **⚙️ Process Fingerprints (ML Classification)**
    * **Script:** `process_fingerprints.py`
    * **Description:** Cleans scraped data, generates content fingerprints, and classifies links using ML/NLP techniques.
    * **Output:** `fingerprints_<date>.json` inside the `fingerprints/` folder.

4.  **📚 Group Links by Title**
    * **Script:** `filter_by_title.py`
    * **Description:** Identifies pages that share the same title across different onion links (useful for detecting mirrors or clones).
    * **Output:** `grouped_titles_<date>.json` inside the `grouped_titles/` folder.

---

## 🧩 Script Summary

| Script                  | Description                                                  | Output                                 |
| ----------------------- | ------------------------------------------------------------ | -------------------------------------- |
| `collect_links.py`      | Collects and saves onion URLs.                               | `links/links_<date>.json`              |
| `scrape_data.py`        | Scrapes metadata (title, description, etc.) from onion sites. | `scraped/scraped_<date>.json`          |
| `process_fingerprints.py` | Cleans and classifies scraped data; creates fingerprints.    | `fingerprints/fingerprints_<date>.json` |
| `filter_by_title.py`    | Groups similar or duplicate sites based on page title.       | `grouped_titles/grouped_titles_<date>.json` |
| `run.py`                | Automates all the above steps into a single execution.       | Runs the full pipeline                 |

---

## 🧠 Tech Stack

* **Python 3.12+**
* **Libraries:** `requests`, `beautifulsoup4`, `pandas`, `scikit-learn`, `nltk`, `transformers`, etc.
* **Environment:** Virtual environment (`env/`) excluded via `.gitignore`.


## 🏁 Running the Pipeline


python scripts/run.py
