from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.cars.models import (
    Battery, BodyType, Brand, CombustionEngine, Country, DriveType,
    DriverAssistanceSystem, ElectricMotor, Generation, Manufacturer, Market,
    Model, ModelTechnology, Modification, ModificationADAS,
    ModificationMarket, Platform, Powertrain, PowertrainMotor, Technology,
    Transmission, TrimLevel,
)
from apps.knowledge.models import Article, Category, Source, Tag, VideoResource


ACCESSED_AT = date(2026, 10, 6)

SOURCES = {
    "byd": ("BYD SEAL and SEAL U DM-i", "BYD", "https://www.byd.com/eu/electric-cars/seal"),
    "zeekr": ("ZEEKR 001 and ZEEKR X", "ZEEKR", "https://www.zeekr.eu/models/001"),
    "geely": ("Geely global model range", "Geely Auto", "https://global.geely.com/en/models"),
    "chery": ("TIGGO model range", "Chery International", "https://www.cheryinternational.com/pc/models/"),
    "li-auto": ("Li L6 and Li L7", "Li Auto", "https://www.lixiang.com/en"),
    "nio": ("NIO ET5 and EL6", "NIO", "https://www.nio.com/et5"),
    "xiaomi": ("Xiaomi EV model information", "Xiaomi EV", "https://www.xiaomiev.com/"),
    "hongqi": ("Hongqi H5 and E-HS9", "Hongqi", "https://www.hongqi-auto.com/pages/cartype/cartype_h5.html"),
    "blade": ("Blade Battery", "BYD", "https://www.bydglobal.com/en/Technology.html"),
    "sea": ("Sustainable Experience Architecture", "ZEEKR", "https://www.zeekrglobal.com/technology"),
    # Expansion of the course set (accessed 2026-11-22).
    "byd-dolphin": ("BYD DOLPHIN", "BYD", "https://www.byd.com/eu/electric-cars/dolphin"),
    "byd-atto3": ("BYD ATTO 3", "BYD", "https://www.byd.com/eu/electric-cars/atto3"),
    "zeekr-7x": ("ZEEKR 7X", "ZEEKR", "https://www.zeekr.eu/models/7x"),
    "nio-et7": ("NIO ET7", "NIO", "https://www.nio.com/et7"),
    "xpeng": ("XPENG G6 and G9", "XPENG", "https://www.xpeng.com/"),
    "leapmotor": ("Leapmotor C10 and T03", "Leapmotor", "https://www.leapmotor.net/"),
    "gwm": ("Great Wall Motor: HAVAL", "Great Wall Motor", "https://www.gwm-global.com/"),
    "tank": ("TANK 300 and TANK 500", "Great Wall Motor", "https://www.tank-global.com/"),
    "deepal": ("DEEPAL S07", "Changan Automobile", "https://www.globalchangan.com/deepal"),
    "lynkco": ("Lynk & Co 01 and 02", "Lynk & Co", "https://www.lynkco.com/"),
    "omoda": ("OMODA C5 and E5", "OMODA & JAECOO", "https://www.omodajaecoo.com/"),
}

# One generation and one or two representative configurations per model. Values describe
# the named market/version in the cited manufacturer material; absent facts stay NULL.
# Variant: (name, powertrain, drive, power kW, battery kWh, range km, range cycle[, extras]);
# optional extras hold confirmed 0–100 km/h time and top speed.
VEHICLES = [
    # brand, model, segment, body, platform, start year, source, variants
    ("BYD", "Seal", "D", "sedan", "e-Platform 3.0", 2022, "byd", [
        ("Excellence AWD", "BEV", "AWD", 390, 82.5, 520, "WLTP", {"acceleration_0_100_s": 3.8, "top_speed_kmh": 180}),
    ]),
    ("BYD", "Seal U DM-i", "D-SUV", "suv", "DM-i", 2024, "byd", [
        ("Boost FWD", "PHEV", "FWD", 160, 18.3, 80, "WLTP"),
        ("Design AWD", "PHEV", "AWD", 238, 18.3, 70, "WLTP"),
    ]),
    ("Zeekr", "001", "E", "liftback", "SEA", 2021, "zeekr", [
        ("Long Range RWD", "BEV", "RWD", 200, 100, 620, "WLTP"),
    ]),
    ("Zeekr", "X", "C-SUV", "suv", "SEA", 2023, "zeekr", [
        ("Long Range RWD", "BEV", "RWD", 200, 69, 446, "WLTP"),
        ("Privilege AWD", "BEV", "AWD", 315, 69, 425, "WLTP"),
    ]),
    ("Geely", "Monjaro", "D-SUV", "suv", "CMA", 2021, "geely", [
        ("2.0T 2WD", "ICE", "FWD", 160, None, None, ""),
        ("2.0T 4WD", "ICE", "AWD", 175, None, None, ""),
    ]),
    ("Geely", "EX5", "C-SUV", "suv", "GEA", 2024, "geely", [
        ("Pro FWD", "BEV", "FWD", 160, 49.5, 430, "CLTC"),
        ("Max FWD", "BEV", "FWD", 160, 60.2, 530, "CLTC"),
    ]),
    ("Chery", "Tiggo 8 Pro Max", "D-SUV", "suv", "T1X", 2022, "chery", [
        ("2.0T 2WD", "ICE", "FWD", 187, None, None, ""),
        ("2.0T AWD", "ICE", "AWD", 187, None, None, ""),
    ]),
    ("Chery", "Tiggo 7 CSH", "C-SUV", "suv", "T1X", 2025, "chery", [
        ("PHEV FWD", "PHEV", "FWD", 255, 18.3, 90, "WLTP"),
        ("PHEV FWD Long Range", "PHEV", "FWD", 255, 18.3, 93, "WLTP"),
    ]),
    ("Li Auto", "L6", "D-SUV", "suv", "Li Auto EREV", 2024, "li-auto", [
        ("Pro AWD", "EREV", "AWD", 300, 36.8, 212, "CLTC"),
        ("Max AWD", "EREV", "AWD", 300, 36.8, 212, "CLTC"),
    ]),
    ("Li Auto", "L7", "E-SUV", "suv", "Li Auto EREV", 2023, "li-auto", [
        ("Pro AWD", "EREV", "AWD", 330, 42.8, 225, "CLTC"),
        ("Ultra AWD", "EREV", "AWD", 330, 52.3, 286, "CLTC"),
    ]),
    ("NIO", "ET5", "D", "sedan", "NT2.0", 2022, "nio", [
        ("Standard Range AWD", "BEV", "AWD", 360, 75, 456, "WLTP"),
        ("Long Range AWD", "BEV", "AWD", 360, 100, 590, "WLTP"),
    ]),
    ("NIO", "ES6", "D-SUV", "suv", "NT2.0", 2023, "nio", [
        ("Standard Range AWD", "BEV", "AWD", 360, 75, 490, "CLTC"),
        ("Long Range AWD", "BEV", "AWD", 360, 100, 625, "CLTC"),
    ]),
    ("Xiaomi", "SU7", "E", "sedan", "Modena", 2024, "xiaomi", [
        ("Pro RWD", "BEV", "RWD", 220, 94.3, 830, "CLTC", {"acceleration_0_100_s": 5.7, "top_speed_kmh": 210}),
        ("Max AWD", "BEV", "AWD", 495, 101, 800, "CLTC", {"acceleration_0_100_s": 2.78, "top_speed_kmh": 265}),
    ]),
    ("Xiaomi", "YU7", "D-SUV", "suv", "Modena", 2025, "xiaomi", [
        ("Standard RWD", "BEV", "RWD", 235, 96.3, 835, "CLTC"),
        ("Max AWD", "BEV", "AWD", 508, 101.7, 760, "CLTC"),
    ]),
    ("Hongqi", "H5", "D", "sedan", "Hongqi FMA", 2022, "hongqi", [
        ("1.5T DCT", "ICE", "FWD", 124, None, None, ""),
        ("2.0T AT", "ICE", "FWD", 165, None, None, ""),
    ]),
    ("Hongqi", "E-HS9", "F-SUV", "suv", "Hongqi EV", 2020, "hongqi", [
        ("Executive AWD", "BEV", "AWD", 320, 99, 465, "WLTP"),
        ("President AWD", "BEV", "AWD", 405, 120, 515, "WLTP"),
    ]),
    # --- Expansion: more models of existing brands and seven new brands ---
    ("BYD", "Dolphin", "C", "hatchback", "e-Platform 3.0", 2021, "byd-dolphin", [
        ("Active FWD", "BEV", "FWD", 70, 44.9, 340, "WLTP"),
        ("Comfort FWD", "BEV", "FWD", 150, 60.4, 427, "WLTP", {"acceleration_0_100_s": 7.0, "top_speed_kmh": 160}),
    ]),
    ("BYD", "Atto 3", "C-SUV", "suv", "e-Platform 3.0", 2022, "byd-atto3", [
        ("Design FWD", "BEV", "FWD", 150, 60.48, 420, "WLTP", {"acceleration_0_100_s": 7.3, "top_speed_kmh": 160}),
    ]),
    ("Zeekr", "7X", "D-SUV", "suv", "SEA", 2024, "zeekr-7x", [
        ("Long Range RWD", "BEV", "RWD", 310, 100, 615, "WLTP"),
        ("Performance AWD", "BEV", "AWD", 475, 100, 543, "WLTP", {"acceleration_0_100_s": 3.8, "top_speed_kmh": 210}),
    ]),
    ("NIO", "ET7", "E", "sedan", "NT2.0", 2022, "nio-et7", [
        ("Long Range AWD", "BEV", "AWD", 480, 100, 580, "WLTP", {"acceleration_0_100_s": 3.8, "top_speed_kmh": 200}),
    ]),
    ("Li Auto", "L9", "F-SUV", "suv", "Li Auto EREV", 2022, "li-auto", [
        ("Max AWD", "EREV", "AWD", 330, 52.3, 280, "CLTC"),
    ]),
    ("Li Auto", "Mega", "MPV", "minivan", "Li Auto BEV", 2024, "li-auto", [
        ("Max AWD", "BEV", "AWD", 400, 102.7, 710, "CLTC", {"acceleration_0_100_s": 5.5, "top_speed_kmh": 180}),
    ]),
    ("Geely", "Coolray", "B-SUV", "suv", "BMA", 2019, "geely", [
        ("1.5T FWD", "ICE", "FWD", 110, None, None, ""),
    ]),
    ("Geely", "Atlas", "C-SUV", "suv", "CMA", 2023, "geely", [
        ("2.0T FWD", "ICE", "FWD", 147, None, None, ""),
        ("2.0T AWD", "ICE", "AWD", 147, None, None, ""),
    ]),
    ("XPeng", "G6", "D-SUV", "suv", "SEPA 2.0", 2023, "xpeng", [
        ("Standard Range RWD", "BEV", "RWD", 190, 66, 435, "WLTP"),
        ("Performance AWD", "BEV", "AWD", 358, 87.5, 550, "WLTP", {"acceleration_0_100_s": 4.1, "top_speed_kmh": 200}),
    ]),
    ("XPeng", "G9", "E-SUV", "suv", "XPeng Edward", 2022, "xpeng", [
        ("Long Range RWD", "BEV", "RWD", 230, 98, 570, "WLTP"),
        ("Performance AWD", "BEV", "AWD", 405, 98, 520, "WLTP", {"acceleration_0_100_s": 3.9, "top_speed_kmh": 200}),
    ]),
    ("Leapmotor", "C10", "D-SUV", "suv", "LEAP 3.0", 2023, "leapmotor", [
        ("Design RWD", "BEV", "RWD", 160, 69.9, 420, "WLTP"),
    ]),
    ("Leapmotor", "T03", "A", "hatchback", "Leapmotor EV", 2020, "leapmotor", [
        ("Design FWD", "BEV", "FWD", 70, 37.3, 265, "WLTP"),
    ]),
    ("Haval", "Jolion", "C-SUV", "suv", "L.E.M.O.N.", 2020, "gwm", [
        ("1.5T FWD", "ICE", "FWD", 105, None, None, ""),
    ]),
    ("Haval", "Dargo", "C-SUV", "suv", "L.E.M.O.N.", 2022, "gwm", [
        ("2.0T 4WD", "ICE", "AWD", 141, None, None, ""),
    ]),
    ("Tank", "300", "D-SUV", "suv", "TANK", 2021, "tank", [
        ("2.0T 4WD", "ICE", "AWD", 162, None, None, ""),
    ]),
    ("Tank", "500", "E-SUV", "suv", "TANK", 2022, "tank", [
        ("3.0T 4WD", "ICE", "AWD", 260, None, None, ""),
    ]),
    ("Deepal", "S07", "D-SUV", "suv", "EPA1", 2023, "deepal", [
        ("BEV RWD", "BEV", "RWD", 160, 79.97, 475, "WLTP"),
    ]),
    ("Lynk & Co", "01", "C-SUV", "suv", "CMA", 2017, "lynkco", [
        ("PHEV FWD", "PHEV", "FWD", 192, 17.6, 69, "WLTP"),
    ]),
    ("Lynk & Co", "02", "C-SUV", "suv", "SEA", 2024, "lynkco", [
        ("BEV RWD", "BEV", "RWD", 200, 66, 445, "WLTP"),
    ]),
    ("Omoda", "C5", "B-SUV", "suv", "T1X", 2022, "omoda", [
        ("1.5T FWD", "ICE", "FWD", 108, None, None, ""),
        ("1.6T FWD", "ICE", "FWD", 137, None, None, ""),
    ]),
    ("Omoda", "E5", "B-SUV", "suv", "E0X", 2023, "omoda", [
        ("BEV FWD", "BEV", "FWD", 150, 61, 430, "WLTP"),
    ]),
]

BRANDS = {
    "BYD": ("BYD Company", 1995, 2003, "byd"),
    "Zeekr": ("Geely Holding", 1986, 2021, "zeekr"),
    "Geely": ("Geely Holding", 1986, 1997, "geely"),
    "Chery": ("Chery Automobile", 1997, 1997, "chery"),
    "Li Auto": ("Li Auto Inc.", 2015, 2015, "li-auto"),
    "NIO": ("NIO Inc.", 2014, 2014, "nio"),
    "Xiaomi": ("Xiaomi Corporation", 2010, 2021, "xiaomi"),
    "Hongqi": ("FAW Group", 1953, 1958, "hongqi"),
    "XPeng": ("XPeng Inc.", 2014, 2014, "xpeng"),
    "Leapmotor": ("Zhejiang Leapmotor Technology", 2015, 2015, "leapmotor"),
    "Haval": ("Great Wall Motor", 1984, 2013, "gwm"),
    "Tank": ("Great Wall Motor", 1984, 2021, "tank"),
    "Deepal": ("Changan Automobile", 1862, 2022, "deepal"),
    "Lynk & Co": ("Geely Holding", 1986, 2016, "lynkco"),
    "Omoda": ("Chery Automobile", 1997, 2022, "omoda"),
}


# Freely licensed photos hosted on Wikimedia Commons (hotlinked, not stored).
# Credit = author, license and Commons file name, as required by CC BY / CC BY-SA.
# Some photos show the Chinese-market twin: Seal U DM-i = Song Plus DM-i,
# EX5 = Galaxy E5, Monjaro = Xingyue L, Tiggo 8 Pro Max shown as Tiggo 8 Plus,
# Atlas = Boyue L, Omoda C5 = Chery Omoda 5.
MODEL_IMAGES = {
    'byd-dolphin': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/4/44/BYD_Dolphin_IAA_2023_1X7A0634.jpg/960px-BYD_Dolphin_IAA_2023_1X7A0634.jpg',
        'Alexander-93, CC BY-SA 4.0, Wikimedia Commons (BYD_Dolphin_IAA_2023_1X7A0634.jpg)',
    ),
    'byd-atto-3': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/7/78/BYD_Atto_3_1X7A6495.jpg/960px-BYD_Atto_3_1X7A6495.jpg',
        'Alexander Migl, CC BY-SA 4.0, Wikimedia Commons (BYD_Atto_3_1X7A6495.jpg)',
    ),
    'zeekr-7x': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/Zeekr_7X_005_%28cropped%29.jpg/960px-Zeekr_7X_005_%28cropped%29.jpg',
        'JustAnotherCarDesigner, CC0, Wikimedia Commons (Zeekr_7X_005_(cropped).jpg)',
    ),
    'nio-et7': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/NIO_ET7_1X7A6682.jpg/960px-NIO_ET7_1X7A6682.jpg',
        'Alexander Migl, CC BY-SA 4.0, Wikimedia Commons (NIO_ET7_1X7A6682.jpg)',
    ),
    'li-auto-l9': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Li_L9%2C_Almaty_%28P1180247%29.jpg/960px-Li_L9%2C_Almaty_%28P1180247%29.jpg',
        'Matti Blume, CC BY-SA 4.0, Wikimedia Commons (Li_L9,_Almaty_(P1180247).jpg)',
    ),
    'li-auto-mega': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/a/a8/Li_Auto_Mega_20240403.jpg/960px-Li_Auto_Mega_20240403.jpg',
        'Evnerd, CC0, Wikimedia Commons (Li_Auto_Mega_20240403.jpg)',
    ),
    'xpeng-g6': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/4/49/XPeng_G6_%282025%29_IAA_2025_DSC_2057.jpg/960px-XPeng_G6_%282025%29_IAA_2025_DSC_2057.jpg',
        'Alexander-93, CC BY-SA 4.0, Wikimedia Commons (XPeng_G6_(2025)_IAA_2025_DSC_2057.jpg)',
    ),
    'xpeng-g9': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/4/42/XPeng_G9_IAA_2023_1X7A0192.jpg/960px-XPeng_G9_IAA_2023_1X7A0192.jpg',
        'Alexander-93, CC BY-SA 4.0, Wikimedia Commons (XPeng_G9_IAA_2023_1X7A0192.jpg)',
    ),
    'leapmotor-c10': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/3/36/Leapmotor_C10_IAA_2023_1X7A0248.jpg/960px-Leapmotor_C10_IAA_2023_1X7A0248.jpg',
        'Alexander-93, CC BY-SA 4.0, Wikimedia Commons (Leapmotor_C10_IAA_2023_1X7A0248.jpg)',
    ),
    'leapmotor-t03': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/9/92/Leapmotor_T03_DSC_8024.jpg/960px-Leapmotor_T03_DSC_8024.jpg',
        'Alexander Migl, CC BY-SA 4.0, Wikimedia Commons (Leapmotor_T03_DSC_8024.jpg)',
    ),
    'haval-jolion': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/d/d5/GWM_Haval_Jolion_Pro_Leonberg_2026_IMG_8660.jpg/960px-GWM_Haval_Jolion_Pro_Leonberg_2026_IMG_8660.jpg',
        'Alexander Migl, CC BY-SA 4.0, Wikimedia Commons (GWM_Haval_Jolion_Pro_Leonberg_2026_IMG_8660.jpg)',
    ),
    'haval-dargo': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/e/ee/2025_Haval_Dargo_Premium_4WD_black_front.jpg/960px-2025_Haval_Dargo_Premium_4WD_black_front.jpg',
        'Throwawayacc222, CC0, Wikimedia Commons (2025_Haval_Dargo_Premium_4WD_black_front.jpg)',
    ),
    'tank-300': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/%D0%90%D0%BB%D0%BC%D0%B0%D1%82%D1%8B%2C_Tank_300_%D0%BD%D0%B0_%D0%9A%D0%B0%D1%80%D0%B8%D0%BC%D0%BE%D0%B2%D0%B0.jpg/960px-%D0%90%D0%BB%D0%BC%D0%B0%D1%82%D1%8B%2C_Tank_300_%D0%BD%D0%B0_%D0%9A%D0%B0%D1%80%D0%B8%D0%BC%D0%BE%D0%B2%D0%B0.jpg',
        'Nikolai Bulykin, CC BY-SA 4.0, Wikimedia Commons (Алматы,_Tank_300_на_Каримова.jpg)',
    ),
    'tank-500': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/d/de/Tank_500%2C_Astana_%28P1190744%29.jpg/960px-Tank_500%2C_Astana_%28P1190744%29.jpg',
        'Matti Blume, CC BY-SA 4.0, Wikimedia Commons (Tank_500,_Astana_(P1190744).jpg)',
    ),
    'deepal-s07': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/3/31/Deepal_S07_IAA_2025_DSC_1897.jpg/960px-Deepal_S07_IAA_2025_DSC_1897.jpg',
        'Alexander Migl, CC BY-SA 4.0, Wikimedia Commons (Deepal_S07_IAA_2025_DSC_1897.jpg)',
    ),
    'lynk-co-01': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/b/b5/Lynk_%26_Co_01_PHEV_1X7A0262.jpg/960px-Lynk_%26_Co_01_PHEV_1X7A0262.jpg',
        'Alexander Migl, CC BY-SA 4.0, Wikimedia Commons (Lynk_&_Co_01_PHEV_1X7A0262.jpg)',
    ),
    'lynk-co-02': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/8/80/2025_Lynk_%26_Co_02_IAA_2025_DSC_2310.jpg/960px-2025_Lynk_%26_Co_02_IAA_2025_DSC_2310.jpg',
        'Alexander-93, CC BY-SA 4.0, Wikimedia Commons (2025_Lynk_&_Co_02_IAA_2025_DSC_2310.jpg)',
    ),
    'omoda-c5': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/e/e2/Chery_Omoda_5_003.jpg/960px-Chery_Omoda_5_003.jpg',
        'Zoerides, CC BY-SA 4.0, Wikimedia Commons (Chery_Omoda_5_003.jpg)',
    ),
    'omoda-e5': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/Omoda_E5_IMG_8096.jpg/960px-Omoda_E5_IMG_8096.jpg',
        'Alexander Migl, CC BY-SA 4.0, Wikimedia Commons (Omoda_E5_IMG_8096.jpg)',
    ),
    'geely-coolray': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/Moscow_-_2026_-_Geely_Coolray_compact_crossover.jpg/960px-Moscow_-_2026_-_Geely_Coolray_compact_crossover.jpg',
        'Юрий Д.К., CC BY 4.0, Wikimedia Commons (Moscow_-_2026_-_Geely_Coolray_compact_crossover.jpg)',
    ),
    'geely-atlas': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/6/6d/2023_Geely_Boyue_L_%282%29%2C_front_8.3.23.jpg/960px-2023_Geely_Boyue_L_%282%29%2C_front_8.3.23.jpg',
        'Kevauto, CC BY-SA 4.0, Wikimedia Commons (2023_Geely_Boyue_L_(2),_front_8.3.23.jpg)',
    ),
    'byd-seal': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/6/60/2022_BYD_Seal.jpg/960px-2022_BYD_Seal.jpg',
        'User3204, CC BY-SA 4.0, Wikimedia Commons (2022_BYD_Seal.jpg)',
    ),
    'byd-seal-u-dm-i': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/0/02/2023_BYD_Song_Plus_DM-i_%28front%29.jpg/960px-2023_BYD_Song_Plus_DM-i_%28front%29.jpg',
        'User3204, CC BY-SA 4.0, Wikimedia Commons (2023_BYD_Song_Plus_DM-i_(front).jpg)',
    ),
    'chery-tiggo-7-csh': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/7/76/Chery_Tiggo_7_II_014_%28cropped%29.jpg/960px-Chery_Tiggo_7_II_014_%28cropped%29.jpg',
        'JustAnotherCarDesigner, CC BY-SA 4.0, Wikimedia Commons (Chery_Tiggo_7_II_014_(cropped).jpg)',
    ),
    'chery-tiggo-8-pro-max': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/3/37/Chery_Tiggo_8_Plus_018_%28cropped%29.jpg/960px-Chery_Tiggo_8_Plus_018_%28cropped%29.jpg',
        'JustAnotherCarDesigner, CC0, Wikimedia Commons (Chery_Tiggo_8_Plus_018_(cropped).jpg)',
    ),
    'geely-ex5': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/c/cf/Geely_Galaxy_E5_003_%28cropped%29.jpg/960px-Geely_Galaxy_E5_003_%28cropped%29.jpg',
        'JustAnotherCarDesigner, CC0, Wikimedia Commons (Geely_Galaxy_E5_003_(cropped).jpg)',
    ),
    'geely-monjaro': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/6/6c/2021_Geely_Xingyue_L_%28front%29.jpg/960px-2021_Geely_Xingyue_L_%28front%29.jpg',
        'User3204, CC BY-SA 4.0, Wikimedia Commons (2021_Geely_Xingyue_L_(front).jpg)',
    ),
    'hongqi-e-hs9': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/1/12/Hongqi_E-HS9_IMG_0753_%28cropped%29.jpg/960px-Hongqi_E-HS9_IMG_0753_%28cropped%29.jpg',
        'Alexander-93, CC BY-SA 4.0, Wikimedia Commons (Hongqi_E-HS9_IMG_0753_(cropped).jpg)',
    ),
    'hongqi-h5': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/c/c9/Hongqi_H5_2023.jpg/960px-Hongqi_H5_2023.jpg',
        'Milhouse35, CC BY-SA 4.0, Wikimedia Commons (Hongqi_H5_2023.jpg)',
    ),
    'li-auto-l6': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/a/a3/%28CHN-Shanghai%29_Showcar_Li_L6_No-plate_2024-12-11.jpg/960px-%28CHN-Shanghai%29_Showcar_Li_L6_No-plate_2024-12-11.jpg',
        'S5A-0043, CC BY 4.0, Wikimedia Commons ((CHN-Shanghai)_Showcar_Li_L6_No-plate_2024-12-11.jpg)',
    ),
    'li-auto-l7': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/e/ed/Li_Auto_L7_008.jpg/960px-Li_Auto_L7_008.jpg',
        'Quzhouliulian, CC0, Wikimedia Commons (Li_Auto_L7_008.jpg)',
    ),
    'nio-es6': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/2/2c/%28CHN-Guangdong%29_Showcar_Nio_ES6_No-plate_2024-05-25.jpg/960px-%28CHN-Guangdong%29_Showcar_Nio_ES6_No-plate_2024-05-25.jpg',
        'S5A-0043, CC BY 2.0, Wikimedia Commons ((CHN-Guangdong)_Showcar_Nio_ES6_No-plate_2024-05-25.jpg)',
    ),
    'nio-et5': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/NIO_ET5_IMG_8291.jpg/960px-NIO_ET5_IMG_8291.jpg',
        'Alexander-93, CC BY-SA 4.0, Wikimedia Commons (NIO_ET5_IMG_8291.jpg)',
    ),
    'xiaomi-su7': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/f/fc/%28CHN-Shanghai%29_Private_Xiaomi_SU7_%E6%B2%AAA7WE106_2024-11-24.jpg/960px-%28CHN-Shanghai%29_Private_Xiaomi_SU7_%E6%B2%AAA7WE106_2024-11-24.jpg',
        'S5A-0043, CC BY 4.0, Wikimedia Commons ((CHN-Shanghai)_Private_Xiaomi_SU7_沪A7WE106_2024-11-24.jpg)',
    ),
    'xiaomi-yu7': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/1/13/Xiaomi_YU7_Emerald_Green_Metallic_01.jpg/960px-Xiaomi_YU7_Emerald_Green_Metallic_01.jpg',
        'Ethan Llamas, CC BY-SA 4.0, Wikimedia Commons (Xiaomi_YU7_Emerald_Green_Metallic_01.jpg)',
    ),
    'zeekr-001': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/0/0a/2022_Zeekr_001_%28front%29.jpg/960px-2022_Zeekr_001_%28front%29.jpg',
        'User3204, CC BY-SA 4.0, Wikimedia Commons (2022_Zeekr_001_(front).jpg)',
    ),
    'zeekr-x': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/3/34/2023_Zeekr_X_%28front%29.jpg/960px-2023_Zeekr_X_%28front%29.jpg',
        'User3204, CC BY-SA 4.0, Wikimedia Commons (2023_Zeekr_X_(front).jpg)',
    ),
}

# Text logos marked public domain on Wikimedia Commons. Hongqi has no free logo there,
# so its logo file is shipped with the project in static/img/brands/.
BRAND_LOGOS = {
    'xpeng': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/c/ca/XPeng_logo.svg/250px-XPeng_logo.svg.png',
        'Логотип XPeng logo.svg, public domain, Wikimedia Commons',
    ),
    'leapmotor': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Leapmotor_logo_zh.svg/250px-Leapmotor_logo_zh.svg.png',
        'Логотип Leapmotor logo zh.svg, public domain, Wikimedia Commons',
    ),
    'haval': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/d/da/Haval_2023_logo.svg/250px-Haval_2023_logo.svg.png',
        'Логотип Haval 2023 logo.svg, public domain, Wikimedia Commons',
    ),
    'tank': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/6/64/Tank_%28Great_Wall_Motor_brand%29_logo%2C_global_market.svg/250px-Tank_%28Great_Wall_Motor_brand%29_logo%2C_global_market.svg.png',
        'Логотип Tank (Great Wall Motor brand) logo, global market.svg, public domain, Wikimedia Commons',
    ),
    'deepal': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/c/c0/Deepal_global_logo.svg/250px-Deepal_global_logo.svg.png',
        'Логотип Deepal global logo.svg, public domain, Wikimedia Commons',
    ),
    'lynk-co': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/9/95/Lynk_%26_Co_2016_logo.svg/250px-Lynk_%26_Co_2016_logo.svg.png',
        'Логотип Lynk & Co 2016 logo.svg, public domain, Wikimedia Commons',
    ),
    'omoda': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/b/b0/Omoda_Logo.jpg/250px-Omoda_Logo.jpg',
        'Логотип Omoda Logo.jpg, public domain, Wikimedia Commons',
    ),
    'byd': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/e/e2/BYD_Auto_2022_logo.svg/250px-BYD_Auto_2022_logo.svg.png',
        'Логотип BYD Auto 2022 logo.svg, public domain, Wikimedia Commons',
    ),
    'chery': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/b/b6/Chery_logo.svg/250px-Chery_logo.svg.png',
        'Логотип Chery logo.svg, public domain, Wikimedia Commons',
    ),
    'geely': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/Geely_Auto_2023.svg/250px-Geely_Auto_2023.svg.png',
        'Логотип Geely Auto 2023.svg, public domain, Wikimedia Commons',
    ),
    'li-auto': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/Li_Auto_logo.svg/250px-Li_Auto_logo.svg.png',
        'Логотип Li Auto logo.svg, public domain, Wikimedia Commons',
    ),
    'nio': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/c/ca/NIO_logo.svg/250px-NIO_logo.svg.png',
        'Логотип NIO logo.svg, public domain, Wikimedia Commons',
    ),
    'xiaomi': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/c/cb/Xiaomi_Auto_logo.svg/250px-Xiaomi_Auto_logo.svg.png',
        'Логотип Xiaomi Auto logo.svg, public domain, Wikimedia Commons',
    ),
    'zeekr': (
        'https://upload.wikimedia.org/wikipedia/commons/thumb/1/1e/Zeekr_logo.svg/250px-Zeekr_logo.svg.png',
        'Логотип Zeekr logo.svg, public domain, Wikimedia Commons',
    ),
    'hongqi': (
        '/static/img/brands/hongqi.png',
        'Логотип Hongqi — товарный знак FAW Group, используется для обозначения марки; файл предоставлен автором проекта',
    ),
}


class Command(BaseCommand):
    help = "Load the idempotent, source-backed course knowledge-base dataset."

    @transaction.atomic
    def handle(self, *args, **options):
        # Preserve and upgrade the original demonstration scenario on an empty DB.
        # Calling the legacy command again after this richer seed has updated codes
        # would make its code-based generation lookup collide with the stable name.
        if not (Model.objects.filter(brand__name="BYD", name="Seal").exists() and Model.objects.filter(brand__name="Zeekr", name="001").exists()):
            call_command("load_demo_data", verbosity=0)
        self._remove_superseded_course_rows()
        china, _ = Country.objects.update_or_create(iso_code="CN", defaults={"name": "Китай"})
        sources = self._sources()
        brands = {}
        # One manufacturer may own several brands (Great Wall: Haval and Tank).
        brand_names_by_manufacturer = {}
        for brand_name, (manufacturer_name, *_rest) in BRANDS.items():
            brand_names_by_manufacturer.setdefault(manufacturer_name, []).append(brand_name)
        for brand_name, (manufacturer_name, founded, brand_founded, source_key) in BRANDS.items():
            owned = ", ".join(brand_names_by_manufacturer[manufacturer_name])
            manufacturer, _ = Manufacturer.objects.update_or_create(
                name=manufacturer_name,
                defaults={
                    "slug": self._slug(manufacturer_name), "country": china,
                    "founded_year": founded, "description": f"Китайский производитель; марки в базе: {owned}.",
                    "source_url": SOURCES[source_key][2], "source_note": "Официальный сайт производителя.",
                },
            )
            brand, _ = Brand.objects.update_or_create(
                manufacturer=manufacturer, name=brand_name,
                defaults={
                    "slug": self._slug(brand_name), "origin_country": china,
                    "founded_year": brand_founded, "description": f"Китайская автомобильная марка {brand_name}.",
                    "source_url": SOURCES[source_key][2], "source_note": "Официальный сайт марки.",
                },
            )
            brands[brand_name] = brand

        body_types = {
            code: BodyType.objects.update_or_create(code=code, defaults={"name": name})[0]
            for code, name in (("sedan", "Седан"), ("suv", "Кроссовер / SUV"), ("liftback", "Лифтбэк"), ("hatchback", "Хэтчбек"), ("minivan", "Минивэн"))
        }
        drives = {
            code: DriveType.objects.update_or_create(code=code, defaults={"name": name})[0]
            for code, name in (("FWD", "Передний привод"), ("RWD", "Задний привод"), ("AWD", "Полный привод"))
        }
        technologies = self._technologies()
        adas = self._adas()
        china_market, _ = Market.objects.update_or_create(code="CN", defaults={"name": "Китай", "country": china})

        seeded_models = {}
        for brand_name, model_name, segment, body, platform_name, start_year, source_key, variants in VEHICLES:
            brand = brands[brand_name]
            # A platform can be shared by brands of one group (SEA: Zeekr and Lynk & Co),
            # so its slug is set only on creation and stays stable afterwards.
            platform, _ = Platform.objects.update_or_create(
                manufacturer=brand.manufacturer, name=platform_name,
                defaults={"description": f"Архитектура {platform_name}."},
                create_defaults={"slug": self._slug(f"{brand_name}-{platform_name}"), "description": f"Архитектура {platform_name}.", "source_url": SOURCES[source_key][2]},
            )
            model, _ = Model.objects.update_or_create(
                brand=brand, name=model_name,
                defaults={"slug": self._slug(f"{brand_name}-{model_name}"), "segment": segment, "description": f"{brand_name} {model_name}: серийная модель актуального поколения.", "source_url": SOURCES[source_key][2], "source_note": "Рынок и версия указаны на уровне модификации."},
            )
            seeded_models[f"{brand_name} {model_name}"] = model
            generation = model.generations.order_by("start_year").first()
            generation_values = {"code": str(start_year), "platform": platform, "body_type": body_types[body], "start_year": start_year, "description": f"Поколение {model_name}, выпускаемое с {start_year} года.", "source_url": SOURCES[source_key][2]}
            if generation is None:
                generation = Generation.objects.create(model=model, name="Актуальное поколение", **generation_values)
            else:
                for field, value in generation_values.items():
                    setattr(generation, field, value)
                generation.save()
            tech = self._technology_for(platform_name, technologies)
            if tech:
                ModelTechnology.objects.update_or_create(model=model, technology=tech, defaults={"note": f"Связано с архитектурой {platform_name}."})
            for variant in variants:
                self._variant(model, generation, drives, china_market, adas, source_key, *variant)

        self._content(seeded_models, technologies, adas, sources)
        self._images()
        self.stdout.write(self.style.SUCCESS(
            f"Course data ready: {Brand.objects.count()} brands, {Model.objects.count()} models, "
            f"{Modification.objects.count()} modifications, {Article.objects.count()} articles."
        ))

    def _images(self):
        for slug, (url, credit) in MODEL_IMAGES.items():
            Model.objects.filter(slug=slug).update(image_url=url, image_credit=credit)
        for slug, (url, credit) in BRAND_LOGOS.items():
            Brand.objects.filter(slug=slug).update(image_url=url, image_credit=credit)

    def _sources(self):
        result = {}
        for key, (name, publisher, url) in SOURCES.items():
            result[key], _ = Source.objects.update_or_create(
                url=url, defaults={"name": name, "publisher": publisher, "accessed_at": ACCESSED_AT, "notes": "Официальный сайт или официальный материал производителя.", "is_active": True},
            )
        return result

    def _remove_superseded_course_rows(self):
        """Remove only obsolete rows created by an earlier revision of this command."""
        slugs = ("byd-seal-design-rwd", "zeekr-001-performance-awd")
        obsolete = list(Modification.objects.filter(slug__in=slugs, source_note__startswith="Конкретная версия"))
        powertrain_ids = [item.powertrain_id for item in obsolete]
        Modification.objects.filter(pk__in=[item.pk for item in obsolete]).delete()
        Powertrain.objects.filter(pk__in=powertrain_ids, modifications__isnull=True, source_note__startswith="course:").delete()

    def _technologies(self):
        rows = [
            ("Blade Battery", "Батареи", "LFP-батарея BYD с ячейками лезвийного формата.", "blade"),
            ("e-Platform 3.0", "Платформы", "Электромобильная платформа BYD.", "byd"),
            ("DM-i Super Hybrid", "Гибриды", "Подключаемая гибридная архитектура BYD.", "byd"),
            ("SEA Architecture", "Платформы", "Масштабируемая электрическая архитектура Geely Holding.", "sea"),
            ("Cell-to-Body", "Батареи", "Интеграция батареи в силовую структуру кузова.", "byd"),
            ("800-volt architecture", "Зарядка", "Высоковольтная архитектура для высокой мощности зарядки.", "xiaomi"),
            ("NIO Battery Swap", "Зарядка", "Система автоматизированной замены тяговой батареи NIO.", "nio"),
            ("Li Auto range extender", "Гибриды", "Последовательная EREV-архитектура Li Auto.", "li-auto"),
            ("Chery Super Hybrid", "Гибриды", "Подключаемая гибридная система семейства Chery CSH.", "chery"),
        ]
        result = {}
        for name, category, description, source_key in rows:
            result[name], _ = Technology.objects.update_or_create(
                name=name, defaults={"slug": self._slug(name), "category": category, "description": description, "source_url": SOURCES[source_key][2], "source_note": "Официальный материал производителя."},
            )
        return result

    def _adas(self):
        rows = [
            ("Адаптивный круиз-контроль", "adaptive-cruise-control", "Продольное управление"),
            ("Ассистент удержания в полосе", "lane-keeping-assist", "Поперечное управление"),
            ("Автоматическое экстренное торможение", "automatic-emergency-braking", "Активная безопасность"),
            ("Контроль слепых зон", "blind-spot-monitoring", "Контроль окружения"),
            ("Парковочный ассистент", "parking-assistance", "Парковка"),
        ]
        result = []
        for name, slug, category in rows:
            item, _ = DriverAssistanceSystem.objects.update_or_create(
                name=name, defaults={"slug": slug, "category": category, "level": "Функция ADAS", "description": f"Типовая функция ADAS: {name.lower()}."},
            )
            result.append(item)
        return result

    def _variant(self, model, generation, drives, market, adas, source_key, name, pt_type, drive, power, capacity, range_km, cycle, extras=None):
        token = self._slug(f"{model.brand.name}-{model.name}-{name}")
        manufacturer = model.brand.manufacturer
        battery = engine = motor = None
        if pt_type != "ICE":
            battery, _ = Battery.objects.update_or_create(
                manufacturer=manufacturer, name=f"{model.brand.name} {model.name} {capacity} кВт·ч",
                defaults={"chemistry": "", "gross_capacity_kwh": Decimal(str(capacity)), "source_url": SOURCES[source_key][2]},
            )
            motor, _ = ElectricMotor.objects.update_or_create(
                manufacturer=manufacturer, code=f"COURSE-{token[:80]}",
                defaults={"motor_type": "Тяговый электродвигатель", "power_kw": Decimal(str(power)), "source_url": SOURCES[source_key][2]},
            )
        if pt_type in {"ICE", "PHEV", "EREV", "HEV"}:
            engine, _ = CombustionEngine.objects.update_or_create(
                manufacturer=manufacturer, code=f"COURSE-ICE-{self._slug(model.name)[:60]}",
                defaults={"fuel_type": CombustionEngine.FuelType.PETROL, "induction": "Турбонаддув", "source_url": SOURCES[source_key][2]},
            )
        transmission, _ = Transmission.objects.update_or_create(
            manufacturer=manufacturer, name=f"COURSE {model.name} {pt_type}",
            defaults={"transmission_type": "Редуктор" if pt_type == "BEV" else "Автоматическая", "gears": 1 if pt_type == "BEV" else None, "source_url": SOURCES[source_key][2]},
        )
        powertrain, _ = Powertrain.objects.update_or_create(
            source_note=f"course:{token}",
            defaults={"type": pt_type, "combustion_engine": engine, "battery": battery, "transmission": transmission, "drive_type": drives[drive], "system_power_kw": Decimal(str(power)), "source_url": SOURCES[source_key][2]},
        )
        if motor:
            PowertrainMotor.objects.update_or_create(powertrain=powertrain, electric_motor=motor, axle="front" if drive == "FWD" else "rear", defaults={"quantity": 1})
        modification, _ = Modification.objects.update_or_create(
            slug=token,
            defaults={**(extras or {}), "generation": generation, "name": name, "powertrain": powertrain, "seats": 5, "range_km": range_km, "range_cycle": cycle, "source_url": SOURCES[source_key][2], "source_note": "Конкретная версия из официального модельного ряда; неизвестные поля не заполнены."},
        )
        offer, _ = ModificationMarket.objects.update_or_create(
            modification=modification, market=market,
            defaults={"sales_name": f"{model.brand.name} {model.name} {name}", "available_from": date(generation.start_year, 1, 1)},
        )
        TrimLevel.objects.update_or_create(
            modification_market=offer, name=name,
            defaults={"price_amount": None, "currency_code": "", "valid_from": None, "equipment_summary": "Цена не внесена: она зависит от даты и локального рынка.", "is_active": True},
        )
        # Official equipment differs by market; attach the conservative core set only.
        for system in adas[:3]:
            ModificationADAS.objects.update_or_create(modification=modification, adas=system, defaults={"availability": ModificationADAS.Availability.STANDARD, "note": "Состав следует сверять с локальной комплектацией."})

    def _content(self, models, technologies, adas, sources):
        user, created = get_user_model().objects.get_or_create(username="course_editor", defaults={"email": "course@example.com"})
        if created:
            user.set_unusable_password(); user.save(update_fields=["password"])
        categories = {}
        category_slugs = {"Производители": "manufacturers", "Электромобили": "electric-vehicles", "Гибриды": "hybrids", "Технологии": "technologies", "Безопасность": "safety", "Платформы": "platforms", "Системы помощи водителю": "adas"}
        for name, slug in category_slugs.items():
            categories[name], _ = Category.objects.update_or_create(name=name, defaults={"slug": slug, "description": f"Материалы по теме «{name}»."})
        tags = {}
        for name in ("BYD", "Zeekr", "BEV", "PHEV", "EREV", "Battery", "ADAS", "SEA", "Blade Battery"):
            tags[name], _ = Tag.objects.update_or_create(name=name, defaults={"slug": self._slug(name)})
        articles = [
            ("chinese-auto-industry", "Китайский автопром: структура и направления", "Производители", "Китайский автопром объединяет крупные концерны, самостоятельные марки и технологические компании. База знаний разделяет производителя, бренд, модель, поколение и модификацию, поэтому корпоративные связи не смешиваются с техническими характеристиками. Представленный набор показывает экспортные и внутренние модели без попытки охватить весь рынок.", ["geely", "chery"], [], []),
            ("china-electric-vehicles", "Электромобили Китая", "Электромобили", "Китайские BEV используют разные платформы, батарейные химии и схемы привода. В каталоге представлены городские кроссоверы, седаны и крупные SUV. Запас хода всегда следует читать вместе с циклом измерения: CLTC и WLTP нельзя считать взаимозаменяемыми.", ["byd", "zeekr", "nio", "xiaomi"], ["BYD Seal", "NIO ET5", "Xiaomi SU7"], []),
            ("powertrain-types", "BEV, HEV, PHEV и EREV: в чём различие", "Гибриды", "BEV движется только за счёт электротяги. PHEV допускает внешнюю зарядку и сочетает ДВС с электрической частью. EREV использует электрический привод, а ДВС преимущественно вырабатывает энергию. HEV не требует внешней зарядки. Эти типы хранятся отдельно, чтобы фильтрация и сравнение оставались однозначными.", ["byd", "li-auto"], ["BYD Seal U DM-i", "Li Auto L6"], []),
            ("blade-battery-course", "Blade Battery: назначение и применение", "Технологии", "Blade Battery — фирменная LFP-технология BYD. Длинные ячейки компонуются в батарейный блок с высокой эффективностью использования пространства. В базе технология отделена от конкретной батареи: одна описывает идею, другая — компонент определённой ёмкости.", ["blade", "byd"], ["BYD Seal"], ["Blade Battery"]),
            ("sea-platform-course", "Платформа SEA и автомобили Zeekr", "Платформы", "SEA — масштабируемая электрическая архитектура Geely Holding. Она служит основой для моделей разных классов. Связь платформы с поколением позволяет не приписывать одну архитектуру всем автомобилям бренда автоматически.", ["sea", "zeekr"], ["Zeekr 001", "Zeekr X"], ["SEA Architecture"]),
            ("high-voltage-ev", "Высоковольтные архитектуры электромобилей", "Технологии", "Повышение рабочего напряжения помогает передавать ту же мощность меньшим током и поддерживать быструю зарядку. Реальная скорость зарядки зависит не только от напряжения, но и от батареи, температуры, зарядной станции и программного управления.", ["xiaomi", "byd"], ["Xiaomi SU7"], ["800-volt architecture"]),
            ("adas-china", "Системы ADAS в китайских автомобилях", "Системы помощи водителю", "ADAS объединяет функции контроля дистанции, полосы, препятствий и парковки. Наличие функции не означает автономное вождение. Оснащение необходимо проверять для конкретной комплектации и рынка, поэтому база связывает ADAS с модификацией и указывает доступность.", ["nio", "zeekr"], [], []),
            ("major-chinese-brands", "Марки китайского автопрома в учебной базе", "Производители", "Учебная выборка включает 15 марок: BYD, Zeekr, Geely, Lynk & Co, Chery, Omoda, Haval, Tank, Deepal, Li Auto, NIO, XPeng, Leapmotor, Xiaomi и Hongqi. Несколько марок принадлежат одной группе: Zeekr и Lynk & Co входят в Geely Holding, Omoda — в Chery, Haval и Tank — в Great Wall Motor, Deepal — в Changan. Вместе они показывают массовые и премиальные марки, внедорожники с ДВС, подключаемые и последовательные гибриды и чистые электромобили.", ["byd", "zeekr", "geely", "chery", "li-auto", "nio", "xiaomi", "hongqi", "xpeng", "leapmotor", "gwm", "tank", "deepal", "lynkco", "omoda"], [], []),
            ("byd-development", "Развитие BYD: от батарей к автомобилям", "Производители", "Опыт BYD в аккумуляторах стал основой для электрических и гибридных автомобилей марки. В актуальном модельном ряду сосуществуют BEV и DM-i. Структура базы связывает фирменные технологии с моделями, не дублируя характеристики отдельных модификаций в статье.", ["byd", "blade"], ["BYD Seal", "BYD Seal U DM-i"], ["Blade Battery", "DM-i Super Hybrid"]),
            ("geely-zeekr-development", "Geely и Zeekr: концерн, бренд и платформа", "Производители", "Geely Holding выступает корпоративным уровнем, а Geely и Zeekr — отдельными марками. Такое различие важно для базы знаний: общая архитектура может использоваться связанными брендами, но модель всегда принадлежит конкретной марке.", ["geely", "zeekr", "sea"], ["Geely EX5", "Zeekr 001"], ["SEA Architecture"]),
        ]
        created_articles = {}
        published = datetime(2026, 9, 1, 9, 0, tzinfo=dt_timezone.utc)
        for slug, title, category, body, source_keys, model_keys, tech_names in articles:
            article, _ = Article.objects.update_or_create(
                slug=slug, defaults={"category": categories[category], "author": user, "title": title, "summary": body.split(". ")[0] + ".", "body": body, "status": Article.Status.PUBLISHED, "published_at": published},
            )
            article.sources.set([sources[k] for k in source_keys if k in sources])
            article.vehicle_models.set([models[k] for k in model_keys if k in models])
            article.technologies.set([technologies[k] for k in tech_names if k in technologies])
            article.tags.set([tag for name, tag in tags.items() if name.casefold() in (title + " " + body).casefold()])
            if slug == "adas-china": article.adas_systems.set(adas)
            created_articles[slug] = article
        # Concrete videos from manufacturers' official YouTube channels. Each ID was checked
        # with YouTube oEmbed (the uploader is the brand's channel and embedding is allowed).
        # Models without a verifiable official video simply have no video block.
        videos = [
            ("BYD SEAL — тизер", "HQc_8l5khc0", "BYD AsiaPacific", None, "Официальный тизер BYD SEAL: дизайн в стиле Ocean.", "blade-battery-course", ["BYD Seal"], "Blade Battery"),
            ("How Räikkönen Mode Works on ZEEKR 001 FR", "jUs6cQkl4Ug", "Zeekr", date(2024, 2, 7), "Официальный ролик Zeekr о режиме Räikkönen Mode версии ZEEKR 001 FR.", "sea-platform-course", ["Zeekr 001"], "SEA Architecture"),
            ("Zeekr X | More technology. More power.", "vTSGPLqvcvc", "Zeekr Europe", None, "Официальный ролик Zeekr Europe о компактном кроссовере Zeekr X.", None, ["Zeekr X"], "SEA Architecture"),
            ("Xiaomi MWC 2025 | Xiaomi SU7 Ultra global debut", "N1f76YiT3v4", "Xiaomi", date(2025, 3, 2), "Официальная мировая премьера Xiaomi SU7 Ultra на MWC 2025.", "high-voltage-ev", ["Xiaomi SU7"], "800-volt architecture"),
            ("The 2026 ET5T Champion Edition", "OJJYhO0_4PI", "NIO", date(2026, 6, 16), "Официальный ролик NIO о ET5T — универсальной версии ET5.", "china-electric-vehicles", ["NIO ET5"], None),
            ("Geely Ice Drive | Geely EX5, The Power Across Winter", "R9Cj6TWam6M", "Geely Auto", None, "Официальный ролик Geely Auto о зимних испытаниях Geely EX5.", None, ["Geely EX5"], None),
            ("Geely Monjaro | CCD Dynamic Damping Suspension System", "oSk0tgao99s", "Geely Auto", date(2026, 11, 16), "Официальный ролик Geely Auto о подвеске с адаптивными амортизаторами Monjaro.", None, ["Geely Monjaro"], None),
            ("Why Li Auto?", "xg2x21o5u0A", "Li Auto Global", date(2026, 10, 27), "Официальный имиджевый ролик Li Auto о марке и её семейных EREV-кроссоверах.", "powertrain-types", ["Li Auto L6", "Li Auto L7"], "Li Auto range extender"),
        ]
        # Earlier versions linked to channels or video pages instead of concrete videos;
        # those rows are converted in place so existing relations keep their primary keys.
        replaced_video_urls = {
            "https://www.youtube.com/watch?v=7sDqJ8o9h5s": "https://www.youtube.com/watch?v=HQc_8l5khc0",
            "https://en.byd.com/auto/videos/": "https://www.youtube.com/watch?v=HQc_8l5khc0",
            "https://www.youtube.com/@ZEEKRGlobal": "https://www.youtube.com/watch?v=jUs6cQkl4Ug",
            "https://www.youtube.com/@NIO": "https://www.youtube.com/watch?v=OJJYhO0_4PI",
            "https://www.nio.com/videos": "https://www.youtube.com/watch?v=OJJYhO0_4PI",
            "https://www.youtube.com/@xiaomi": "https://www.youtube.com/watch?v=N1f76YiT3v4",
            "https://www.youtube.com/@LiAutoGlobal": "https://www.youtube.com/watch?v=xg2x21o5u0A",
            "https://www.liauto.com/about.html": "https://www.youtube.com/watch?v=xg2x21o5u0A",
        }
        for old_url, new_url in replaced_video_urls.items():
            old_video = VideoResource.objects.filter(url=old_url).first()
            if old_video and not VideoResource.objects.filter(url=new_url).exists():
                old_video.url = new_url
                old_video.save(update_fields=["url"])
        # The demo placeholder and the former Chery channel link are not concrete videos.
        VideoResource.objects.filter(
            url__in=["https://example.com/videos/chinese-ev-demo", "https://www.youtube.com/@cheryinternational"]
        ).update(is_active=False)
        for title, video_id, provider, published_on, description, article_slug, model_keys, tech_name in videos:
            video, _ = VideoResource.objects.update_or_create(
                url=f"https://www.youtube.com/watch?v={video_id}",
                defaults={
                    "title": title,
                    "description": description,
                    "provider": provider,
                    "thumbnail_url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                    "published_at": datetime(published_on.year, published_on.month, published_on.day, tzinfo=dt_timezone.utc) if published_on else None,
                    "is_active": True,
                },
            )
            video.articles.set([created_articles[article_slug]] if article_slug in created_articles else [])
            video.vehicle_models.set([models[key] for key in model_keys if key in models])
            video.technologies.set([technologies[tech_name]] if tech_name in technologies else [])

    @staticmethod
    def _technology_for(platform_name, technologies):
        mapping = {"e-Platform 3.0": "e-Platform 3.0", "DM-i": "DM-i Super Hybrid", "SEA": "SEA Architecture", "Li Auto EREV": "Li Auto range extender"}
        return technologies.get(mapping.get(platform_name))

    @staticmethod
    def _slug(value):
        from django.utils.text import slugify
        return slugify(value, allow_unicode=False) or "course-item"
