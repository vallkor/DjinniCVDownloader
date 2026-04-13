# Djinni CV Downloader

A Python CLI tool that bulk-downloads candidate CVs (PDF resumes) from your [Djinni.co](https://djinni.co) recruiter inbox.

## How it works

1. Auto-detects all Chrome profiles and finds one with a valid Djinni session
2. Scrapes candidate data (name, salary, CV link) from your inbox pages
3. Downloads each CV as a PDF into a separate folder per job

Files are saved as `01 - Candidate Name - 5000 USD.pdf` into a folder named after the job ID (e.g. `djinni_CVs_12345/`). If no job filter is used, files go into `djinni_CVs_inbox/`.

## Supported platforms

- macOS
- Linux
- Windows

## Requirements

- Python 3
- Google Chrome with an active Djinni login session
- [`pycookiecheat`](https://github.com/n8henrie/pycookiecheat)

## Installation

```bash
pip install pycookiecheat
```

## Usage

**Always wrap the URL in quotes** to prevent shell errors with `?` characters.

Download all CVs from your inbox:

```bash
python3 download.py "https://djinni.co/home/inbox/"
```

Download CVs for a specific job posting:

```bash
python3 download.py "https://djinni.co/home/inbox/?job=12345"
```

Limit to a specific number of pages:

```bash
python3 download.py "https://djinni.co/home/inbox/?job=12345" --pages 3
```

Show help:

```bash
python3 download.py --help
```

## Options

| Argument | Description |
|---|---|
| `url` | Djinni inbox URL (required, must be in quotes) |
| `--pages N` | Max number of pages to scrape (default: all) |

## Output

Downloaded PDFs are saved next to the script in a folder based on the job ID:

| URL | Output folder |
|---|---|
| `https://djinni.co/home/inbox/?job=12345` | `djinni_CVs_12345/` |
| `https://djinni.co/home/inbox/` | `djinni_CVs_inbox/` |

## How cookie detection works

The script automatically scans all Chrome profiles (`Default`, `Profile 1`, `Profile 2`, etc.) for Djinni session cookies. If one profile's session has expired, it moves on to the next until it finds a valid login. No manual profile configuration is needed.

## Troubleshooting

The tool can usually read cookies while Chrome is still running. If you get cookie-related errors, close all Chrome windows first and try again — some systems lock the cookie database while Chrome is open.
