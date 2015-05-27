# -*- coding: utf-8 -*-


import os
import sys
import re

import yaml
import arrow
import requests
from lxml import html
import unidecode


def render_event(filename, event):
    with open(filename, 'w') as f:
        yaml.safe_dump(event, f, default_flow_style=False, allow_unicode=True)


def slugify(name):
    """Make a filename-friendly approximation of a string

    The result only uses the characters a-z, 0-9, _, -
    """
    decoded = unidecode.unidecode(name).lower()
    return re.sub('[^a-z0-9_]+', '-', decoded).strip('-')


def create_filename(event):
    date = event['start'][0:10]
    topic = event['topic']
    if topic:
        return '{}-{}.yaml'.format(date, slugify(topic))
    return '{}.yaml'.format(date)


def pull_event_series(url):
    tree = scrape(url)
    events = (
        pull_event(link.get('href')) for link
        in tree.cssselect('.conference-listing .url')
    )
    return text(tree, 'h1'), events


def pull_event(url):
    tree = scrape(url)

    # title
    title = meta(tree, 'name')
    parts = title.split(':')
    if len(parts) > 1:
        name, topic = (part.strip() for part in parts)
    else:
        name = title
        topic = None

    # series
    series_name = text(tree, '.series a')

    # description
    desc = text(tree, '#event-description') or None

    # parse date and time
    timestamp = meta(tree, 'lanyrdcom:start_date')
    start_date = arrow.get(timestamp)

    time_str = text(tree, '.time')
    if time_str:
        try:
            start_time = arrow.get(time_str, 'H:mmA')
        except arrow.parser.ParserError:
            start_time = arrow.get(time_str, 'HA')

        start = '{} {}'.format(
            start_date.format('YYYY-MM-DD'),
            start_time.format('HH:mm')
        )
    else:
        start = start_date.format('YYYY-MM-DD')

    # venue
    try:
        venue = tree.cssselect('.venue')[0]
    except IndexError:
        venue_name = text(tree, '.sub-place')
        address_lines = []
    else:
        venue_name = text(venue, 'h3')

        address_lines = []
        for p in venue.cssselect('p'):
            if not len(p):
                address_lines.append(p.text_content().strip())


    # location
    location = '{};{}'.format(
        meta(tree, 'place:location:latitude'),
        meta(tree, 'place:location:longitude')
    )

    # talks
    talks = []
    for talk in tree.cssselect('.session-detail'):
        talks.append('{}: {}'.format(
            text(talk, 'p a'),
            text(talk, 'h3 a'),
        ))

    # compose the final object
    return {
        'name': name,
        'series': series_name,
        'topic': topic,
        'start': start,
        'description': desc,
        'venue': venue_name,
        'address': '\n'.join(address_lines) or None,
        'location': location,
        'talks': talks,
        'links': [url],
    }


def scrape(url):
    resp = requests.get(url)
    resp.raise_for_status()

    parser = html.HTMLParser(encoding='utf-8')
    tree = html.fromstring(resp.content, parser=parser)

    tree.make_links_absolute(resp.url)
    return tree


def text(tree, css):
    elements = tree.cssselect(css)
    try:
        element = elements[0]
    except IndexError:
        return ''
    else:
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
