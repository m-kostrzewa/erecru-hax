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
* `"codility_token"`: (Optional) Codility Authorization token
* `"http_debug"`: (Optional) enable http debug (default: False)
* `"debug"`: (Optional) enable application level debug (default: True)
* `"limit"`: (Optional) limit filter for eRecruiter API calls (default: 100)

If specified credentials for eRecruiter are correct but no `companyId` is specified, the client will connect
and print out all available companies for current user.
Place desired `companyId` in the config file.
# Usage

```
python3.6 dump_all.py
```