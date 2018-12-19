#!/usr/bin/env python

from __future__ import print_function
import requests, json, sys, ConfigParser

def main(args):
    cfg = ConfigParser.ConfigParser()
    cfg.read('/tmp/call_queue.config')
    d = dict(cfg.items('dev'))

    r = requests.get('https://platform.ringcentral.com/restapi/v1.0/account/2062564011/call-queues/2355373011/members',
            params=d)

    print(r.text)

if __name__ == "__main__":
    main(sys.argv)
