from core.components.pattern_matcher import PatternMatcher


def test_match_pattern():
    matcher = PatternMatcher(r"ctdapp-([a-zA-Z]+)-node-(\d+)\.ctdapp\.([a-zA-Z]+)")
    test_cases = [
        ("ctdapp-xyz-node-3.ctdapp.test", ["xyz", "3", "test"]),
        ("ctdapp-xyz-node-5.ctdapp", None),
    ]

    for input_str, expected in test_cases:
        assert matcher.search(input_str) == expected


def test_match_pattern_with_defaults():
    matcher = PatternMatcher(
        r"ctdapp-([a-zA-Z]+)-node-(\d+)\.ctdapp\.([a-zA-Z]+)",
        "default_value",
    )

    test_cases = [
        ("ctdapp-xyz-node-3.ctdapp.test", ["xyz", "3", "test", "default_value"]),
        ("ctdapp-xyz-node-5.ctdapp", None),
    ]

    for input_str, expected in test_cases:
        assert matcher.search(input_str) == expected


def test_match_pattern_with_multiple_defaults():
    matcher = PatternMatcher(
        r"ctdapp-([a-zA-Z]+)-node-(\d+)\.ctdapp\.([a-zA-Z]+)",
        "default_value1",
        "default_value2",
    )

    test_cases = [
        (
            "ctdapp-xyz-node-3.ctdapp.test",
            ["xyz", "3", "test", "default_value1", "default_value2"],
        ),
        ("ctdapp-xyz-node-5.ctdapp", None),
    ]

    for input_str, expected in test_cases:
        assert matcher.search(input_str) == expected
