#!/bin/env python

#
#	TODO : Add a config file, to set the default download directory.
#	TODO : Add a verbose mode, for all the debugging stuff.
#	TODO : Split all the code into nice py files, it's messy here.
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

import threading
import queue

PROXYSITE = "https://proxyspotting.in"
PROXYLIST_URL = "https://thepiratebay-proxylist.org"

TSIZE = 105
TIMEOUT_TIME = 10
MAGNET_TIMEOUT_TIME = 10
QUERY_COUNT = 50

DOWNLOAD_COMMAND_LIST = ['aria2c', '--seed-time=0']
TORRENT_COMMAND_LIST = ['aria2c', '--bt-metadata-only=true', '--bt-save-metadata=true']

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

def getProxyList(expiry_time = 8640000, file_path='~'):

	print('[+] Checking if proxylist exists.')

	file_path = os.path.expanduser(file_path)
	file_path += '/.proxylist'

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
		print('[+] Proxylist downloaded.')
		return proxylist

def getsite(proxysite, queryDict, result_queue):
	# print(proxysite)
	try:
		searchResultPage = requests.get(proxysite + '/s/' + convertQueryDict(queryDict), timeout = TIMEOUT_TIME)
		searchResultPage = searchResultPage.text
		soup = BeautifulSoup(searchResultPage, 'html.parser').find('table', {'id':'searchResult'})
		if soup:
			PROXYSITE = proxysite
			result_queue.put(soup)
	except Exception as e:
		# print("Exception!" + proxysite + ': ' + str(e))
		pass

def getSearchList(proxylist, queryDict, chunkSize = 3):
	
	for i in range(0, len(proxylist), chunkSize):	
		q = queue.Queue()
		chunk = proxylist[i:i+chunkSize]	
		
		for links in chunk:
			print('[-] Querying ' + links)

		threads = [ threading.Thread(target=getsite, args=(chunk[j], queryDict, q)) for j in range(chunkSize)]
		for th in threads:
			th.daemon = True
			th.start()
		
		try:
			realsoup = q.get(True, TIMEOUT_TIME + 1)	
		except queue.Empty:
			pass # This batch of URLs did not yield any, let's try again?		
		else:
			return realsoup

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

	return queryResults[:QUERY_COUNT]	
	
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

def getmag(url, result_queue):
	try:
		torrentPage = requests.get(url, timeout = MAGNET_TIMEOUT_TIME).text
		soup = BeautifulSoup(torrentPage, "html.parser")

		downloadDiv = soup.find('div', {'class' : 'download'})
		downloadLink = downloadDiv.a['href']

		if downloadLink.startswith("magnet:"):
			result_queue.put(downloadLink)
	
	except Exception as e:
		# print('!Exception ' + url + ' ' + str(e))
		pass

def getMagnets(choice, proxylist):
	chunkSize = 3
	for i in range(0, len(proxylist), chunkSize):
		q = queue.Queue()
		chunk = proxylist[i:i+chunkSize]
		
		threads = [ threading.Thread(target=getmag, args=(chunk[j] + choice['link'], q)) for j in range(chunkSize)]
		for th in threads:
			th.daemon = True
			th.start()
		
		try:
			magnet = q.get(True, MAGNET_TIMEOUT_TIME + 1)	
		except queue.Empty:
			pass # This batch of URLs did not yield any, let's try again?		
		else:
			print("[+] Extracted magnet link for " + choice['name'][:30])
			return magnet		


def gotoChoiceAndDownload(queryVector, proxylist):
	with Pool(8) as pool:
		return pool.starmap(getMagnets, zip(queryVector, itertools.repeat(proxylist)))

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
#	
#
def getTorrents():
	torrentlist = [f for f in os.listdir('.') if os.path.isfile(f) and f.endswith('.torrent')]
	return torrentlist

#
#	Convert magnet links to torrent files.
#
def convertMagnetToTorrent(downloadLinks):
	print('[+] Downloading torrents...')
	call(TORRENT_COMMAND_LIST + downloadLinks)
		
#
#	The main() function, lol.
#
if __name__ == '__main__':	

	parser = argparse.ArgumentParser()
	parser.add_argument("query", nargs='?', help = "The query you wanna search.")
	parser.add_argument("-e", "--extra", help = "Extra params")
	parser.add_argument("-t", "--torrent-file-only", help = "Do not download file",
						action="store_true")
	parser.add_argument("-r", "--resume", help = "Resume incomplete torrent files.", action = "store_true")
	parser.add_argument("-p", "--page", help = "Page number", const = 0, nargs = '?')
	args = parser.parse_args()

	torrentLinks = None

	if args.resume:
		print("[+] Resuming previous downloads...")
		torrentLinks = resumeDownloads()
	else:

		# Check if args.query is empty or not. If empty, return
		if not args.query:
			print("[!] No queries entered! Please enter some query.")
			sys.exit(-1)

		# Constructing queryDict.
		queryDict = {'q' : args.query}
		if args.extra:
			queryDict[args.extra] = 'on'
		queryDict['page'] = args.page
		queryDict['orderby'] = 99
 
		print("[+] Searching for " + args.query)
		proxylist = getProxyList()
		soup = getSearchList(proxylist, queryDict)
		if soup is None:
			print('[!] Cannot connect to servers, sorry.')
			sys.exit(-1)
		queryResults = extractQueryResults(soup)
		choice = printPresentableQueries(queryResults)
		# torrentLinks = getMagnets(choice, proxylist)
		torrentLinks = gotoChoiceAndDownload(choice, proxylist)

		if len(torrentLinks) == 0:
			print('[!] No download link specified! Exiting...')
			sys.exit(-2) 

	if args.torrent_file_only:
		print('[+] Converting magnet to torrent...')
		convertMagnetToTorrent(torrentLinks)
	else:
		call(DOWNLOAD_COMMAND_LIST + torrentLinks)
