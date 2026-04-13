#!/usr/bin/env python3

import argparse
import os
import platform
import re
import sys
import time
import urllib.request
from pycookiecheat import chrome_cookies

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_URL = "https://djinni.co"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def get_download_dir(url):
    """Build download directory name based on the job ID from the URL."""
    match = re.search(r'[?&]job=(\d+)', url)
    if match:
        folder = f"djinni_CVs_{match.group(1)}"
    else:
        folder = "djinni_CVs_inbox"
    return os.path.join(SCRIPT_DIR, folder)


def get_chrome_dir():
    """Return the Chrome user data directory for the current platform."""
    system = platform.system()
    if system == "Darwin":
        return os.path.expanduser("~/Library/Application Support/Google/Chrome")
    elif system == "Linux":
        return os.path.expanduser("~/.config/google-chrome")
    elif system == "Windows":
        return os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data")
    else:
        print(f"Error: Unsupported platform: {system}")
        sys.exit(1)


def find_chrome_profiles():
    """Find all Chrome profile directories that contain a Cookies file."""
    chrome_dir = get_chrome_dir()
    profiles = []
    if not os.path.isdir(chrome_dir):
        return profiles
    for entry in sorted(os.listdir(chrome_dir)):
        cookie_path = os.path.join(chrome_dir, entry, "Cookies")
        if os.path.isfile(cookie_path):
            profiles.append((entry, cookie_path))
    return profiles


def get_all_chrome_cookies():
    """Return a list of (profile_name, cookies_dict) for profiles that have Djinni cookies."""
    profiles = find_chrome_profiles()
    if not profiles:
        print("Error: No Chrome profiles with cookies found.")
        sys.exit(1)

    results = []
    for profile_name, cookie_path in profiles:
        try:
            cookies = chrome_cookies("https://djinni.co/", cookie_file=cookie_path)
            if cookies:
                results.append((profile_name, cookies))
        except Exception:
            continue

    if not results:
        print("Error: No Chrome profile contains Djinni cookies.")
        print("Make sure Chrome is completely closed and you are logged in to djinni.co.")
        sys.exit(1)

    return results


def fetch_page(url, cookie_str):
    """Fetch a page and return its HTML content"""
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Referer": "https://djinni.co/",
        "Cookie": cookie_str,
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def scrape_candidates(html):
    """Parse candidate info from inbox page HTML.

    Returns list of (name, salary, cv_url) tuples.
    """
    candidates = []

    # Find each candidate block: name link followed by CV link and salary
    # Pattern: chat-header-name link has the name, candidate_cv link has CV URL,
    # itemprop="salary" span has the salary
    name_pattern = re.compile(
        r'class="chat-header-name[^"]*"[^>]*>([^<]+)</a>'
    )
    cv_pattern = re.compile(
        r'href="(/home/inbox/\d+/candidate_cv\?source=inbox)"'
    )
    salary_pattern = re.compile(
        r'itemprop="salary">\s*\$([0-9,]+)\s*</span>'
    )

    # Split HTML into candidate blocks using the chat-item-link boundaries
    blocks = re.split(r'class="chat-item-link"', html)

    for block in blocks[1:]:  # skip the part before the first candidate
        name_match = name_pattern.search(block)
        cv_match = cv_pattern.search(block)
        salary_match = salary_pattern.search(block)

        if not name_match:
            continue

        name = name_match.group(1).strip()
        salary = salary_match.group(1).replace(",", "") if salary_match else "0"
        cv_url = BASE_URL + cv_match.group(1) if cv_match else None

        candidates.append((name, salary, cv_url))

    return candidates


def scrape_all_pages(start_url, cookie_str, max_pages=None):
    """Scrape candidates from the given URL and all subsequent pages."""
    all_candidates = []
    url = start_url
    page = 1

    while url:
        if max_pages and page > max_pages:
            break
        print(f"  Scraping page {page}...", end=" ")
        html = fetch_page(url, cookie_str)

        if "Log In to Djinni" in html:
            print("not logged in.")
            return None

        candidates = scrape_candidates(html)
        print(f"found {len(candidates)} candidates")

        if not candidates:
            break

        all_candidates.extend(candidates)

        # Find next page: look for page link right after the active page
        next_match = re.search(
            r'page-item active.*?<li class="page-item\s*">\s*<a[^>]*class="page-link"[^>]*href="[^"]*page=(\d+)"',
            html,
            re.DOTALL,
        )
        if next_match:
            next_page_num = int(next_match.group(1))
            # Build next page URL from original URL
            base = re.sub(r'[?&]page=\d+', '', start_url).rstrip("/")
            sep = "&" if "?" in base else "/?"
            url = base + sep + f"page={next_page_num}"
            page = next_page_num
        else:
            break

    return all_candidates


def download_cv(index, total, name, salary, cv_url, cookie_str, download_dir):
    """Download a single CV"""
    filename = f"{index:02d} - {name} - {salary} USD.pdf"
    filepath = os.path.join(download_dir, filename)

    print(f"[{index:02d}/{total:02d}] Downloading: {filename}...", end=" ")

    if cv_url is None:
        print("- (No CV)")
        return False

    try:
        req = urllib.request.Request(cv_url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/pdf,text/html,application/xhtml+xml",
            "Referer": "https://djinni.co/",
            "Cookie": cookie_str,
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
    except Exception:
        print("FAIL (download error)")
        return False

    if data[:4] == b"%PDF":
        with open(filepath, "wb") as f:
            f.write(data)
        print("OK")
        return True
    else:
        print("FAIL (not a PDF)")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Bulk-download candidate CVs (PDFs) from your Djinni.co recruiter inbox.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s "https://djinni.co/home/inbox/"
      Download all CVs from your entire inbox.

  %(prog)s "https://djinni.co/home/inbox/?job=12345"
      Download CVs only for a specific job posting.

  %(prog)s "https://djinni.co/home/inbox/?job=12345" --pages 2
      Download CVs from the first 2 pages only.

notes:
  - IMPORTANT: Always wrap the URL in quotes to prevent shell errors:
      %(prog)s "https://djinni.co/home/inbox/?job=12345"   (correct)
      %(prog)s https://djinni.co/home/inbox/?job=12345     (will fail!)
  - Usually works with Chrome running. If you get cookie errors, close Chrome and retry.
  - You must be logged in to djinni.co in Chrome.
  - Downloaded PDFs are saved to djinni_CVs_<jobID>/ (or djinni_CVs_inbox/ for unfiltered inbox).
""",
    )
    parser.add_argument("url",
                        help='Djinni inbox URL in quotes '
                             '(e.g. "https://djinni.co/home/inbox/?job=12345")')
    parser.add_argument("--pages", type=int, default=None,
                        help="max number of pages to scrape (default: all)")
    args = parser.parse_args()

    inbox_url = args.url

    print("=" * 50)
    print("Djinni CV Downloader")
    print("=" * 50)

    # Get cookies
    print("Reading Chrome cookies...")
    all_cookies = get_all_chrome_cookies()
    print(f"Found Djinni cookies in {len(all_cookies)} profile(s)")
    print()

    # Try each profile until we find one with a valid session
    candidates = None
    for profile_name, cookies in all_cookies:
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        print(f"Trying profile: {profile_name}")
        print(f"Scraping candidates from: {inbox_url}")
        candidates = scrape_all_pages(inbox_url, cookie_str, max_pages=args.pages)
        if candidates is not None:
            break
        print(f"Profile {profile_name} session expired, trying next...\n")

    if candidates is None:
        print("Error: No Chrome profile has a valid Djinni session.")
        print("Log in to djinni.co in Chrome and try again.")
        sys.exit(1)

    if not candidates:
        print("No candidates found. Check the URL and try again.")
        sys.exit(1)

    total = len(candidates)
    with_cv = sum(1 for _, _, cv in candidates if cv)
    print(f"\nFound {total} candidates ({with_cv} with CV)")
    print()

    # Create download directory
    download_dir = get_download_dir(inbox_url)
    os.makedirs(download_dir, exist_ok=True)
    print(f"Downloading to: {download_dir}")
    print()

    # Download
    successful = 0
    failed = 0
    no_cv = 0

    for i, (name, salary, cv_url) in enumerate(candidates, 1):
        if cv_url is None:
            no_cv += 1
            print(f"[{i:02d}/{total:02d}] {name} - ${salary} - No CV")
        elif download_cv(i, total, name, salary, cv_url, cookie_str, download_dir):
            successful += 1
        else:
            failed += 1
        time.sleep(0.3)

    # Summary
    print()
    print("=" * 50)
    print("Done!")
    print("=" * 50)
    print(f"  Downloaded: {successful}/{total}")
    if failed:
        print(f"  Failed:     {failed}/{total}")
    if no_cv:
        print(f"  No CV:      {no_cv}/{total}")
    print(f"  Location:   {download_dir}")
    print("=" * 50)


if __name__ == "__main__":
    main()
