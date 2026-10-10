"""Tests for EcoPulse Quick Keyword Relevance Filter."""

from ai.relevance_filter import quick_relevance_check

QUICK_FILTER_TEST_CASES = [
    (
        "Heavy rainfall causes flooding in Chennai",
        "Several areas experienced severe waterlogging.",
        True,
    ),
    (
        "Cyclone warning issued for Tamil Nadu",
        "Authorities issued a weather warning.",
        True,
    ),
    (
        "Chennai water supply affected",
        "Residents were asked to conserve drinking water.",
        True,
    ),
    (
        "Plastic waste cleanup drive",
        "Volunteers collected plastic waste for recycling.",
        True,
    ),
    (
        "Actor announces new movie",
        "The actor announced a new cinema release.",
        False,
    ),
    (
        "India wins cricket match",
        "The team won the tournament.",
        False,
    ),
    (
        "Company reports higher profits",
        "The company reported strong quarterly revenue.",
        False,
    ),
]


def test_quick_filter():
    """Verify keyword pre-filter correctly classifies environmental vs non-environmental articles."""
    for title, description, expected in QUICK_FILTER_TEST_CASES:
        actual = quick_relevance_check(title, description)
        assert actual == expected, f"Failed for '{title}': expected {expected}, got {actual}"


def main():
    tests = QUICK_FILTER_TEST_CASES
    passed = 0

    print("=" * 70)
    print("EcoPulse Quick Relevance Filter Test")
    print("=" * 70)

    for number, (title, description, expected) in enumerate(tests, 1):
        actual = quick_relevance_check(title, description)

        status = "PASS" if actual == expected else "FAIL"

        print(f"\nTest {number}: {status}")
        print(f"Title    : {title}")
        print(f"Expected : {expected}")
        print(f"Actual   : {actual}")

        if actual == expected:
            passed += 1

    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Total tests : {len(tests)}")
    print(f"Passed      : {passed}")
    print(f"Failed      : {len(tests) - passed}")

    if passed == len(tests):
        print("\nALL QUICK FILTER TESTS PASSED")
    else:
        print("\nSOME QUICK FILTER TESTS FAILED")
        raise SystemExit(1)


if __name__ == "__main__":
    main()