#!/usr/bin/env python3
'Reconstruct Luna comparison inputs locally from independently downloaded ELLIPSE files.\n\nValidate the complete comparison design, preserve essay text and presented order, and write prompts only to a new external local directory. No provider calls are made. The synthetic example needs no corpus files or credentials.'
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
from merge_human_ratings import public_essay_key, read_index, TRAITS

CONTRACT_SHA256 = '4c20ceec2134dd4db99aa1436d8d2b5578f9e54e595c954872772a48d2430350'
ASSETS = Path(__file__).resolve().parent
EXPECTED = dict(target_essays=1714, prompts=16, cells=96, base=676326,
                selectable=608652, heldout=67674, reversal=33858)
CELL_COLUMNS = ('cell_id', 'prompt_id', 'trait', 'n_items', 'n_base',
                'n_selectable', 'n_heldout', 'n_reversal')
BASE_COLUMNS = ('pair_id', 'first_id', 'second_id', 'first_wins', 'partition')
REV_COLUMNS = ('cell_id', 'base_pair_id', 'first_id', 'second_id', 'first_wins')


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha_text(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def resources(root=ASSETS):
    need(sha_file(root / 'luna_prompt_contract.json') == CONTRACT_SHA256, 'Frozen scientific contract hash mismatch')
    contract = json.loads((root / 'luna_prompt_contract.json').read_text(encoding='utf-8'))
    need(set(contract['traits']) == set(TRAITS), 'Expected all six original traits')
    assets = {}
    for spec in [contract['template'], *contract['traits'].values()]:
        name = spec['file']
        need(name in ['luna_prompt_template.txt', *['luna_traits/' + t.lower() + '.txt' for t in TRAITS]],
             'Unexpected prompt resource path')
        path = root / name
        need(path.is_file() and not path.is_symlink() and sha_file(path) == spec['sha256'],
             'Frozen model-facing resource hash mismatch')
        assets[name] = spec['sha256']
    assets['luna_prompt_contract.json'] = sha_file(root / 'luna_prompt_contract.json')
    template = (root / contract['template']['file']).read_bytes().decode('utf-8')
    guidance = {t: (root / spec['file']).read_bytes().decode('utf-8')
                for t, spec in contract['traits'].items()}
    
    for marker in contract['placeholder_order']:
        need(marker in template, 'Missing historical prompt placeholder')
    need(template.count('{SAMPLE_1}') == template.count('{SAMPLE_2}') == 1 and
         template.index('{SAMPLE_1}') < template.index('{SAMPLE_2}'),
         'Invalid historical sample placeholder order')
    for trait, guide in guidance.items():
        sample = render(template, trait, guide, 'SYNTHETIC SAMPLE ONE.', 'SYNTHETIC SAMPLE TWO.')
        spec = contract['traits'][trait]
        need(sha_text(sample) == spec['synthetic_prompt_sha256'] and
             len(sample) == spec['synthetic_prompt_chars'], 'W006 synthetic full-prompt parity failed')
    return template, guidance, assets, contract


def render(template, trait, guide, text1, text2):
    for marker, value in (('{TRAIT_NAME}', trait), ('{TRAIT_DESCRIPTION}', guide),
                          ('{SAMPLE_1}', text1), ('{SAMPLE_2}', text2)):
        template = template.replace(marker, value)
    return template


def rows(path, columns):
    need(path.is_file() and not path.is_symlink(), 'Required input file missing or symlinked')
    with path.open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        need(reader.fieldnames == list(columns), 'Unexpected CSV schema')
        for row in reader:
            need(None not in row and all(v is not None for v in row.values()), 'Malformed CSV row')
            yield row


def external_output(output, package_roots):
    original = output.expanduser().absolute()
    resolved = original.resolve()
    need(not original.exists() and not original.is_symlink(), 'Use a NEW external output directory')
    need(not any(resolved.is_relative_to(p.resolve()) for p in package_roots),
         'Text outputs must remain outside the reviewer package')
    need(not any((p / '.git').exists() for p in (resolved, *resolved.parents)),
         'Text outputs must remain outside all Git checkouts')
    
    need(not any(p.is_symlink() for p in (original, *original.parents)),
         'Output ancestors must not be symlinks')
    return resolved


def verify_observation_manifest(data_root):
    manifest = data_root / 'data/SHA256SUMS'
    need(manifest.is_file() and not manifest.is_symlink(), 'Observation hash manifest missing')
    seen = set()
    for line in manifest.read_text(encoding='ascii').splitlines():
        digest, filename = line.split(maxsplit=1)
        rel = Path(filename)
        need(not rel.is_absolute() and '..' not in rel.parts and filename not in seen,
             'Unsafe or duplicate observation manifest entry')
        seen.add(filename)
        path = data_root / rel
        need(path.is_file() and not path.is_symlink() and sha_file(path) == digest,
             'Observation input hash mismatch')
    needed = {'data/essays/item_index.csv', 'data/design/cells.csv', 'data/judgments/reversals.csv'}
    need(needed <= seen, 'Incomplete observation hash manifest')
    return seen


def read_design(data_root, expected=EXPECTED):
    frozen = verify_observation_manifest(data_root)
    index = read_index(data_root / 'data/essays/item_index.csv', expected=expected['target_essays'])
    items = {item: prompt for item, prompt in index.values()}
    cells, prompt_traits = {}, set()
    for row in rows(data_root / 'data/design/cells.csv', CELL_COLUMNS):
        need(all(re.fullmatch(r'[0-9]+', row[k]) for k in CELL_COLUMNS if k not in ('prompt_id', 'trait')),
             'Noninteger cell metadata')
        cell = {k: int(v) if k not in ('prompt_id', 'trait') else v for k, v in row.items()}
        n = cell['cell_id']
        need(n not in cells and cell['trait'] in TRAITS, 'Duplicate cell or invalid trait')
        key = (cell['prompt_id'], cell['trait'])
        need(key not in prompt_traits, 'Duplicate prompt-by-trait cell')
        prompt_traits.add(key)
        members = {item for item, prompt in items.items() if prompt == cell['prompt_id']}
        need(len(members) == cell['n_items'] >= 2 and
             cell['n_base'] == len(members) * (len(members)-1)//2 and
             cell['n_selectable'] + cell['n_heldout'] == cell['n_base'],
             'Cell graph counts or item coverage differ')
        cell['members'] = members
        cells[n] = cell
        need(f'data/judgments/cell_{n:03d}.csv' in frozen, 'Cell file absent from hash manifest')
    need(len(cells) == expected['cells'] and
         len(set(items.values())) == expected['prompts'] and
         prompt_traits == {(p, t) for p in items.values() for t in TRAITS},
         'Study cell, prompt, or six-trait coverage differs')
    return index, cells


def match_texts(index, train, test, contract, package_roots):
    need(train.resolve() != test.resolve(), 'Train and test must be separate original files')
    need(not any(p.resolve().is_relative_to(root.resolve()) for p in (train, test) for root in package_roots),
         'Keep original corpus files outside the reviewer package')
    matches, ids = {}, set()
    for label, path in (('train', train), ('test', test)):
        need(path.is_file() and not path.is_symlink() and
             sha_file(path) == contract['public_source_sha256'][label],
             'Original public corpus file hash differs; use the unmodified published CSVs')
        for row in rows(path, contract['public_csv_columns']):
            source_id = row['text_id_kaggle']
            need(source_id.strip() and source_id.strip() not in ids,
                 'Missing or duplicate public corpus identifier')
            ids.add(source_id.strip())
            key = public_essay_key(source_id)
            if key not in index:
                continue
            item, _ = index[key]
            text = row['full_text']
            need(text and text.strip() and item not in matches, 'Missing or duplicate matched full text')
            
            matches[item] = text
    need(len(matches) == len(index), 'Incomplete essay matching; check original public train/test versions')
    return matches


def pair_design(data_root, cells, expected=EXPECTED):
    reversals = defaultdict(list)
    for row in rows(data_root / 'data/judgments/reversals.csv', REV_COLUMNS):
        need(row['cell_id'].isdigit() and int(row['cell_id']) in cells, 'Unknown reversal cell')
        reversals[int(row['cell_id'])].append(row)
    totals = Counter()
    for n, cell in sorted(cells.items()):
        base, edges, counts = {}, set(), Counter()
        for row in rows(data_root / f'data/judgments/cell_{n:03d}.csv', BASE_COLUMNS):
            pair, first, second = row['pair_id'], row['first_id'], row['second_id']
            need(re.fullmatch(r'b[0-9]{6}', pair) and pair not in base, 'Missing or duplicate published pair ID')
            need(first in cell['members'] and second in cell['members'] and first != second,
                 'Unknown item or cross-prompt comparison')
            edge = tuple(sorted((first, second)))
            need(edge not in edges and row['partition'] in ('selectable', 'heldout') and
                 row['first_wins'] in ('0', '1'), 'Duplicate edge, invalid partition or archived winner')
            edges.add(edge)
            base[pair] = row
            counts['base'] += 1
            counts[row['partition']] += 1
        for field in ('base', 'selectable', 'heldout'):
            need(counts[field] == cell['n_' + field], 'Per-cell base/partition coverage differs')
        reversed_pairs = set()
        for row in reversals[n]:
            pair = row['base_pair_id']
            need(pair in base and pair not in reversed_pairs, 'Missing base pair or duplicate reversal')
            parent = base[pair]
            need(row['first_id'] == parent['second_id'] and row['second_id'] == parent['first_id'] and
                 row['first_wins'] in ('0', '1'), 'Reversal orientation or archived winner differs')
            reversed_pairs.add(pair)
        counts['reversal'] = len(reversed_pairs)
        need(counts['reversal'] == cell['n_reversal'], 'Per-cell reversal count differs')
        totals.update(counts)
        for pair, row in base.items():
            yield n, cell, pair, 'base', row['partition'], row['first_id'], row['second_id']
        for row in reversals[n]:
            pair = row['base_pair_id']
            yield n, cell, pair, 'reversal', base[pair]['partition'], row['first_id'], row['second_id']
    need(all(totals[k] == expected[k] for k in ('base', 'selectable', 'heldout', 'reversal')),
         'Complete 710,184-request or partition coverage differs')


def record_for(pair, texts, template, guidance):
    n, cell, pair_id, role, partition, first, second = pair
    prompt = render(template, cell['trait'], guidance[cell['trait']], texts[first], texts[second])
    return dict(request_id=f'review-c{n:03d}-{role}-{pair_id}', pair_id=pair_id, role=role,
                partition=partition, cell_id=n, trait=cell['trait'], prompt_id=cell['prompt_id'],
                ID1=first, text1=texts[first], ID2=second, text2=texts[second],
                input=prompt, prompt_sha256=sha_text(prompt))


def generate(data_root, train, test, output=None, limit=None, all_requests=False, chunk_size=1000):
    data_root = data_root.expanduser().resolve()
    package_roots = (ASSETS.parent, data_root.parent)
    need(chunk_size > 0 and (limit is None or limit > 0), 'Limit/chunk size must be positive')
    if output is not None:
        output = external_output(output, package_roots)
    template, guidance, assets, contract = resources()
    index, cells = read_design(data_root)
    texts = match_texts(index, train, test, contract, package_roots)
    
    count = sum(1 for _ in pair_design(data_root, cells))
    need(count == EXPECTED['base'] + EXPECTED['reversal'], 'Total request count differs')
    report = dict(validated_counts=EXPECTED, validated_request_count=count, matched_essays=len(texts),
                  provider_calls=0, historical_custom_ids_reconstructed=False)
    if output is None:
        return report
    output.mkdir(parents=True, mode=0o700)
    manifest = dict(format_version=1, **report, resources=assets, request_count=0, chunks=[],
                    kind='reconstructed historical inputs for optional NEW judgments',
                    new_request_ids_are_not_historical_custom_ids=True,
                    source_hashes={'train': sha_file(train), 'test': sha_file(test),
                                   'observations': sha_file(data_root / 'data/SHA256SUMS')})
    max_records = count if all_requests else limit
    need(max_records is not None, 'Choose --limit or --all to materialize inputs')
    handle, chunk, chunk_number = None, None, Counter()
    try:
        for pair in pair_design(data_root, cells):
            if manifest['request_count'] >= max_records:
                break
            n = pair[0]
            if chunk is None or chunk['cell_id'] != n or chunk['n_requests'] == chunk_size:
                if handle:
                    handle.close()
                    chunk['sha256'] = sha_file(output / chunk['file'])
                chunk_number[n] += 1
                filename = f'cell_{n:03d}_chunk_{chunk_number[n]:04d}.jsonl'
                chunk = dict(file=filename, cell_id=n, trait=pair[1]['trait'], n_requests=0)
                manifest['chunks'].append(chunk)
                handle = (output / filename).open('x', encoding='utf-8', newline='\n')
            record = record_for(pair, texts, template, guidance)
            handle.write(json.dumps(record, ensure_ascii=False, separators=(',', ':')) + '\n')
            chunk['n_requests'] += 1
            manifest['request_count'] += 1
        if handle:
            handle.close()
            chunk['sha256'] = sha_file(output / chunk['file'])
        need(manifest['request_count'] == min(max_records, count), 'Generated request count differs')
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    finally:
        if handle and not handle.closed:
            handle.close()
    return manifest


def synthetic_example(output):
    output = external_output(output, (ASSETS.parent,))
    template, guidance, assets, _ = resources()
    output.mkdir(parents=True, mode=0o700)
    filename = 'cell_001_chunk_0001.jsonl'
    cell = dict(trait='Cohesion', prompt_id='synthetic')
    texts = {'synthetic_1': 'SYNTHETIC SAMPLE ONE.', 'synthetic_2': 'SYNTHETIC SAMPLE TWO.'}
    records = [record_for((1, cell, 'b000001', role, 'selectable', first, second), texts, template, guidance)
               for role, first, second in [('base', 'synthetic_1', 'synthetic_2'),
                                            ('reversal', 'synthetic_2', 'synthetic_1')]]
    (output / filename).write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in records), encoding='utf-8')
    manifest = dict(format_version=1, kind='synthetic example; no original corpus text',
                    provider_calls=0, request_count=2, resources=assets,
                    historical_custom_ids_reconstructed=False,
                    new_request_ids_are_not_historical_custom_ids=True,
                    chunks=[dict(file=filename, cell_id=1, trait='Cohesion', n_requests=2,
                                 sha256=sha_file(output / filename))])
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, default=Path('observations'))
    parser.add_argument('--train', type=Path)
    parser.add_argument('--test', type=Path)
    parser.add_argument('--output', type=Path, help='NEW directory outside the package and every Git checkout')
    parser.add_argument('--chunk-size', type=int, default=1000)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true', help='Read-only complete input validation')
    mode.add_argument('--limit', type=int, help='Small offline materialization after full preflight')
    mode.add_argument('--all', action='store_true', help='Generate all 710,184 inputs offline')
    mode.add_argument('--synthetic-example', action='store_true', help='Local example without ELLIPSE or credentials')
    args = parser.parse_args()
    need((args.check and args.output is None) or (not args.check and args.output is not None),
         '--check has no output; generation requires --output')
    if args.synthetic_example:
        need(args.train is None and args.test is None, 'Synthetic mode needs no source files')
        report = synthetic_example(args.output)
    else:
        need(args.train is not None and args.test is not None, 'Provide original train and test CSVs')
        report = generate(args.data_root, args.train, args.test, args.output, args.limit,
                          args.all, args.chunk_size)
    print('PASS: provider-free input validation; requests:',
          report.get('request_count', report.get('validated_request_count')))
    if args.output:
        print('Text-bearing files are local only. Keep them outside the reviewer repository.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, UnicodeError, csv.Error, KeyError, json.JSONDecodeError):
        
        raise SystemExit('Input preparation failed. Check schemas, hashes, counts and external-only NEW paths.')
