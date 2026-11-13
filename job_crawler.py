"""
Scraping jobs given job title and location from indeed website
"""
from __future__ import annotations

from collections.abc import Generator

import requests
from bs4 import BeautifulSoup

# url = "https://www.indeed.co.in/jobs?q=mobile+app+development&l="
url = "https://fr.indeed.com/jobs?q=python+bash&l=06&vjk=7e7ef90f4124ac2c"


def fetch_jobs(location: str = "Nice") -> Generator[tuple[str, str], None, None]:
    soup = BeautifulSoup(requests.get(url + location).content, "html.parser")
    # This attribute finds out all the specifics listed in a job
    for job in soup.find_all("div", attrs={"data-tn-component": "organicJob"}):
        job_title = job.find("a", attrs={"data-tn-element": "jobTitle"}).text.strip()
        company_name = job.find("span", {"class": "company"}).text.strip()
        yield job_title, company_name


if __name__ == "__main__":
    for i, job in enumerate(fetch_jobs("Valbonne"), 1):
        print(f"Job {i:>2} is {job[0]} at {job[1]}")