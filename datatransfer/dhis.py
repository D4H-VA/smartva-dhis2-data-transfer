import json
from datetime import datetime, timedelta

import requests
from logzero import logger

from .config import Config, log_and_exit

"""
Module for DHIS2 access and Import Status
"""


class OrgUnitNotAssignedError(Exception):
    pass


class DuplicateEventImportError(Exception):
    pass


class GenericImportException(Exception):
    pass


class RaiseImportFailure(object):
    """Raise exception if import failed"""
    def __init__(self, response):

        try:
            self.status_code = int(response['httpStatusCode'])
            self.imported = int(response['response']['imported'])
            self.updated = int(response['response']['updated'])
            self.ignored = int(response['response']['ignored'])
            self.deleted = int(response['response']['deleted'])
        except (ValueError, KeyError, TypeError):
            GenericImportException(response)

        else:
            if self.status_code not in {200, 201} or self.imported == 0:
                try:
                    # check if all response state are SUCCESS
                    self.description = set([
                        r['description'] for r in response['response']['importSummaries']
                        if r['status'] != 'SUCCESS'])
                except KeyError:
                    try:
                        self.description = set([c[0]['value'] for c in
                                                [r['conflicts'] for r in response['response']['importSummaries'] if
                                                 r['status'] != 'SUCCESS']])
                    except KeyError:
                        GenericImportException(self.description)

                if [d for d in self.description if "Event.orgUnit does not point to a valid organisation unit" in d]:
                    log_and_exit(self.description)
                elif [d for d in self.description if "Event.program does not point to a valid program" in d]:
                    log_and_exit(self.description)
                elif [d for d in self.description if "Program is not assigned to this organisation unit" in d]:
                    raise OrgUnitNotAssignedError(self.description)
                else:
                    GenericImportException(self.description)


def raise_if_duplicate(response, sid):
    """Check response and raise if there is already an event"""
    event_count = int(response.get('height', 0))
    if event_count > 0:
        raise DuplicateEventImportError()


class Dhis(object):
    """Class for accessing DHIS2"""
    def __init__(self, origin):

        if origin not in {'source', 'target'}:
            log_and_exit("Must adhere to dish.json structure with source and target objects")

        url = Config.dish[origin]['baseurl']
        __username = Config.dish[origin]['username']
        __password = Config.dish[origin]['password']

        if '/api' in url:
            log_and_exit('Do not specify /api in the URL')
        if url.startswith('localhost') or url.startswith('127.0.0.1'):
            url = 'http://{}'.format(url)
        elif url.startswith('http://'):
            url = url
        elif not url.startswith('https://'):
            url = 'https://{}'.format(url)

        self.url = url
        self.api_url = '{}/api'.format(self.url)
        self.api = requests.Session()
        self.auth = (__username, __password)
        logger.info("Connecting to DHIS2 on {}".format(url))

        self.root_orgunit = self.root_orgunit()

    def get(self, endpoint, params=None):
        """DHIS2 HTTP GET, returns requests.Response object"""
        url = '{}/{}.json'.format(self.api_url, endpoint)
        logger.debug('GET: {} - Params: {}'.format(url, params))
        return self.api.get(url, params=params, auth=self.auth)

    def post(self, endpoint, data, params=None):
        """DHIS2 HTTP POST, returns requests.Response object"""
        url = '{}/{}'.format(self.api_url, endpoint)
        logger.debug('POST: {} - Params: {} - Data: {}'.format(url, params, json.dumps(data)))
        return self.api.post(url, params=params, auth=self.auth, json=data)

    def post_event(self, data):
        """POST DHIS2 Event"""

        data['attributeCategoryOptions'] = Config.target_attribute_category_option
        data['attributeOptionCombo'] = Config.target_attribute_option_combo

        if not Config.retain_event_uid:
            # remove Event UID to enable pushing
            # without needing to permanently delete soft-deleted events
            del data['event']

        r = self.post(endpoint='events', data=data)
        try:
            RaiseImportFailure(r.json())
            r.raise_for_status()
        except OrgUnitNotAssignedError:
            self.assign_orgunit_to_program(data)
            self.post(endpoint='events', data=data)
        except requests.RequestException:
            raise GenericImportException("POST failed - {} {}".format(r.url, r.text))

    def get_events(self, from_date):
        """Use Paging to export events, otherwise getting all at once can crash servers"""
        params = {
            'program': Config.program_uid,
            'orgUnit': self.root_orgunit,
            'ouMode': 'DESCENDANTS',
            'pageSize': 100,
            'totalPages': True
        }
        if from_date:
            params['startDate'] = from_date
            params['endDate'] = from_date
        first_page = self.get(endpoint='events', params=params).json()
        yield first_page

        try:
            no_of_pages = first_page['pager']['pageCount']
        except KeyError:
            yield None
        else:
            logger.debug(no_of_pages)
            for p in range(2, no_of_pages + 1):
                params['page'] = p
                next_page = self.get(endpoint='events', params=params).json()
                yield next_page

    def is_duplicate(self, sid):
        """Check DHIS2 for a duplicate event by SID across all OrgUnits"""
        params = {
            'programStage': Config.programstage_uid,
            'orgUnit': self.root_orgunit,
            'ouMode': 'DESCENDANTS',
            'filter': '{}:EQ:{}'.format(Config.study_id, sid)
        }
        r = self.get(endpoint='events/query', params=params)
        raise_if_duplicate(r.json(), sid)

    def root_orgunit(self):
        params = {
            'fields': 'id',
            'filter': 'level:eq:1'
        }
        req = self.get(endpoint='organisationUnits', params=params).json()
        root_orgunit_uid = self._get_root_id(req)
        logger.info("Root org unit to query: {}".format(root_orgunit_uid))
        return root_orgunit_uid

    @staticmethod
    def _get_root_id(response):
        if len(response['organisationUnits']) > 1:
            log_and_exit("More than one Organisation Units found. Can not proceed.")
        if len(response['organisationUnits']) == 0:
            log_and_exit("No Organisation Unit found. Can not proceed.")
        return response['organisationUnits'][0]['id']

    def assign_orgunit_to_program(self, data):
        """Assign OrgUnit to program"""
        params = {
            'fields': ':owner'
        }
        existing = self.get('programs/{}'.format(Config.program_uid), params=params).json()
        org_unit = data['orgUnit']

        if org_unit not in [ou['id'] for ou in existing['organisationUnits']]:
            existing['organisationUnits'].append({"id": org_unit})
            self.post('metadata', data={'programs': [existing]})
            logger.info("Assigned orgUnit {}".format(org_unit))