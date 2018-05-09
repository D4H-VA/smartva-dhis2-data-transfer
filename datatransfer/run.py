import argparse
import sys

from logzero import logger

from datatransfer.config import setup_logger
from datatransfer.dhis import Dhis, DuplicateEventImportError, OrgUnitNotAssignedError, GenericImportException
from datatransfer.config import Config


def _parse_args(args=sys.argv[1:]):
    """Parse arguments"""
    description = u"Transfer Verbal Autopsy Events from DHIS2 server to DHIS2 server"
    parser = argparse.ArgumentParser(usage='%(prog)s', description=description)

    parser.add_argument(u'--log',
                        dest='log',
                        action='store',
                        required=True,
                        help=u"File path to log file")

    parser.add_argument(u'--all',
                        dest='all',
                        action='store_true',
                        required=False,
                        default=False,
                        help=u"Pull & push all events")

    arguments = parser.parse_args(args)
    return arguments


def run(import_all=False):

    source_api = Dhis('source')
    target_api = Dhis('target')

    counter = 0
    for i, event_page in enumerate(source_api.get_events(import_all), 1):
        counter += len(event_page.get('events', 0))
        for event in event_page['events']:
            try:
                sid = [dv['value'] for dv in event['dataValues'] if dv['dataElement'] == Config.study_id][0]
            except KeyError:
                logger.warning("Event '{}' has no Study ID record in source DHIS2 ({})".format(event.get('event'), source_api.url))
                break
            else:
                try:
                    target_api.is_duplicate(sid)
                except DuplicateEventImportError:
                    logger.warning("Study ID record '{}' already exists in target DHIS2 ({})".format(sid, target_api.url))
                    break
                else:
                    try:
                        target_api.post_event(data=event)
                    except OrgUnitNotAssignedError:
                        target_api.assign_orgunit_to_program(event)
                        try:
                            target_api.post_event(data=event)
                        except GenericImportException as e:
                            logger.error(e)
                            break


def launch():
    try:
        opts = _parse_args()
        setup_logger(opts.log)
        run(opts.all)
    except KeyboardInterrupt:
        logger.warning("Aborted!")
    except Exception as e:
        logger.exception(e)
