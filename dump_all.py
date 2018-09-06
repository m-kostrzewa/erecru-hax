# !/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import print_function

import hashlib
import logging
import pprint
import requests

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


DEFAULT_HASH_TYPE='sha1'
erecruiter_pl_url = 'https://api.erecruiter.pl/v1.1/'
erecruiter_pl_url = 'https://testapi.io/api/m-kostrzewa/v1.1/'

endpoints = [('Account/Permissions',),
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
    ('Candidates', None, None),
    ('Candidates/{id}/Recruitments', 'Candidates', u'CandidateId'),
    ('Candidates/{id}/Educations', 'Candidates', 'CandidateId'),
    ('Candidates/{id}/LanguageSkills', 'Candidates', 'CandidateId'),
    ('Candidates/{id}/EmploymentExperiences', 'Candidates', 'CandidateId'),
    ('Candidates/{id}/EmploymentHistories', 'Candidates', 'CandidateId'),
    ('Candidates/{id}/Notes', 'Candidates', 'CandidateId'),
    ('Candidates/{id}/DesiredSalary', 'Candidates', 'CandidateId'),
    ('Candidates/{id}/JobWanted', 'Candidates', 'CandidateId'),
    ('Candidates/{id}/Notes', 'Candidates', 'CandidateId'),
    ('Candidates/{id}/DesiredSalary', 'Candidates', 'CandidateId'),
    ('Candidates/{id}/JobWanted', 'Candidates', 'CandidateId'),
]

hash_keys = [
    'LastName',
    'Email',
]

def dump_all(client):
    db = {}

    for endpoint_spec in endpoints:
        path = endpoint_spec[0]
        path_collection = endpoint_spec[1] or path
        path_collection_key = endpoint_spec[2]
        if '{' not in path:
            response = client.get(erecruiter_pl_url + path)
            if not response.ok:
                logger.warn(f'Failed to get {erecruiter_pl_url + path}. {response.text}')
                continue
            try:
                db[path] = response.json()[path_collection]
                logger.debug(f'Printing whole db: {db}')
            except:
                logger.warn(f'Failed to json(). {response.text}')
                continue
        if '{' in path:
            if not path_collection in db:
                logger.warn(f'Skipping path {path}. Collection {path_collection} not present in db.')
                continue
            for collection_item in db[path_collection]:
                candidate_id = str(collection_item[path_collection_key])
                path_with_id = path.replace('{id}', candidate_id)
                url = erecruiter_pl_url + path_with_id
                logger.debug(f'About to get resource from {url}')
                try:
                    response = client.get(url).json()
                except:
                    logger.warn(f'Failed to json().')
                    continue
                sub_collection_name = path.split('/')[-1]
                found_candidate = -1
                for index, candidate in enumerate(db[path_collection]):
                    if str(candidate[path_collection_key]) == str(candidate_id):
                        found_candidate = index
                        break
                if found_candidate != -1:
                    db[path_collection][found_candidate][sub_collection_name] = response

    _hash_db(db)
    pprint.pprint(db)

def _hash_value(value, algorithm=DEFAULT_HASH_TYPE):
    try:
        hashobj = hashlib.new(algorithm)
    except ValueError:
        logger.warn(f'Invalid hash type "{algorithm}". Falling back to "{DEFAULT_HASH_TYPE}".')
        hashobj = hashlib.new(DEFAULT_HASH_TYPE)

    if isinstance(value, str):
        hashobj.update(value.encode())
    elif isinstance(value, bytes):
        hashobj.update(value).hexdigest()
    else:
        logger.warn(f'Failed to hash value "{value}". Returning "None".')
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

def main():
    dump_all(requests)


if __name__ == '__main__':
    main()
