# run.py
from collect_links import collect_links
from scrape_data import scrape_data
from process_fingerprints import process_scraped_file
from filter_by_title import group_links_by_title, save_grouped_titles

def main():
    print("=== Step 1: Collecting Onion Links ===")
    links_file = collect_links()

    print("=== Step 2: Scraping Onion Data (enriched) ===")
    scrape_file = scrape_data(links_file)

    print("=== Step 3: Preprocessing Fingerprints & ML classification ===")
    fingerprint_file = process_scraped_file(scrape_file)
    print(f"Fingerprints saved to {fingerprint_file}")

    print("=== Step 4: Grouping by Title ===")
    grouped_links = group_links_by_title(fingerprint_file)

    if not grouped_links:
        print("No titles with multiple links found.")
    else:
        grouped_file = save_grouped_titles(grouped_links)
        print(f"Grouped titles saved to {grouped_file}")

    print("\nAll done ✅")
    print(f"Links saved: {links_file}")
    print(f"Scraped data saved: {scrape_file}")
    print(f"Fingerprints saved: {fingerprint_file}")

if __name__ == "__main__":
    main()
