#!/usr/bin/env python
# encoding: utf-8

import requests
import re
import json
from html import HTML
from bs4 import BeautifulSoup
from datetime import datetime

client = requests.Session()
headers = {'User-Agent': 'Mozilla/5.0'}
url = 'https://service.ringcentral.com/login/main.asp?CDXB1210:DA0A2200A66E57FD74BD5868D267AE1926D22F&enc=2&rdr='

#Request cookie and extract csrf for auth
soup = BeautifulSoup(client.get(url).text, "html.parser")
csrf = soup.find(name="csrf")

#Login - supply user / pass below
login_data = dict(username='<USERNAME>', password='<PASSWORD>', csrfmiddlewaretoken=csrf, next='/mobile/api/proxy.html?cmd=extensions.listQueueAgents&uuid=2252920011_1524068243546_642101&depId=2355373011')
r = client.post(url, data=login_data, headers=dict(Referer=url))

#Request queue data
url2 = 'https://service.ringcentral.com/mobile/api/proxy.html?cmd=extensions.listQueueAgents&uuid=2252920011_1524068243546_642101'
r2 = client.get(url2, params=dict(depId=2355373011))

#Cast content as json
agentstatus = r2.content
d = json.loads(agentstatus)

#Find and output feilds
list = []
for x in d['agents']:
  agent = x
  name = agent['name']
  extension = agent['pin']
  status = agent['agentStatus']
  list.append(name + ' (' + extension + ') is ' + status)
  #if status == 'Available':
  #  print bcolors.OKGREEN + (name + ' (' + extension + ') is ' + status)
  #else: 
  #  print bcolors.FAIL + (name + ' (' + extension + ') is ' + status)  

h = HTML('html', 'text')
t = h.table(border='1')
j = t.h4("Agent Phone Queue Status: " + str(datetime.now())[:-7]  + " UTC\n")
for i in list:
  r = j.tr
  #Default color
  color = 'red'
  if ('Unavailable' in i):
    color = 'red'
  if ('Busy' in i):
    color = 'yellow'
  if ('Available' in i):
    color = '#33CC00'
  j.td(i,bgcolor=color)
print t
