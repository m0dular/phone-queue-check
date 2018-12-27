#!/usr/bin/env python

from __future__ import print_function
from requests_toolbelt.multipart import decoder
import requests, json, sys, ConfigParser, traceback
import pprint
import datetime
import pytz
import time


def in_business_hours(_id):
    r = requests.get('https://platform.ringcentral.com/restapi/v1.0/account/%s/extension/%s/' %
            (account_id, _id), params=api_params)
    tz = pytz.timezone(r.json().get('regionalSettings')['timezone']['name'])
    today = datetime.datetime.now(tz)
    today_day = today.strftime("%A")

    r = requests.get('https://platform.ringcentral.com/restapi/v1.0/account/%s/extension/%s/business-hours'
            % (account_id, _id), params=api_params)
    hours = r.json().get('schedule')['weeklyRanges'][today_day.lower()][0]
    _from = datetime.datetime(today.year, today.month, today.day, int(hours['from'].split(':')[0]),
            int(hours['from'].split(':')[1]), today.second, today.microsecond, tzinfo=None)
    _to = datetime.datetime(today.year, today.month, today.day, int(hours['to'].split(':')[0]),
            int(hours['to'].split(':')[1]), today.second, today.microsecond, tzinfo=None)

    if _from < today.replace(tzinfo=None) < _to:
        users[_id]['availability'] = 'Available'
    else:
        users[_id]['availability'] = 'Unavailable'


def main(args):
    try:
        cfg = ConfigParser.ConfigParser()
        cfg.read('./call_queue.config')

        global users, api_params, account_id, call_queue_id
        api_params = dict(cfg.items('dev'))
        account_params = dict(cfg.items('account'))
        account_id, call_queue_id = account_params['account_id'], account_params['call_queue_id']
        users = {}
    except Exception as e:
        print("Error parsing configuration")
        print(traceback.format_exc(e))
        exit(1)

    try:
        # Get a list of members in our call queue and add them to the users dict
        r = requests.get('https://platform.ringcentral.com/restapi/v1.0/account/%s/call-queues/%s/members' %
                (account_id, call_queue_id), params=api_params)

        for r in r.json().get('records'):
            users[ r['id'] ] = {}

        r = requests.get('https://platform.ringcentral.com/restapi/v1.0/account/%s/extension' % account_id, params=api_params)

        for x in r.json().get('records'):
            if x['id'] in users:
                users[ x['id'] ]['name'] = x['name']

        # Bath request.  The extension ids are part of the url, so I don't think we can do this with parameters
        user_string = '%2c'.join([str(x) for x in users.keys()])
        r = requests.get('https://platform.ringcentral.com/restapi/v1.0/account/%s/extension/%s/presence' %
                (account_id, user_string), params=api_params)

        multi_r = decoder.MultipartDecoder.from_response(r)

        # The first part of the response is an array of statuses.  Exit it any of them aren't 200
        statuses = json.loads(multi_r.parts[0].text)['response']
        if any([s['status'] != 200 for s in statuses]): exit(1)

        for p in multi_r.parts[1:]:
            p = json.loads(p.text)
            users[p['extension']['id']]['status'] = p['dndStatus']

        # We are unavailable if we select a status other than "Take all calls" in RingCentral
        # However, we are considered unavailable if outside business hours regardless
        for k,v in users.iteritems():
            if users[k]['status'] != 'TakeAllCalls':
                users[k]['availability'] = 'Unavailable'
            else:
                in_business_hours(k)

    except Exception as e:
        print("Error in api calls")
        print(traceback.format_exc(e))
        print(r.text)
        return

    pprint.pprint(users)


if __name__ == "__main__":
    while True:
        main(sys.argv)
        time.sleep(60)
