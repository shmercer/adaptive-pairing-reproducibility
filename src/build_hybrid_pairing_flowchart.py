#!/usr/bin/env python3
'Draw Figure 1, which explains the hybrid pairing method. Check that arrows and labels fit within the diagram.'
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch, PathPatch, Polygon, Rectangle
from matplotlib.path import Path as MplPath

EDGE = '#222222'
HEADER = '#E9E9E9'


@dataclass
class Node:
    x: float
    y: float
    w: float
    h: float
    patch: object
    texts: list = field(default_factory=list)

    def port(self, side: str) -> tuple[float, float]:
        return {
            'left': (self.x, self.y + self.h / 2),
            'right': (self.x + self.w, self.y + self.h / 2),
            'top': (self.x + self.w / 2, self.y + self.h),
            'bottom': (self.x + self.w / 2, self.y),
        }[side]


class Diagram:
    def __init__(self):
        self.fig = plt.figure(figsize=(7.35, 7.0), dpi=160)
        self.ax = self.fig.add_axes([0.018, 0.025, 0.964, 0.963])
        self.ax.set(xlim=(0, 1), ylim=(0, 1))
        self.ax.axis('off')
        self.nodes: dict[str, Node] = {}
        self.texts = []
        self.arrows = []

    def text(self, x, y, text, size=7.6, weight='normal', style='normal', ha='center'):
        artist = self.ax.text(x, y, text, transform=self.ax.transAxes,
                              ha=ha, va='center', fontsize=size, color=EDGE,
                              fontweight=weight, fontstyle=style, linespacing=1.16)
        self.texts.append(artist)
        return artist

    def title(self, y, text):
        self.text(0.045, y, text, size=10.3, weight='bold', ha='left')

    def divider(self, y):
        self.ax.plot([0.045, 0.970], [y, y], color=EDGE, lw=0.55,
                     transform=self.ax.transAxes)

    def box(self, name, x, y, w, h, title, body, title_size=8.2, body_size=7.0):
        
        patch = FancyBboxPatch((x, y), w, h, transform=self.ax.transAxes,
                              boxstyle='round,pad=0,rounding_size=0.009',
                              facecolor='white', edgecolor=EDGE, linewidth=0.85)
        self.ax.add_patch(patch)
        labels = [self.text(x + w/2, y + h*0.70, title, title_size, 'semibold'),
                  self.text(x + w/2, y + h*0.30, body, body_size)]
        self.nodes[name] = Node(x, y, w, h, patch, labels)

    def stage(self, name, x, title, quota, body, role):
        y, w, h = 0.720, 0.205, 0.125
        patch = FancyBboxPatch((x, y), w, h, transform=self.ax.transAxes,
                              boxstyle='round,pad=0,rounding_size=0.008',
                              facecolor='white', edgecolor=EDGE, linewidth=0.85)
        self.ax.add_patch(patch)
        band = Rectangle((x + 0.004, y + h*0.67), w - 0.008, h*0.29,
                         transform=self.ax.transAxes, facecolor=HEADER, edgecolor='none')
        self.ax.add_patch(band)
        labels = [self.text(x + 0.012, y + h*0.815, title, 8.7, 'bold', ha='left'),
                  self.text(x + w - 0.012, y + h*0.815, quota, 7.5, ha='right'),
                  self.text(x + w/2, y + h*0.32, body, 7.0)]
        self.text(x + w/2, 0.862, role, 7.2, style='italic')
        self.nodes[name] = Node(x, y, w, h, patch, labels)

    def diamond(self, name, cx, cy, w, h, text):
        vertices = [(cx, cy + h/2), (cx + w/2, cy),
                    (cx, cy - h/2), (cx - w/2, cy)]
        patch = Polygon(vertices, closed=True, transform=self.ax.transAxes,
                        facecolor='white', edgecolor=EDGE, linewidth=0.85)
        self.ax.add_patch(patch)
        label = self.text(cx, cy, text, 8.0, 'semibold')
        self.nodes[name] = Node(cx - w/2, cy - h/2, w, h, patch, [label])

    def arrow(self, source, source_side, target, target_side, via=()):
        start = self.nodes[source].port(source_side)
        end = self.nodes[target].port(target_side)
        points = np.asarray([start, *via, end], dtype=float)
        display = self.ax.transAxes.transform(points)
        direction = display[-1] - display[-2]
        length = np.linalg.norm(direction)
        if length <= 0:
            raise ValueError('Arrow must have a nonzero final segment.')
        unit = direction / length
        normal = np.array([-unit[1], unit[0]])
        head_length = min(4.3 * self.fig.dpi / 72, length * 0.75)
        half_width = 1.8 * self.fig.dpi / 72
        base = display[-1] - head_length * unit
        triangle = np.array([display[-1], base + half_width*normal, base - half_width*normal])
        
        shaft = points.copy()
        shaft[-1] = self.ax.transAxes.inverted().transform(base)
        line = PathPatch(MplPath(shaft, [MplPath.MOVETO] + [MplPath.LINETO]*(len(shaft)-1)),
                         transform=self.ax.transAxes, fill=False, edgecolor=EDGE,
                         lw=0.82, capstyle='butt', joinstyle='round', zorder=4)
        head = Polygon(self.ax.transAxes.inverted().transform(triangle), closed=True,
                       transform=self.ax.transAxes, facecolor=EDGE, edgecolor='none', zorder=4)
        self.ax.add_patch(line)
        self.ax.add_patch(head)
        self.arrows.append((source, target, points, line, head))

    def validate(self):
        self.fig.canvas.draw()
        renderer = self.fig.canvas.get_renderer()
        issues = []
        
        for name, node in self.nodes.items():
            outline = node.patch.get_path().transformed(node.patch.get_transform())
            for text in node.texts:
                bounds = text.get_window_extent(renderer).padded(1.7)
                corners = np.array([[bounds.x0, bounds.y0], [bounds.x0, bounds.y1],
                                    [bounds.x1, bounds.y0], [bounds.x1, bounds.y1]])
                if not outline.contains_points(corners).all():
                    issues.append(f'Text too close to {name} outline: {text.get_text()}')
        extents = [t.get_window_extent(renderer) for t in self.texts]
        for i, a in enumerate(extents):
            if not self.fig.bbox.contains(a.x0, a.y0) or not self.fig.bbox.contains(a.x1, a.y1):
                issues.append(f'Text outside canvas: {self.texts[i].get_text()}')
            for j in range(i):
                if a.overlaps(extents[j]):
                    issues.append(f'Text overlap: {self.texts[i].get_text()} / {self.texts[j].get_text()}')
        max_error = 0.0
        for source, target, points, line, head in self.arrows:
            for name, point in [(source, points[0]), (target, points[-1])]:
                outline = self.nodes[name].patch.get_path().transformed(self.nodes[name].patch.get_transform())
                boundary = outline.to_polygons()[0]
                p = self.ax.transAxes.transform(point)
                a, b = boundary[:-1], boundary[1:]
                ab = b - a
                t = np.clip(np.sum((p-a)*ab, axis=1)/np.maximum(np.sum(ab*ab, axis=1), 1e-20), 0, 1)
                distance = float(np.min(np.linalg.norm(p - (a + t[:, None]*ab), axis=1)))
                max_error = max(max_error, distance)
                if distance > 0.01:
                    issues.append(f'Arrow endpoint off {name} boundary: {distance:.4f} px')
            
            for patch in (line, head):
                path = patch.get_path().transformed(patch.get_transform())
                for label, bounds in zip(self.texts, extents):
                    if path.intersects_bbox(bounds.padded(0.7), filled=patch is head):
                        issues.append(f'Arrow overlaps text: {label.get_text()}')
        centers = [self.nodes[n].y + self.nodes[n].h/2 for n in ('NO', 'DECISION', 'YES')]
        if max(centers) - min(centers) > 1e-12:
            issues.append('Panel C centers do not align.')
        report = {'nodes': len(self.nodes), 'arrows': len(self.arrows),
                  'max_arrow_boundary_error_px': max_error,
                  'panel_c_centers': centers, 'issues': issues}
        if issues:
            raise RuntimeError('\n'.join(issues))
        return report


def build_figure(out_dir: Path):
    d = Diagram()

    
    d.title(0.965, 'A. Round composition')
    d.text(
        0.5075, 0.925,
        r'Each round targets approximately $N/4$ new comparisons using the current TrueSkill ranking ($N$ = essays in the cell).',
        7.25
    )
    d.text(
        0.5075, 0.892,
        'Initial stage quotas (% of pair selections within the round)',
        7.75, 'semibold'
    )

    specs = [
        ('ANCHOR', 0.045, '30%',
         'One anchor\n+ one non-anchor',
         'Linkage across the scale'),
        ('LONG', 0.285, '10%',
         'Non-anchor pairs\nfrom distant strata',
         'Exploration'),
        ('MID', 0.525, '10%',
         'Non-anchor pairs\n2-4 strata apart',
         'Exploration'),
        ('LOCAL', 0.765, '50%',
         'Non-anchor pairs in the\nsame or adjacent strata',
         'Local refinement'),
    ]

    for name, x, quota, body, role in specs:
        d.stage(name, x, name, quota, body, role)

    for a, b in [('ANCHOR', 'LONG'), ('LONG', 'MID'), ('MID', 'LOCAL')]:
        d.arrow(a, 'right', b, 'left')

    d.divider(0.682)

    
    d.title(0.650, 'B. Pair selection within each stage')

    d.box(
        'POOL', 0.065, 0.505, 0.255, 0.112,
        '1. Form eligible-pair pool',
        'Unused pairs allowed by the stage,\n'
        'with limited repeated essay use\n'
        'within the round',
        8.05, 6.65
    )

    d.box(
        'SELECT', 0.373, 0.505, 0.255, 0.112,
        '2. Select one pair',
        'Prioritize less-compared essays\n'
        'or favor high TrueSkill ambiguity',
        8.2, 6.9
    )

    d.box(
        'UPDATE', 0.681, 0.505, 0.255, 0.112,
        '3. Reveal and update',
        'Reveal stored judgment;\nupdate TrueSkill',
        8.1, 7.0
    )

    d.arrow('POOL', 'right', 'SELECT', 'left')
    d.arrow('SELECT', 'right', 'UPDATE', 'left')
    d.arrow(
        'UPDATE', 'bottom', 'POOL', 'bottom',
        via=((0.8085, 0.394), (0.1925, 0.394))
    )

    d.text(
        0.5005, 0.463,
        'Each selection counts as one pair toward the current stage quota.',
        7.05
    )
    d.text(
        0.5005, 0.421,
        'Repeat until the stage quota is filled.',
        7.3
    )

    d.divider(0.356)

    
    d.title(0.325, 'C. Periodic routing check')
    d.text(
        0.500, 0.282,
        'At scheduled Bayesian BT refits, evaluate if:',
        7.75
    )
    d.text(
        0.500, 0.249,
        r'EAP reliability $\geq .80$ and TrueSkill-BT rank agreement $\geq .90$',
        7.6, 'semibold'
    )

    cy, h = 0.151, 0.136

    d.box(
        'NO', 0.045, cy-h/2, 0.255, h,
        'Keep base routing',
        'Scheduled quotas\nremain unchanged',
        8.3, 7.2
    )

    d.diamond(
        'DECISION', 0.500, cy, 0.240, 0.120,
        'Both criteria\nmet?'
    )

    d.box(
        'YES', 0.700, cy-h/2, 0.270, h,
        'Shift toward local refinement',
        'Reduce within-stage exploration;\n'
        'reduce the long-stage quota;\n'
        'reallocate mainly to Local',
        7.9, 6.85
    )

    d.arrow('DECISION', 'left', 'NO', 'right')
    d.arrow('DECISION', 'right', 'YES', 'left')
    d.text(0.340, cy+0.017, 'No', 7.5)
    d.text(0.660, cy+0.017, 'Yes', 7.5)
    d.text(
        0.5075, 0.043,
        'The selected routing applies to subsequent hybrid rounds.',
        7.3
    )

    report = d.validate()
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = out_dir / 'figure_hybrid_pairing_flowchart'
    plt.rcParams['svg.fonttype'] = 'none'
    plt.rcParams['pdf.fonttype'] = 42
    paths = [stem.with_suffix(ext) for ext in ('.pdf', '.svg', '.png')]

    for path in paths:
        d.fig.savefig(path, dpi=300, facecolor='white')

    (out_dir / 'layout_checks.json').write_text(
        json.dumps(report, indent=2) + '\n',
        encoding='utf-8'
    )
    plt.close(d.fig)
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', type=Path, default=Path("output/figures"))
    args = parser.parse_args()
    for path in build_figure(args.out_dir.resolve()):
        print(path)


if __name__ == '__main__':
    main()
