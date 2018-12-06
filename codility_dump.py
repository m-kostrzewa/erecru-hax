# -*- coding: utf-8 -*-
import coloredlogs
import hashlib
import http
import json
import logging
import pickle
import pprint
import requests
import time


from functools import wraps
from oauthlib.oauth2 import LegacyApplicationClient
from pathlib import Path
from ratelimit import limits, sleep_and_retry, exception
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth2Session
from time import sleep


# Configuration of ratelimitter
# CALLS_RATE_LIMIT=1
# PERIOD_IN_SECONDS_RATE_LIMIT=0.5
# means 1 request in 0.5 second, therefore 120 requests in 1 minute
ERECRUITER_CALLS_RATE_LIMIT=1
ERECRUITER_PERIOD_RATE_LIMIT=0.1

CODILITY_CALLS_RATE_LIMIT=1
CODILITY_PERIOD_RATE_LIMIT=10


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
#    ('candidates/{id}/Notes',
#        'candidates', 'candidateId', 'notes'),
#    ('candidates/{id}/DesiredSalary',
#        'candidates', 'candidateId', 'desiredsalary'),
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
#    ('candidateapplications/{id}/notes',
#        'applications', 'applicationId', 'notes'),
]


hash_keys = [
    'firstName',
    'lastName',
    'email',
    'candidateName',
    'candidateLastName',
    'candidateEmail',
    'candidatePhone',
    'candidatePhoneNumber',
    'createUserFullName',
    'createUserLastName',
    'candidateCvFiles',

    'first_name',
    'last_name',
    'profile_url'
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


def hash_db(db, keys):
    def _walk(thing):
        if isinstance(thing, dict):
            for key in thing:
                if not thing[key]:
                    continue
                if key in keys:
                    logger.debug(f'Hashing key "{key}"')
                    thing[key] = _hash_value(str(thing[key]).lower())
                    continue
                _walk(thing[key])
        elif isinstance(thing, list):
            for i in thing:
                _walk(i)
    _walk(db)
    return db


def get_config(filename=CONFIG_FILE):
    config = None
    try:
        logger.debug(f'About to open config file {filename}.')
        with open(filename, 'r') as f:
            config = json.load(f)
    except Exception as e:
        logger.error(f'Failed to load config {filename}. {str(e)}')
        exit(1)
    if 'limit' not in config:
        logger.warning(f'Limit not specified in config file {filename}. '
                       'Using default 100.')
        config['limit'] = 100
    logger.debug(f'Using configuration:\n{config}')
    return config


def _oauth2_token_updater(token):
    with open(TOKEN_FILE_PATH, 'wb') as handle:
        logger.debug(f'Updating token {token}.')
        pickle.dump(token, handle, protocol=pickle.HIGHEST_PROTOCOL)


def _get_oauth2_token(token_url, client_id, client_secret, username, password,
                      **kwargs):
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
            logger.info(f'Getting token from {token_url}.')
            auth = HTTPBasicAuth(client_id, client_secret)
            client = LegacyApplicationClient(client_id)
            oauth = OAuth2Session(client=client)
            token = oauth.fetch_token(token_url=token_url,
                                      auth=auth,
                                      username=username,
                                      password=password)
            _oauth2_token_updater(token)

        except Exception as e:
            logger.error(f'Failed to get token. Reason: {e}')
            exit(1)

    return token


def http_debug_on():
    http.client.HTTPConnection.debuglevel = 1
    req_log = logging.getLogger('requests')
    req_log.propagate = True
    coloredlogs.install(level='DEBUG', logger=req_log)

    oa_log = logging.getLogger('requests_oauthlib')
    coloredlogs.install(level='DEBUG', logger=oa_log)


def create_client(client_id, client_secret, token_url, **kwargs):
    token = _get_oauth2_token(token_url=token_url, client_id=client_id,
                              client_secret=client_secret,**kwargs)

    extra = {
        'client_id': client_id,
        'client_secret': client_secret,
    }

    client = OAuth2Session(
        client_id=client_id,
        token=token,
        auto_refresh_url=token_url,
        auto_refresh_kwargs=extra,
        token_updater=_oauth2_token_updater
    )

    return client


def log_time(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        logger.debug(f"{func.__name__}({args}, {kwargs}) ran in {round(end - start, 4)}s")
        return result
    return wrapper


@sleep_and_retry
@limits(calls=ERECRUITER_CALLS_RATE_LIMIT, period=ERECRUITER_PERIOD_RATE_LIMIT)
@log_time
def erecruiter_limitted_request(client, url, params):
    return client.get(url, params=params)


def get_resource_range(client, url, offset, limit, companyId, **kwargs):
    payload = {'companyId': companyId,
               'limit': limit,
               'offset': offset}
    logger.debug(f'About to get resource from {url} with params {payload}.')
    response = erecruiter_limitted_request(client, url, payload)
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
#                if ('rowCount' not in resource and
#                        'totalRowCount' not in resource and
#                        'totalRowsCount' not in resource) or not collection:
                    break
                else:
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
def process_applications(client, db, apps_endpoints, **kwargs):
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

@sleep_and_retry
@limits(calls=CODILITY_CALLS_RATE_LIMIT, period=CODILITY_PERIOD_RATE_LIMIT)
@log_time
def codility_limitted_request(url, headers):
    return requests.get(url, headers=headers)


def _get_codility_collection_list(codility_token, collection_name, **kwargs):
    collection_list = []

    codility_headers = {}
    codility_headers['Authorization'] = f'Bearer {codility_token}'
    codility_headers['Content-Type'] = 'application/json'

    url = CODILITY_API_URL + collection_name # + '/?page=1'
    while url:
        logger.debug(f'Processing {url}')
        result = codility_limitted_request(url, headers=codility_headers)
        result_json = result.json()
        if 'results' in result_json:
            collection_list.extend(result_json['results'])
        else:
            logger.warning(f'No results for {url}.')
            break
        url = result_json.get('next', None)
    return collection_list


def get_codility_info(codility_token, **kwargs):
    db= {}

    codility_headers = {}
    codility_headers['Authorization'] = f'Bearer {codility_token}'
    codility_headers['Content-Type'] = 'application/json'

    #test auth for codility
    tests = codility_limitted_request(
        CODILITY_API_URL + 'tests', headers=codility_headers)
    if tests.status_code == 401:
        logger.error('Codility authorization failed. '
                     f'Headers: {codility_headers}. '
                     f'{tests.json()}')
        return db

    tests_list = _get_codility_collection_list(codility_token, 'tests')
    db['tests_list'] = tests_list
    logger.debug(f'Got tests from Codility :{tests_list}')
    sessions_list = _get_codility_collection_list(codility_token, 'sessions')
    db['sessions_list'] = sessions_list
    logger.debug(f'Got sessions from Codility :{sessions_list}')
    # We should be fine here
    db['tests'] = []
    for test in tests_list:
        retries = 100
        i = 0
        while i < retries:
            try:
                result = codility_limitted_request(
                    test['url'], headers=codility_headers)
                db['tests'].append(result.json())
                break
            except (exception.RateLimitException,
                    requests.exceptions.ConnectionError) as e:
                logger.error(f'Failed to get {test["url"]}. {e}. '
                             'Lets wait 10m and see')
                sleep(10*60)



    db['sessions'] = []
    for session in sessions_list:
        retries = 100
        i = 0
        while i < retries:
            try:
                result = codility_limitted_request(
                    session['url'], headers=codility_headers)
                db['sessions'].append(result.json())
                break
            except (exception.RateLimitException,
                    requests.exceptions.ConnectionError) as e:
                logger.error(f'Failed to get {test["url"]}. {e}. '
                             'Lets wait 10m and see')
                sleep(10*60)
    return db

def dump_db_json(db, name='db_dump', path='./db_dump.d'):
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    filename = p.joinpath(f'{name}_{str(int(time.time()*1000000))}.json')
    logger.info(f'Dumping db to "{filename}.')
    with open(filename, 'w') as f:
        json.dump(db, f, sort_keys=True, indent=4, ensure_ascii=False)


def main():
    config = get_config()
    if config.get('http_debug', False):
        http_debug_on()
    if config.get('debug', True):
        coloredlogs.install(level='DEBUG', logger=logger)
    db = {}
    cod_db = get_codility_info(**config)
    db['codility'] = cod_db
    #hash_db(db, hash_keys)
    dump_db_json(db, name='codility_db')
    pprint.pprint(db)



if __name__ == '__main__':
    main()
