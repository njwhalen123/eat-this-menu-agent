from menu_agent.text import SearchableText, key, named_in, normalize


def test_quote_found_across_lines_and_quote_marks():
    st = SearchableText(["Grilled Octopus 18", "chickpeas, smoked paprika, olive oil,", "lemon"])
    sp = st.find("chickpeas, smoked paprika, olive oil, lemon")
    assert sp and sp.start_line == 2 and sp.end_line == 3
    st2 = SearchableText(["za’atar hummus"])
    assert st2.find("za'atar hummus").text == "za’atar hummus"  # stored as the page wrote it


def test_quote_not_found_when_words_differ():
    st = SearchableText(["roasted beets, whipped goat cheese"])
    assert st.find("roasted beet, goat cheese") is None
    assert st.find("") is None


def test_named_in_and_key():
    assert named_in("crab", "lump crab, old bay aioli")
    assert named_in("tomato", "tomatoes, basil")
    assert not named_in("chicken", "romaine, parmesan")
    assert key("Saffron & Slate") == key("saffron and slate")
    assert normalize("a   b") == "a b"
