"""Version/layout compatibility guard.

The field numbers in Edge's internal protobuf are not a public API.  We only
claim support for layouts that were actually decoded on a real machine.  A
new Edge version gets support by adding one row to KNOWN_LAYOUTS after running
``scan`` and checking the structure -- never by silently guessing.

Layout is identified by *both* the Edge major version and a structural
signature, so an unknown version with an unchanged structure is reported as
"shape-compatible", and a changed structure is refused.
"""

from __future__ import annotations

from . import workspace_proto as wp

# Structural signature that must be present in a workspace record.
REQUIRED_OUTER = {1: 0, 3: 2}
REQUIRED_DETAILS = {1: 2, 2: 0, 3: 0}  # field number -> wire type

KNOWN_LAYOUTS = {
    'edge-158-layout-1': {
        'edge_major': ['158'],
        'outer': REQUIRED_OUTER,
        'details_field': 4,
        'tab_details_field': 5,
        'name_field': 1,
        'color_field': 2,
        'emoji_field': 9,
        'details': REQUIRED_DETAILS,
        'note': 'decoded byte-by-byte on Edge 158.0.4370.45; details.9 is a UTF-8 string',
    },
}

DEFAULT_LAYOUT = KNOWN_LAYOUTS['edge-158-layout-1']


def _major(version: str) -> str:
    return (version or '').split('.')[0]


def signature_ok(record, spec) -> tuple:
    """Return (ok, reasons) for a decoded WorkspaceRecord."""
    reasons = []
    outer_types = {f: w for f, w, _v in record.outer}
    for field, wire in spec['outer'].items():
        if outer_types.get(field) != wire:
            reasons.append('outer.%d wire type %s != %s' % (field, outer_types.get(field), wire))
    detail_types = {f: w for f, w, _v in record.details}
    for field, wire in spec['details'].items():
        if detail_types.get(field) != wire:
            reasons.append('details.%d wire type %s != %s' % (field, detail_types.get(field), wire))
    if spec['emoji_field'] not in detail_types and 9 in detail_types:
        reasons.append('emoji field moved from %d to 9' % spec['emoji_field'])
    return (not reasons), reasons


def detect(version: str, records) -> dict:
    """Pick a layout and explain the confidence.  ``records`` is a list of values."""
    major = _major(version)
    candidates = []
    for name, spec in KNOWN_LAYOUTS.items():
        if major in spec['edge_major']:
            candidates.append((name, spec, 'version+shape'))
    if not candidates:
        candidates = [(name, spec, 'shape-only') for name, spec in KNOWN_LAYOUTS.items()]

    if not records:
        return {'id': None, 'status': 'unknown', 'version': version,
                'reasons': ['no workspace record available to validate']}

    for name, spec, source in candidates:
        reasons = []
        checked = 0
        for raw in records[:20]:
            try:
                rec = wp.WorkspaceRecord(raw, details_field=spec['details_field'],
                                         emoji_field=spec['emoji_field'],
                                         name_field=spec['name_field'],
                                         color_field=spec['color_field'])
            except Exception as exc:
                reasons.append('record parse failed: %s' % exc)
                continue
            _ok, why = signature_ok(rec, spec)
            checked += 1
            reasons.extend(why)
        if checked and not reasons:
            status = 'known' if source == 'version+shape' else 'shape-compatible'
            return {'id': name, 'status': status, 'version': version,
                    'source': source, 'reasons': [], 'spec': spec}
    return {'id': None, 'status': 'unknown', 'version': version,
            'reasons': reasons or ['structure does not match any known layout']}


def require_writable(layout: dict, allow_unknown: bool = False):
    if layout['status'] in ('known', 'shape-compatible'):
        return
    if allow_unknown:
        return
    raise RuntimeError(
        'unsupported Edge/layout (%s %s); run `scan` and update layout.py, '
        'or pass --allow-unknown explicitly: %s'
        % (layout.get('version'), layout.get('status'), '; '.join(layout.get('reasons', [])))
    )
