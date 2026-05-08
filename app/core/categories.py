from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceCategory:
    slug: str
    label: str
    label_hi: str
    group: str
    group_hi: str


SERVICE_CATEGORIES: tuple[ServiceCategory, ...] = (
    ServiceCategory("mens-grooming", "Men's grooming", "मेन्स ग्रूमिंग", "Personal Care", "पर्सनल केयर"),
    ServiceCategory("spa-massage-at-home", "Spa & massage at home", "घर पर स्पा और मसाज", "Personal Care", "पर्सनल केयर"),
    ServiceCategory("salon-at-home", "Salon at home", "घर पर सैलून", "Personal Care", "पर्सनल केयर"),
    ServiceCategory("spa-at-home", "Spa at home", "घर पर स्पा", "Personal Care", "पर्सनल केयर"),
    ServiceCategory("makeup-services", "Makeup Services", "मेकअप सेवा", "Personal Care", "पर्सनल केयर"),
    ServiceCategory("hair-care", "Hair Care", "हेयर केयर", "Personal Care", "पर्सनल केयर"),
    ServiceCategory(
        "skincare-advanced-treatments",
        "Skincare Advanced Treatments",
        "स्किन केयर ट्रीटमेंट",
        "Personal Care",
        "पर्सनल केयर",
    ),
    ServiceCategory("mehndi-services", "Mehndi Services", "मेहंदी सेवा", "Personal Care", "पर्सनल केयर"),
    ServiceCategory("plumber", "Plumber", "प्लंबर", "Cleaning & Handyman", "सफाई और मरम्मत"),
    ServiceCategory("house-cleaning", "House Cleaning", "घर की सफाई", "Cleaning & Handyman", "सफाई और मरम्मत"),
    ServiceCategory("carpenter-service", "Carpenter Service", "कारपेंटर सेवा", "Cleaning & Handyman", "सफाई और मरम्मत"),
    ServiceCategory("pest-control", "Pest Control", "पेस्ट कंट्रोल", "Cleaning & Handyman", "सफाई और मरम्मत"),
    ServiceCategory("painter-service", "Painter Service", "पेंटर सेवा", "Cleaning & Handyman", "सफाई और मरम्मत"),
    ServiceCategory("bike-mechanic", "Bike Mechanic", "बाइक मैकेनिक", "Home Repairs & Maintenance", "घर की मरम्मत"),
    ServiceCategory("car-mechanic", "Car Mechanic", "कार मैकेनिक", "Home Repairs & Maintenance", "घर की मरम्मत"),
    ServiceCategory("mobile-servicing", "Mobile Servicing", "मोबाइल सर्विसिंग", "Home Repairs & Maintenance", "घर की मरम्मत"),
    ServiceCategory("electronic-mechanic", "Electronic Mechanic", "इलेक्ट्रॉनिक मैकेनिक", "Home Repairs & Maintenance", "घर की मरम्मत"),
    ServiceCategory("electrician", "Electrician", "इलेक्ट्रीशियन", "Home Repairs & Maintenance", "घर की मरम्मत"),
    ServiceCategory("ac-fridge-service", "AC/Fridge Service", "AC/फ्रिज सेवा", "Home Repairs & Maintenance", "घर की मरम्मत"),
    ServiceCategory("ro-servicing", "RO Servicing", "RO सर्विसिंग", "Home Repairs & Maintenance", "घर की मरम्मत"),
    ServiceCategory("battery-servicing", "Battery Servicing", "बैटरी सर्विसिंग", "Home Repairs & Maintenance", "घर की मरम्मत"),
    ServiceCategory("computer-service", "Computer Service", "कंप्यूटर सेवा", "Home Repairs & Maintenance", "घर की मरम्मत"),
    ServiceCategory("gas-stove-service", "Gas Stove Service", "गैस स्टोव सेवा", "Home Repairs & Maintenance", "घर की मरम्मत"),
    ServiceCategory("second-hand-device", "Second Hand Device", "सेकंड हैंड डिवाइस", "Other Services", "अन्य सेवाएं"),
    ServiceCategory("camera-servicing", "Camera Servicing", "कैमरा सर्विसिंग", "Other Services", "अन्य सेवाएं"),
    ServiceCategory("cctv-servicing", "CCTV Servicing", "CCTV सर्विसिंग", "Other Services", "अन्य सेवाएं"),
    ServiceCategory("printer-servicing", "Printer Servicing", "प्रिंटर सर्विसिंग", "Other Services", "अन्य सेवाएं"),
    ServiceCategory("e-rickshaw-mechanic", "E-Rickshaw Mechanic", "ई-रिक्शा मैकेनिक", "Other Services", "अन्य सेवाएं"),
    ServiceCategory("water-tank-cleaning", "Water Tank Cleaning", "पानी टंकी सफाई", "Other Services", "अन्य सेवाएं"),
    ServiceCategory("laundry-dry-cleaning", "Laundry & Dry Cleaning", "लॉन्ड्री और ड्राई क्लीनिंग", "Other Services", "अन्य सेवाएं"),
    ServiceCategory("packers-movers", "Packers & Movers", "पैकर्स और मूवर्स", "Other Services", "अन्य सेवाएं"),
    ServiceCategory("car-bike-wash", "Car/Bike Wash", "कार/बाइक वॉश", "Other Services", "अन्य सेवाएं"),
    ServiceCategory("home-tutors", "Home Tutors", "होम ट्यूटर", "Other Services", "अन्य सेवाएं"),
    ServiceCategory("computer-training", "Computer Training", "कंप्यूटर ट्रेनिंग", "Other Services", "अन्य सेवाएं"),
)

CATEGORY_BY_SLUG = {category.slug: category for category in SERVICE_CATEGORIES}


def is_valid_category_slug(slug: str) -> bool:
    return slug in CATEGORY_BY_SLUG
