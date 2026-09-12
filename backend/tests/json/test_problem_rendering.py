from json_component.problems import Problem, ProblemCode
from json_component.types import format_path


def test_format_empty_path():
    assert format_path(()) == "$"


def test_format_identifier_path():
    assert format_path(("a", "b", 2)) == "$.a.b[2]"


def test_format_quoted_path():
    assert format_path(("not a key",)) == "$['not a key']"


def test_problem_string_contains_code_path_message():
    text = str(Problem(ProblemCode.DECODE_TYPE, "bad", ("x", 1)))
    assert "decode.type" in text
    assert "$.x[1]" in text
    assert "bad" in text
