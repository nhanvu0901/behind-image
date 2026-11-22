from bti.voice.speak import speak


def test_year_after_of_and_quantities():
    assert speak("Portrait of 1434") == "Portrait of fourteen thirty-four"
    assert speak("a total of 1434") == "a total of one thousand four hundred thirty-four"
    assert speak("of 1434 pieces") == "of one thousand four hundred thirty-four pieces"
