import requests
import urllib

import urllib3

from datetime import datetime

print(datetime.now())

url = "https://www.google.com"

request_response = requests.head(url)
status_code = request_response.status_code
website_is_up = status_code == 200

print(website_is_up)

import validators
result = validators.url("http:/gogle.com")
print(result)
