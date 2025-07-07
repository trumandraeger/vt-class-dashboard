import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from tqdm import tqdm

BASE  = "https://catalog.vt.edu"
INDEX = f"{BASE}/undergraduate/course-descriptions/"

def pull(block, css, default=""):
    tag = block.select_one(css)
    if not tag:
        return default
    raw = tag.get_text(" ", strip=True)
    return raw.split(":", 1)[1].strip() if ":" in raw else raw

def collect_subject_urls():
    s = BeautifulSoup(requests.get(INDEX, timeout=15).text, "lxml")
    return {
        urljoin(BASE, a["href"])
        for a in s.select('a[href^="/undergraduate/course-descriptions/"]')
        if re.fullmatch(r"/undergraduate/course-descriptions/[a-z0-9-]+/?", a["href"])
    }

def parse_subject(url):
    soup = BeautifulSoup(requests.get(url, timeout=15).text, "lxml")
    rows = []

    for blk in soup.select("div.courseblock"):
        code_tag = blk.select_one(".detail-code")
        title_tag = blk.select_one(".detail-title")
        cred_tag = blk.select_one(".detail-hours_html")
        if not (code_tag and title_tag and cred_tag):
            continue

        code_str = code_tag.get_text(strip=True)  # e.g. "ACIS 1004" or "FIN XXXX"
        title = title_tag.get_text(strip=True).lstrip('-').strip()
        credits = re.search(r"\d+(-\d+)?", cred_tag.get_text()).group()

        desc_tag = blk.select_one("p.courseblockextra")
        desc = desc_tag.get_text(" ", strip=True) if desc_tag else ""

        num_match = re.search(r"\d{3,4}[A-Z]?|\d{4}-\d{4}|XXXX", code_str)
        if not num_match:  # nothing we recognize → skip row or log
            print(f"⚠︎ Unusual code: {code_str!r}")
            continue  # or keep going with course_num = ""
        course_num = num_match.group()

        rows.append({
            "subject"      : re.match(r"[A-Z]+", code_str).group(),
            "number"       : course_num,
            "title"        : title,
            "credits"      : credits,
            "description"  : desc,
            "prerequisites": pull(blk, ".detail-prereq"),
            "corequisites" : pull(blk, ".detail-coreq"),
            "contact_hours": pull(blk, ".detail-contact_hours"),
            "pathways"     : pull(blk, ".detail-pathway"),
        })
    return rows

def main():
    all_rows = []
    for url in tqdm(sorted(collect_subject_urls())):
        all_rows.extend(parse_subject(url))
        time.sleep(1)                         # polite crawl
    pd.DataFrame(all_rows).to_csv("vt_courses.csv", index=False)
    print(f"Saved {len(all_rows):,} rows → vt_courses.csv")

if __name__ == "__main__":
    main()
