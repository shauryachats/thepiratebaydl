#!/bin/env python

#
#   TODO : Add a config file, to set the default download directory.
#   TODO : Add a verbose mode, for all the debugging stuff.
#   TODO : Split all the code into nice py files, it's messy here.
#

import requests
from bs4 import BeautifulSoup
import argparse
import json
from subprocess import call
import sys
import os
import time
import pickle
from multiprocessing import Pool
import itertools
import struct
import urllib

import threading
import queue

PROXYSITE = "https://proxyspotting.in"
PROXYLIST_URL = "https://thepiratebay-proxylist.org"

TSIZE = 105
TIMEOUT_TIME = 30
MAGNET_TIMEOUT_TIME = 30
QUERY_COUNT = 50

DOWNLOAD_COMMAND_LIST = ['aria2c', '--seed-time=0']
TORRENT_COMMAND_LIST = ['aria2c', '--bt-metadata-only=true', '--bt-save-metadata=true']


def sizeof_fmt(num, suffix='B'):
    num = int(num)
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


class TPB(object):
    """
    The TPB class implements the functionality.
    """
    headers = {
        "User-Agent": 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
    }
    # Timeout to tpb pages request.
    tpb_request_timeout = 10

    MAGNET_SYNTAX_HEADER = "magnet:?"
    list_of_trackers = [
        'udp://tracker.coppersurfer.tk:6969/announce',
        'udp://9.rarbg.me:2850/announce',
        'udp://9.rarbg.to:2920/announce',
        'udp://tracker.opentrackr.org:1337',
        'udp://tracker.leechers-paradise.org:6969/announce',
    ]
    
    def __init__(self, proxylist_url = 'https://thepiratebay-proxylist.org'):
        self.proxylist_url = proxylist_url


    def get_proxies(self, proxies_file: str = '~/.tpb_proxies', expiry_time: int = 864000):
        """
        Get proxies from the proxylist_url.
        """
        print("[+] Checking if proxies_file exists...")
        proxies_file = os.path.expanduser(proxies_file)

        if os.path.exists(proxies_file) and int(time.time()) - os.path.getmtime(proxies_file) <= expiry_time:
            print("[+] Proxies_file exists, reading...")
            with open(proxies_file) as f:
                return json.load(f)

        print("[-] Proxies_file does not exists, redownloading...")
        proxies = self.download_proxies()
        with open(proxies_file, 'w') as f:
            json.dump(proxies, f)
        return proxies


    def download_proxies(self):
        """
        Parse proxies from default proxylist ('https://thepiratebay-proxylist.org')
        """
        proxysite = requests.get(self.proxylist_url, headers=self.headers).text
        soup = BeautifulSoup(proxysite, "html.parser")
        soup = soup.find('table', {'class' : 'proxies'}).tbody
        proxies = [tr.td['data-href'] for tr in soup.findAll('tr')]
        return proxies



    def get_search_results(self, search_query: str, proxies=None):
        """
        Return the search results in a JSON list from search_query, and the proxies obtained from self.get_proxies().


        The results will be returned as a list of Result objects.
        """
        print("Hello!")
        if proxies is None:
            proxies = self.get_proxies()

        # This version is easier, just an API call.
        for proxy in proxies:
            try:
                search_results_url = proxy + "/apibay/q.php"
                search_payload = {
                    "q": search_query,
                }
                search_results = requests.get(search_results_url, params=search_payload, headers=self.headers, timeout=self.tpb_request_timeout).json()
                return search_results
            except Exception as e:
                print("Exception occured, retrying...", e)
        return None


    def draw_choice(self, search_results):
        """
        Draw search_results to terminal for better UI.
        """
        print("[+] Queries fetched : ")
        for index, torrent in enumerate(search_results):
            # print(f"{torrent['name']}")
            print("%s %s S:%s L:%s Size:%s" %  ((str(index)+'.').ljust(3), torrent['name'][:TSIZE].ljust(TSIZE), torrent['seeders'].ljust(5), torrent['leechers'].ljust(5), sizeof_fmt(torrent['size']).ljust(15)))
            
        choice_input = input("Choose the range which you want to download : ")

        choices = [ search_results[int(choice)] for choice in choice_input.split(',') ]
        return choices


    def construct_magnet(self, info_hash, name=None):
        params = {
            "xt": "urn:btih:" + info_hash,
            "tr": self.list_of_trackers
        }
        if name is not None:
            params['dn'] = name
        return self.MAGNET_SYNTAX_HEADER + urllib.parse.urlencode(params, doseq=True)


    def get_magnets(self, choices):
        """
        Extract magnets from choices.
        """
        return [ self.construct_magnet(choice['info_hash'], choice['name']) for choice in choices ]


    def build_info_hash(self, ariafile):
        with open(ariafile, 'rb') as f:
            f.read(6)
            val = struct.unpack('>I', f.read(4))[0]
            strs = "0123456789abcdef"
            info_hash = [strs[i//16] + strs[i%16] for i in f.read(val)]
            info_hash = "".join(info_hash)
            return info_hash


    def resume_downloads(self):
        magnets = [ self.construct_magnet(self.build_info_hash(f)) for f in os.listdir('.') if os.path.isfile(f) and f.endswith('.aria2')]
        return magnets


    def start_ui(self):
        """
        Starting point.
        """
        parser = argparse.ArgumentParser()
        parser.add_argument("query", nargs='?', help = "The query you wanna search.")
        parser.add_argument("-r", "--resume", help = "Resume incomplete torrent files.", action = "store_true")
        args = parser.parse_args()

        if args.resume:
            magnets = self.resume_downloads()
        else:
            search_results = self.get_search_results(args.query)
            choices = self.draw_choice(search_results)
            magnets = self.get_magnets(choices)
        print(magnets)
        call(DOWNLOAD_COMMAND_LIST + magnets)

if __name__ == '__main__':
    tpb = TPB()
    tpb.start_ui()