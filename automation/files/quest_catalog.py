#!/usr/bin/env python3
"""Export and inspect the bundled main-quest definitions without running the game."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parent
DEFAULT_WORLD = ROOT / 'linux/world'
DEFAULT_OUTPUT = ROOT / 'linux/quest-catalog'


def _optional_json(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else default


def _known_text(value):
    return value if isinstance(value, str) and value.strip() else None


def build_catalog(client_jar=ROOT / 'app/client.jar', world_root=DEFAULT_WORLD, text_root=None):
    """Keep original step order and enrich only exact map/logical-NPC matches.

    Optional text_root contains places.json and talk<N>.json string arrays.
    By default use world_root/auxiliary/text/en. Candidate NPC dialogue records
    are not treated as exact quest-step dialogue or a complete quest script.
    """
    world_root = Path(world_root)
    resources = {}
    with zipfile.ZipFile(client_jar) as jar:
        for name in ('quests/steps.json', 'quests/places.json'):
            resources[name] = jar.read(name)
    definitions = json.loads(resources['quests/steps.json'])['chapters']
    chapter_places = json.loads(resources['quests/places.json'])['chapters']
    if len(definitions) != len(chapter_places):
        raise ValueError('Quest chapter counts differ between steps.json and places.json.')
    atlas = _optional_json(world_root / 'atlas.json', {'maps': []})
    maps = {entry['id']: entry for entry in atlas['maps']}
    npc_entries = _optional_json(world_root / 'auxiliary/npcs.json', [])
    npcs = defaultdict(list)
    for entry in npc_entries:
        npcs[(entry.get('stage'), entry.get('npc'))].append(entry)
    text_root = Path(text_root) if text_root is not None else world_root / 'auxiliary/text/en'
    place_texts = _optional_json(text_root / 'places.json', [])
    if not isinstance(place_texts, list):
        raise ValueError('places.json text resource must be a string array.')
    talk_files = {}
    text_sources = {}
    for name in ['places.json', *[f'talk{index}.json' for index in sorted({entry['file'] for entry in npc_entries if isinstance(entry.get('file'), int)})]]:
        path = text_root / name
        if path.is_file():
            data = path.read_bytes()
            text_sources[name] = {'sha256': hashlib.sha256(data).hexdigest()}
            if name != 'places.json':
                value = json.loads(data)
                if not isinstance(value, list):raise ValueError(name + ' text resource must be a string array.')
                talk_files[name] = value

    def speaker(text):
        if isinstance(text, str):
            for match in re.finditer(r'\[name\](.*?)\[name\]', text, re.DOTALL):
                name = match.group(1).strip()
                if name and '[' not in name and not name.startswith('?'):return name
        return None

    def npc_record(entry):
        filename = f"talk{entry.get('file')}.json"
        values = talk_files.get(filename, [])
        candidates = []
        for index in entry.get('texts', []):
            text = values[index] if isinstance(index, int) and 0 <= index < len(values) and isinstance(values[index], str) else None
            candidates.append({'index': index, 'text': text, 'speaker': speaker(text),
                               'source': filename if text is not None else None})
        return {'character': entry.get('character'), 'text_file': entry.get('file'),
                'text_indices': entry.get('texts', []), 'dialogue_candidates': candidates,
                'source': 'linux/world/auxiliary/npcs.json'}

    def map_info(identifier):
        entry = maps.get(identifier, {})
        raw_name = _known_text(entry.get('name'))
        # Atlas room values sometimes contain a base-map ID, not a name.
        name = raw_name if raw_name and not re.fullmatch(r's\d+', raw_name) else None
        place_id = entry.get('place')
        place_name = _known_text(place_texts[place_id]) if isinstance(place_id, int) and 0 < place_id < len(place_texts) else None
        return {
            'id': identifier, 'name': name, 'name_source': 'linux/world/atlas.json' if name else None,
            'room_key': raw_name, 'width': entry.get('width'), 'height': entry.get('height'),
            'place_id': place_id, 'place_name': place_name,
            'place_name_source': f'places.json[{place_id}]' if place_name else None,
            'metadata': entry.get('metadata'), 'collision': entry.get('collision'),
            'atlas_match': bool(entry),
        }

    chapters = []
    for chapter_number, (steps, places) in enumerate(zip(definitions, chapter_places), 1):
        title = None
        chapter = {
            'number': chapter_number, 'title': title,
            'title_source': None,
            'place_ids': places, 'places': [map_info(identifier) for identifier in places], 'steps': [],
        }
        for step_number, definition in enumerate(steps, 1):
            stage = definition.get('stage')
            npc_id = definition.get('npc')
            npc = None
            if npc_id is not None:
                records = [npc_record(entry) for entry in npcs[(stage, npc_id)]]
                named = next((candidate for record in records for candidate in record['dialogue_candidates'] if candidate['speaker']), None)
                name = named['speaker'] if named else None
                npc = {
                    'logical_id': npc_id, 'id_source': 'quests/steps.json:npc',
                    'name': name, 'name_source': f"{named['source']}[{named['index']}]:[name] speaker label" if named else None,
                    'records': records, 'records_match': 'exact stage and logical NPC ID',
                    'dialogue_selection': 'unknown; records contain candidates, not the server-selected quest dialogue',
                    'position': None,
                }
            guidance = {'talk': 'Talk to the logical NPC on this map',
                        'drop': 'Win battles on this map',
                        'enter': 'Go to this map', 'zone': 'Go to this map'}.get(definition.get('how'))
            chapter['steps'].append({
                'number': step_number, 'definition': definition,
                'action': definition.get('how', 'unknown'),
                'map': map_info(stage), 'npc': npc, 'objective': None,
                'objective_source': None, 'client_guidance': guidance,
                'completion_condition': None, 'trigger_bounds': None, 'rewards': None,
            })
        chapters.append(chapter)
    all_steps = [step for chapter in chapters for step in chapter['steps']]
    action_counts = Counter(step['action'] for step in all_steps)
    return {
        'schema': 1, 'scope': 'offline bundled main-quest definitions',
        'numbering': 'chapter and step numbers are 1-based; original ordering is preserved',
        'sources': {
            name: {'sha256': hashlib.sha256(data).hexdigest()} for name, data in resources.items()
        } | {
            'atlas': 'linux/world/atlas.json' if maps else None,
            'npcs': 'linux/world/auxiliary/npcs.json' if npc_entries else None,
            'text_resources': text_sources,
        },
        'summary': {
            'chapter_count': len(chapters), 'step_count': len(all_steps),
            'action_counts': dict(sorted(action_counts.items())),
            'map_count': len({step['map']['id'] for step in all_steps}),
            'npc_step_count': sum(step['npc'] is not None for step in all_steps),
            'matched_npc_steps': sum(bool(step['npc'] and step['npc']['records']) for step in all_steps),
            'unknown_map_steps': sum(not step['map']['atlas_match'] for step in all_steps),
        },
        'limitations': [
            'These files describe the client\'s bundled main-quest sequence, not observed quest completion or a complete server implementation.',
            'Action tokens talk, enter, zone and drop are preserved verbatim. The client presents drop as winning battles and enter/zone as going to a map. Exact trigger geometry, battle targets/counts, access requirements and completion predicates are not specified by these definitions.',
            'Chapter places are a separate bundled list, not a verified map-exit graph or a travel route.',
            'NPC IDs are logical definition IDs, not live rendered entity IDs; coordinates and live availability remain unknown.',
            'NPC text indices are candidate dialogue references; the exact dialogue chosen for each quest step remains server-dependent. NPC names are first valid speaker labels in those candidate resources, not independently verified live names.',
            'Rewards, prerequisites, branches and any server-only quests are unknown. Missing titles, names and objectives remain null.',
        ],
        'chapters': chapters,
    }


def _cell(value):
    return str(value if value is not None else 'unknown').replace('|', '\\|').replace('\n', '<br>')


def chapter_markdown(chapter):
    lines = [f"## Chapter {chapter['number']}: {_cell(chapter['title'])}", '',
             'Bundled chapter places (not a route): ' + ', '.join(map(str, chapter['place_ids'])), '',
             '| Step | Action | Map | Map name | Size | Place | Logical NPC | NPC name | Client guidance |',
             '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for step in chapter['steps']:
        map_entry, npc = step['map'], step['npc']
        size = f"{map_entry['width']}x{map_entry['height']}" if map_entry['width'] is not None and map_entry['height'] is not None else None
        cells = [f"{chapter['number']}.{step['number']}", step['action'], map_entry['id'], map_entry['name'], size,
                 map_entry['place_name'] or map_entry['place_id'], npc['logical_id'] if npc else 'not specified',
                 npc['name'] if npc else 'not applicable', step['client_guidance']]
        lines.append('| ' + ' | '.join(map(_cell, cells)) + ' |')
    candidates = [(step['number'], step['npc']['records']) for step in chapter['steps'] if step['npc'] and step['npc']['records']]
    if candidates:
        lines += ['', 'NPC resource candidates (not verified quest-step dialogue):', '']
        for step_number, records in candidates:
            for record in records:
                lines.append(f"- {chapter['number']}.{step_number}: character `{record['character']}`, text file `{record['text_file']}`, indices {record['text_indices']}.")
    return '\n'.join(lines) + '\n'


def catalog_markdown(catalog):
    summary = catalog['summary']
    lines = ['# Bundled main-quest catalog', '',
             f"{summary['chapter_count']} chapters; {summary['step_count']} steps; {summary['map_count']} distinct step maps.", '',
             'Sources: original `app/client.jar` resources `quests/steps.json` and `quests/places.json`; optional exported map/NPC metadata and verified text enrichment.', '',
             'Unknown fields are written as `unknown`. Action values are original tokens.', '']
    lines.extend('- ' + limitation for limitation in catalog['limitations'])
    lines.append('')
    lines.extend(chapter_markdown(chapter) for chapter in catalog['chapters'])
    return '\n'.join(lines)


def export_catalog(catalog, output=DEFAULT_OUTPUT):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'main-quests.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'main-quests.md').write_text(catalog_markdown(catalog), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('export', 'list', 'chapter'):
        command = commands.add_parser(name)
        command.add_argument('--jar', type=Path, default=ROOT / 'app/client.jar')
        command.add_argument('--world', type=Path, default=DEFAULT_WORLD)
        command.add_argument('--texts', type=Path, help='Directory containing exported places.json and talk<N>.json text arrays (default: WORLD/auxiliary/text/en)')
        if name == 'export':
            command.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
        else:
            command.add_argument('--json', action='store_true')
        if name == 'chapter':
            command.add_argument('number', type=int, help='1-based chapter number')
    args = parser.parse_args()
    catalog = build_catalog(args.jar, args.world, args.texts)
    if args.command == 'export':
        export_catalog(catalog, args.output)
        print(json.dumps({'output': str(args.output), **catalog['summary']}, ensure_ascii=False))
    elif args.command == 'list':
        if args.json:
            print(json.dumps(catalog['summary'] | {'chapters': [{'number': chapter['number'], 'title': chapter['title'], 'steps': len(chapter['steps'])} for chapter in catalog['chapters']]}, ensure_ascii=False, indent=2))
        else:
            for chapter in catalog['chapters']:
                print(f"{chapter['number']:2}  {len(chapter['steps']):2} steps  {chapter['title'] or 'unknown title'}")
    else:
        if not 1 <= args.number <= len(catalog['chapters']):
            parser.error(f"chapter must be between 1 and {len(catalog['chapters'])}")
        chapter = catalog['chapters'][args.number - 1]
        print(json.dumps(chapter, ensure_ascii=False, indent=2) if args.json else chapter_markdown(chapter), end='\n' if args.json else '')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        raise SystemExit(str(error))
