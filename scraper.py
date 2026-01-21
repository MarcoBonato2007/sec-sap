# scraper.ipynb, but in a .py for importing

import time
import requests
import typing
import re
from bs4 import BeautifulSoup, SoupStrainer

last_req = time.time() # time at which last request was made

def request(url: str, type: typing.Literal["json", "raw"]) -> dict:
    cur_time = time.time()
    if cur_time-last_req < 0.1: # max request rate is 10/sec
        time.sleep(0.1-(cur_time-last_req))

    req = requests.get(
        url,
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
        }
    )
    if req.status_code != 200:
        print(req.content.decode())
        raise RuntimeError(f"Failed request, code {req.status_code}")

    if type == "json":
        return req.json()
    else:
        return req.content.decode()

# May be expanded in future
class Document:
    def __init__(self, raw_text: str):
        self.text = raw_text.strip()
    
class Filing:
    # parser = BeautifulSoup(filing_txt, parse_only=SoupStrainer(["xbrli:context", "context", re.compile(r'^us-gaap')]))
    # all_tags = parser.find_all(lambda tag: tag.name in ["xbrli:context", "context"] or tag.name.startswith("us-gaap"))

    def __init__(self, cik: str, accession_num: str, form_num: str, date: str):
        self.cik = cik
        self.accession_num = str(accession_num)
        self.form_num = form_num
        self.date = date

    def get(self) -> tuple[Document, list[Document]]: # returns (header, [documents])
        filing_txt = request(f"https://www.sec.gov/Archives/edgar/data/{self.cik}/{self.accession_num.replace("-", "")}/{self.accession_num}.txt", "raw")

        # Remove <(/)SEC-DOCUMENT> tags
        filing_txt = filing_txt[filing_txt.index("<SEC-HEADER>"):].replace("\n</SEC-DOCUMENT>", "")

        header_txt, docs_txt = filing_txt.split("</SEC-HEADER>", maxsplit=1)
        header_txt += "</SEC-HEADER>"
        header = Document(header_txt)

        docs = [Document(doc_txt+"</DOCUMENT>") for doc_txt in docs_txt.split("</DOCUMENT>") if doc_txt]

        return (header, docs) 
    
class Company:
    def __init__(self, name: str, cik: str | int, ticker: str, exchange: str):
        self.name = name
        self.cik = str(cik).zfill(10)
        self.ticker = ticker
        self.exchange = exchange

    def get_filings(self):
        filings = []

        def add_to_filings(filings_json):
            num_filings = len(filings_json["accessionNumber"])
            for i in range(num_filings):
                filings.append(Filing(
                    self.cik,
                    filings_json["accessionNumber"][i],
                    filings_json["form"][i],
                    filings_json["reportDate"][i],
                ))

        filings_info = request(f"https://data.sec.gov/submissions/CIK{self.cik}.json", "json")
        extra_filenames = [file["name"] for file in filings_info["filings"]["files"]]

        filings_json = filings_info["filings"]["recent"]
        add_to_filings(filings_json)
        for file_name in extra_filenames:
            filings_json = request(f"https://data.sec.gov/submissions/{file_name}", "json")
            add_to_filings(filings_json)

        return filings

    def get_facts(self):
        return request(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{self.cik}.json", "json")
    
def get_companies() -> list[Company]:
    companies = []
    companies_info = request("https://www.sec.gov/files/company_tickers_exchange.json", "json")
    for cik, name, ticker, exchange in companies_info["data"]:
        companies.append(Company(name, cik, ticker, exchange))
    return companies
