from __future__ import annotations

from planner.people import (
    match_people_tags,
    new_person_tags,
    parse_people_tags,
    people_bullets,
)

_PEOPLE = """#wpl/sushil
#wpl/juno
#wpl/sherry

VIP
#vip/ray_rouleau
#contractor/andrew_castle
#wp/kevin_white
"""


def test_parse_people_tags_keeps_only_hashtag_lines() -> None:
    tags = parse_people_tags(_PEOPLE)
    assert "#vip/ray_rouleau" in tags
    assert "#wpl/sherry" in tags
    assert "VIP" not in tags and "" not in tags


def test_match_people_tags_matches_full_and_first_name() -> None:
    tags = parse_people_tags(_PEOPLE)
    # full name -> first_last slug; "Sherry Zhou" -> single-token slug "sherry"
    assert match_people_tags(["Ray Rouleau", "Sherry Zhou"], tags) == [
        "#wpl/sherry", "#vip/ray_rouleau"]


def test_match_people_tags_ignores_unknown_and_noise() -> None:
    tags = parse_people_tags(_PEOPLE)
    assert match_people_tags(["organized by PLACEHOLDER", "Nobody Here"], tags) == []


def test_match_people_tags_dedupes() -> None:
    tags = parse_people_tags(_PEOPLE)
    assert match_people_tags(["Andrew Castle", "Andrew Castle"], tags) == [
        "#contractor/andrew_castle"]


def test_new_person_tags_adds_unknown_named_attendees() -> None:
    existing = ["#wpl/sherry", "#vip/ray_rouleau"]
    new = new_person_tags(
        ["Sherry Zhou", "John Doe", "organized by PLACEHOLDER"], existing, "person")
    assert new == ["#person/john_doe"]  # Sherry matched existing; noise skipped


def test_new_person_tags_skips_existing_and_dedupes() -> None:
    new = new_person_tags(["John Doe", "John Doe", "Jane Roe"], ["#person/john_doe"], "person")
    assert new == ["#person/jane_roe"]


def test_new_person_tags_ignores_non_name_noise() -> None:
    noise = ["organized by PLACEHOLDER", "no listed attendees", "Sherry only / no listed"]
    assert new_person_tags(noise, [], "person") == []


def test_people_bullets_mixes_tags_and_plain_text() -> None:
    tags = parse_people_tags(_PEOPLE)
    bullets = people_bullets(["Ray Rouleau", "and others", "Sherry Zhou"], tags)
    assert bullets == ["#vip/ray_rouleau", "and others", "#wpl/sherry"]


def test_people_bullets_dedupes_resolved_organizer() -> None:
    tags = parse_people_tags(_PEOPLE)
    assert people_bullets(["Sherry Zhou", "organized by Sherry"], tags) == ["#wpl/sherry"]
