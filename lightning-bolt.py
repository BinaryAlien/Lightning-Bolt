#!/usr/bin/env python3

from discord import Embed, Webhook
from ics import Calendar
from urllib.parse import urlparse, urlunparse
import asyncio
import aiohttp
import datetime
import json
import sys

TIMEZONE = datetime.timezone(datetime.timedelta(hours=2), name='CEST')

EMBEDS_PER_MESSAGE = 10

async def get_calendar(url, session):
    async with session.get(url) as response:
        return Calendar(await response.text())

async def get_events(url, session, day=None):
    calendar = await get_calendar(url, session)
    if day is not None:
        events = filter(lambda event: event.begin.date() == day, calendar.events)
    else:
        events = calendar.events
    return sorted(events, key=lambda event: event.begin)

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

def sanitize_url(url):
    url_parts = urlparse(url)
    if not url_parts.netloc:
        return sanitize_url('//' + url)
    if not url_parts.scheme:
        url_parts = url_parts._replace(scheme='https')
    return urlunparse(url_parts)

def event_to_embed(event):
    embed = Embed(title=event.begin.astimezone(TIMEZONE).strftime('%H:%M'), description=event.name)
    embed.add_field(name='Durée', value=duration_to_str(event.duration))
    embed.add_field(name='Fin', value=event.end.astimezone(TIMEZONE).strftime('%H:%M'))
    for room in get_rooms(event):
        embed.add_field(name='Salle', value=room, inline=False)
    if event.url:
        embed.url = sanitize_url(event.url)
    return embed

def load_groups(filename):
    with open(filename) as file:
        return json.load(file)

async def send_embeds(webhook, embeds):
    for i in range(0, len(embeds), EMBEDS_PER_MESSAGE):
        embeds_chunk = embeds[i:i + EMBEDS_PER_MESSAGE]
        await webhook.send(embeds=embeds_chunk)

async def publish_events_for(group, session, day=None):
    events = await get_events(group['ics'], session, day or datetime.date.today())
    if not events:
        return
    embeds = list(map(event_to_embed, events))
    webhooks = map(lambda webhook_url: Webhook.from_url(webhook_url, session=session), group['webhooks'])
    tasks = set()
    for webhook in webhooks:
        task = asyncio.create_task(send_embeds(webhook, embeds))
        task.add_done_callback(tasks.discard)
        tasks.add(task)
    await asyncio.gather(*tasks)

async def main():
    if len(sys.argv) == 2:
        groups_filename = sys.argv[1]
    else:
        groups_filename = 'groups.json'
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
