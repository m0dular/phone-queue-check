#!/bin/bash

error() {
  echo "oh no"
  echo "$@"

  exit 1
}

source /tmp/call_queue.config

_temp="$(mktemp)"

curl -X POST "https://platform.devtest.ringcentral.com/restapi/oauth/token" -H "Accept: application/json" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -u "${_client_id}:${_client_secret}" \
  -d "refresh_token=${_refresh_token}&grant_type=refresh_token" || error "Couldn't refresh token"


call_queue_ids="$(curl -s --request GET \
  --url 'https://platform.ringcentral.com/restapi/v1.0/account/2062564011/call-queues/2355373011/members?page=1&perPage=100'\
  --header 'accept: application/json' \
  --header "authorization: Bearer ${_access_token}" | jq -r '[.records[].id] | @uri')"

# jq's @uri filter correctly formats the array of ids, but the RingCentral api takes a comma separated string and not an array
# So, strip out the %5B and %5D denoting an array
call_queue_ids="${call_queue_ids//%5[BD]/}"
#echo "$call_queue_ids"

curl -s --request GET --url https://platform.ringcentral.com/restapi/v1.0/account/~/extension/"${call_queue_ids}"/presence \
  --header 'Content-Type: multipart/form-data; boundary=???' \
  --header 'accept: application/json' \
  --header "authorization: Bearer ${_access_token}"
