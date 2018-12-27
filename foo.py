#!/usr/bin/env python

from __future__ import print_function
from requests_toolbelt.multipart import decoder
import requests, json, sys, ConfigParser, traceback
import pprint
import datetime
import pytz

def main(args):
    try:
        cfg = ConfigParser.ConfigParser()
        cfg.read('./call_queue.config')

        api_params = dict(cfg.items('dev'))
        users = {}
    except Exception as e:
        print("Error parsing configuration")
        print(traceback.format_exc(e))
        exit(1)

    try:
        # Get a list of members in our call queue and add them to the users dict
        r = requests.get('https://platform.ringcentral.com/restapi/v1.0/account/2062564011/call-queues/2355373011/members',
                params=api_params)

        for r in r.json().get('records'):
            users[ r['id'] ] = {}

        r = requests.get('https://platform.ringcentral.com/restapi/v1.0/account/2062564011/extension',
                params=api_params)

        for x in r.json().get('records'):
            if x['id'] in users:
                users[ x['id'] ]['name'] = x['name']

        # The extension ids are part of the url, so I don't think we can do this the right way
        user_string = '%2c'.join([str(x) for x in users.keys()])
        r = requests.get('https://platform.ringcentral.com/restapi/v1.0/account/2062564011/extension/%s/presence' % user_string,
                params=api_params)

        multi_r = decoder.MultipartDecoder.from_response(r)

        # The first part of the response is an array of statuses.  Exit it any of them aren't 200
        statuses = json.loads(multi_r.parts[0].text)['response']
        if any([s['status'] != 200 for s in statuses]): exit(1)

        for p in multi_r.parts[1:]:
            p = json.loads(p.text)
            users[p['extension']['id']]['status'] = p['dndStatus']

    except Exception as e:
        print("Error in api calls")
        print(traceback.format_exc(e))
        exit(1)

    for k,v in users.iteritems():
        if users[k]['status'] != 'TakeAllCalls':
            users[k]['availability'] = 'Unavailable'
        else:
            r = requests.get('https://platform.ringcentral.com/restapi/v1.0/account/2062564011/extension/%s/'
                    % k, params=api_params)
            tz = pytz.timezone(r.json().get('regionalSettings')['timezone']['name'])
            today = datetime.datetime.now(tz)
            today_day = today.strftime("%A")

            r = requests.get('https://platform.ringcentral.com/restapi/v1.0/account/2062564011/extension/%s/business-hours'
                    % k, params=api_params)
            hours = r.json().get('schedule')['weeklyRanges'][today_day.lower()][0]
            _from = datetime.datetime(today.year, today.month, today.day, int(hours['from'].split(':')[0]),
                    int(hours['from'].split(':')[1]), today.second, today.microsecond, tzinfo=None)
            _to = datetime.datetime(today.year, today.month, today.day, int(hours['to'].split(':')[0]),
                    int(hours['to'].split(':')[1]), today.second, today.microsecond, tzinfo=None)

            if _from < today.replace(tzinfo=None) < _to:
                users[k]['availability'] = 'Available'
            else:
                users[k]['availability'] = 'Unavailable'

    pprint.pprint(users)


if __name__ == "__main__":
    main(sys.argv)
