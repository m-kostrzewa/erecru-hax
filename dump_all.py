# !/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import print_function

import requests
import sys
import os
import logging
import httplib
import json
import pickle




def dump_all(client):
    erecruiter_pl_url = 'https://api.erecruiter.pl/v1.1/'
    erecruiter_pl_url = 'https://testapi.io/api/m-kostrzewa/v1.1/'

    endpoints = [('Account/Permissions',),
        ('Account/AppVersion', ),
        ('Account/Companies', ),
        ('Account/Stages/{id}', ),
        ('Account/Tags', ),
        ('Account/Origins', ),
        ('CandidateApplications/{candidateApplicationId}/FullCandidateFormWithWorkLocations', ),
        ('CandidateApplications/{id}/Tags', ),
        ('CandidateApplications/{id}/Notes', ),
        ('CandidateApplications/{id}', ),
        ('CandidateApplications/{candidateApplicationId}/Full', ),
        # (# 'CandidateApplications/FormCustomFiles/{id}', ),
        ('CandidateApplications/{id}/StagesHistory', ),
        ('Candidates/{id}/JobWantedWithExpectedSalaries', ),
        ('Candidates', ),
        ('Candidates/Favourites', ),
        # (# 'Candidates/{id}/Photo', ),
        # (# 'Candidates/CVs/{id}', ),
        ('Candidates/{id}/Recruitments', 'Candidates', 'CandidateId'),
        # (# 'Candidates/{id}/DriverLicense', ),
        ('Candidates/{id}/ContactData', 'Candidates', 'CandidateId'),
        ('Candidates/{id}/Educations', 'Candidates', 'CandidateId'),
        ('Candidates/{id}', 'Candidates', 'CandidateId'),
        ('Candidates/{id}/LanguageSkills', 'Candidates', 'CandidateId'),
        ('Candidates/{id}/EmploymentExperiences', 'Candidates', 'CandidateId'),
        ('Candidates/{id}/EmploymentHistories', 'Candidates', 'CandidateId'),
        ('Candidates/{id}/Notes', 'Candidates', 'CandidateId'),
        ('Candidates/{id}/DesiredSalary', 'Candidates', 'CandidateId'),
        ('Candidates/{id}/JobWanted', 'Candidates', 'CandidateId'),
        ('Dictionaries/Languages', ),
        ('Dictionaries/RecruitmentStages', ),
        ('Recruitments/{id}/CandidateApplications', ),
        ('Recruitments', ),
        ('Recruitments/{id}', ),
        ('Recruitments/My', ),
        ('Recruitments/Closed', ),
        ('Recruitments/Closed/My', ),
        ('Recruitments/{id}/Stages', )]

    endpoints = [
        ('Candidates', None, None),
        ('Candidates/{id}/Recruitments', 'Candidates', u'CandidateId'),

        ('Candidates/{id}/Educations', 'Candidates', 'CandidateId'),
    ]

    import collections
    # db = collections.defaultdict(dict)
    db = {}

    for endpoint in endpoints:
        path = endpoint[0]
        path_collection = endpoint[1]
        path_collection_key = endpoint[2]
        if '{' not in path:
            respose = client.get(erecruiter_pl_url + path).json()
            db[path] = respose
            print(db)
        if '{' in path:
            for collection_item in db[path_collection][path_collection]:
                candidate_id = str(collection_item[path_collection_key])
                path_with_id = path.replace('{id}', candidate_id)
                url = erecruiter_pl_url + path_with_id
                print(url)
                try:
                    respose = client.get(url).json()
                except:
                    continue
                print(db[path_collection][path_collection])
                sub_collection_name = path.split('/')[-1]
                found_candidate = -1
                for index, candidate in enumerate(db[path_collection][path_collection]):
                    print(candidate[path_collection_key])
                    print(candidate_id)
                    if str(candidate[path_collection_key]) == str(candidate_id):
                        print(index)
                        found_candidate = index
                        break
                if found_candidate != -1:
                    db[path_collection][path_collection][found_candidate][sub_collection_name] = respose

    print(db)





def main():
    dump_all(requests)


if __name__ == '__main__':
    main()
