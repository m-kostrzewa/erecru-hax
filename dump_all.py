# -*- coding: utf-8 -*-
import coloredlogs
import hashlib
import http
import json
import logging
import pickle
import pprint
import requests


from oauthlib.oauth2 import LegacyApplicationClient
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth2Session


logger = logging.getLogger(__name__)
coloredlogs.install(level='INFO', logger=logger)


ACCESS_TOKEN_URL = 'https://authorization-api.erecruiter.pl/oAuth/Token'
CONFIG_FILE = 'creds/config.json'
TOKEN_FILE_PATH = 'creds/token.pickle'
DEFAULT_HASH_TYPE = 'sha1'
ERECRUITER_API_URL = 'https://api.erecruiter.pl/v1.1/'
CODILITY_API_URL = 'http://codility.com/api/'
# ERECRUITER_API_URL='https://testapi.io/api/m-kostrzewa/v1.1/'


# Top level resource dndpoint definition list
# (endpoint path, db collection name)
# * endpoint path - this will be the suffix of the API url
# * db collection name - name of the top level collection to be put in DB
top_level_collection_endpoints = [
    ('candidates', 'candidates'),

    ('recruitments', 'recruitments'),

    ('Dictionaries/Languages', 'languages'),
    ('Dictionaries/RecruitmentStages', 'stages'),

    ('Account/Stages', 'accountstages'),
    ('Account/Tags', 'tags'),
    ('Account/Origins', 'accountorigins'),

    ('Candidates/Favourites', 'candidatefavourites'),
]


# Additional endpoint lists for resource extensions
# (endpoint_path, collection, collection_item_id, extension_name)
# * endpoint_path      - a parametrized endpoint path
# * collection         - which collection will be extended
# * collection_item_id - which collection item identified by this id
#                        should be extended
#                        This value will be used to format the endpoint path
# * extension_name     - the endpoint request result may return a dict
#                        with this key. Extract it if it exists, else return
#                        the result as is. Whole resource will be added
#                        to the collection under this key
collection_extension_endpoints = [
    ('candidates/{id}/Recruitments',
        'candidates', u'candidateId', 'recruitments'),
    ('candidates/{id}/Educations',
        'candidates', 'candidateId', 'educations'),
    ('candidates/{id}/LanguageSkills',
        'candidates', 'candidateId', 'languageSkills'),
    ('candidates/{id}/EmploymentExperiences',
        'candidates', 'candidateId', 'employmentexperiences'),
    ('candidates/{id}/EmploymentHistories',
        'candidates', 'candidateId', 'employmenthistories'),
    ('candidates/{id}/Notes',
        'candidates', 'candidateId', 'notes'),
    ('candidates/{id}/DesiredSalary',
        'candidates', 'candidateId', 'desiredsalary'),
    ('candidates/{id}/JobWanted',
        'candidates', 'candidateId', 'jobwanted'),


    ('recruitments/{id}/candidateapplications',
        'recruitments', 'id', 'applications'),
    ('recruitments/{id}/stages',
        'recruitments', 'id', 'stages'),
]


apps_endpoints = [
    ('candidateapplications/{id}/stageshistory',
        'applications', 'applicationId', 'candidateApplicationStages'),
    ('candidateapplications/{id}/tags',
        'applications', 'applicationId', 'tags'),
    ('candidateapplications/{id}/notes',
        'applications', 'applicationId', 'notes'),
]


hash_keys = [
    'lastName',
    'email',
    'candidateLastName',
    'candidateEmail',

    'last_name'
]


def _hash_value(value, algorithm=DEFAULT_HASH_TYPE):
    try:
        hashobj = hashlib.new(algorithm)
    except ValueError:
        logger.warning(f'Invalid hash type "{algorithm}".'
                       ' Falling back to "{DEFAULT_HASH_TYPE}".')
        hashobj = hashlib.new(DEFAULT_HASH_TYPE)

    if isinstance(value, str):
        hashobj.update(value.encode())
    elif isinstance(value, bytes):
        hashobj.update(value)
    else:
        logger.warning(f'Failed to hash value "{value}". Returning "None".')
        return 'None'

    return hashobj.hexdigest()


def _hash_db(db, keys):
    def _walk(thing):
        if isinstance(thing, dict):
            for key in thing:
                if key in keys:
                    logger.debug(f'Hashing key "{key}"')
                    thing[key] = _hash_value(str(thing[key]).lower())
                    continue
                _walk(thing[key])
        elif isinstance(thing, list):
            for i in thing:
                _walk(i)
    _walk(db)


def _get_config():
    config = None
    try:
        logger.debug(f'About to open config file {CONFIG_FILE}.')
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    except Exception as e:
        logger.error(f'Failed to load config {CONFIG_FILE}. {str(e)}')
        exit(1)
    if 'limit' not in config:
        logger.warning(f'Limit not specified in config file {CONFIG_FILE}. '
                       'Using default 100.')
        config['limit'] = 100
    logger.debug(f'Using configuration:\n{config}')
    return config


def _token_updater(token):
    with open(TOKEN_FILE_PATH, 'wb') as handle:
        logger.debug(f'Updating token {token}.')
        pickle.dump(token, handle, protocol=pickle.HIGHEST_PROTOCOL)


def _get_token(config):
    token = None
    # Uncomment this if you want to use a stored token
    # try:
    #     with open(TOKEN_FILE_PATH, 'rb') as handle:
    #         logger.info(f'Using token from file {TOKEN_FILE_PATH}.')
    #         token = pickle.load(handle)
    # except Exception as e:
    #     logger.info(f'Failed to get token from {TOKEN_FILE_PATH}.')

    if token is None:
        try:
            logger.info(f'Getting token from {ACCESS_TOKEN_URL}.')
            auth = HTTPBasicAuth(config['client_id'], config['client_secret'])
            client = LegacyApplicationClient(client_id=config['client_id'])
            oauth = OAuth2Session(client=client)
            token = oauth.fetch_token(token_url=ACCESS_TOKEN_URL,
                                      auth=auth,
                                      username=config['username'],
                                      password=config['password'])
            _token_updater(token)

        except Exception as e:
            logger.error(f'Failed to get token. Reason: {e}')
            exit(1)

    return token


def _http_debug_on():
    http.client.HTTPConnection.debuglevel = 1
    req_log = logging.getLogger('requests')
    req_log.propagate = True
    coloredlogs.install(level='DEBUG', logger=req_log)

    oa_log = logging.getLogger('requests_oauthlib')
    coloredlogs.install(level='DEBUG', logger=oa_log)


def create_client(config):
    token = _get_token(config)

    extra = {
        'client_id': config['client_id'],
        'client_secret': config['client_secret'],
    }

    client = OAuth2Session(
        client_id=config['client_id'],
        token=token,
        auto_refresh_url=ACCESS_TOKEN_URL,
        auto_refresh_kwargs=extra,
        token_updater=_token_updater
    )

    return client


def get_resource_range(client, url, offset, limit, companyId, **kwargs):
    payload = {'companyId': companyId,
               'limit': limit,
               'offset': offset}
    logger.debug(f'About to get resource from {url} with params {payload}.')
    response = client.get(url, params=payload)
    if not response.ok:
        raise Exception(
            f'Failed to get {url}. '
            f'offset:{offset} limit:{limit} companyId:{companyId}\n'
            f'{response.status_code}:{response.reason}. {response.text}')
    try:
        resp_json = response.json()
    except Exception:
        raise Exception(f'Failed to json() response from {url}. '
                        '{response.text}')
    logger.debug(f'Got resource {resp_json}.')
    return resp_json


def get_resources(client, url, collection_name, limit, **kwargs):
    offset = 0
    res_list = []
    while True:
        try:
            resource = get_resource_range(
                client, url=url, offset=offset, limit=limit, **kwargs)
        except Exception as e:
            logger.error(f'{str(e)}')
            break
        if isinstance(resource, dict):
            try:
                collection = resource[collection_name]
            except Exception:
                logger.warning(
                    f'No "{collection_name}" in {resource} for {url}. '
                    'Returning as is.')
                res_list.append(resource)
                break
            # Keyd dicts may be paginated by offset if row count is provided.
            # Keep expanding until the result is empty.
            if isinstance(collection, list):
                if collection:
                    res_list.extend(collection)
                if ('rowCount' not in resource and
                        'totalRowCount' not in resource and
                        'totalRowsCount' not in resource) or not collection:
                    break
            else:
                res_list.append(collection)
                break
        elif isinstance(resource, list):
            res_list.extend(resource)
            break
        offset += limit
    return res_list


def get_collection(client, endp_spec, **kwargs):
    path_spec = endp_spec[0]
    collection_name = endp_spec[1]

    if '{' in path_spec:
        logger.warning(
            f'Collection specified in {endp_spec} is parameterized. '
            'Skipping.')
        return []

    url = ERECRUITER_API_URL + path_spec
    return get_resources(
        client, url=url, collection_name=collection_name, **kwargs)


# Some collection extensions return different data types
# Most important is that even if the return value is a dict
# with a key 'target_collection_name',
# the list under this key may not support pagination.
def get_collection_extensions(client, collection, ext_spec, **kwargs):
    path_spec = ext_spec[0]
    collection_key = ext_spec[2]
    target_collection_name = ext_spec[3]

    if '{' not in path_spec:
        logger.warning(
            f'Collection extension {ext_spec} is not parameterized. '
            'Skipping.')
        return []
    for col_item in collection:
        collection_item_id = str(col_item[collection_key])
        path_with_id = path_spec.replace('{id}', collection_item_id)
        url = ERECRUITER_API_URL + path_with_id
        try:
            resource = get_resources(
                client,
                url=url,
                collection_name=target_collection_name,
                **kwargs)
        except Exception as e:
            logger.warning(
                f'Skipping target_collection {target_collection_name}. '
                f'{str(e)}')
            continue
        col_item[target_collection_name] = resource


# extract applications from 'recruitments' collection
# Add applications as top level resource
# extend applications by its own prefixes
def process_applications(client, db, **kwargs):
    db['applications'] = []
    if 'recruitments' not in db:
        logger.warning(f'No recruitments in DB. Cannot process applications.')
        return db
    for rec in db['recruitments']:
        if 'applications' not in rec:
            logger.warning(
                f'Cannot process recruitment {rec} for applications.')
            continue
        for app in rec['applications']:
            app['recruitmentId'] = rec['id']
        db['applications'].extend(rec['applications'])
        rec.pop('applications')
        for apps_ext_spec in apps_endpoints:
            get_collection_extensions(client,
                                      collection=db['applications'],
                                      ext_spec=apps_ext_spec,
                                      **kwargs)
    return db

def get_codility_info(codility_token, **kwargs):
    db= {}

    codility_headers = {}
    codility_headers['Authorization'] = f'Bearer {codility_token}'
    codility_headers['Content-Type'] = 'application/json'

    tests = requests.get(CODILITY_API_URL + 'tests', headers=codility_headers)
    if tests.status_code == 401:
        logger.error('Codility authorization failed. '
                     f'Headers: {codility_headers}. '
                     f'{tests.json()}')
        return db
    # We should be fine here
    db['tests'] = []
    for test in tests.json()['results']:
        result = requests.get(test['url'], headers=codility_headers)
        db['tests'].append(result.json())

    sessions = requests.get(CODILITY_API_URL + 'sessions', headers=codility_headers)
    db['sessions'] = []
    for session in sessions.json()['results']:
        result = requests.get(session['url'], headers=codility_headers)
        db['sessions'].append(result.json())
    return db

def main():
    config = _get_config()
    if config.get('http_debug', False):
        _http_debug_on()
    if config.get('debug', True):
        coloredlogs.install(level='DEBUG', logger=logger)
    client = create_client(config)
    if 'companyId' not in config:
        logger.error(
            f'Missing "companyId" in the config file. Please provide one.')
        companies = client.get(ERECRUITER_API_URL + 'Account/Companies')
        logger.info(
            f'Client connected. '
            f'Available companies: {companies.json()}. '
            f'Add the one you want in the config file.')
        exit(1)

    db = {}
    for endp_spec in top_level_collection_endpoints:
        collection_name = endp_spec[1]
        collection_list = get_collection(client, endp_spec, **config)
        db[collection_name] = collection_list
    for ext_spec in collection_extension_endpoints:
        collection_name = ext_spec[1]
        get_collection_extensions(
            client, db[collection_name], ext_spec, **config)

    process_applications(client, db, **config)
    cod_db = get_codility_info(**config)
    db['codility'] = cod_db
    _hash_db(db, hash_keys)
    pprint.pprint(db)


if __name__ == '__main__':
    main()
