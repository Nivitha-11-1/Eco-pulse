"""
EcoPulse - Relevance Filter Tests

Tests the article relevance classification logic.

These tests use the MockHeuristicProvider so they do not consume
Gemini API quota.
"""

from ai.relevance_filter import (
    MockHeuristicProvider,
    check_relevance,
)


def run_test(number, title, description, expected, provider):
    """Run one relevance test."""

    result = check_relevance(
        title=title,
        description=description,
        provider=provider,
    )

    actual = result["is_relevant"]

    status = "PASS" if actual == expected else "FAIL"

    print(f"\nTest {number}: {status}")
    print(f"Title    : {title}")
    print(f"Expected : {expected}")
    print(f"Actual   : {actual}")
    print(f"Reason   : {result['reason']}")

    return actual == expected


def main():
    print("=" * 70)
    print("EcoPulse Relevance Filter Test")
    print("=" * 70)

    # Use mock provider so this test does NOT consume Gemini quota.
    provider = MockHeuristicProvider()

    tests = [
        (
            1,
            "Heavy rainfall causes flooding in Chennai",
            "Several areas of Chennai experienced severe flooding after heavy rainfall.",
            True,
        ),

        (
            2,
            "Waterlogging reported in several parts of Chennai",
            "Heavy rain caused waterlogging on roads and affected local residents.",
            True,
        ),

        (
            3,
            "Cyclone warning issued for Tamil Nadu coast",
            "Authorities issued a warning because of an approaching cyclone.",
            True,
        ),

        (
            4,
            "Chennai air quality deteriorates",
            "Air pollution levels increased across several parts of Chennai.",
            True,
        ),

        (
            5,
            "Water shortage expected in Chennai",
            "Residents have been advised to conserve water because reservoir levels are low.",
            True,
        ),

        (
            6,
            "Plastic waste cleanup drive held in Chennai",
            "Volunteers collected plastic waste from a public area as part of a recycling initiative.",
            True,
        ),

        (
            7,
            "Actor announces new movie",
            "The actor discussed an upcoming cinema release.",
            False,
        ),

        (
            8,
            "India wins cricket match",
            "The team won an important cricket tournament match.",
            False,
        ),

        (
            9,
            "Company reports higher quarterly profits",
            "The company announced increased revenue and profits.",
            False,
        ),

        (
            10,
            "Man arrested for alleged financial fraud",
            "Police arrested a person in connection with a financial fraud investigation.",
            False,
        ),

        (
            11,
            "Schools closed because of heavy rainfall",
            "Schools in several districts were closed because of severe rainfall and flooding.",
            True,
        ),

        (
            12,
            "Chennai roads flooded after overnight rain",
            "Several roads were flooded and traffic was disrupted following heavy rain.",
            True,
        ),
    ]

    passed = 0
    failed = 0

    for number, title, description, expected in tests:
        if run_test(
            number,
            title,
            description,
            expected,
            provider,
        ):
            passed += 1
        else:
            failed += 1

    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    print(f"Total tests : {len(tests)}")
    print(f"Passed      : {passed}")
    print(f"Failed      : {failed}")

    if failed == 0:
        print("\nALL RELEVANCE TESTS PASSED")
    else:
        print("\nSOME RELEVANCE TESTS FAILED")

    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    success = main()

    if not success:
        raise SystemExit(1)