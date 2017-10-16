#!/bin/env python
import requests
from bs4 import BeautifulSoup

import argparse
import json

from subprocess import call
import sys

import os
import time

# Pickling the file, why not.
import pickle

from multiprocessing.dummy import Pool as ThreadPool

PROXYSITE = "https://proxyspotting.in"
PROXYLIST_URL = "https://thepiratebay-proxylist.org"

TSIZE = 50

def convert(queryString):
	return queryString.replace(' ', '+')

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

def searchForShit(proxysite, query):
	
	searchResultPage = requests.get(proxysite + "/s/?q=" + convert(query) + "&page=0", timeout=5).text
	print(proxysite + "/s/?q=" + convert(query) + "&page=0")
	print("[+] Query page fetched using " + proxysite)
	soup = BeautifulSoup(searchResultPage, "html.parser")

	soup = soup.find('table', {'id' : 'searchResult'})
	
	if soup is None:
		print("ERROR : No results found.")
		sys.exit(0)
	# print(soup)
	
	queryResults = []

	for tr in soup.findAll('tr')[1:]:
		
		currentResult = {}

		currentResult['name'] = tr.find('a', {'class' : 'detLink'}).text
		currentResult['link'] = tr.find('a', {'class' : 'detLink'})['href']

		#Appending the proxysite link to convert relative link to absolute
		currentResult['link'] = proxysite + currentResult['link']

		stuff = tr.findAll('td', {'align' : 'right'})

		currentResult['seeds'] = stuff[0].text
		currentResult['leechers'] = stuff[1].text

		details = tr.find('font', {'class' : 'detDesc'}).text.replace('&nbsp;', ' ')
		details = details.split(',')[1].strip()
		details = details.split(' ')[1]

		currentResult['size'] = details

		queryResults.append(currentResult)

	# print(json.dumps(queryResults, indent = 4))
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
	
	magnetVector = ["aria2c"]

	for choice in queryVector:
		
		print("[+] Extracting magnet link...")

		torrentPage = requests.get(choice['link']).text
		soup = BeautifulSoup(torrentPage, "html.parser")

		downloadDiv = soup.find('div', {'class' : 'download'})
		downloadLink = downloadDiv.a['href']

		if downloadLink.startswith("magnet:"):
			print("[+] Magnet link successfully extracted.")
		else:
			print("[!] Magnet link cannot be extracted. Aborting...")
			return

		#print("Downloading via aria2c...")
		magnetVector.append(downloadLink)

	#Calling a subprocess to download the actual thing.
	call(magnetVector)

#
#	The main() function, lol.
#
if __name__ == '__main__':	

	parser = argparse.ArgumentParser()
	parser.add_argument("query", help = "The query you wanna search.")
	args = parser.parse_args()
	print("[+] Searching for " + args.query)
	proxylist = getProxyList(file_path = '.proxylist')
	queryResults = None
	i = 0
	while queryResults is None:
		try:		
			print("[+] Proxysite selected : " + proxylist[i])
			print("[+] Downloading query page...")
			queryResults = searchForShit(proxylist[i], args.query)
		except:
			pass
		i += 1
	choice = printPresentableQueries(queryResults)
	gotoChoiceAndDownload(choice)
