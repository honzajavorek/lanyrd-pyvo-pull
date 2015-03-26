# -*- coding: utf-8 -*-


import sys

import yaml
import arrow
import requests
from lxml import html


def pull_event_series(url):
    tree = scrape(url)
    for link in tree.cssselect('.conference-listing .url'):
        url = link.get('href')
        yield pull_event(url)


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

    # description
    desc = text(tree, '#event-description') or None

    # parse date and time
    timestamp = meta(tree, 'lanyrdcom:start_date')
    start_date = arrow.get(timestamp)

    time_str = text(tree, '.time')
    if time_str:
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
        results = pull_event_series(url)
    else:
        results = [pull_event(url)]

    for result in results:
        doc = yaml.dump(result, default_flow_style=False)
        print('---')
        print(doc)
