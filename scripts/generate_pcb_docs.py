#!/usr/bin/env python3
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import sexpdata
from sexpdata import Symbol

ROOT = Path(__file__).resolve().parents[1]
IGNORE_DIRS = {".git", ".history", ".github"}


def sval(value):
    if isinstance(value, Symbol):
        return value.value()
    if isinstance(value, str):
        return value.strip('"')
    return str(value).strip('"')


def walk(obj):
    if isinstance(obj, list):
        yield obj
        for item in obj:
            yield from walk(item)


def project_dirs(root: Path):
    projects = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if child.name in IGNORE_DIRS:
            continue
        if any(child.rglob("*.kicad_pro")) or any(child.rglob("*.kicad_sch")) or any(child.rglob("*.kicad_pcb")):
            projects.append(child)
    return projects


def find_kicad_file(project: Path, suffix: str):
    matches = sorted(
        p for p in project.iterdir()
        if p.is_file() and p.suffix.lower() == suffix and ".history" not in p.parts
    )
    if matches:
        return matches[0]
    for p in sorted(project.rglob(f"*{suffix}")):
        if ".history" not in p.parts:
            return p
    return None


def extract_components(sch_path: Path):
    if not sch_path or not sch_path.exists():
        return []

    components = {}
    data = sexpdata.loads(sch_path.read_text(encoding="utf-8"))

    for item in walk(data):
        if not item or not isinstance(item[0], Symbol):
            continue
        if item[0].value() != "symbol":
            continue

        props = {}
        for child in item[1:]:
            if isinstance(child, list) and child and isinstance(child[0], Symbol):
                tag = child[0].value()
                if tag == "property" and len(child) >= 3:
                    props[sval(child[1])] = sval(child[2])

        ref = props.get("Reference", "")
        if ref and re.fullmatch(r"[A-Za-z]+[0-9]+", ref):
            components[ref] = {
                "reference": ref,
                "value": props.get("Value", ""),
                "footprint": props.get("Footprint", ""),
                "description": props.get("Description", ""),
            }

    return sorted(components.values(), key=lambda item: item["reference"])


def extract_board_dimensions(pcb_path: Path):
    result = {"width": 0.0, "height": 0.0, "area": 0.0, "thickness": 1.6, "layers": 2}
    if not pcb_path or not pcb_path.exists():
        return result

    data = sexpdata.loads(pcb_path.read_text(encoding="utf-8"))
    min_x = float("inf")
    min_y = float("inf")
    max_x = float("-inf")
    max_y = float("-inf")
    copper_layers = set()

    def add_xy(x, y):
        nonlocal min_x, min_y, max_x, max_y
        try:
            x_value = float(x)
            y_value = float(y)
        except (TypeError, ValueError):
            return
        min_x = min(min_x, x_value)
        min_y = min(min_y, y_value)
        max_x = max(max_x, x_value)
        max_y = max(max_y, y_value)

    for item in walk(data):
        if not item or not isinstance(item[0], Symbol):
            continue
        key = item[0].value()

        if key == "general":
            for child in item[1:]:
                if isinstance(child, list) and len(child) >= 2 and isinstance(child[0], Symbol) and child[0].value() == "thickness":
                    try:
                        result["thickness"] = float(child[1])
                    except (TypeError, ValueError):
                        pass

        elif key == "layers":
            for child in item[1:]:
                if isinstance(child, list) and len(child) >= 3:
                    name = sval(child[1])
                    layer_type = sval(child[2])
                    if name in {"F.Cu", "B.Cu"} or re.fullmatch(r"In\d+\.Cu", name):
                        if layer_type in {"signal", "power", "jumper"}:
                            copper_layers.add(name)

        elif key in {"gr_line", "gr_arc", "gr_rect", "gr_poly", "gr_circle"}:
            layer = None
            for child in item[1:]:
                if isinstance(child, list) and len(child) >= 2 and isinstance(child[0], Symbol) and child[0].value() == "layer":
                    layer = sval(child[1])
                    break
            if layer != "Edge.Cuts":
                continue

            for child in item[1:]:
                if not (isinstance(child, list) and child):
                    continue
                if not isinstance(child[0], Symbol):
                    continue
                k = child[0].value()

                if k in {"start", "end", "mid", "center"} and len(child) >= 3:
                    add_xy(child[1], child[2])
                elif k == "pts":
                    for pt in child[1:]:
                        if isinstance(pt, list) and len(pt) >= 3 and isinstance(pt[0], Symbol) and pt[0].value() == "xy":
                            add_xy(pt[1], pt[2])

    if min_x != float("inf"):
        result["width"] = round(max_x - min_x, 2)
        result["height"] = round(max_y - min_y, 2)
        result["area"] = round(result["width"] * result["height"], 2)

    if copper_layers:
        result["layers"] = len(copper_layers)

    return result


def clean_value(value):
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def generate_project_readme(project: Path):
    pro = find_kicad_file(project, ".kicad_pro")
    sch = find_kicad_file(project, ".kicad_sch")
    pcb = find_kicad_file(project, ".kicad_pcb")
    components = extract_components(sch)
    board = extract_board_dimensions(pcb)
    render_dir = project / "renders"
    renders = []
    if render_dir.exists():
        renders = sorted(
            p for p in render_dir.iterdir()
            if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}
        )

    title = project.name.replace("_", " ").replace("-", " ").title() or "KiCad PCB Project"
    description = f"KiCad PCB design project for {title}."

    lines = [
        f"# {title}",
        "",
        "## Description",
        "",
        description,
        "",
        "## Board Specifications",
        "",
        "| Specification | Details |",
        "|---|---|",
        f"| Dimensions | {board['width']} × {board['height']} mm |",
        f"| Area | {board['area']} mm² |",
        f"| Thickness | {board['thickness']} mm |",
        f"| Copper Layers | {board['layers']} |",
        "",
        f"## Components ({len(components)})",
        "",
        "| Reference | Value | Footprint | Description |",
        "|---|---|---|---|",
    ]

    if components:
        for item in components:
            lines.append(
                f"| {clean_value(item['reference'])} | {clean_value(item['value'])} | "
                f"{clean_value(item['footprint']) or '—'} | {clean_value(item['description']) or '—'} |"
            )
    else:
        lines.append("| — | No schematic components detected | — | — |")

    lines += ["", "## PCB Renders", ""]
    if renders:
        for render in renders:
            rel = render.relative_to(project).as_posix()
            if render.suffix.lower() == ".gif":
                lines += ["### Rotating 3D View", f"![Rotating PCB](./{rel})", ""]
            elif "top" in render.name.lower():
                lines += ["### Top View", f"![Top View](./{rel})", ""]
            elif "bottom" in render.name.lower():
                lines += ["### Bottom View", f"![Bottom View](./{rel})", ""]
            else:
                lines += [f"### {render.stem}", f"![{render.stem}](./{rel})", ""]
    else:
        lines += ["_No PCB renders were generated yet. GitHub Actions will create PNG and GIF renders for this project on push._", ""]

    lines += ["## KiCad Project Files", ""]
    for item in sorted(project.iterdir()):
        if item.is_file() and item.suffix.lower() in {".kicad_pro", ".kicad_sch", ".kicad_pcb", ".kicad_prl"}:
            lines.append(f"- `{item.name}`")

    lines += ["", "---", "", "_This README is automatically generated and maintained by the PCB documentation workflow._"]
    readme_path = project / "README.md"
    readme_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "title": title,
        "description": description,
        "project": project.name,
        "components": len(components),
        "dimensions": f"{board['width']} × {board['height']} mm",
        "renders": [p.name for p in renders],
    }


def write_root_readme(projects):
    lines = [
        "# PCB Designs",
        "",
        "A collection of completed KiCad PCB design projects with automatically generated documentation and PCB renders.",
        "",
        "## Projects",
        "",
        "| Project Title | Description |",
        "|---|---|",
    ]

    sorted_projects = sorted(projects, key=lambda item: item["title"].lower())
    for project in sorted_projects:
        lines.append(f"| [{project['title']}]({project['link']}) | {project['description'].replace('|', '\\|')} |")

    lines += [
        "",
        "---",
        "",
        f"_Automatically updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
        f"_Total projects: {len(sorted_projects)}_",
    ]

    (ROOT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_log(entries):
    log_path = ROOT / "automation-log.json"
    if log_path.exists():
        try:
            data = json.loads(log_path.read_text(encoding="utf-8"))
        except Exception:
            data = {"schema_version": 1, "runs": []}
    else:
        data = {"schema_version": 1, "runs": []}

    data.setdefault("schema_version", 1)
    data.setdefault("runs", [])
    data["runs"].append(entries)
    data["runs"] = data["runs"][-100:]
    log_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main():
    project_list = []
    for project in project_dirs(ROOT):
        info = generate_project_readme(project)
        project_list.append({
            "title": info["title"],
            "description": info["description"],
            "path": project.name,
            "link": f"./{project.name}/README.md",
            "components": info["components"],
            "dimensions": info["dimensions"],
            "renders": info["renders"],
        })

    write_root_readme(project_list)
    write_log({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "workflow": "PCB Designs Automation",
        "triggered_by": "local-run",
        "projects_processed": [entry["path"] for entry in project_list],
        "process_result": "success",
        "total_projects": len(project_list),
        "summary": {
            "total_components": sum(entry["components"] for entry in project_list),
            "total_renders": sum(len(entry["renders"]) for entry in project_list),
            "successful_projects": len(project_list),
        },
    })

    print(json.dumps({"projects": project_list}, indent=2))


if __name__ == "__main__":
    main()
