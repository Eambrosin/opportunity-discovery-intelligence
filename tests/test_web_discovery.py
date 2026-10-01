from web_discovery import (
    _looks_like_generic_service_label,
    _looks_like_person_name,
    _person_name_from_text,
)


def test_title_fragment_is_not_accepted_as_person_name():
    assert _looks_like_person_name("Alberto Zampori La") is False
    assert _looks_like_person_name("Noviello Nel") is False


def test_honorific_parser_stops_before_title_fragment():
    assert (
        _person_name_from_text(
            "Dott. Paolo Montemurro chirurgo plastico e medicina estetica Milano"
        )
        == "Paolo Montemurro"
    )


def test_valid_two_word_person_name_remains_supported():
    assert _looks_like_person_name("Paolo Montemurro") is True


def test_location_list_is_not_a_person_name():
    assert _looks_like_person_name("Milano, Roma, Caserta") is False


def test_category_plus_city_is_not_treated_as_account_identity():
    assert _looks_like_generic_service_label(
        "Centri medici e cliniche di Medicina Estetica a Milano"
    ) is True


def test_treatment_plus_city_is_not_treated_as_account_identity():
    assert _looks_like_generic_service_label("Criolipolisi Milano") is True


def test_compact_brand_name_remains_distinctive():
    assert _looks_like_generic_service_label(
        "LaserMilano Centro di Medicina Estetica"
    ) is False
