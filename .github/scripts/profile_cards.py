"""Generate monochrome profile cards from public GitHub REST data."""
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree.ElementTree import Element, SubElement, tostring

USERNAME = "Sayoneku"
API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")


def fetch(path):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Sayoneku-profile-cards",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    with urlopen(Request(API + path, headers=headers), timeout=30) as response:
        return json.load(response)


def text(svg, x, y, value, size=13, colour="#777777", weight="400"):
    element = SubElement(svg, "text", {
        "x": str(x), "y": str(y), "fill": colour,
        "font-size": str(size), "font-weight": weight,
        "font-family": "-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif",
    })
    element.text = str(value)


def card(width, height, title, description, dark):
    svg = Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "width": str(width), "height": str(height),
        "viewBox": f"0 0 {width} {height}", "role": "img",
    })
    SubElement(svg, "title").text = title
    SubElement(svg, "desc").text = description
    foreground = "#eeeeee" if dark else "#111111"
    secondary = "#aaaaaa" if dark else "#666666"
    text(svg, 18, 28, title, 16, foreground, "600")
    return svg, foreground, secondary


def main():
    destination = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
    destination.mkdir(parents=True, exist_ok=True)
    user = fetch("/users/" + USERNAME)
    repos = []
    page = 1
    while True:
        batch = fetch(f"/users/{USERNAME}/repos?type=owner&per_page=100&page={page}")
        if not isinstance(batch, list):
            raise ValueError("Expected a repository list")
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    original_repos = [repo for repo in repos if not repo["fork"]]
    languages = Counter()
    for repo in original_repos:
        languages.update(fetch(f'/repos/{repo["full_name"]}/languages'))

    metrics = [
        ("Public repositories", len(repos)),
        ("Followers", user["followers"]),
        ("Stars earned", sum(repo["stargazers_count"] for repo in original_repos)),
        ("Forks received", sum(repo["forks_count"] for repo in original_repos)),
    ]
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    description = (
        "Public GitHub data for " + USERNAME + ". Updated " + generated
        + ". Star, fork and language totals cover owned, non-fork public repositories."
    )
    total_bytes = sum(languages.values())
    ranked_languages = languages.most_common(4)
    remainder = total_bytes - sum(value for _, value in ranked_languages)
    if remainder:
        ranked_languages.append(("Other", remainder))

    for dark in (False, True):
        suffix = "-dark" if dark else ""
        svg, foreground, secondary = card(430, 176, "GitHub at a glance", description, dark)
        for index, (label, value) in enumerate(metrics):
            x = 18 + (index % 2) * 210
            y = 72 + (index // 2) * 72
            text(svg, x, y, format(value, ","), 25, foreground, "600")
            text(svg, x, y + 21, label, 12, secondary)
        (destination / ("stats" + suffix + ".svg")).write_text(
            tostring(svg, encoding="unicode"), encoding="utf-8"
        )

        svg, foreground, secondary = card(300, 176, "Public code", description, dark)
        if total_bytes:
            x = 18.0
            shades = ["#bbbbbb", "#999999", "#777777", "#555555", "#333333"] if dark else [
                "#222222", "#555555", "#888888", "#aaaaaa", "#cccccc"
            ]
            for index, (name, count) in enumerate(ranked_languages):
                width = 264 * count / total_bytes
                SubElement(svg, "rect", {
                    "x": str(x), "y": "48", "width": str(width), "height": "6",
                    "fill": shades[index],
                })
                x += width
                y = 81 + index * 19
                text(svg, 18, y, name, 12, foreground)
                text(svg, 230, y, f"{100 * count / total_bytes:.1f}%", 12, secondary)
        else:
            text(svg, 18, 76, "No public language data yet.", 12, secondary)
        (destination / ("languages" + suffix + ".svg")).write_text(
            tostring(svg, encoding="unicode"), encoding="utf-8"
        )

    print(json.dumps({
        "user": USERNAME, "generated_at": generated,
        "metrics": dict(metrics), "language_bytes": dict(languages),
        "cards": 4,
    }))


if __name__ == "__main__":
    main()
