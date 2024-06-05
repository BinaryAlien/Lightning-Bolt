#!/usr/bin/env python3

from discord import Embed, Object, Webhook
from ics import Calendar
from pytz import timezone
from urllib.parse import parse_qs, urlparse
import aiohttp
import asyncio
import datetime
import os
import sys
import yaml

TIMEZONE = os.getenv('LIGHTNING_BOLT_TZ', 'Europe/Paris')

EMBEDS_PER_MESSAGE = 10

async def get_calendar(url, session):
    async with session.get(url) as response:
        return Calendar(await response.text())

def duration_to_str(duration):
    seconds = round(duration.total_seconds())
    hours, minutes = (seconds // 3600, seconds // 60 % 60)
    if hours > 0:
        duration_str = f'{hours}h{minutes:02}'
    else:
        duration_str = f'{minutes} min'
    return duration_str

def get_rooms(event):
    location = event.location.strip()
    if location:
        rooms = location.split(', ')
    else:
        rooms = []
    return rooms

def is_valid_url(url):
    url_parts = urlparse(url)
    return bool(url_parts.scheme) and bool(url_parts.netloc)

def parse_thread(webhook_url):
    thread = None
    webhook_url = urlparse(webhook_url)
    webhook_query = parse_qs(webhook_url.query)
    thread_id = webhook_query.get('thread_id')
    if thread_id:
        thread_id = thread_id[-1]
        thread = Object(thread_id)
    return thread

def split_embeds(embeds):
    assert len(embeds) > 0, "should not be empty"
    chunk = [embeds[0]]
    for embed in embeds[1:]:
        if len(chunk) == EMBEDS_PER_MESSAGE or any(embed.url == other.url for other in chunk if other.url):
            yield chunk
            chunk.clear()
        chunk.append(embed)
    yield chunk

async def get_events(url, session, day=None):
    calendar = await get_calendar(url, session)
    if day is not None:
        events = filter(lambda event: event.begin.date() == day, calendar.events)
    else:
        events = calendar.events
    return sorted(events, key=lambda event: event.begin)

def event_to_embed(event):
    tz = timezone(TIMEZONE)
    embed = Embed(title=event.begin.astimezone(tz).strftime('%H:%M'), description=event.name)
    embed.add_field(name='Durée', value=duration_to_str(event.duration))
    embed.add_field(name='Fin', value=event.end.astimezone(tz).strftime('%H:%M'))
    for room in get_rooms(event):
        embed.add_field(name='Salle', value=room, inline=False)
    if event.url and is_valid_url(event.url):
        embed.url = event.url
    return embed

async def send_embeds(webhook_url, session, embeds):
    webhook = Webhook.from_url(webhook_url, session=session)
    thread = parse_thread(webhook_url)
    if thread:
        webhook_send = lambda embeds: webhook.send(embeds=embeds, thread=thread)
    else:
        webhook_send = lambda embeds: webhook.send(embeds=embeds)
    for embeds_chunk in split_embeds(embeds):
        await webhook_send(embeds=embeds_chunk)


def load_groups(filename):
    with open(filename) as file:
        return yaml.safe_load(file)

async def publish_events_for(group, session, day=None):
    events = await get_events(group['ics'], session, day or datetime.date.today())
    if not events:
        return
    embeds = list(map(event_to_embed, events))
    tasks = set()
    for webhook_url in group['webhooks']:
        task = asyncio.create_task(send_embeds(webhook_url, session, embeds))
        task.add_done_callback(tasks.discard)
        tasks.add(task)
    await asyncio.gather(*tasks)


async def main():
    if len(sys.argv) == 2:
        groups_filename = sys.argv[1]
    else:
        groups_filename = 'groups.yml'
    groups = load_groups(groups_filename)
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    async with aiohttp.ClientSession() as session:
        tasks = set()
        for group in groups:
            task = asyncio.create_task(publish_events_for(group, session, tomorrow))
            task.add_done_callback(tasks.discard)
            tasks.add(task)
        await asyncio.gather(*tasks)

if __name__ == '__main__':
    asyncio.run(main())
