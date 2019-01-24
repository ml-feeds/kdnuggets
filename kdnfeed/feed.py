import logging
import os
import urllib.request
from typing import Union
from xml.etree import ElementTree

from kdnfeed import config

config.configure_logging()

log = logging.getLogger(__name__)


class Feed:
    def __init__(self):
        self._on_gcloud = bool(os.getenv('GCLOUD_PROJECT'))
        self._blacklist = config.BLACKLIST.copy()
        self._blacklist['Value'] = self._blacklist['Value'].str.lower()  # For case-insensitive comparison.

    def _is_blacklisted(self, item: ElementTree.Element) -> Union[tuple, bool]:
        item = {'title': item.findtext('title').lower(),
                'link': item.findtext('link').lower(),
                'category': [c.text.lower() for c in item.findall('category')],
                }
        for filter_tuple in self._blacklist.itertuples(index=False, name='Filter'):
            operator = config.OPERATORS[filter_tuple.Operator]
            actual_value = item[filter_tuple.Field]
            blacklisted_value = filter_tuple.Value
            if filter_tuple.Field == 'category':
                for actual_individual_category in actual_value:
                    if operator(actual_individual_category, blacklisted_value):
                        return filter_tuple
            else:
                if operator(actual_value, blacklisted_value):
                    return filter_tuple
        return False

    def feed(self) -> bytes:
        log.debug('Reading input feed.')
        text = urllib.request.urlopen(config.INPUT_FEED_URL).read()
        xml = ElementTree.fromstring(text)
        log.info('Received input feed of size %s bytes with %s items.', len(text), len(xml.findall('./channel/item')))

        not_on_gcloud = not self._on_gcloud
        channel = next(xml.iter('channel'))
        for item in list(channel.iter('item')):  # https://stackoverflow.com/a/19419905/
            title = item.findtext('title')
            guid = item.findtext('guid')
            filter_status = self._is_blacklisted(item)
            if filter_status:
                channel.remove(item)

            if not_on_gcloud:
                if filter_status:
                    log.info('❌ Removed %s "%s" as its %s %s "%s".\n',
                              guid, title, filter_status.Field, filter_status.Operator, filter_status.Value)
                else:
                    log.info('✅ Approved %s "%s" having categories: %s\n',
                              guid, title, ', '.join(c.text for c in item.findall('category')))

        text = ElementTree.tostring(xml)
        log.info('Generated output feed of size %s bytes with %s items.', len(text), len(xml.findall('./channel/item')))
        return text
