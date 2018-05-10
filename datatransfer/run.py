import argparse
import sys
import time
from datetime import datetime, timedelta

from logzero import logger

from datatransfer.config import Config
from datatransfer.config import setup_logger
from datatransfer.dhis import Dhis, DuplicateEventImportError, OrgUnitNotAssignedError, GenericImportException


def valid_date(s):
    try:
        return datetime.strftime(datetime.strptime(s, "%Y-%m-%d"), "%Y-%m-%d")
    except ValueError:
        msg = "Not a valid date: '{}'.".format(s)
        raise argparse.ArgumentTypeError(msg)


def _parse_args(args=sys.argv[1:]):
    """Parse arguments"""
    description = u"Transfer Verbal Autopsy Events from DHIS2 server to DHIS2 server. \n" \
                  u"Without arguments, yesterday's events will be pulled."
    parser = argparse.ArgumentParser(usage='%(prog)s', description=description)

    parser.add_argument(u'--log',
                        dest='log',
                        action='store',
                        required=True,
                        help=u"File path to log file")

    group = parser.add_mutually_exclusive_group()
    group.add_argument(u'--all',
                       dest='all',
                       action='store_true',
                       required=False,
                       default=False,
                       help=u"Get all events")

    group.add_argument(u'--from_date',
                       dest='from_date',
                       action='store',
                       required=False,
                       type=valid_date,
                       help=u"Get events from a certain date")

    arguments = parser.parse_args(args)
    return arguments


def run(import_all, from_date):
    source_api = Dhis('source')
    target_api = Dhis('target')

    if not import_all:
        if not from_date:
            from_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')  # yesterday
        logger.info("Getting events for {} from {}".format(from_date, source_api.url))
    else:
        logger.warning("Getting ALL events from {}".format(source_api.url))
        time.sleep(4)

    success_count, error_count, duplicate_count, no_of_records = 0, 0, 0, 0
    for i, event_page in enumerate(source_api.get_events(from_date), 1):
        if event_page and event_page.get('events'):
            no_of_records += len(event_page.get('events', 0))
            for event in event_page['events']:
                try:
                    sid = [dv['value'] for dv in event['dataValues'] if dv['dataElement'] == Config.study_id][0]
                except KeyError:
                    logger.warning(
                        "Event '{}' has no Study ID record in source DHIS2 ({})".format(event.get('event'), source_api.url))
                    error_count += 1
                else:
                    try:
                        target_api.is_duplicate(sid)
                    except DuplicateEventImportError:
                        logger.warning(
                            "Study ID record '{}' already exists in target DHIS2 ({})".format(sid, target_api.url))
                        duplicate_count += 1
                    else:
                        try:
                            target_api.post_event(data=event)
                        except OrgUnitNotAssignedError:
                            target_api.assign_orgunit_to_program(event)
                            target_api.post_event(data=event)
                            success_count += 1
                        except GenericImportException as e:
                            logger.error(e)
                            error_count += 1
                        else:
                            logger.info("SID: {} - Import successful!".format(sid))
                            success_count += 1

    logger.info("SUMMARY: "
                "Total number of events: {} | "
                "Imported: {} | "
                "Duplicates: {} | "
                "Errors: {}".format(no_of_records, success_count, duplicate_count, error_count))


def launch():
    try:
        opts = _parse_args()
        setup_logger(opts.log)
        run(opts.all, opts.from_date)
    except KeyboardInterrupt:
        logger.warning("Aborted!")
    except Exception as e:
        logger.exception(e)
