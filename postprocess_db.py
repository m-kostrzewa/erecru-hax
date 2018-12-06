# -*- coding: utf-8 -*-
import coloredlogs
import hashlib
import json
import logging
import sys


from pathlib import Path


logger = logging.getLogger(__name__)
coloredlogs.install(level='INFO', logger=logger)


DEFAULT_HASH_TYPE = 'sha1'


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
    'profile_url',

    'email_login',
    'email_domain'
]

email_keys = [
    'email',
    'candidateEmail'
]

def hash_value(value, algorithm=DEFAULT_HASH_TYPE, salt=None):
    try:
        hashobj = hashlib.new(algorithm)
    except ValueError:
        logger.warning(f'Invalid hash type "{algorithm}".'
                       ' Falling back to "{DEFAULT_HASH_TYPE}".')
        hashobj = hashlib.new(DEFAULT_HASH_TYPE)

    logger.debug(f'Hashing value {value}.')
    if isinstance(value, str):
        hashobj.update(value.encode())
    elif isinstance(value, bytes):
        hashobj.update(value)
    else:
        logger.warning(f'Failed to hash value "{value}". Returning "None".')
        return 'None'

    if salt:
        logger.debug(f'Using salt {salt}')
        hashobj.update(str(salt).encode())

    logger.debug(f'Hashed {value} as {hashobj.hexdigest()}')
    return hashobj.hexdigest()


def _replace_key_value_with_hash(thing, key,
                                 algorithm=DEFAULT_HASH_TYPE, salt=None,
                                 **kwargs):
    value = str(thing[key]).lower()
    logger.debug(f'Replacing {key} as {value} in {thing}')
    thing[key] = hash_value(value, algorithm=algorithm, salt=salt)
    logger.debug(f'Replaced as {thing[key]}')


def _transform_email(thing, key):
    value = str(thing[key]).lower()
    try:
        thing['email_login'], thing['email_domain'] = value.split('@')
    except (KeyError, ValueError):
        pass


def process_db(db, hash_salt=None):
    def _walk(thing):
        if isinstance(thing, dict):
            for key in list(thing.keys()):
                if not thing[key]:
                    continue
                if key in email_keys:
                    _transform_email(thing, key)
            for key in thing:
                if not thing[key]:
                    continue
                if hash_salt and key in hash_keys:
                    logger.debug(f'Hashing key "{key}"')
                    _replace_key_value_with_hash(thing, key, salt=hash_salt)
                    continue
                _walk(thing[key])
        elif isinstance(thing, list):
            for i in thing:
                _walk(i)
    _walk(db)
    return db


def _print_help():
    logger.info(f'''
Usage:
{sys.argv[0]} db_file_name salt''')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        _print_help()
        exit(-1)
    try:
        salt = sys.argv[2]
    except IndexError:
        salt = None

    dbfilepath = Path(sys.argv[1])
    if not dbfilepath.is_file():
        logger.error(f'Argument {sys.argv[1]} is not a file.')
    try:
        posix_dbfilepath = dbfilepath.absolute().as_posix()
        with open(posix_dbfilepath, 'r') as f:
            logger.info(f'Loading db file {posix_dbfilepath}.')
            db = json.load(f)
        db = process_db(db, hash_salt=salt)
        posix_processed = posix_dbfilepath + '.processed.json'
        with open(posix_processed, 'w') as f:
            logger.info(f'Saving processed db file to {posix_processed}')
            json.dump(db, f, sort_keys=True, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f'Something went wrong. {e}')


