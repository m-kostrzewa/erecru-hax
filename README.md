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
  "http_debug": true,
  "debug": true,
  "filters.limit": 100
}
```
* `"client_id"`: (Required) client id
* `"client_secret"`: (Required) client secret
* `"username"`: (Required) account user name
* `"password"`: (Required) account password
* `"companyId"`: (Required) company id
* `"http_debug"`: (Optional) enable http debug (default: False)
* `"debug"`: (Optional) enable application level debug (default: True)
* `"filters.limit"`: (Optional) limit filter for API calls (default: 100)

If specified credentials are correct but no `companyId` is specified, the client will connect
and print out all available companies for current user.
Place desired `companyId` in the config file.
# Usage

```
python3.6 dump_all.py
```