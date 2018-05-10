import sys
import json
import os
import logging
from configparser import ConfigParser

import logzero
from logzero import logger


def load_auth(parser):
    """Load the authentication file as specified in config.ini and return a Python object"""
    path = parser.get('auth', 'auth_file')

    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (IOError, AttributeError):
        raise FileNotFoundError("Could not read authentication file at {}".format(path))


class Config(object):
    ROOT_DIR = os.path.abspath('.')
    _parser = ConfigParser()
    _parser.read(os.path.join(ROOT_DIR, 'config.ini'))
    dish = load_auth(_parser)

    program_uid = _parser.get('dhis', 'program')
    programstage_uid = _parser.get('dhis', 'program_stage')
    study_id = _parser.get('dhis', 'study_id')

    source_baseurl = dish['source']['baseurl']
    source_username = dish['source']['username']
    source_password = dish['source']['password']

    target_baseurl = dish['target']['baseurl']
    target_username = dish['target']['username']
    target_password = dish['target']['password']

    target_attribute_category_option = _parser.get('dhis', 'attribute_category_option')
    target_attribute_option_combo = _parser.get('dhis', 'attribute_option_combo')


def setup_logger(log_path):
    # Default logger
    log_format = '%(color)s* %(levelname)1s%(end_color)s  %(asctime)s  %(message)s [%(module)s:%(lineno)d]'
    formatter = logzero.LogFormatter(fmt=log_format)
    logzero.setup_default_logger(formatter=formatter)

    logzero.loglevel(logging.INFO)

    # Log file
    log_format_no_color = '* %(levelname)1s  %(asctime)s  %(message)s [%(module)s:%(lineno)d]'
    formatter_no_color = logzero.LogFormatter(fmt=log_format_no_color)
    # Log rotation of 20 files for 10MB each
    logzero.logfile(log_path, formatter=formatter_no_color, loglevel=logging.INFO, maxBytes=int(1e7), backupCount=20)


def log_and_exit(message):
    logger.error(message)
    sys.exit(1)
