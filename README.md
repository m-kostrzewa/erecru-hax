# Setup

1. Install Python 3.6
2. Install required packages in a virtual env:

```
virtualenv venv --python /usr/bin/python3.6
source venv/bin/activate
pip install -r requirements.txt
```
# Configuration

Create a file `config.json` in `creds/` subdirectory:
```json
{
  "client_id": "client_id",
  "client_secret": "client_secret",
  "username": "username",
  "password": "password",
  "companyId": 123456789,
  "codility_token": "token",
  "http_debug": true,
  "debug": true,
  "limit": 100
}
```
* `"client_id"`: (Required) eRecruiter client id
* `"client_secret"`: (Required) eRecruiter client secret
* `"username"`: (Required) eRecruiter account user name
* `"password"`: (Required) eRecruiter account password
* `"companyId"`: (Required) eRecruiter company id
* `"codility_token"`: (Optional) Codility Authorization token (without the `Authorization: Bearer` part)
* `"http_debug"`: (Optional) enable http debug (default: False)
* `"debug"`: (Optional) enable application level debug (default: True)
* `"limit"`: (Optional) limit filter for eRecruiter API calls (default: 100)

### Where to get keys from

* eRecruiter API keys can be found under https://system.erecruiter.pl/Settings/Integration,
* Codility API key can be found under https://app.codility.com/accounts/integrations/.
  You may need to create an application (`Create an integration` panel on the right).

### companyId

If specified credentials for eRecruiter are correct but no `companyId` is specified, the client will connect
and print out all available companies for current user.
Place desired `companyId` in the config file.

# Usage

```
python3.6 dump_all.py
```

Dump to file:

```
python3.6 dump_all.py > dump.json
```

# Hiding personal information

The script has the ability to hide personal information (by hashing).

To hash any value, add it to `hash_keys` list in `dump_all.py` script, like so:

```
hash_keys = [
    'lastName',
    'email',
    ...
    'myOwnCustomField'
]
```

# How to analyze the dump

This is just a simple dump. To associate candidate entries from Codility and eRecruiter, you can use the `email` field.
They are the same for the same candidates in both Codility and eRecruiter dicts.

# Known issues

eRecruiter likes to 500 sometimes, but it's ok:

```
ERROR Failed to get https://api.erecruiter.pl/v1.1/candidates/XXXX/DesiredSalary. offset:0 limit:100 companyId:YYYY
500:Internal Server Error. [{"message":"Internal server error ocured. Please contact with us to resolve problem.","errorCode":"InternalServerError","modelType":null}]
```
