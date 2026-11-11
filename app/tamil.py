# -*- coding: utf-8 -*-
"""
Reviewed Tamil translation dictionary (static, never generated at run time).
Every technical identifier the API returns carries both the English key and
the Tamil display string from these tables.
"""

SIGNS_EN = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
            "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
SIGNS_TA = ["மேஷம்", "ரிஷபம்", "மிதுனம்", "கடகம்", "சிம்மம்", "கன்னி",
            "துலாம்", "விருச்சிகம்", "தனுசு", "மகரம்", "கும்பம்", "மீனம்"]

PLANETS_EN = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
PLANETS_TA = {"Sun": "சூரியன்", "Moon": "சந்திரன்", "Mars": "செவ்வாய்", "Mercury": "புதன்",
              "Jupiter": "குரு", "Venus": "சுக்கிரன்", "Saturn": "சனி", "Rahu": "ராகு",
              "Ketu": "கேது", "Mandi": "மாந்தி", "Ascendant": "லக்னம்"}
PLANETS_TA_SHORT = {"Sun": "சூ", "Moon": "சந்", "Mars": "செவ்", "Mercury": "புத", "Jupiter": "குரு",
                    "Venus": "சுக்", "Saturn": "சனி", "Rahu": "ரா", "Ketu": "கே", "Mandi": "மா", "Ascendant": "லக்"}

NAKSHATRAS_EN = ["Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu",
                 "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta",
                 "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha",
                 "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada",
                 "Uttara Bhadrapada", "Revati"]
NAKSHATRAS_TA = ["அஸ்வினி", "பரணி", "கிருத்திகை", "ரோகிணி", "மிருகசீரிடம்", "திருவாதிரை", "புனர்பூசம்",
                 "பூசம்", "ஆயில்யம்", "மகம்", "பூரம்", "உத்திரம்", "ஹஸ்தம்",
                 "சித்திரை", "சுவாதி", "விசாகம்", "அனுஷம்", "கேட்டை", "மூலம்", "பூராடம்",
                 "உத்திராடம்", "திருவோணம்", "அவிட்டம்", "சதயம்", "பூரட்டாதி",
                 "உத்திரட்டாதி", "ரேவதி"]

WEEKDAYS_TA = ["திங்கள்", "செவ்வாய்", "புதன்", "வியாழன்", "வெள்ளி", "சனி", "ஞாயிறு"]  # Monday = 0
TITHIS_TA = ["பிரதமை", "துவிதியை", "திருதியை", "சதுர்த்தி", "பஞ்சமி", "சஷ்டி", "சப்தமி", "அஷ்டமி",
             "நவமி", "தசமி", "ஏகாதசி", "துவாதசி", "திரயோதசி", "சதுர்த்தசி"]
PAKSHA_TA = {"Shukla": "சுக்ல பட்சம்", "Krishna": "கிருஷ்ண பட்சம்"}
KARANAS_TA = {"Bava": "பவம்", "Balava": "பாலவம்", "Kaulava": "கௌலவம்", "Taitila": "தைதிலம்",
              "Garija": "கரஜம்", "Vanija": "வணிஜம்", "Vishti": "பத்ரை (விஷ்டி)", "Shakuni": "சகுனி",
              "Chatushpada": "சதுஷ்பாதம்", "Naga": "நாகவம்", "Kimstughna": "கிம்ஸ்துக்னம்"}
YOGAS_EN = ["Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana", "Atiganda", "Sukarma",
            "Dhriti", "Shula", "Ganda", "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra",
            "Siddhi", "Vyatipata", "Variyan", "Parigha", "Shiva", "Siddha", "Sadhya", "Shubha",
            "Shukla", "Brahma", "Indra", "Vaidhriti"]
YOGAS_TA = ["விஷ்கம்பம்", "ப்ரீதி", "ஆயுஷ்மான்", "சௌபாக்யம்", "சோபனம்", "அதிகண்டம்", "சுகர்மம்",
            "திருதி", "சூலம்", "கண்டம்", "விருத்தி", "துருவம்", "வியாகாதம்", "ஹர்ஷணம்", "வஜ்ரம்",
            "சித்தி", "வியதீபாதம்", "வரியான்", "பரிகம்", "சிவம்", "சித்தம்", "சாத்யம்", "சுபம்",
            "சுப்ரம்", "பிராம்யம்", "ஐந்திரம்", "வைதிருதி"]

DIGNITY_TA = {"exalted": "உச்சம்", "debilitated": "நீச்சம்", "own": "ஆட்சி", "neutral": "சமம்", "-": "-"}
MODE_TA = {"traditional": "பாரம்பரிய ஜோதிடம்", "kp": "கே.பி. ஜோதிடம்"}
HOUSE_SYSTEM_TA = {"whole_sign": "முழு ராசி வீடு முறை", "placidus": "பிளாசிடஸ் பாவக முறை"}
AYANAMSA_TA = {"lahiri": "லஹிரி அயனாம்சம்", "krishnamurti": "கிருஷ்ணமூர்த்தி அயனாம்சம்"}
