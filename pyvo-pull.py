# -*- coding: utf-8 -*-


import os
import sys
import re
import collections
import datetime

import yaml
import arrow
import requests
from lxml import html
import unidecode

CITY_BY_SERIES = {
    'Brněnské PyVo + BRUG': 'Brno',
    'Pražské PyVo': 'Praha',
    'Ostravské Pyvo s Rubači': 'Ostrava',
}

class EventDumper(yaml.SafeDumper):
    def __init__(self, *args, **kwargs):
        kwargs['default_flow_style'] = False
        kwargs['allow_unicode'] = True
        super(EventDumper, self).__init__(*args, **kwargs)

def _dict_representer(dumper, data):
    return dumper.represent_mapping(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        data.items())

EventDumper.add_representer(collections.OrderedDict, _dict_representer)


def render_event(filename, event):
    with open(filename, 'w') as f:
        yaml.dump(event, f, Dumper=EventDumper)


def slugify(name):
    """Make a filename-friendly approximation of a string

    The result only uses the characters a-z, 0-9, _, -
    """
    decoded = unidecode.unidecode(name).lower()
    return re.sub('[^a-z0-9_]+', '-', decoded).strip('-')


def create_filename(event):
    date = event['start'].strftime('%Y-%m-%d')
    topic = event.get('topic')
    if topic:
        return '{}-{}.yaml'.format(date, slugify(topic))
    return '{}.yaml'.format(date)


def pull_event_series(url):
    tree = scrape(url)
    events = (
        pull_event(link.get('href')) for link
        in tree.cssselect('.conference-listing .url')
    )
    series_name = text(tree, 'h1')
    city = CITY_BY_SERIES[series_name]
    return city, events


def pull_event(url):
    tree = scrape(url)

    # title
    title = meta(tree, 'name')
    event_number = None
    parts = re.split(':| - | – ', title, maxsplit=1)
    if len(parts) > 1:
        name, topic = (part.strip() for part in parts)
    else:
        parts = re.split(r'#([0-9]+)', title, maxsplit=1)
        if len(parts) > 1:
            name, event_number, topic = (part.strip() for part in parts)
            event_number = int(event_number)
        else:
            name = title
            topic = None

    # city -- this depends on series
    # (so Brno Pyvo will have city 'Brno' even if it was a trip to Bratislava)
    series_name = text(tree, '.series a')
    event_city = CITY_BY_SERIES[series_name]

    # description
    desc = text(tree, '#event-description') or None

    # parse date and time
    timestamp = meta(tree, 'lanyrdcom:start_date')
    start_date = arrow.get(timestamp)

    time_str = text(tree, '.dtstart .time')
    if time_str:
        try:
            start_time = arrow.get(time_str, 'H:mmA')
        except arrow.parser.ParserError:
            start_time = arrow.get(time_str, 'HA')

        start_date = start_date.replace(hour=start_time.hour,
                                        minute=start_time.minute,
                                        second=start_time.second)
        start = start_date.naive
    else:
        start = start_date.date()

    # venue
    venue_info = collections.OrderedDict()
    venue_info['city'] = text(tree, '.prominent-place .sub-place')
    try:
        venue = tree.cssselect('.venue')[0]
    except IndexError:
        venue_info['name'] = text(tree, '.sub-place')
    else:
        venue_info['name'] = text(venue, 'h3')

        venue_info['address'] = '\n'.join([p.text_content().strip()
                                           for p in venue.cssselect('p')
                                           if not len(p)])

    # location
    venue_info['location'] = collections.OrderedDict()
    venue_info['location']['latitude'] = meta(tree, 'place:location:latitude')
    venue_info['location']['longitude'] = meta(tree, 'place:location:longitude')

    # talks
    talks = []
    for talk in tree.cssselect('.session-detail'):
        talkinfo = collections.OrderedDict()
        talks.append(talkinfo)
        talkinfo['title'] = text(talk, 'h3 a')
        for speaker_p in talk.cssselect('p'):
            speaker_text = speaker_p.text_content()
            speaker_text = speaker_text.replace('presented by', '')
            talkinfo['speakers'] = [t.strip()
                                    for t in speaker_text.split(' and ')]
        for link in talk.cssselect('h3 a'):
            add_coverage(talkinfo, link.attrib['href'])

    # compose the final object
    eventinfo = collections.OrderedDict()
    eventinfo['city'] = event_city
    eventinfo['start'] = start
    eventinfo['name'] = name
    if event_number is not None:
        eventinfo['number'] = event_number
    if topic:
        eventinfo['topic'] = topic
    if desc:
        eventinfo['description'] = desc
    eventinfo['venue'] = venue_info
    eventinfo['talks'] = talks
    eventinfo['urls'] = [url]
    return eventinfo


def add_coverage(talk, url):
    talk['urls'] = [url]
    coverage = talk['coverage'] = []

    tree = scrape(url)
    for item in tree.cssselect('#coverage .coverage-item'):
        classes = set(item.attrib['class'].split())
        classes.discard('coverage-item')
        for cls in classes:
            coverage_type = {
                'coverage-slides': 'slides',
                'coverage-video': 'video',
                'coverage-links': 'link',
                'coverage-writeups': 'writeup',
                'coverage-notes': 'notes',
                'coverage-sketchnotes': 'notes',
            }[cls]
        for link in item.cssselect('h3 a'):
            coverage.append({coverage_type: link.attrib['href']})


def scrape(url):
    resp = requests.get(url)
    resp.raise_for_status()

    parser = html.HTMLParser(encoding='utf-8')
    tree = html.fromstring(resp.content, parser=parser)

    tree.make_links_absolute(resp.url)
    return tree


def text(tree, css):
    elements = tree.cssselect(css)
    if not elements:
        return ''
    [element] = elements
    content = element.text_content() or ''
    return content.strip()


def meta(tree, property_name):
    templates = [
        'meta[itemprop="{name}"]',
        'meta[property="{name}"]',
        'meta[name="{name}"]',
    ]
    css = ', '.join(templates).format(name=property_name)
    meta = tree.cssselect(css)[0]
    return meta.get('content')


if __name__ == '__main__':
    url = sys.argv[1]

    if '/series/' in url:
        series_name, events = pull_event_series(url)
        output_dir = os.path.join(os.getcwd(), slugify(series_name))
        os.makedirs(output_dir, exist_ok=True)
    else:
        events = [pull_event(url)]
        output_dir = os.getcwd()

    print('Directory: {}'.format(output_dir))
    for event in events:
        filename = create_filename(event)
        print("Rendering '{}'".format(filename))
        render_event(os.path.join(output_dir, filename), event)
