# -*- coding: utf-8 -*-
import coloredlogs
import hashlib
import http
import json
import logging
import pickle
import pprint


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
# ERECRUITER_API_URL='https://testapi.io/api/m-kostrzewa/v1.1/'


endp_list = [('Account/Permissions',),
             ('Account/AppVersion',),
             ('Account/Companies',),
             ('Account/Stages/{id}',),
             ('Account/Tags',),
             ('Account/Origins',),
             ('CandidateApplications/{candidateApplicationId}/FullCandidateFormWithWorkLocations',),
             ('CandidateApplications/{id}/Tags',),
             ('CandidateApplications/{id}/Notes',),
             ('CandidateApplications/{id}',),
             ('CandidateApplications/{candidateApplicationId}/Full',),
             # (# 'CandidateApplications/FormCustomFiles/{id}', ),
             ('CandidateApplications/{id}/StagesHistory',),
             ('Candidates/{id}/JobWantedWithExpectedSalaries',),
             ('Candidates',),
             ('Candidates/Favourites',),
             # (# 'Candidates/{id}/Photo', ),
             # (# 'Candidates/CVs/{id}', ),
             ('Candidates/{id}/Recruitments', 'Candidates', 'CandidateId'),
             # (# 'Candidates/{id}/DriverLicense', ),
             ('Candidates/{id}/ContactData', 'Candidates', 'CandidateId'),
             ('Candidates/{id}/Educations', 'Candidates', 'CandidateId'),
             ('Candidates/{id}/LanguageSkills', 'Candidates', 'CandidateId'),
             ('Candidates/{id}/EmploymentExperiences', 'Candidates', 'CandidateId'),
             ('Candidates/{id}/EmploymentHistories', 'Candidates', 'CandidateId'),
             ('Candidates/{id}/Notes', 'Candidates', 'CandidateId'),
             ('Candidates/{id}/DesiredSalary', 'Candidates', 'CandidateId'),
             ('Candidates/{id}/JobWanted', 'Candidates', 'CandidateId'),
             ('Dictionaries/Languages',),
             ('Dictionaries/RecruitmentStages',),
             ('Recruitments/{id}/CandidateApplications',),
             ('Recruitments',),
             ('Recruitments/{id}',),
             ('Recruitments/My',),
             ('Recruitments/Closed',),
             ('Recruitments/Closed/My',),
             ('Recruitments/{id}/Stages',)]

endpoints = [
    ('candidates', None, None),
    ('candidates/{id}/Recruitments', 'candidates', u'candidateId'),
    ('candidates/{id}/Educations', 'candidates', 'candidateId'),
    ('candidates/{id}/LanguageSkills', 'candidates', 'candidateId'),
    ('candidates/{id}/EmploymentExperiences', 'candidates', 'candidateId'),
    ('candidates/{id}/EmploymentHistories', 'candidates', 'candidateId'),
    ('candidates/{id}/Notes', 'candidates', 'candidateId'),
    ('candidates/{id}/DesiredSalary', 'candidates', 'candidateId'),
    ('candidates/{id}/JobWanted', 'candidates', 'candidateId'),
    ('candidates/{id}/Notes', 'candidates', 'candidateId'),
    ('candidates/{id}/DesiredSalary', 'candidates', 'candidateId'),
    ('candidates/{id}/JobWanted', 'candidates', 'candidateId'),
]

hash_keys = [
    'lastName',
    'email',
]


def get_resource(client, config, path):
    payload = {'companyId': config.get('companyId', 0),
               'filters.limit': config.get('filters.limit', 0)}
    logger.debug(f'About to get resource from {path} with params {payload}.')
    response = client.get(path, params=payload)
    if not response.ok:
        raise Exception(f'Failed to get {path}. '
                        f'{response.status_code}:{response.reason}. {response.text}')
    try:
        resp_json = response.json()
    except Exception:
        raise Exception(f'Failed to json() response from {path}. {response.text}.')
    logger.debug(f'Got resource {resp_json}.')
    return resp_json


def dump_all(client, config):
    db = {}

    for endpoint_spec in endpoints:
        path = endpoint_spec[0]
        path_collection = endpoint_spec[1] or path
        path_collection_key = endpoint_spec[2]
        if '{' not in path:
            try:
                resource = get_resource(client, config, ERECRUITER_API_URL + path)
                db[path] = resource[path_collection]
            except KeyError as ke:
                logger.error(f'Failed to get collection {path_collection} from {resource}. {str(ke)}.')
            except Exception as e:
                logger.error(f'{str(e)}')
            continue
        if '{' in path:
            if path_collection not in db:
                logger.warning(f'Skipping path {path}. Collection {path_collection} not present in db.')
                continue
            for collection_item in db[path_collection]:
                candidate_id = str(collection_item[path_collection_key])
                path_with_id = path.replace('{id}', candidate_id)
                url = ERECRUITER_API_URL + path_with_id
                sub_collection_name = path.split('/')[-1]
                try:
                    resource = get_resource(client, config, url)
                except Exception as e:
                    logger.warning(f'Skipping subcollection {sub_collection_name}. {str(e)}')
                    continue
                found_candidate = -1
                for index, candidate in enumerate(db[path_collection]):
                    if str(candidate[path_collection_key]) == str(candidate_id):
                        found_candidate = index
                        break
                if found_candidate != -1:
                    db[path_collection][found_candidate][sub_collection_name] = resource

    logger.info(f'Hashing db keys {hash_keys}.')
    _hash_db(db)
    logger.info(f'Done. Dumping DB.')
    pprint.pprint(db)


def _hash_value(value, algorithm=DEFAULT_HASH_TYPE):
    try:
        hashobj = hashlib.new(algorithm)
    except ValueError:
        logger.warning(f'Invalid hash type "{algorithm}". Falling back to "{DEFAULT_HASH_TYPE}".')
        hashobj = hashlib.new(DEFAULT_HASH_TYPE)

    if isinstance(value, str):
        hashobj.update(value.encode())
    elif isinstance(value, bytes):
        hashobj.update(value)
    else:
        logger.warning(f'Failed to hash value "{value}". Returning "None".')
        return 'None'

    return hashobj.hexdigest()


def _hash_db(db):
    def _walk(thing):
        if isinstance(thing, dict):
            for key in thing.keys():
                if key in hash_keys:
                    logger.debug(f'Hashing key "{key}"')
                    thing[key] = _hash_value(thing[key])
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
    if 'filters.limit' not in config.keys():
        logger.warning(f'Limit not specified in config file {CONFIG_FILE}. Using default 100.')
        config['filters.limit'] = 100
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


def _create_client(config):
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


def _http_debug_on():
    http.client.HTTPConnection.debuglevel = 1
    req_log = logging.getLogger('requests')
    req_log.propagate = True
    coloredlogs.install(level='DEBUG', logger=req_log)

    oa_log = logging.getLogger('requests_oauthlib')
    coloredlogs.install(level='DEBUG', logger=oa_log)


def main():
    config = _get_config()
    if config.get('http_debug', False):
        _http_debug_on()
    if config.get('debug', True):
        coloredlogs.install(level='DEBUG', logger=logger)
    client = _create_client(config)
    if 'companyId' not in config.keys():
        logger.error(f'Missing "companyId" in the config file. Please provide one.')
        companies = client.get(ERECRUITER_API_URL + 'Account/Companies')
        logger.info(f'Client connected. Available companies: {companies.json()}. Add the one you want in the config file.')
        exit(1)
    dump_all(client, config)


if __name__ == '__main__':
    main()
