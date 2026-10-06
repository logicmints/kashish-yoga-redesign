"""Build a content-preserving prototype and editable SVGs from Kashish's page."""

import base64
import concurrent.futures
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urljoin
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
SOURCE = "https://kashishyoga.com/200-multi-style/"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr"}
CARDS = {"sec1-box1", "sec5-box1", "sec9a-box", "sec10-boxs",
         "sec11-box", "sec11-box1", "sec12-box-1", "sec-13-box",
         "border-bottom01"}


class Node:
    def __init__(self, tag="", attrs=()):
        self.tag = tag
        self.attrs = dict(attrs)
        self.children = []

    def text(self):
        return " ".join(" ".join(c.text() if isinstance(c, Node) else c
                                for c in self.children).split())

    def classes(self):
        return set(self.attrs.get("class", "").split())

    def find(self, tag):
        for child in self.children:
            if isinstance(child, Node):
                if child.tag == tag:
                    return child
                result = child.find(tag)
                if result:
                    return result
        return None


class Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        if tag == "li":
            for index in range(len(self.stack) - 1, 0, -1):
                if self.stack[index].tag == "li":
                    self.stack = self.stack[:index]
                    break
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, attrs))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                self.stack = self.stack[:index]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def blocks(node, inside_card=False):
    result = []
    for child in node.children:
        if not isinstance(child, Node):
            continue
        attrs, tag, classes = child.attrs, child.tag, child.classes()
        if tag in {"script", "style", "noscript", "i"}:
            continue
        if tag == "a" and attrs.get("data-bs-target"):
            continue
        if tag == "li":
            trigger = child.find("a")
            if trigger and trigger.attrs.get("data-bs-target"):
                answer = next(c for c in child.children
                              if isinstance(c, Node) and c.tag == "div")
                result.append({"kind": "detail", "text": trigger.text(),
                               "children": blocks(answer)})
                continue
        if classes & CARDS and not inside_card:
            result.append({"kind": "card", "variant": sorted(classes & CARDS)[0],
                           "children": blocks(child, True)})
        elif tag in {"h1", "h2", "h3", "h4", "h5", "p"} or tag == "li" or "faq-item" in classes:
            if child.text():
                result.append({"kind": tag if tag.startswith("h") else "p",
                               "text": child.text(), "id": attrs.get("id", "")})
        elif tag == "img":
            src = urljoin(SOURCE, attrs.get("src", ""))
            decorative = any(token in src for token in (
                "star-", "line-1", "simple-sentiayoga", "whatsapp.svg",
                "right-arrow.svg", "down-arrow.svg", "left-arrow.svg"))
            if not decorative:
                result.append({"kind": "image", "src": src,
                               "alt": attrs.get("alt", "")})
        elif tag == "iframe":
            result.append({"kind": "video", "src": attrs["src"]})
        elif tag == "a" and child.find("button"):
            result.append({"kind": "action", "text": child.text(),
                           "href": urljoin(SOURCE, attrs["href"]) if not
                           attrs["href"].startswith("#") else attrs["href"]})
        elif "whatsapp-btn" in classes:
            continue
        elif any(c.classes() & {"subtitle_02", "subtitle_04"} for c in child.children
                 if isinstance(c, Node)):
            result.append({"kind": "price", "text": child.text()})
        else:
            result.extend(blocks(child, inside_card))
    return result


def text_leaves(node):
    ignored = {"script", "style", "noscript", "i"}
    if node.tag in ignored or "whatsapp-btn" in node.classes():
        return []
    result = []
    for child in node.children:
        if isinstance(child, Node):
            result.extend(text_leaves(child))
        elif child.strip():
            result.append(" ".join(child.split()))
    return result


def content_text(items):
    result = []
    for item in items:
        if item.get("text"):
            result.append(item["text"])
        result.extend(content_text(item.get("children", [])))
    return result


def load_content():
    source = ROOT.joinpath("source.html").read_text()
    sections, evidence = [], []
    for index, match in enumerate(re.finditer(
            r"<section\b[^>]*>.*?</section>", source, re.S)):
        parser = Parser()
        parser.feed(match.group())
        section = parser.root.find("section")
        content = blocks(section)
        if "section-1" in section.classes():
            trust_start = next(i for i, block in enumerate(content)
                               if block.get("text", "").startswith("★★★★★"))
            trust_end = next(i for i, block in enumerate(content)
                             if block["kind"] == "h2")
            content[trust_start:trust_end] = [{
                "kind": "card", "variant": "trust",
                "children": content[trust_start:trust_end]}]
        # The original includes duplicate desktop/mobile certificate imagery.
        if "section-9b" in section.classes():
            seen = set()
            unique = []
            for item in content:
                if item["kind"] == "image":
                    if item["src"] in seen:
                        continue
                    seen.add(item["src"])
                unique.append(item)
            content = unique
        leaves = text_leaves(section)
        joined = " ".join(content_text(content))
        missing = [leaf for leaf in leaves if leaf not in joined]
        if missing:
            raise ValueError(f"Content omitted in section {index}: {missing}")
        if " ".join(leaves) != joined:
            raise ValueError(f"Source wording or order changed in section {index}")
        sections.append({"id": f"section-{index}", "class": section.attrs.get(
            "class", ""), "blocks": content})
        evidence.append({"section": index, "source_text_fragments": len(leaves),
                         "missing": missing})
    if len(sections) != 23:
        raise ValueError(f"Expected 23 source sections, got {len(sections)}")
    return sections, evidence


def walk(items):
    for item in items:
        yield item
        yield from walk(item.get("children", []))


def download_asset(url):
    digest = hashlib.sha256(url.encode()).hexdigest()[:12]
    path = ROOT / "assets" / (digest + ".jpg")
    if path.with_suffix(".svg").exists():
        return url, str(path.with_suffix(".svg").relative_to(ROOT))
    if not path.exists():
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=45) as response:
            data = response.read()
            content_type = response.headers.get("Content-Type", "")
        if "svg" in content_type or url.endswith(".svg"):
            path = path.with_suffix(".svg")
            path.write_bytes(data)
        else:
            raw = ROOT / "assets" / (digest + ".download")
            raw.write_bytes(data)
            subprocess.run(["sips", "-s", "format", "jpeg", "-Z", "1000",
                            str(raw), "--out", str(path)], check=True,
                           stdout=subprocess.DEVNULL)
            raw.unlink()
    return url, str(path.relative_to(ROOT))


def escaped(value):
    return html.escape(str(value), quote=True)


def html_block(item, assets):
    kind, text = item["kind"], escaped(item.get("text", ""))
    if kind in {"h1", "h2", "h3", "h4", "h5", "p"}:
        anchor = f' id="{escaped(item["id"])}"' if item.get("id") else ""
        return f"<{kind}{anchor}>{text}</{kind}>"
    if kind == "image":
        return f'<img src="{assets[item["src"]]}" alt="{escaped(item["alt"])}" loading="lazy">'
    if kind == "video":
        return (f'<a class="video" href="{escaped(video_destination(item["src"]))}" '
                'target="_blank" rel="noopener noreferrer" '
                f'data-video-source="{escaped(item["src"])}" '
                'aria-label="View original Kashish Yoga video">'
                '<span class="play" aria-hidden="true">▶</span>'
                '<span><strong>Kashish Yoga</strong><br>Play video ↗</span></a>')
    if kind == "action":
        cls = "secondary" if "COUNSELLOR" in item["text"] else ""
        return f'<a class="button {cls}" href="{escaped(item["href"])}">{text}<span aria-hidden="true">↗</span></a>'
    if kind == "price":
        return f'<p class="price">{text}</p>'
    if kind == "detail":
        return f'<details><summary>{text}</summary><div class="answer">{html_blocks(item["children"], assets)}</div></details>'
    if kind == "card":
        return f'<article class="card {item["variant"]}">{html_blocks(item["children"], assets)}</article>'
    raise ValueError(kind)


def html_blocks(items, assets):
    output, group, group_kind = [], [], None

    def flush():
        if group:
            output.append(f'<div class="{group_kind}-grid">'
                          + "".join(group) + "</div>")
            group.clear()

    for item in items:
        kind = item["kind"]
        grouped = kind if kind in {"card", "image", "action"} else None
        if grouped != group_kind:
            flush()
            group_kind = grouped
        rendered = html_block(item, assets)
        if grouped:
            group.append(rendered)
        else:
            output.append(rendered)
    flush()
    return "\n".join(output)


def certificate_parts(items):
    headings = [item for item in items if item["kind"] in {"h2", "h3"}]
    copy = [item for item in items if item["kind"] == "p"]
    images = [item for item in items if item["kind"] == "image"]
    if len(images) != 3 or len(copy) != 6:
        raise ValueError("Unexpected certificate section structure")
    return headings, copy, images[0], images[1], images[2]


def travel_parts(items):
    intro = [item for item in items if item["kind"] in {"h2", "h3", "p"}]
    cards = [item for item in items if item["kind"] == "card"]
    actions = [item for item in items if item["kind"] == "action"]
    if len(cards) != 4:
        raise ValueError("Expected four travel preparation steps")
    by_heading = {card["children"][0]["text"]: card for card in cards}
    ordered = [by_heading[heading] for heading in (
        "BEFORE YOU FLY", "ARRIVAL IN GOA", "DURING YOUR STAY", "GOING HOME")]
    return intro, ordered, actions


def html_section(section, assets):
    items = section["blocks"]
    classes = section["class"].split()
    if "section-9b" in classes:
        headings, copy, collage, logos, certificate = certificate_parts(items)
        outcomes = "".join(f'<li>{escaped(item["text"])}</li>' for item in copy[1:4])
        return (html_blocks(headings, assets) +
                '<div class="certificate-layout"><div class="certificate-copy">' +
                '<p class="eyebrow">' + escaped(copy[0]["text"]) + "</p>" +
                '<ul class="certificate-outcomes">' + outcomes + "</ul>" +
                '<div class="certificate-note">' + html_block(copy[4], assets) + "</div>" +
                html_block(copy[5], assets) +
                '<div class="certificate-accreditation">' + html_block(logos, assets) + "</div>" +
                '</div><div class="certificate-media"><div class="certificate-collage">' +
                html_block(collage, assets) + '</div><div class="certificate-document">' +
                html_block(certificate, assets) + "</div></div></div>")
    if "section-13" in classes:
        intro, cards, actions = travel_parts(items)
        steps = "".join('<li class="travel-step"><span class="step-number" aria-hidden="true">' +
                        f"{index:02d}</span>" + html_blocks(card["children"], assets) + "</li>"
                        for index, card in enumerate(cards, 1))
        return (html_blocks(intro, assets) + '<ol class="travel-steps">' + steps +
                "</ol>" + html_blocks(actions, assets))
    return html_blocks(items, assets)


def make_html(sections, assets):
    hero = sections[0]["blocks"]
    hero_copy = [item for item in hero if item["kind"] != "video"]
    video = next(item for item in hero if item["kind"] == "video")
    hero_photo = next(item for item in sections[3]["blocks"]
                      if item["kind"] == "image")
    body = []
    for index, section in enumerate(sections[1:], 1):
        body.append(f'<section class="content {section["class"]}" id="{section["id"]}">'
                    '<div class="section-inner">' +
                    html_section(section, assets) + "</div></section>")
    header = """<header><a class="brand" href="#hero" aria-label="Kashish Yoga">
    <img src="assets/kashish-logo.svg" alt="Kashish Yoga"></a>
    <nav aria-label="Course navigation"><a href="#course">Course</a>
    <a href="#experience">Experience</a><a href="#course_date">Dates &amp; Prices</a>
    <a href="#reviews">Reviews</a><a href="#faq_01">FAQ</a></nav>
    <a class="button small" href="#course_date">CHECK DATES <span aria-hidden="true">↗</span></a>
    <button class="menu-toggle" aria-expanded="false" aria-controls="mobile-nav" aria-label="Open menu">☰</button></header>
    <nav id="mobile-nav" aria-label="Mobile course navigation" hidden>
    <a href="#course">Course</a><a href="#experience">Experience</a>
    <a href="#course_date">Dates &amp; Prices</a><a href="#reviews">Reviews</a>
    <a href="#faq_01">FAQ</a></nav>"""
    # Keep source anchors even when wrapper elements are replaced.
    aliases = '<span id="learn_the_knowledge"></span>'
    for index in range(len(body)):
        if "section-5a" in sections[index + 1]["class"]:
            body[index] = body[index].replace('<div class="section-inner">',
                                               '<div class="section-inner">' + aliases, 1)
        if "section-15" in sections[index + 1]["class"]:
            body[index] = body[index].replace('<div class="section-inner">',
                                               '<div class="section-inner"><span id="faq_01"></span>', 1)
    result = """<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <meta name="theme-color" content="#eaf8f2">
    <title>Kashish Yoga — 200-Hour Teacher Training · Design Prototype</title>
    <link rel="stylesheet" href="styles.css"></head><body>
    <a class="skip" href="#main">Skip to course content</a>"""
    result += header + '<main id="main"><section class="hero" id="hero"><div class="hero-copy">'
    result += html_blocks(hero_copy, assets)
    result += '</div><div class="hero-visual"><div class="hero-image">'
    result += html_block(hero_photo, assets)
    result += '<span class="image-caption">GOA, INDIA</span></div>'
    result += html_block(video, assets) + "</div></section>" + "".join(body)
    result += """</main><footer><img src="assets/kashish-logo.svg" alt="Kashish Yoga">
    <a class="button" href="https://kashishyoga.com/goa/200-hour-yoga-teacher-training-apply/">ENQUIRE NOW <span aria-hidden="true">↗</span></a>
    </footer><a class="whatsapp" aria-label="Chat on WhatsApp" href="https://wa.me/9732189000?text=Multi-Style%20200%20Hour">WhatsApp ↗</a>
    <script src="prototype.js"></script></body></html>"""
    ROOT.joinpath("index.html").write_text(result)


def line_width(text, size):
    return sum(0.27 if c in " ilI.,'!:;|"
               else 0.86 if c in "MW@%m"
               else 0.59 if c.isupper() else 0.53
               for c in text) * size


def wrap(text, width, size):
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and line_width(candidate, size) > width * 0.92:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def video_destination(src):
    anchors = {"749185649": "hero", "749591324": "learn_the_knowledge",
               "1078905458": "experience", "1078897771": "choose_the_stay"}
    video_id = src.split("/")[-1].split("?")[0]
    return SOURCE + "#" + anchors.get(video_id, "reviews")


class Canvas:
    def __init__(self, width, assets):
        self.width, self.assets, self.parts = width, assets, []
        self.mobile = width < 600
        self.hero = False

    def rect(self, x, y, width, height, fill, radius=0, stroke="none"):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>')

    def text(self, text, x, y, width, size=16, color="#52666a", bold=False, anchor=""):
        lines = wrap(text, width, size)
        line_height = size * 1.45
        anchor_attr = f' id="{escaped(anchor)}"' if anchor else ""
        self.parts.append(f'<text{anchor_attr} font-family="Arial" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}" aria-label="{escaped(text)}">')
        for index, line in enumerate(lines):
            self.parts.append(f'<tspan x="{x}" y="{y + size + index * line_height}">{escaped(line)}</tspan>')
        self.parts.append("</text>")
        return len(lines) * line_height

    def image(self, url, x, y, width, height, fit=None):
        path = ROOT / self.assets[url]
        mime = "image/svg+xml" if path.suffix == ".svg" else "image/jpeg"
        data = base64.b64encode(path.read_bytes()).decode()
        clip_id = f"image-{len(self.parts)}"
        self.parts.append(f'<defs><clipPath id="{clip_id}"><rect x="{x}" y="{y}" width="{width}" height="{height}" rx="20"/></clipPath></defs>')
        fit = fit or ("meet" if path.suffix == ".svg" or "certificate" in url else "slice")
        self.parts.append(f'<image x="{x}" y="{y}" width="{width}" height="{height}" preserveAspectRatio="xMidYMid {fit}" clip-path="url(#{clip_id})" xlink:href="data:{mime};base64,{data}"/>')

    def block(self, item, x, y, width):
        kind = item["kind"]
        sizes = {"h1": 12, "h2": 30 if self.mobile else 42,
                 "h3": 26 if self.mobile else 36, "h4": 20,
                 "h5": 21, "p": 15 if self.mobile else 17, "price": 25}
        if self.hero:
            sizes["h2"] = 40 if self.mobile else 58
            sizes["h3"] = 15
        if kind in sizes:
            return self.text(item["text"], x, y, width, sizes[kind],
                             "#123a3d" if kind in {"h2", "h4", "h5", "price"}
                             else "#207467" if kind in {"h1", "h3"} else "#52666a",
                             kind != "p", item.get("id", "")) + 14
        if kind == "image":
            height = min(width * 0.63, 520)
            if self.assets[item["src"]].endswith(".svg"):
                height = 80
            self.image(item["src"], x, y, width, height)
            return height + 16
        if kind == "video":
            height = 110 if self.mobile else 140
            self.parts.append(f'<a href="{escaped(video_destination(item["src"]))}">')
            self.rect(x, y, width, height, "#dceddf", 20)
            self.text("▶", x + 24, y + 24, width - 48, 30, "#207467")
            self.text("Kashish Yoga", x + 24, y + 74, width - 48, 16, "#123a3d")
            self.parts.append("</a>")
            return height + 20
        if kind == "action":
            height = 52
            secondary = "COUNSELLOR" in item["text"]
            button_width = min(width, line_width(item["text"], 12) + 64)
            self.parts.append(f'<a href="{escaped(item["href"])}">')
            self.rect(x, y, button_width, height, "#ecf5f0" if secondary else "#176858", 26)
            self.text(item["text"], x + 20, y + 15, button_width - 32,
                      12, "#176858" if secondary else "#ffffff", True)
            self.parts.append("</a>")
            return height + 14
        if kind in {"card", "detail"}:
            start = len(self.parts)
            self.parts.append("")
            current = y + 24
            if kind == "detail":
                current += self.text(item["text"] + "  −", x + 24, current,
                                     width - 48, 18, "#123a3d", True) + 16
            for child in item["children"]:
                current += self.block(child, x + 24, current, width - 48)
            height = current - y + 12
            self.parts[start] = f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="24" fill="#ffffff" stroke="#dce9e3"/>'
            return height + 20
        raise ValueError(kind)

    def flow(self, items, x, y, width):
        index = 0
        while index < len(items):
            item = items[index]
            if item["kind"] in {"card", "image"}:
                kind = item["kind"]
                end = index
                while end < len(items) and items[end]["kind"] == kind:
                    end += 1
                group = items[index:end]
                cols = 1 if self.mobile else min(3, len(group))
                if kind == "image" and not self.mobile:
                    cols = min(4, len(group))
                gap = 24
                card_width = (width - gap * (cols - 1)) / cols
                for row in range(0, len(group), cols):
                    heights = [self.block(child, x + column * (card_width + gap),
                                          y, card_width)
                               for column, child in enumerate(group[row:row + cols])]
                    y += max(heights) + 12
                index = end
            else:
                y += self.block(item, x, y, width)
                index += 1
        return y

    def section(self, section, x, y, width):
        classes = section["class"].split()
        if "section-9b" in classes:
            headings, copy, collage, logos, certificate = certificate_parts(section["blocks"])
            y = self.flow(headings, x, y, width) + 18
            column = width if self.mobile else (width - 48) / 2
            copy_end = y
            copy_end += self.text(copy[0]["text"], x, copy_end, column, 13, "#207467", True) + 20
            for item in copy[1:4]:
                self.rect(x, copy_end + 7, 7, 7, "#207467", 3)
                copy_end += self.text(item["text"], x + 22, copy_end, column - 22,
                                      16, "#123a3d") + 18
            for item in copy[4:]:
                copy_end += self.block(item, x, copy_end, column)
            self.image(logos["src"], x, copy_end + 8, min(column, 380), 72, "meet")
            copy_end += 104
            media_x = x if self.mobile else x + column + 48
            media_y = copy_end + 24 if self.mobile else y
            collage_height = 220 if self.mobile else 260
            self.image(collage["src"], media_x, media_y, column, collage_height, "meet")
            document_y = media_y + collage_height + 24
            document_height = column * 0.72 + 32
            self.rect(media_x, document_y, column, document_height, "#ffffff", 24, "#dce9e3")
            self.image(certificate["src"], media_x + 16, document_y + 16,
                       column - 32, document_height - 32, "meet")
            return max(copy_end, document_y + document_height) + 24
        if "section-13" in classes:
            intro, cards, actions = travel_parts(section["blocks"])
            y = self.flow(intro, x, y, width) + 18
            columns = 1 if self.mobile else 4
            gap = 20
            card_width = (width - gap * (columns - 1)) / columns
            for row in range(0, len(cards), columns):
                ends, backgrounds = [], []
                for column, card in enumerate(cards[row:row + columns]):
                    card_x = x + column * (card_width + gap)
                    background = len(self.parts)
                    self.parts.append("")
                    self.rect(card_x + 24, y + 24, 42, 42, "#eaf8f2", 21)
                    self.text(f"{row + column + 1:02d}", card_x + 34, y + 35,
                              30, 14, "#176858", True)
                    end = self.flow(card["children"], card_x + 24, y + 86,
                                    card_width - 48) + 12
                    ends.append(end)
                    backgrounds.append((background, card_x))
                row_end = max(ends)
                for background, card_x in backgrounds:
                    self.parts[background] = (f'<rect x="{card_x}" y="{y}" width="{card_width}" '
                                              f'height="{row_end - y}" rx="24" fill="#ffffff" stroke="#dce9e3"/>')
                y = row_end + 24
            return self.flow(actions, x, y + 8, width)
        return self.flow(section["blocks"], x, y, width)

    def export(self, filename, height):
        content = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                   f'width="{self.width}" height="{height}" viewBox="0 0 {self.width} {height}">'
                   "<title>Kashish Yoga course redesign</title>"
                   + "".join(self.parts) + "</svg>")
        ET.fromstring(content)
        ROOT.joinpath(filename).write_text(content)


def make_svg(sections, assets, width):
    canvas = Canvas(width, assets)
    pad = 24 if canvas.mobile else 96
    usable = width - 2 * pad
    canvas.rect(0, 0, width, 92, "#f4fbf7")
    canvas.image("logo", pad, 22, 125, 45)
    if not canvas.mobile:
        canvas.text("Course     Experience     Dates & Prices     Reviews     FAQ",
                    435, 33, 650, 14, "#123a3d")
    canvas.block({"kind": "action", "text": "CHECK DATES", "href": "#course_date"},
                 width - pad - 160, 24, 160)
    hero = sections[0]["blocks"]
    canvas.hero = True
    copy = [item for item in hero if item["kind"] != "video"]
    photo = next(item for item in sections[3]["blocks"]
                 if item["kind"] == "image")
    video = next(item for item in hero if item["kind"] == "video")
    bg_index = len(canvas.parts)
    canvas.parts.append("")
    if canvas.mobile:
        y = canvas.flow(copy, pad, 130, usable)
        y += canvas.block(photo, pad, y + 20, usable) + 20
        y += canvas.block(video, pad, y, usable)
    else:
        left_width = usable * 0.49
        left_end = canvas.flow(copy, pad, 150, left_width)
        right_x = pad + left_width + 64
        right_width = usable - left_width - 64
        canvas.image(photo["src"], right_x, 142, right_width, 380)
        right_end = 550 + canvas.block(video, right_x, 550, right_width)
        y = max(left_end, right_end)
    y += 64
    canvas.hero = False
    canvas.parts[bg_index] = f'<rect x="0" y="92" width="{width}" height="{y - 92}" fill="#eaf8f2"/>'
    for index, section in enumerate(sections[1:], 1):
        start = y
        background_index = len(canvas.parts)
        canvas.parts.append("")
        canvas.parts.append(f'<g id="{section["id"]}" aria-label="{escaped(section["class"])}">')
        if "section-5a" in section["class"]:
            canvas.parts.append('<g id="learn_the_knowledge"/>')
        if "section-15" in section["class"]:
            canvas.parts.append('<g id="faq_01"/>')
        y = canvas.section(section, pad, y + 64, usable) + 48
        canvas.parts.append("</g>")
        background = "#f3f8f4" if index % 3 == 0 else "#fffdfa"
        canvas.parts[background_index] = f'<rect x="0" y="{start}" width="{width}" height="{y - start}" fill="{background}"/>'
    canvas.rect(0, y, width, 140, "#123a3d")
    canvas.text("Kashish Yoga", pad, y + 40, usable, 24, "#ffffff", True)
    canvas.block({"kind": "action", "text": "ENQUIRE NOW",
                  "href": "https://kashishyoga.com/goa/200-hour-yoga-teacher-training-apply/"},
                 width - pad - 160, y + 40, 160)
    filename = "mobile-390.svg" if canvas.mobile else "desktop-1440.svg"
    canvas.export(filename, round(y + 140))
    return {"file": filename, "width": width, "height": round(y + 140)}


def main():
    sections, evidence = load_content()
    images = {item["src"] for section in sections
              for item in walk(section["blocks"]) if item["kind"] == "image"}
    assets = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for url, path in pool.map(download_asset, sorted(images)):
            assets[url] = path
    logo = "https://storage.googleapis.com/kashishyoga01/new200/k-logo.svg"
    with urlopen(logo, timeout=30) as response:
        ROOT.joinpath("assets/kashish-logo.svg").write_bytes(response.read())
    assets["logo"] = "assets/kashish-logo.svg"
    ROOT.joinpath("content.json").write_text(json.dumps(sections, ensure_ascii=False, indent=2))
    ROOT.joinpath("assets.json").write_text(json.dumps(assets, indent=2))
    make_html(sections, assets)
    frames = [make_svg(sections, assets, width) for width in (1440, 390)]
    report = {"source": SOURCE, "sections": len(sections), "content": evidence,
              "images": len(images), "frames": frames, "missing_text_fragments": 0,
              "note": "Original wording retained, including source inconsistencies. SVG disclosures are expanded."}
    ROOT.joinpath("validation.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({key: report[key] for key in
                      ("sections", "images", "frames", "missing_text_fragments")}, indent=2))


if __name__ == "__main__":
    main()
