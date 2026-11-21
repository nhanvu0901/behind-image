from bti.voice.speak import cardinal, ordinal, speak, speak_units, year_words


def test_cardinal():
    assert cardinal(0) == "zero"
    assert cardinal(13) == "thirteen"
    assert cardinal(21) == "twenty-one"
    assert cardinal(100) == "one hundred"
    assert cardinal(123) == "one hundred twenty-three"
    assert cardinal(1200) == "one thousand two hundred"
    assert cardinal(2_000_005) == "two million five"
    assert cardinal(-4) == "minus four"


def test_ordinal():
    assert ordinal(1) == "first"
    assert ordinal(2) == "second"
    assert ordinal(12) == "twelfth"
    assert ordinal(15) == "fifteenth"
    assert ordinal(20) == "twentieth"
    assert ordinal(21) == "twenty-first"
    assert ordinal(100) == "one hundredth"


def test_years():
    assert year_words(1434) == "fourteen thirty-four"
    assert year_words(1905) == "nineteen oh five"
    assert year_words(1900) == "nineteen hundred"
    assert year_words(2007) == "two thousand seven"
    assert year_words(2020) == "twenty twenty"
    assert year_words(1000) == "one thousand"


def test_sentence_with_year_and_number():
    assert speak("In 1434, Jan van Eyck painted it.") == "In fourteen thirty-four, Jan van Eyck painted it."
    assert speak("About 1500 soldiers came.") == "About one thousand five hundred soldiers came."
    assert speak("He paid 1,200 florins.") == "He paid one thousand two hundred florins."
    assert speak("There were 12 men.") == "There were twelve men."


def test_ordinals_centuries_decades():
    assert speak("the 15th century") == "the fifteenth century"
    assert speak("a 15th-century panel") == "a fifteenth-century panel"
    assert speak("in the 1430s") == "in the fourteen thirties"
    assert speak("the 1960s") == "the nineteen sixties"
    assert speak("on the 1st of May") == "on the first of May"


def test_ranges():
    assert speak("from 1434-1436") == "from fourteen thirty-four to fourteen thirty-six"
    assert speak("1434-36") == "fourteen thirty-four to thirty-six"


def test_currency_percent_symbols():
    assert speak("It cost $5.") == "It cost five dollars."
    assert speak("It cost $1.50.") == "It cost one dollar fifty cents."
    assert speak("worth $2 million") == "worth two million dollars"
    assert speak("worth $1.5 million today") == "worth one point five million dollars today"
    assert speak("£20 a year") == "twenty pounds a year"
    assert speak("50% of it") == "fifty percent of it"
    assert speak("12.5% of it") == "twelve point five percent of it"
    assert speak("Tom & Jerry") == "Tom and Jerry"
    assert speak("a 3.5 metre") == "a three point five metre"


def test_time_and_degrees():
    assert speak("at 3:30 sharp") == "at three thirty sharp"
    assert speak("at 10:00") == "at ten o'clock"
    assert speak("45° angle") == "forty-five degrees angle"


def test_abbreviations():
    assert speak("Mr. Smith and Dr. Jones") == "Mister Smith and Doctor Jones"
    assert speak("St. Peter") == "Saint Peter"
    assert speak("apples, pears, etc. Then we left.") == "apples, pears, et cetera. Then we left."
    assert speak("apples, etc. and more") == "apples, et cetera and more"
    assert speak("e.g., a mirror") == "for example, a mirror"
    assert speak("c. 1434") == "circa fourteen thirty-four"
    assert speak("12 cm wide") == "twelve centimeters wide"
    assert speak("500 BC") == "five hundred B C"
    assert speak("in 476 AD.") == "in four hundred seventy-six A D."


def test_roman_numerals_for_kings_and_popes():
    assert speak("Henry VIII") == "Henry the eighth"
    assert speak("Pope Pius XII, who") == "Pope Pius the twelfth, who"
    assert speak("Charles V's court") == "Charles the fifth's court"
    assert speak("World War II") == "World War two"
    assert speak("I think so") == "I think so"          # a pronoun stays
    assert speak("Paul C. Smith") == "Paul C. Smith"


def test_plain_text_is_unchanged():
    t = "A mirror hangs behind the couple, and it shows two more people."
    assert speak(t) == t


def test_pronounce_table_first():
    t = {"Arnolfini": "Ar-nol-fee-nee", "van Eyck": "van Ike"}
    assert speak("Arnolfini and Jan van Eyck.", t) == "Ar-nol-fee-nee and Jan van Ike."
    assert speak("the arnolfini, again", t) == "the Ar-nol-fee-nee, again"      # ignores case and keeps the punctuation


def test_units_keep_written_words():
    u = speak_units("In 1434, he left.")
    assert [x.written for x in u] == [["In"], ["1434,"], ["he"], ["left."]]
    assert u[1].spoken == "fourteen thirty-four,"
    u = speak_units("worth $2 million now")
    assert [x.written for x in u] == [["worth"], ["$2", "million"], ["now"]]


def test_dash_is_a_pause():
    u = speak_units("He left - quickly.")
    assert [x.written for x in u] == [["He"], ["left", "-"], ["quickly."]]
    assert u[1].spoken == "left,"


def test_curly_quotes_and_markup():
    assert speak("“Hello,” she said.") == '"Hello," she said.'
    assert speak("a *strong* word") == "a strong word"
