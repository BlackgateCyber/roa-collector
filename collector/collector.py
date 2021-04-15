import argparse
import logging
import urllib.request
import urllib.error
from bs4 import BeautifulSoup as bs, SoupStrainer
import requests
import gzip
import json
from pathlib import Path
import datetime


class RoaCollector(object):
    # TODO: discuss whether to include "apnic-xxxx" tals

    # CT's code: TRUST_ANCHORS = ['arin', 'apnic', 'apnic-iana', 'apnic-ripe', 'apnic-arin', 'apnic-lacnic', 'apnic-afrinic', 'lacnic', 'afrinic', 'ripencc']

    # RPKI trust anchors
    # - key: short identifier used in RIPE validator FTP site
    # - value: trust anchor long name used in RIPE validator's API output (export.json)
    TRUST_ANCHORS = {
        "arin": "ARIN",
        "apnic": "APNIC RPKI Root",
        "apnic-iana": "APNIC RPKI Root",
        "apnic-arin": "APNIC RPKI Root",
        "apnic-ripe": "APNIC RPKI Root",
        "apnic-lacnic": "APNIC RPKI Root",
        "apnic-afrinic": "APNIC RPKI Root",
        "lacnic": "LACNIC RPKI Root",
        "afrinic": "AfriNIC RPKI Root",
        "ripencc": "RIPE NCC RPKI Root",
    }

    def __init__(self, datadir="./"):
        self.datadir = datadir
        pass

    def _download_csv_to_json(self, url):
        # https://ftp.ripe.net/rpki/ripencc.tal/2021/04/06/roas.csv
        ta_id = url.split("/")[-5].split(".")[0]
        trust_anchor = self.TRUST_ANCHORS[ta_id]
        roas = []
        try:
            for line in urllib.request.urlopen(url):
                line = line.decode().rstrip()
                uri, asn, pfx, maxlen, notbefore, notafter = line.split(',')
                if "/" not in uri:
                    # skip comment/header line
                    continue
                if len(maxlen) == 0:
                    maxlen = pfx.split('/')[1]
                roas.append(
                    {
                        "asn": asn,
                        "prefix": pfx,
                        "maxLength": int(maxlen),
                        "ta": trust_anchor
                    }
                )
        except urllib.error.HTTPError:
            logging.debug("missing roas.csv file for {}".format(url))

        return roas

    def _scan_ftp_site(self, only_year=None, only_month=None):
        """
        Scan RIPE FTP site and collect a list of urls for all interested trust anchors.
        :return: list of URLs
        """
        # https://ftp.ripe.net/rpki/
        site_base_url = "https://ftp.ripe.net/rpki/"

        def get_links(url, base=None):
            logging.info("getting links for {}".format(url))
            get_base = requests.get(url, timeout=60)
            links = []
            for link in bs(get_base.content, 'html.parser', parse_only=SoupStrainer('a')):
                if not link.has_attr('href') or link['href'] == "/" or link['href'].startswith("/"):
                    continue
                link = link['href']
                if base:
                    link = base + link
                links.append(link)
            return links

        ta_uris = []
        for ta_link in get_links(site_base_url):
            if ta_link.rstrip("/").split(".")[0] not in self.TRUST_ANCHORS:
                continue
            ta_uris.append(site_base_url + ta_link)

        roa_urls = []
        for ta_uri in ta_uris:
            # year/month/day/file
            year_links = get_links(ta_uri, base=ta_uri)
            for year_link in year_links:
                if only_year and int(year_link.rstrip("/").split("/")[-1]) != int(only_year):
                    continue
                month_links = get_links(year_link, base=year_link)
                for month_link in month_links:
                    if only_month and int(month_link.rstrip("/").split("/")[-1]) != int(only_month):
                        continue
                    day_links = get_links(month_link, base=month_link)
                    roa_urls.extend([l + "roas.csv" for l in day_links])
        return roa_urls

    def _group_links_by_date(self, roa_urls):
        roa_dict = {}
        for url in roa_urls:
            year, month, day = url.split("/")[-4:-1]
            key = "-".join([year, month, day])
            if key not in roa_dict:
                roa_dict[key] = []
            roa_dict["-".join([year, month, day])].append(url)

        return roa_dict

    def _download_and_merge(self, datestr, urls):
        year, month, day = datestr.split("-")
        utc_ts = int(datetime.datetime.fromisoformat("{}-{}-{}T00:00:00+00:00".format(year, month, day)).timestamp())

        dir_path = "{}/{}/{}/{}".format(self.datadir, year, month, day)
        file_path = "{}/roas.daily.{}.json.gz".format(dir_path, utc_ts)
        if Path(file_path).exists():
            logging.info("day file exists, skip downloading")
            return

        logging.info("downloading {} files for {} and merging into gzipped json file".format(len(urls), datestr))
        # download csvs
        roas = []
        for url in urls:
            roas.extend(self._download_csv_to_json(url))
        if not roas:
            # if we have not found any valid roas from raos.csv, exit
            logging.info("no roas found for {}".format(datestr))
            return
        res = {"roas": roas}

        Path(dir_path).mkdir(parents=True, exist_ok=True)
        with gzip.open(file_path, "w") as outfile:
            outfile.write((json.dumps(res) + "\n").encode('utf-8'))

    def download_current_json(self):
        now_ts = int(datetime.datetime.now().timestamp() / 300) * 300
        dt = datetime.datetime.utcfromtimestamp(now_ts)

        year, month, day, hour = dt.year, dt.month, dt.day, dt.hour
        dir_path = "{}/{}/{:02}/{:02}/{:02}".format(self.datadir, year, month, day, hour)
        file_path = "{}/roas.5min.{}.json.gz".format(dir_path, now_ts)
        if Path(file_path).exists():
            logging.info("file {} exists, skip downloading".format(file_path))
            return
        logging.info("downloading new validated roas from RIPE to {}...".format(file_path))
        Path(dir_path).mkdir(parents=True, exist_ok=True)

        r = requests.get("https://rpki-validator.ripe.net/api/export.json")
        assert r.status_code == 200

        with gzip.open(file_path, "w") as outfile:
            outfile.write(r.content)
        logging.info("download successful")

    def download_historical(self, only_year=None, only_month=None):
        links = self._scan_ftp_site(only_year=only_year, only_month=only_month)
        link_groups = self._group_links_by_date(links)
        for datestr, ls in link_groups.items():
            self._download_and_merge(datestr, ls)


def main():
    parser = argparse.ArgumentParser(description="RIPE Validated ROAs Collector")
    subparsers = parser.add_subparsers(help='commands', dest='command')

    parser.add_argument("-d", "--dir", required=True, help="location to store the downloaded ROAs")

    subparsers.add_parser("now", help="collect current validated ROAs")

    hist_parser = subparsers.add_parser("hist", help="collect historical validated ROAs")

    hist_parser.add_argument("-c", "--current-month", action="store_true", default=False,
                             help="download current month's hisotrical data")
    hist_parser.add_argument("-y", "--year", help="only download ROAs for the given year")
    hist_parser.add_argument("-m", "--month", help="only download ROAs for the given month")

    opts = parser.parse_args()

    logging.basicConfig(format="%(levelname)s %(asctime)s: %(message)s",
                        level=logging.INFO)

    collector = RoaCollector(opts.dir)
    if opts.command == "now":
        collector.download_current_json()
    elif opts.command == "hist":
        if opts.current_month:
            now = datetime.datetime.utcnow()
            year = now.year
            month = now.month
        else:
            year = opts.year
            month = opts.month
        logging.info("downloading historical data for year={}, month={}".format(year, month))
        collector.download_historical(only_year=year, only_month=month)


if __name__ == '__main__':
    main()
