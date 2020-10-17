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


    def start_ui(self):
        """
        Starting point.
        """
        parser = argparse.ArgumentParser()
        parser.add_argument("query", nargs='?', help = "The query you wanna search.")
        args = parser.parse_args()

        search_results = self.get_search_results(args.query)
        choices = self.draw_choice(search_results)
        magnets = self.get_magnets(choices)
        print(magnets)
        call(DOWNLOAD_COMMAND_LIST + magnets)


tpb = TPB()
tpb.start_ui()
        

# def convertQueryDict(queryDict):
#     returnString = "?"
#     for key in queryDict:
#         returnString += str(key) + '=' + str(queryDict[key]) + '&'
#     return returnString[:-1]


# def downloadProxyList():


# def getProxyList(expiry_time = 8640000, file_path='~'):

#     print('[+] Checking if proxylist exists.')

#     file_path = os.path.expanduser(file_path)
#     file_path += '/.proxylist'

#     # If the file exists and is not yet expired
#     if os.path.exists(file_path) and int(time.time()) - os.path.getmtime(file_path) <= expiry_time:
#         # Read from it.
#         print('[+] Proxylist exists. Reading...')
#         with open(file_path, 'rb') as f:
#             return pickle.load(f)
#     # Otherwise, redownload the proxylist and write it to file.
#     else:
#         print('[!] Proxylist does not exist. Redownloading...')
#         proxylist = downloadProxyList()
#         with open(file_path, 'wb') as f:
#             pickle.dump(proxylist, f)
#         print('[+] Proxylist downloaded.')
#         return proxylist

# def getsite(proxysite, queryDict, result_queue):
#     # print(proxysite)
#     try:
#         url = proxysite + '/search.php' + convertQueryDict(queryDict)
#         print(url)
#         searchResultPage = requests.get(url, headers={'User-Agent':user_agent}, timeout = TIMEOUT_TIME)
#         # print(searchResultPage.url)
#         searchResultPage = searchResultPage.content
#         soup = BeautifulSoup(searchResultPage, 'html.parser')
#         print(soup)
#         soup = soup.find('ol', {'id':'torrents'})
#         print(soup)
#         if soup:
#             PROXYSITE = proxysite
#             result_queue.put(soup)
#         else:
#             print("Cant parse soup, exception!")
#     except Exception as e:
#         print("Exception!" + proxysite + ': ' + str(e))
#         pass

# def getSearchList(proxylist, queryDict, chunkSize = 3):
    
#     for i in range(0, len(proxylist), chunkSize):   
#         q = queue.Queue()
#         chunk = proxylist[i:i+chunkSize]    
        
#         for links in chunk:
#             print('[-] Querying ' + links)

#         threads = [ threading.Thread(target=getsite, args=(chunk[j], queryDict, q)) for j in range(chunkSize)]
#         for th in threads:
#             th.daemon = True
#             th.start()
        
#         try:
#             realsoup = q.get(True, TIMEOUT_TIME + 1)    
#         except queue.Empty:
#             pass # This batch of URLs did not yield any, let's try again?       
#         else:
#             return realsoup

# def extractQueryResults(soup):
#     queryResults = []
#     for tr in soup.findAll('tr')[1:]:
#         currentResult = {}

#         currentResult['name'] = tr.find('a', {'class' : 'detLink'}).text
#         currentResult['link'] = tr.find('a', {'class' : 'detLink'})['href']

#         #Appending the proxysite link to convert relative link to absolute
#         currentResult['link'] = currentResult['link']

#         stuff = tr.findAll('td', {'align' : 'right'})

#         currentResult['seeds'] = stuff[0].text
#         currentResult['leechers'] = stuff[1].text

#         details = tr.find('font', {'class' : 'detDesc'}).text.replace('&nbsp;', ' ')
#         details = details.split(',')[1].strip()
#         details = details.split(' ')[1]

#         currentResult['size'] = details

#         queryResults.append(currentResult)

#     return queryResults[:QUERY_COUNT]   
    
# def printPresentableQueries(queryResults):
#     i = 1
#     print("[+] Queries fetched : ")
#     for torrent in queryResults:
#         print("%s %s S:%s L:%s Size:%s" %  ((str(i)+'.').ljust(3), torrent['name'][:TSIZE].ljust(TSIZE), torrent['seeds'].ljust(5), torrent['leechers'].ljust(5), torrent['size'].ljust(15)))
#         i += 1
#     choice = input("Choose the range which you want to download : ")
#     choice = choice.split(',')
#     queryVector = []
#     for ch in choice:
#         queryVector.append(queryResults[int(ch)-1])
#     return queryVector

# def getmag(url, result_queue):
#     try:
#         torrentPage = requests.get(url, timeout = MAGNET_TIMEOUT_TIME).text
#         soup = BeautifulSoup(torrentPage, "html.parser")

#         downloadDiv = soup.find('div', {'class' : 'download'})
#         downloadLink = downloadDiv.a['href']

#         if downloadLink.startswith("magnet:"):
#             result_queue.put(downloadLink)
    
#     except Exception as e:
#         # print('!Exception ' + url + ' ' + str(e))
#         pass

# def getMagnets(choice, proxylist):
#     chunkSize = 3
#     for i in range(0, len(proxylist), chunkSize):
#         q = queue.Queue()
#         chunk = proxylist[i:i+chunkSize]
        
#         threads = [ threading.Thread(target=getmag, args=(chunk[j] + choice['link'], q)) for j in range(chunkSize)]
#         for th in threads:
#             th.daemon = True
#             th.start()
        
#         try:
#             magnet = q.get(True, MAGNET_TIMEOUT_TIME + 1)   
#         except queue.Empty:
#             pass # This batch of URLs did not yield any, let's try again?       
#         else:
#             print("[+] Extracted magnet link for " + choice['name'][:30])
#             return magnet       


# def gotoChoiceAndDownload(queryVector, proxylist):
#     with Pool(8) as pool:
#         return pool.starmap(getMagnets, zip(queryVector, itertools.repeat(proxylist)))

# #
# #   Builds the infohash from the .aria file to resume downloading.
# #
# def buildHash(ariafile):
#     with open(ariafile, 'rb') as f:
#         f.read(6)
#         val = struct.unpack('>I', f.read(4))[0]
#         strs = "0123456789abcdef"
#         infohash = [strs[i//16] + strs[i%16] for i in f.read(val)]
#         infohash = "magnet:?xt=urn:btih:" + "".join(infohash)
#         return infohash

# def resumeDownloads():
#     hashes = [buildHash(f) for f in os.listdir('.') if os.path.isfile(f) and f.endswith('.aria2')]
#     return hashes

# #
# #   
# #
# def getTorrents():
#     torrentlist = [f for f in os.listdir('.') if os.path.isfile(f) and f.endswith('.torrent')]
#     return torrentlist

# #
# #   Convert magnet links to torrent files.
# #
# def convertMagnetToTorrent(downloadLinks):
#     print('[+] Downloading torrents...')
#     call(TORRENT_COMMAND_LIST + downloadLinks)
        
#
#   The main() function, lol.
#
# if __name__ == '__main__':  

#     parser = argparse.ArgumentParser()
#     parser.add_argument("query", nargs='?', help = "The query you wanna search.")
#     parser.add_argument("-e", "--extra", help = "Extra params")
#     parser.add_argument("-t", "--torrent-file-only", help = "Do not download file",
#                         action="store_true")
#     parser.add_argument("-r", "--resume", help = "Resume incomplete torrent files.", action = "store_true")
#     parser.add_argument("-p", "--page", help = "Page number", const = 0, nargs = '?')
#     args = parser.parse_args()

#     torrentLinks = None

#     if args.resume:
#         print("[+] Resuming previous downloads...")
#         torrentLinks = resumeDownloads()
#     else:

#         # Check if args.query is empty or not. If empty, return
#         if not args.query:
#             print("[!] No queries entered! Please enter some query.")
#             sys.exit(-1)

#         # Constructing queryDict.
#         queryDict = {'q' : args.query.replace(' ', '+'), 'all': 'on', 'search': 'Pirate+Search'}
#         if args.extra:
#             queryDict[args.extra] = 'on'
#         queryDict['page'] = 0
#         if args.page:
#             queryDict['page'] = args.page
#         queryDict['orderby'] = ''
 
#         print("[+] Searching for " + args.query)
#         proxylist = getProxyList()
#         soup = getSearchList(proxylist, queryDict)
#         if soup is None:
#             print('[!] Cannot connect to servers, sorry.')
#             sys.exit(-1)
#         queryResults = extractQueryResults(soup)
#         choice = printPresentableQueries(queryResults)
#         # torrentLinks = getMagnets(choice, proxylist)
#         torrentLinks = gotoChoiceAndDownload(choice, proxylist)

#         if len(torrentLinks) == 0:
#             print('[!] No download link specified! Exiting...')
#             sys.exit(-2) 

#     if args.torrent_file_only:
#         print('[+] Converting magnet to torrent...')
#         convertMagnetToTorrent(torrentLinks)
#     else:
#         call(DOWNLOAD_COMMAND_LIST + torrentLinks)
