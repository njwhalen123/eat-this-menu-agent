import json
import os

import pytest

from conftest import PRACTICE
from menu_agent import captures
from menu_agent.reference_check import check


@pytest.mark.parametrize("rid", ["P1", "P2", "P3", "P4"])
def test_practice_answer_keys_are_on_their_pages(rid):
    root = os.path.join(PRACTICE, rid)
    ref = json.load(open(os.path.join(root, "reference.json")))
    assert check(ref, captures.load(root)) == []
