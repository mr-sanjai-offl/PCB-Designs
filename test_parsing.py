#!/usr/bin/env python3
"""
Test script to verify KiCad parsing logic works with the actual project files.
Run this from S:\pcb-designs directory.
"""

import os
import sys
import sexpdata
from sexpdata import Symbol
import json
import re
from pathlib import Path

def parse_sexp(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    return sexpdata.loads(content)

def extract_components(sch_data):
    """Extract component info from schematic S-expression."""
    components = []

    def walk(obj):
        if isinstance(obj, list) and obj:
            if isinstance(obj[0], Symbol) and obj[0].value() == 'symbol':
                comp = {}
                for item in obj[1:]:
                    if isinstance(item, list) and item:
                        if isinstance(item[0], Symbol):
                            key = item[0].value()
                            if key == 'lib_id':
                                comp['lib_id'] = str(item[1]) if len(item) > 1 else ''
                            elif key == 'property':
                                if len(item) >= 3:
                                    prop_name = str(item[1]).strip('"')
                                    prop_value = str(item[2]).strip('"')
                                    if prop_name == 'Reference':
                                        comp['reference'] = prop_value
                                    elif prop_name == 'Value':
                                        comp['value'] = prop_value
                                    elif prop_name == 'Footprint':
                                        comp['footprint'] = prop_value
                                    elif prop_name == 'Description':
                                        comp['description'] = prop_value
                # Only keep components with proper reference designators (e.g., R1, C1, D1, J1)
                # Filter out library symbols which have references like "R", "C", "D", "J" without numbers
                ref = comp.get('reference', '')
                if ref and re.match(r'^[A-Z]+\d+$', ref):
                    components.append(comp)
            else:
                for item in obj:
                    walk(item)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(sch_data)
    return components

def parse_pcb_dimensions(pcb_data):
    """Extract board outline from PCB S-expression."""
    edge_cuts = []

    def walk(obj):
        if isinstance(obj, list) and obj:
            if isinstance(obj[0], Symbol):
                key = obj[0].value()
                # KiCad uses gr_rect for rectangles, gr_circle for arcs, gr_line for lines, gr_arc for arcs
                if key in ('gr_line', 'gr_arc', 'gr_rect', 'gr_circle', 'gr_poly'):
                    layer = None
                    for item in obj[1:]:
                        if isinstance(item, list) and item and isinstance(item[0], Symbol):
                            if item[0].value() == 'layer':
                                layer = str(item[1]).strip('"')
                                break
                    if layer == 'Edge.Cuts':
                        edge_cuts.append(obj)
            for item in obj:
                if isinstance(item, list):
                    walk(item)

    walk(pcb_data)

    # Calculate bounding box from edge cuts
    min_x = min_y = float('inf')
    max_x = max_y = float('-inf')

    for item in edge_cuts:
        if not isinstance(item[0], Symbol):
            continue
        key = item[0].value()

        if key == 'gr_line':
            start = end = None
            for prop in item[1:]:
                if isinstance(prop, list) and prop and isinstance(prop[0], Symbol):
                    if prop[0].value() == 'start':
                        start = (float(prop[1]), float(prop[2]))
                    elif prop[0].value() == 'end':
                        end = (float(prop[1]), float(prop[2]))
            if start:
                min_x = min(min_x, start[0])
                min_y = min(min_y, start[1])
                max_x = max(max_x, start[0])
                max_y = max(max_y, start[1])
            if end:
                min_x = min(min_x, end[0])
                min_y = min(min_y, end[1])
                max_x = max(max_x, end[0])
                max_y = max(max_y, end[1])

        elif key == 'gr_arc':
            # Arc: center + radius
            center = None
            radius = None
            for prop in item[1:]:
                if isinstance(prop, list) and prop and isinstance(prop[0], Symbol):
                    if prop[0].value() == 'center':
                        center = (float(prop[1]), float(prop[2]))
                    elif prop[0].value() == 'radius':
                        radius = float(prop[1])
            if center and radius:
                cx, cy = center
                min_x = min(min_x, cx - radius)
                min_y = min(min_y, cy - radius)
                max_x = max(max_x, cx + radius)
                max_y = max(max_y, cy + radius)

        elif key == 'gr_rect':
            # Rectangle: start and end corners
            start = end = None
            for prop in item[1:]:
                if isinstance(prop, list) and prop and isinstance(prop[0], Symbol):
                    if prop[0].value() == 'start':
                        start = (float(prop[1]), float(prop[2]))
                    elif prop[0].value() == 'end':
                        end = (float(prop[1]), float(prop[2]))
            if start:
                min_x = min(min_x, start[0])
                min_y = min(min_y, start[1])
                max_x = max(max_x, start[0])
                max_y = max(max_y, start[1])
            if end:
                min_x = min(min_x, end[0])
                min_y = min(min_y, end[1])
                max_x = max(max_x, end[0])
                max_y = max(max_y, end[1])

        elif key == 'gr_circle':
            # Circle: center and end point (on circumference)
            center = end = None
            for prop in item[1:]:
                if isinstance(prop, list) and prop and isinstance(prop[0], Symbol):
                    if prop[0].value() == 'center':
                        center = (float(prop[1]), float(prop[2]))
                    elif prop[0].value() == 'end':
                        end = (float(prop[1]), float(prop[2]))
            if center and end:
                cx, cy = center
                ex, ey = end
                # Calculate radius from center to end point
                radius = ((ex - cx) ** 2 + (ey - cy) ** 2) ** 0.5
                min_x = min(min_x, cx - radius)
                min_y = min(min_y, cy - radius)
                max_x = max(max_x, cx + radius)
                max_y = max(max_y, cy + radius)

        elif key == 'gr_poly':
            # Polygon: list of points
            points = []
            for prop in item[1:]:
                if isinstance(prop, list) and prop and isinstance(prop[0], Symbol):
                    if prop[0].value() == 'pts':
                        # pts contains list of (xy x y) points
                        for pt in prop[1:]:
                            if isinstance(pt, list) and pt and isinstance(pt[0], Symbol) and pt[0].value() == 'xy':
                                x = float(pt[1])
                                y = float(pt[2])
                                points.append((x, y))
            for px, py in points:
                min_x = min(min_x, px)
                min_y = min(min_y, py)
                max_x = max(max_x, px)
                max_y = max(max_y, py)

    if min_x == float('inf'):
        return {"width_mm": 0, "height_mm": 0, "area_mm2": 0}

    width = max_x - min_x
    height = max_y - min_y
    return {
        "width_mm": round(width, 2),
        "height_mm": round(height, 2),
        "area_mm2": round(width * height, 2),
        "min_x": round(min_x, 2),
        "min_y": round(min_y, 2),
        "max_x": round(max_x, 2),
        "max_y": round(max_y, 2)
    }

def parse_project_info(proj_data):
    """Extract project metadata from .kicad_pro JSON."""
    info = {}
    # Version
    info['version'] = proj_data.get('meta', {}).get('version', 'unknown')
    # Board thickness
    board = proj_data.get('board', {})
    design_settings = board.get('design_settings', {})
    defaults = design_settings.get('defaults', {})
    # Thickness might be in general section
    general = board.get('general', {})
    info['thickness_mm'] = general.get('thickness', 1.6)
    # Layer count from layer_presets or layer_pairs
    layer_presets = board.get('layer_presets', [])
    if layer_presets:
        # Count copper layers from first preset
        copper_layers = layer_presets[0].get('copper_layers', [])
        info['copper_layers'] = len(copper_layers)
    else:
        info['copper_layers'] = 2  # Default
    return info

def get_footprint_description(footprint):
    """Map footprint to human-readable description."""
    footprint_lower = footprint.lower()
    desc_map = {
        'screw_terminal': 'Screw Terminal Block',
        'terminal_block': 'Terminal Block',
        'diode_tht': 'Through-Hole Diode',
        'd_a-405': 'Axial Diode (A-405 package)',
        'led_tht': 'Through-Hole LED',
        'led_d5': '5mm LED',
        'capacitor_tht': 'Through-Hole Capacitor',
        'cp_radial': 'Radial Electrolytic Capacitor',
        'resistor_tht': 'Through-Hole Resistor',
        'r_axial': 'Axial Resistor',
        'din0204': 'DIN0204 Axial Resistor',
    }
    for key, desc in desc_map.items():
        if key in footprint_lower:
            return desc
    return footprint.replace('_', ' ').replace(':', ' - ')

def format_dimensions(dim):
    if dim['width_mm'] > 0 and dim['height_mm'] > 0:
        return f"{dim['width_mm']} \u00d7 {dim['height_mm']} mm"
    return "Unknown"

# Main test
PROJECT_DIR = "AC_to_DC_Converter"
KICAD_PRO = os.path.join(PROJECT_DIR, "ac_to_dc.kicad_pro")
KICAD_SCH = os.path.join(PROJECT_DIR, "ac_to_dc.kicad_sch")
KICAD_PCB = os.path.join(PROJECT_DIR, "ac_to_dc.kicad_pcb")

print(f"Testing parsing for: {PROJECT_DIR}")
print("=" * 60)

# Test schematic parsing
print("\n1. Parsing Schematic (.kicad_sch)...")
if os.path.exists(KICAD_SCH):
    sch_data = parse_sexp(KICAD_SCH)
    components = extract_components(sch_data)
    print(f"   Found {len(components)} components:")
    for comp in sorted(components, key=lambda x: x.get('reference', '')):
        ref = comp.get('reference', '')
        val = comp.get('value', '')
        fp = comp.get('footprint', '')
        desc = comp.get('description') or get_footprint_description(fp)
        print(f"     {ref}: {val} | {fp} | {desc}")
else:
    print(f"   ERROR: {KICAD_SCH} not found")

# Test PCB parsing
print("\n2. Parsing PCB (.kicad_pcb)...")
if os.path.exists(KICAD_PCB):
    pcb_data = parse_sexp(KICAD_PCB)
    dimensions = parse_pcb_dimensions(pcb_data)
    print(f"   Board dimensions: {format_dimensions(dimensions)}")
    print(f"   Area: {dimensions.get('area_mm2', 0):.1f} mm^2")
    print(f"   Bounds: ({dimensions['min_x']}, {dimensions['min_y']}) to ({dimensions['max_x']}, {dimensions['max_y']})")
else:
    print(f"   ERROR: {KICAD_PCB} not found")

# Test project file parsing
print("\n3. Parsing Project (.kicad_pro)...")
if os.path.exists(KICAD_PRO):
    with open(KICAD_PRO, 'r') as f:
        proj_data = json.load(f)
    proj_info = parse_project_info(proj_data)
    print(f"   KiCad project version: {proj_info['version']}")
    print(f"   Board thickness: {proj_info['thickness_mm']} mm")
    print(f"   Copper layers: {proj_info['copper_layers']}")
else:
    print(f"   ERROR: {KICAD_PRO} not found")

print("\n" + "=" * 60)
print("Test complete!")