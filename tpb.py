#!/bin/env python
import requests
from bs4 import BeautifulSoup
import argparse
import json
from subprocess import call
import sys
import os
import time
import pickle
from multiprocessing.dummy import Pool as ThreadPool
import itertools
import struct

PROXYSITE = "https://proxyspotting.in"
PROXYLIST_URL = "https://thepiratebay-proxylist.org"

TSIZE = 50
TIMEOUT_TIME = 5

def convertQueryDict(queryDict):
	returnString = "?"
	for key in queryDict:
		returnString += str(key) + '=' + str(queryDict[key]) + '&'
	return returnString[:-1]


def downloadProxyList():
	proxysite = requests.get(PROXYLIST_URL).text
	soup = BeautifulSoup(proxysite, "html.parser")
	soup = soup.find('table', {'class' : 'proxies'}).tbody
	proxylist = [tr.td.a['href'] for tr in soup.findAll('tr')]
	return proxylist

def getProxyList(expiry_time = 86400, file_path='.'):

	print('[+] Checking if proxylist exists.')

	# If the file exists and is not yet expired
	if os.path.exists(file_path) and int(time.time()) - os.path.getmtime(file_path) <= expiry_time:
		# Read from it.
		print('[+] Proxylist exists. Reading...')
		with open(file_path, 'rb') as f:
			return pickle.load(f)
	# Otherwise, redownload the proxylist and write it to file.
	else:
		print('[!] Proxylist does not exist. Redownloading...')
		proxylist = downloadProxyList()
		with open(file_path, 'wb') as f:
			pickle.dump(proxylist, f)
		return proxylist


def xyz(proxysite, queryDict):
	global PROXYSITE

	try:
		searchResultPage = requests.get(proxysite + '/s/' + convertQueryDict(queryDict), timeout = TIMEOUT_TIME)
		print(searchResultPage.url)
		searchResultPage = searchResultPage.text
	except Exception as e:
		return None

	soup = BeautifulSoup(searchResultPage, 'html.parser').find('table', {'id':'searchResult'})
	if soup is not None:
		PROXYSITE = proxysite

	return soup

def getSearchList(proxylist, queryDict, chunkSize = 3):
	# Downloads the search result in groups of chunkSize
	for i in range(0, len(proxylist), chunkSize):
		chunk = proxylist[i:i+chunkSize]
		
		pool = ThreadPool(4)
		soups = pool.starmap(xyz, zip(chunk, itertools.repeat(queryDict)))

		for soup in soups:
			if soup is not None:
				return soup

def extractQueryResults(soup):
	queryResults = []
	for tr in soup.findAll('tr')[1:]:
		currentResult = {}

		currentResult['name'] = tr.find('a', {'class' : 'detLink'}).text
		currentResult['link'] = tr.find('a', {'class' : 'detLink'})['href']

		#Appending the proxysite link to convert relative link to absolute
		currentResult['link'] = currentResult['link']

		stuff = tr.findAll('td', {'align' : 'right'})

		currentResult['seeds'] = stuff[0].text
		currentResult['leechers'] = stuff[1].text

		details = tr.find('font', {'class' : 'detDesc'}).text.replace('&nbsp;', ' ')
		details = details.split(',')[1].strip()
		details = details.split(' ')[1]

		currentResult['size'] = details

		queryResults.append(currentResult)

	return queryResults[:20]	
	
def printPresentableQueries(queryResults):
	i = 1
	print("[+] Queries fetched : ")
	for torrent in queryResults:
		print("%s %s S:%s L:%s Size:%s" %  ((str(i)+'.').ljust(3), torrent['name'][:TSIZE].ljust(TSIZE), torrent['seeds'].ljust(5), torrent['leechers'].ljust(5), torrent['size'].ljust(15)))
		i += 1
	choice = input("Choose the range which you want to download : ")
	choice = choice.split(',')
	queryVector = []
	for ch in choice:
		queryVector.append(queryResults[int(ch)-1])
	return queryVector

def gotoChoiceAndDownload(queryVector):
	downloadLinks = []
	for choice in queryVector:
		print("[+] Extracting magnet link...")

		torrentPage = requests.get(PROXYSITE + choice['link']).text
		soup = BeautifulSoup(torrentPage, "html.parser")

		downloadDiv = soup.find('div', {'class' : 'download'})
		downloadLink = downloadDiv.a['href']

		if downloadLink.startswith("magnet:"):
			print("[+] Magnet link successfully extracted.")
		else:
			print("[!] Magnet link cannot be extracted. Aborting...")
			return

		downloadLinks.append(downloadLink)
	return downloadLinks

#
#	Builds the infohash from the .aria file to resume downloading.
#
def buildHash(ariafile):
	with open(ariafile, 'rb') as f:
		f.read(6)
		val = struct.unpack('>I', f.read(4))[0]
		strs = "0123456789abcdef"
		infohash = [strs[i//16] + strs[i%16] for i in f.read(val)]
		infohash = "magnet:?xt=urn:btih:" + "".join(infohash)
		return infohash

def resumeDownloads():
	hashes = [buildHash(f) for f in os.listdir('.') if os.path.isfile(f) and f.endswith('.aria2')]
	return hashes

#
#	The main() function, lol.
#
if __name__ == '__main__':	

	parser = argparse.ArgumentParser()
	parser.add_argument("query", help = "The query you wanna search.")
	parser.add_argument("-e", "--extra", help = "Extra params")
	args = parser.parse_args()
	
	# Constructing queryDict.
	downloadLinks = None

	if args.query == 'resume':
		print("[+] Resuming previous downloads...")
		downloadLinks = resumeDownloads()
	else:

		# Constructing queryDict.
		queryDict = {'q' : args.query}
		if args.extra:
			queryDict[args.extra] = 'on'
		queryDict['page'] = 0
		queryDict['orderby'] = 99
 
		print("[+] Searching for " + args.query)
		proxylist = getProxyList(file_path = '.proxylist')
		soup = getSearchList(proxylist, queryDict)
		if soup is None:
			print('[!] Cannot connect to servers, sorry.')
			sys.exit(-1)
		queryResults = extractQueryResults(soup)
		choice = printPresentableQueries(queryResults)
		downloadLinks = gotoChoiceAndDownload(choice)

	if len(downloadLinks) == 0:
		print('[!] No download link specified! Exiting...')
		sys.exit(-2) 

	# Here we call aria2c.
	call(['aria2c', '--seed-time=0'] + downloadLinks)
