from web_discovery import _looks_like_person_name, _person_name_from_text


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
