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

# Endpoint definition list
# (endpoint path, db collection name, id of the resource)
# * endpoint path - this will be the suffix of the API url
#                   if {} is in the path, it will get replaced
# * db collection name - name of the top level collection to be put in DB
#                        and also in which collection to look for the id
# * id of the resource - this is the key which value will be substituted for {}
#                        in endpoint path
endpoints = [
    ('candidates', 'candidates', None),
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

    ('recruitments', 'recruitments', None),
    ('recruitments/{id}/candidateapplications', 'recruitments', 'id'),
    ('recruitments/{id}/stages', 'recruitments', 'id'),

    ('Dictionaries/Languages', 'languages', None),
    ('Dictionaries/RecruitmentStages', 'stages', None),

    ('Account/Stages', 'accountstages', None),
    ('Account/Tags', 'accounttags', None),
    ('Account/Origins', 'accountorigins', None),

    ('Candidates/Favourites', 'candidatefavourites', None),
]


apps_endpoints = [
    ('candidateapplications/{id}/stageshistory', 'applications', 'applicationId'),
    ('candidateapplications/{id}/tags', 'applications', 'applicationId'),
    ('candidateapplications/{id}/notes', 'applications', 'applicationId'),
]


hash_keys = [
    'lastName',
    'email',
    'candidateLastName',
    'candidateEmail',
]


def get_resource(client, config, path, offset=0):
    payload = {'companyId': config.get('companyId', 0),
               'limit': config.get('limit', 100),
               'offset': offset}
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

def _process_applications(client, config, db):
    db['applications'] = []
    if 'recruitments' not in db:
        logger.warning(f'No recruitments in DB. Cannot process applications.')
        return db
    for rec in db['recruitments']:
        if 'candidateapplications' not in rec or 'applications' not in rec['candidateapplications']:
            logger.warning(f'Cannot process recruitment {rec} for applications.')
            continue
        for app in rec['candidateapplications']['applications']:
            app['recruitmentsId'] = rec['id']
        db['applications'].extend(rec['candidateapplications']['applications'])
        rec.pop('candidateapplications')
    dump_all(client, config, apps_endpoints, db)
    return db

def dump_all(client, config, endpoints, db=None):
    if not db:
        db = {}

    for endpoint_spec in endpoints:
        path = endpoint_spec[0]
        path_collection = endpoint_spec[1] or path
        path_collection_key = endpoint_spec[2]
        if '{' not in path:
            # Here we process top level collection list
            if path_collection not in db:
                db[path_collection] = []
            try:
                # keep paginating over the results for normal collections
                # stupid API returns different data types for different
                offset = 0
                while True:
                    resource = get_resource(client, config, ERECRUITER_API_URL + path, offset)
                    if isinstance(resource, list):
                        # Add lists as is
                        db[path_collection] = resource
                        break
                    elif isinstance(resource, dict):
                        # try to get path_collection from resource first so we can add dicts without this key as is
                        # in the KeyError exception
                        db[path_collection].extend(resource[path_collection])

                        # path_collection key usually has a list
                        # if offset was to high, this list will be empty
                        # quick solution for pagination
                        if resource[path_collection]:
                            offset += config['limit']
                        else:
                            break
                    else:
                        logger.error(f'Failed to identify resource {resource}.')
                        break
            except KeyError as ke:
                logger.warning(f'Failed to get collection {path_collection} from {resource}. {str(ke)}.')
                db[path_collection].extend(resource)
            except Exception as e:
                logger.error(f'{str(e)}')
            continue
        if '{' in path:
            # here we fetch specific resources for a collection item
            if path_collection not in db:
                logger.warning(f'Skipping path {path}. Collection {path_collection} not present in db.')
                continue
            for collection_item in db[path_collection]:
                collection_item_id = str(collection_item[path_collection_key])
                path_with_id = path.replace('{id}', collection_item_id)
                url = ERECRUITER_API_URL + path_with_id
                sub_collection_name = path.split('/')[-1]
                try:
                    resource = get_resource(client, config, url)
                except Exception as e:
                    logger.warning(f'Skipping subcollection {sub_collection_name}. {str(e)}')
                    continue
                found_collection_item_idx = -1
                for index, item in enumerate(db[path_collection]):
                    if str(item[path_collection_key]) == str(collection_item_id):
                        found_collection_item_idx = index
                        break
                if found_collection_item_idx != -1:
                    db[path_collection][found_collection_item_idx][sub_collection_name] = resource
    logger.info(f'Done. Dumping DB.')
    return db


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


def _hash_db(db, hash_keys):
    def _walk(thing):
        if isinstance(thing, dict):
            for key in thing:
                if key in hash_keys:
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
        logger.warning(f'Limit not specified in config file {CONFIG_FILE}. Using default 100.')
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
    if 'companyId' not in config:
        logger.error(f'Missing "companyId" in the config file. Please provide one.')
        companies = client.get(ERECRUITER_API_URL + 'Account/Companies')
        logger.info(f'Client connected. Available companies: {companies.json()}. Add the one you want in the config file.')
        exit(1)

    db = dump_all(client, config, endpoints)
    _process_applications(client, config, db)
    _hash_db(db, hash_keys)
    pprint.pprint(db)


if __name__ == '__main__':
    main()
