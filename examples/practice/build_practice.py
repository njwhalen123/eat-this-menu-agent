"""Builds the four fictional practice restaurants and their answer keys.

Everything here is invented: the restaurants, names, addresses (.example
domains, "Example City") and menus. No real restaurant's name is attached to
any of it (D-029, D-052).

Each menu is written once, as data, and rendered to its page format:
  P1 Quillfeather Tavern   one HTML page (name – description price on one line)
  P2 Saffron & Slate       one HTML page with tabbed panels, prices on their own line,
                           and an image-only Specials panel
  P3 Larkspur Noodle Bar   an index page linking to separate menu pages; one linked
                           page (brunch) was not saved; a drinks page is out of scope
  P4 Tidewater Example     a two-page PDF with a description that runs across the
     Kitchen               page break

The answer key (reference.json) was written by the same author as the menus,
so it tests the pipeline, not anyone's accuracy. tests/test_reference.py
checks that every fact in it is on its page.

Run from the repository root:  python3 -I examples/practice/build_practice.py
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RETRIEVED = "2026-11-25"

# Each dish: (name, description or None, price or None, ingredients as named, statements, dish type)
# Statements are the page's own words about the dish (warnings, labels, options, qualifiers).
#
# Coding rules used in this answer key (the real coding notes come from the catalog chat):
#  - Ingredients are the components the description lists, as named ("lump crab" -> "crab"
#    is allowed by the scorer's containment match). Words only in the dish name don't count.
#  - An option ("choice of chicken or tofu") is a statement, not an ingredient (CATALOG-EXPANSION §5.3).
#  - Allergen words that appear only in a "contains" warning are the warning, not ingredients.


def D(name, desc, price, ingredients=(), statements=(), dt=None):
    return {"name": name, "description": desc, "price": price, "ingredients": list(ingredients),
            "statements": list(statements), "dish_type": dt}


# ---------------------------------------------------------------- P1
P1 = {
    "id": "P1", "name": "Quillfeather Tavern", "base": "https://quillfeather.example",
    "scope": "every food section of the dinner menu",
    "sections": [
        ("Starters", [
            D("Smoked Beet Salad", "roasted beets, whipped goat cheese, pistachio, arugula", "13",
              ["beets", "goat cheese", "pistachio", "arugula"]),
            D("Chowder Cup", "clams, potato, smoked bacon, cream", "9",
              ["clams", "potato", "smoked bacon", "cream"]),
            D("Crispy Brussels Sprouts", "maple glaze, chili, toasted peanuts. Contains peanuts.", "11",
              ["maple glaze", "chili", "peanuts"], [("warning", "Contains peanuts.")]),
            D("Oysters on the Half Shell*", "lemon, mignonette", "MP", ["lemon", "mignonette"]),
            D("Soup of the Day", None, "8"),
        ]),
        ("Mains", [
            D("Tavern Burger", "8 oz beef patty, cheddar, pickles, brioche bun. GF bun available", "18",
              ["beef patty", "cheddar", "pickles", "brioche bun"], [("qualifier", "GF bun available")], "DT10"),
            D("Pan-Roasted Cod", "lemon butter, capers, fingerling potatoes", "27",
              ["lemon butter", "capers", "fingerling potatoes"]),
            D("Mushroom Risotto (V)", "arborio rice, wild mushrooms, parmesan, truffle oil", "23",
              ["arborio rice", "wild mushrooms", "parmesan", "truffle oil"], [("dietary_label", "(V)")]),
            D("Chicken Caesar", "romaine, parmesan, house Caesar dressing, no croutons", "19",
              ["romaine", "parmesan", "Caesar dressing"], [("qualifier", "no croutons")], "DT02"),
            D("Stir-Fry Bowl", "seasonal vegetables, jasmine rice, choice of chicken or tofu", "21",
              ["seasonal vegetables", "jasmine rice"], [("option", "choice of chicken or tofu")]),
            D("Fish and Chips", "beer-battered haddock, fries, tartar sauce", "22",
              ["haddock", "fries", "tartar sauce"], [], "DT12"),
        ]),
        ("Sides", [D("Fries", None, "6"), D("Coleslaw", None, "5", [], [], "DT30"), D("Side Salad", None, "6")]),
        ("Desserts", [
            D("Warm Apple Crisp", "oat crumble, vanilla ice cream", "10", ["oat crumble", "vanilla ice cream"]),
            D("Chocolate Pot de Crème", "dark chocolate, whipped cream. Contains tree nuts (hazelnut).", "10",
              ["dark chocolate", "whipped cream"], [("warning", "Contains tree nuts (hazelnut).")]),
        ]),
    ],
    "menu_statements": [
        "*Consuming raw or undercooked meats, poultry, seafood, shellfish, or eggs may increase your risk of foodborne illness.",
        "Please tell your server about any food allergies before ordering.",
    ],
    "facts": {"hours": "Hours: Tue–Sun 5 pm – 10 pm", "address": "12 Harbor Lantern Way, Example City",
              "phone": "(555) 010-0199"},
    "problems": [],
}


def render_p1(r):
    out = ["<!DOCTYPE html><html><head><title>Menu – Quillfeather Tavern (fictional)</title>",
           "<style>.price{float:right}</style></head><body>",
           '<nav><a href="/">Home</a> | <a href="/menu/">Menu</a> | <a href="/reservations/">Reservations</a> | <a href="/contact/">Contact</a></nav>',
           "<main><h1>Menu</h1><p><em>A fictional practice menu.</em></p>"]
    for sec, dishes in r["sections"]:
        out.append(f'<div class="menu-section"><h2>{html.escape(sec)}</h2>')
        for d in dishes:
            desc = f" – {html.escape(d['description'])}" if d["description"] else ""
            out.append(f'<div class="menu-item"><p><strong>{html.escape(d["name"])}</strong>{desc} '
                       f'<span class="price">{html.escape(d["price"])}</span></p></div>')
        out.append("</div>")
    for s in r["menu_statements"]:
        out.append(f'<p class="note">{html.escape(s)}</p>')
    f = r["facts"]
    out.append(f"</main><footer><p>{html.escape(f['hours'])}</p><p>{html.escape(f['address'])}</p>"
               f"<p>{html.escape(f['phone'])}</p></footer></body></html>")
    return {"menu.html": "\n".join(out)}


# ---------------------------------------------------------------- P2
P2 = {
    "id": "P2", "name": "Saffron & Slate", "base": "https://saffron-and-slate.example",
    "scope": "the Lunch and Dinner menus (the Specials panel is an image)",
    "sections": [
        ("Lunch", [
            D("Lamb Kofta Plate", "grilled lamb kofta, saffron rice, cucumber yogurt, pickled onion", "$16",
              ["lamb kofta", "saffron rice", "cucumber yogurt", "pickled onion"]),
            D("Falafel Wrap", "chickpea falafel, tahini, tomato, parsley, in a warm pita", "$13",
              ["chickpea falafel", "tahini", "tomato", "parsley", "pita"], [], "DT09"),
            D("Lentil Soup", "red lentils, cumin, lemon. Vegan.", "$8",
              ["red lentils", "cumin", "lemon"], [("dietary_label", "Vegan.")]),
            D("Halloumi Salad", "grilled halloumi, watermelon, mint, sumac", "$14",
              ["halloumi", "watermelon", "mint", "sumac"]),
            D("Chicken Shawarma Bowl", "marinated chicken, garlic sauce, turnip pickles, rice", "$15",
              ["chicken", "garlic sauce", "turnip pickles", "rice"], [], "DT20"),
        ]),
        ("Dinner", [
            D("Lamb Kofta Plate", "grilled lamb kofta, saffron rice, cucumber yogurt, pickled onion", "$24",
              ["lamb kofta", "saffron rice", "cucumber yogurt", "pickled onion"]),
            D("Whole Branzino", "charred lemon, herbs, olive oil. Served with the bones in.", "$34",
              ["lemon", "herbs", "olive oil"], [("warning", "Served with the bones in.")]),
            D("Hummus Trio", "classic, roasted red pepper, and za'atar hummus with pita. Contains sesame.", "$12",
              ["hummus", "roasted red pepper", "za'atar", "pita"], [("warning", "Contains sesame.")], "DT19"),
            D("Saffron Chicken", "half chicken, saffron butter, freekeh", "$27",
              ["chicken", "saffron butter", "freekeh"]),
            D("Baklava", "phyllo, walnuts, pistachio, honey syrup. Contains wheat and tree nuts.", "$9",
              ["phyllo", "walnuts", "pistachio", "honey syrup"], [("warning", "Contains wheat and tree nuts.")]),
        ]),
    ],
    "menu_statements": ["Our kitchen handles sesame, tree nuts and wheat; please ask your server about allergens."],
    "facts": {"hours": "Mon–Sat 11:30 am – 9:30 pm", "address": "88 Slate Row, Example City", "phone": None},
    "problems": [{"kind": "image_only", "where": "Specials"}],
}


def render_p2(r):
    tabs = [s for s, _ in r["sections"]] + ["Specials"]
    out = ["<!DOCTYPE html><html><head><title>Saffron &amp; Slate – Menus (fictional)</title>",
           "<style>.tab-panel{display:none}.tab-panel.active{display:block}</style>",
           "<script>function show(t){/* tab switcher */}</script></head><body>",
           "<header><h1>Saffron &amp; Slate</h1><p>A fictional practice menu.</p></header>",
           '<div class="tabs">' + "".join(f'<button data-tab="{t.lower()}">{t}</button>' for t in tabs) + "</div>"]
    for i, (sec, dishes) in enumerate(r["sections"]):
        out.append(f'<section class="tab-panel{" active" if i == 0 else ""}" id="{sec.lower()}"><h2>{sec}</h2>')
        for d in dishes:
            out.append(f'<div class="menu-item"><h4 class="item-title">{html.escape(d["name"])}</h4>'
                       f'<span class="price">{html.escape(d["price"])}</span>'
                       f'<p class="desc">{html.escape(d["description"])}</p></div>')
        out.append("</section>")
    out.append('<section class="tab-panel" id="specials"><h2>Specials</h2>'
               '<img src="/images/specials-board.jpg" alt="Chalkboard of today\'s specials"></section>')
    out.append(f'<p class="note">{html.escape(r["menu_statements"][0])}</p>')
    f = r["facts"]
    out.append(f"<footer><p>{html.escape(f['hours'])}</p><p>{html.escape(f['address'])}</p></footer></body></html>")
    return {"menus.html": "\n".join(out)}


# ---------------------------------------------------------------- P3
P3 = {
    "id": "P3", "name": "Larkspur Noodle Bar", "base": "https://larkspur-noodles.example",
    "scope": "the Noodles and Small Plates pages (drinks excluded)",
    "sections": [
        ("Noodles", [
            D("Dan Dan Noodles", "wheat noodles, spicy pork, Sichuan pepper, peanuts", "15",
              ["wheat noodles", "pork", "Sichuan pepper", "peanuts"]),
            D("Pad Thai", "rice noodles, egg, tamarind, bean sprouts, crushed peanuts; choice of shrimp or tofu", "16",
              ["rice noodles", "egg", "tamarind", "bean sprouts", "peanuts"], [("option", "choice of shrimp or tofu")], "DT03"),
            D("Tonkotsu Ramen", "pork broth, chashu, soft egg, nori, scallion", "18",
              ["pork broth", "chashu", "egg", "nori", "scallion"]),
            D("Cold Sesame Noodles (V)", "wheat noodles, sesame sauce, cucumber", "13",
              ["wheat noodles", "sesame sauce", "cucumber"], [("dietary_label", "(V)")]),
            D("Beef Chow Fun", "wide rice noodles, beef, bean sprouts, soy sauce", "17",
              ["rice noodles", "beef", "bean sprouts", "soy sauce"]),
        ]),
        ("Small Plates", [
            D("Pork Gyoza", None, "9", [], [], "DT24"),
            D("Vegetable Spring Rolls (V)", None, "8", [], [("dietary_label", "(V)")]),
            D("Shrimp Tempura", None, "12", [], [], "DT17"),
            D("Edamame (V)", None, "6", [], [("dietary_label", "(V)")]),
            D("Scallion Pancake", None, "8"),
        ]),
    ],
    "menu_statements": ["Dishes marked (V) are vegetarian.", "Ask us about allergens."],
    "facts": {"hours": "Daily 11 am – 10 pm", "address": "3 Larkspur Lane, Example City", "phone": None},
    "problems": [{"kind": "missing_page", "where": "Weekend Brunch"}],
}


def render_p3(r):
    head = lambda t: f"<!DOCTYPE html><html><head><title>{t} – Larkspur Noodle Bar (fictional)</title></head><body>"
    nav = ('<nav><a href="/menu/">Menu</a> · <a href="/menu/noodles.html">Noodles</a> · '
           '<a href="/menu/small-plates.html">Small Plates</a> · <a href="/menu/drinks.html">Drinks</a> · '
           '<a href="/menu/brunch.html">Weekend Brunch</a></nav>')
    f = r["facts"]
    pages = {}
    pages["index.html"] = (head("Menu") + nav + "<h1>Our Menu</h1><p>A fictional practice menu. Pick a page:</p><ul>"
                           '<li><a href="/menu/noodles.html">Noodles</a></li><li><a href="/menu/small-plates.html">Small Plates</a></li>'
                           '<li><a href="/menu/drinks.html">Drinks</a></li><li><a href="/menu/brunch.html">Weekend Brunch</a></li></ul>'
                           f"<footer><p>{html.escape(f['hours'])}</p><p>{html.escape(f['address'])}</p></footer></body></html>")
    (n_sec, noodles), (s_sec, small) = r["sections"]
    body = [head("Noodles") + nav + "<h1>Noodles</h1><table>"]
    for d in noodles:
        body.append(f"<tr><td><b>{html.escape(d['name'])}</b><br>{html.escape(d['description'])}</td><td>{d['price']}</td></tr>")
    body.append("</table><p>Ask us about allergens.</p></body></html>")
    pages["noodles.html"] = "\n".join(body)
    body = [head("Small Plates") + nav + "<h1>Small Plates</h1><ul>"]
    for d in small:
        body.append(f"<li>{html.escape(d['name'])} ...... {d['price']}</li>")
    body.append("</ul><p>Dishes marked (V) are vegetarian.</p></body></html>")
    pages["small-plates.html"] = "\n".join(body)
    pages["drinks.html"] = (head("Drinks") + nav + "<h1>Drinks</h1><ul><li>Thai Iced Tea ...... 5</li>"
                            "<li>Yuzu Lemonade ...... 5</li><li>Jasmine Tea ...... 4</li></ul></body></html>")
    return pages


# ---------------------------------------------------------------- P4
P4 = {
    "id": "P4", "name": "Tidewater Example Kitchen", "base": "https://tidewater-kitchen.example",
    "scope": "the whole dinner menu (PDF)",
    "sections": [
        ("DINNER > RAW BAR", [
            D("Littleneck Clams*", None, "3 each", []),
            D("Shrimp Cocktail", "poached shrimp, cocktail sauce, lemon", "16", ["shrimp", "cocktail sauce", "lemon"]),
        ]),
        ("DINNER > STARTERS", [
            D("Crab Cakes", "lump crab, old bay aioli, frisée", "17", ["crab", "old bay aioli", "frisée"], [], "DT16"),
            D("Clam Chowder", "New England style; contains milk and wheat", "10", [],
              [("warning", "contains milk and wheat")], "DT15"),
            D("Fried Calamari", "cherry peppers, marinara", "14", ["cherry peppers", "marinara"], [], "DT11"),
            D("Grilled Octopus", "chickpeas, smoked paprika, olive oil, lemon", "18",
              ["chickpeas", "smoked paprika", "olive oil", "lemon"]),
        ]),
        ("DINNER > MAINS", [
            D("Lobster Roll", "chilled lobster, mayonnaise, celery, toasted split-top bun", "32",
              ["lobster", "mayonnaise", "celery", "split-top bun"]),
            D("Seared Scallops", "cauliflower purée, brown butter, capers", "34",
              ["cauliflower purée", "brown butter", "capers"]),
            D("Fish Tacos", "fried cod, cabbage slaw, chipotle crema, corn tortillas", "22",
              ["cod", "cabbage slaw", "chipotle crema", "corn tortillas"], [], "DT29"),
            D("Steak Frites", "8 oz hanger steak, herb butter, fries. Gluten-free on request", "36",
              ["hanger steak", "herb butter", "fries"], [("qualifier", "Gluten-free on request")]),
        ]),
        ("DINNER > DESSERTS", [
            D("Blueberry Cobbler", "buttermilk biscuit, vanilla ice cream", "9",
              ["buttermilk biscuit", "vanilla ice cream"]),
        ]),
    ],
    "menu_statements": ["*Consuming raw or undercooked shellfish may increase your risk of foodborne illness."],
    "facts": {"hours": "Open Wed–Sun, 4 pm – 10 pm", "address": "1 Tidewater Wharf, Example City", "phone": None},
    "problems": [],
}


def render_p4(r, path):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    font = "Helvetica"
    for cand in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if os.path.exists(cand):
            pdfmetrics.registerFont(TTFont("DejaVu", cand))
            font = "DejaVu"
    c = canvas.Canvas(path, pagesize=letter, invariant=1)
    c.setTitle("Tidewater Example Kitchen – Dinner (fictional)")
    W, H = letter
    y = H - 60

    def line(text, size=11, x=60, gap=16):
        nonlocal y
        c.setFont(font, size)
        c.drawString(x, y, text)
        y -= gap

    line("TIDEWATER EXAMPLE KITCHEN", 16, gap=20)
    line("A fictional practice menu", 9, gap=24)
    line("DINNER", 14, gap=22)
    secs = r["sections"]
    for si, (sec, dishes) in enumerate(secs):
        if sec == "DINNER > MAINS":
            c.showPage()
            y = H - 60
            line("lemon")  # the Grilled Octopus description continues here (page 2)
        line(sec.split(" > ")[-1], 12, gap=18)
        for d in dishes:
            line(f"{d['name']}  {d['price']}")
            if d["description"]:
                desc = d["description"]
                if d["name"] == "Grilled Octopus":
                    desc = "chickpeas, smoked paprika, olive oil,"
                line(desc, 10, x=72)
    line(r["menu_statements"][0], 8, gap=12)
    line(f"{r['facts']['hours']} · {r['facts']['address']}", 8)
    c.save()


# ---------------------------------------------------------------- write


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def reference(r, minutes=None):
    items = []
    for sec, dishes in r["sections"]:
        for d in dishes:
            items.append({"section": sec, "name": d["name"], "description": d["description"], "price": d["price"],
                          "ingredients": d["ingredients"],
                          "statements": [{"kind": k, "text": t} for k, t in d["statements"]],
                          "dish_type": d["dish_type"]})
    return {"format": "menu-agent-reference/0", "restaurant_id": r["id"], "fictional": True,
            "built_by": "the practice menus' author (AG chat); a pipeline test, not an accuracy measure",
            "minutes": minutes, "menu_scope": r["scope"], "items": items,
            "menu_statements": r["menu_statements"], "restaurant_facts": r["facts"], "problems": r["problems"]}


def write(r, files: dict, kinds: dict, urls: dict, roles: dict):
    root = os.path.join(HERE, f"{r['id']}")
    os.makedirs(os.path.join(root, "captures"), exist_ok=True)
    caps = []
    for i, (fname, content) in enumerate(files.items(), 1):
        p = os.path.join(root, "captures", fname)
        if content is not None:
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
        caps.append({"capture_id": f"{r['id']}-C{i}", "url": urls[fname], "kind": kinds.get(fname, "html"),
                     "path": f"captures/{fname}", "sha256": sha(p), "retrieved_at": RETRIEVED,
                     "role": roles.get(fname, "menu")})
    manifest = {"restaurant_id": r["id"], "display_name": r["name"], "fictional": True,
                "menu_scope": r["scope"], "captures": caps}
    with open(os.path.join(root, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(os.path.join(root, "reference.json"), "w", encoding="utf-8") as f:
        json.dump(reference(r), f, indent=2, ensure_ascii=False)
        f.write("\n")


def main():
    write(P1, render_p1(P1), {}, {"menu.html": P1["base"] + "/menu/"}, {})
    write(P2, render_p2(P2), {}, {"menus.html": P2["base"] + "/menus/"}, {})
    p3 = render_p3(P3)
    b = P3["base"] + "/menu/"
    write(P3, p3, {}, {"index.html": b, "noodles.html": b + "noodles.html",
                       "small-plates.html": b + "small-plates.html", "drinks.html": b + "drinks.html"},
          {"index.html": "menu index", "drinks.html": "drinks (out of scope)"})
    os.makedirs(os.path.join(HERE, "P4", "captures"), exist_ok=True)
    pdf = os.path.join(HERE, "P4", "captures", "dinner.pdf")
    render_p4(P4, pdf)
    write(P4, {"dinner.pdf": None}, {"dinner.pdf": "pdf"}, {"dinner.pdf": P4["base"] + "/dinner.pdf"}, {})
    print("built P1–P4 in", HERE, file=sys.stderr)


if __name__ == "__main__":
    main()
