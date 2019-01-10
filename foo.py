#!/usr/bin/env python

from __future__ import print_function
from requests_toolbelt.multipart import decoder
from oauthlib.oauth2 import LegacyApplicationClient
from requests_oauthlib import OAuth2Session
import json
import sys
import ConfigParser
import traceback
import datetime
import pytz


def get_token(creds):
    # Ideally we'd use the refresh flow, but I couldn't get it to work
    # Requesting a token every time this runs should be ok
    oauth = OAuth2Session(
            client=LegacyApplicationClient(client_id=creds['client_id']))
    token = oauth.fetch_token(**creds)

    return OAuth2Session(creds['client_id'], token=token)


def in_business_hours(client, _id):
    # The fact that RingCentral stores user business hours per day in local
    # timezones makes this a lot harder
    # There's also currently no batch support for getting user timezones or
    # business hours.  Lame

    # This is what a schedule object looks like:
    # "weeklyRanges" : {
    #   "monday" : [ {
    #     "from" : "09:00",
    #     "to" : "18:00"
    #   } ]

    # First, make a call to this endpoint to get a user's timezone
    r = client.get(
            '%s/account/%s/extension/%s/' %
            (api_url, account_id, _id), params=api_params)

    # Then, create a datetime object in his timezone to get the correct day
    tz = pytz.timezone(r.json().get('regionalSettings')['timezone']['name'])
    today = datetime.datetime.now(tz)
    today_day = today.strftime("%A")

    # Create datetime objects for his from and to hours ignorant of timezone.
    # e.g. because we want exactly 09:00:00.000000 for 9 a.m. with no offset
    r = client.get(
        '%s/account/%s/extension/%s/business-hours'
        % (api_url, account_id, _id), params=api_params)

    try:
        hours = r.json().get('schedule')['weeklyRanges'][today_day.lower()][0]
    except KeyError:
        # Assume it's the weekend if there's no entry for today
        users[_id]['availability'] = 'Unavailable'
        return

    # Split timestamp into hour and minute and contruct datetime objects
    hour = int(hours['from'].split(':')[0])
    minute = int(hours['from'].split(':')[1])
    _from = datetime.datetime(
        today.year, today.month, today.day, hour,
        minute, today.second, today.microsecond, tzinfo=None)

    hour = int(hours['to'].split(':')[0])
    minute = int(hours['to'].split(':')[1])
    _to = datetime.datetime(
        today.year, today.month, today.day, hour,
        minute, today.second, today.microsecond, tzinfo=None)

    # Finally, remove the timezone offset from today and do a date comparison
    # to see if it's during business hours for a user
    if _from < today.replace(tzinfo=None) < _to:
        users[_id]['availability'] = 'Available'
    else:
        users[_id]['availability'] = 'Unavailable'


def main(args):
    try:
        cfg = ConfigParser.ConfigParser()
        # .config file must be in the same directory as this file
        cfg.read(os.path.dirname(__file__) + '/call_queue.config')

        global users, api_params, account_id, call_queue_id, api_url
        api_params = dict(cfg.items('dev_creds'))
        account_params = dict(cfg.items('dev_account'))
        account_id = account_params['account_id']
        call_queue_id = account_params['call_queue_id']
        api_url = account_params['api_url']
        users = {}
    except Exception as e:
        print("Error parsing configuration")
        print(traceback.format_exc(e))
        exit(1)

    try:
        client = get_token(api_params)
    except Exception as e:
        print("Error generating Oauth token")
        print(traceback.format_exc(e))
        exit(1)

    try:
        # Get a list of members in our call queue and add them to the user dict
        r = client.get(
            '%s/account/%s/call-queues/%s/members' %
            (api_url, account_id, call_queue_id), params=api_params)

        for r in r.json().get('records'):
            users[r['id']] = {}

        # I think the easiest way to get everyone's name is to use
        # the extension endpoint for Puppet's account
        r = client.get(
            '%s/account/%s/extension' %
            (api_url, account_id), params=api_params)

        for x in r.json().get('records'):
            if x['id'] in users:
                users[x['id']]['name'] = x['name']

        # Batch request.  The extension ids are part of the url,
        # so I don't think we can do this with parameters
        user_string = '%2c'.join([str(x) for x in users.keys()])
        r = client.get(
            '%s/account/%s/extension/%s/presence' %
            (api_url, account_id, user_string), params=api_params)

        # Nice library to parse the multipart response for us
        multi_r = decoder.MultipartDecoder.from_response(r)

        # The first part of the response is an array of statuses.
        # Return if any of them aren't 200 (success)
        statuses = json.loads(multi_r.parts[0].text)['response']
        if any([s['status'] != 200 for s in statuses]):
            print("Error in api calls")
            print(r.text)
            exit(1)

        # For each response, grab the 'dndStatus' field,
        # which corresponds to dropdown for call queue availability
        for p in multi_r.parts[1:]:
            p = json.loads(p.text)
            users[p['extension']['id']]['status'] = p['dndStatus']

        # We are unavailable if we select a status other than "Take all calls"
        # However, we are considered unavailable if outside business hours
        # Currently there isn't an api call for this so we have to do the work
        for k, v in users.iteritems():
            if users[k]['status'] != 'TakeAllCalls':
                users[k]['availability'] = 'Unavailable'
            else:
                in_business_hours(client, k)

    except Exception as e:
        print("Error in api calls")
        print(traceback.format_exc(e))
        return

    # Write serialized json for the dashboard to read
    # i.e. [{label: "Foo", label: "Bar"}]
    with open('/tmp/queue.json', 'w') as f:
        f.write(json.dumps(
                [dict({"label": v['name']}) for k, v in users.items()
                    if v['availability'] == 'Available']))


if __name__ == "__main__":
    main(sys.argv)
