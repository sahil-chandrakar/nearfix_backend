from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceCategory:
    slug: str
    label: str
    group: str


SERVICE_CATEGORIES: tuple[ServiceCategory, ...] = (
    ServiceCategory("mens-grooming", "Men's grooming", "Personal Care"),
    ServiceCategory("spa-massage-at-home", "Spa & massage at home", "Personal Care"),
    ServiceCategory("salon-at-home", "Salon at home", "Personal Care"),
    ServiceCategory("spa-at-home", "Spa at home", "Personal Care"),
    ServiceCategory("makeup-services", "Makeup Services", "Personal Care"),
    ServiceCategory("hair-care", "Hair Care", "Personal Care"),
    ServiceCategory(
        "skincare-advanced-treatments",
        "Skincare Advanced Treatments",
        "Personal Care",
    ),
    ServiceCategory("mehndi-services", "Mehndi Services", "Personal Care"),
    ServiceCategory("plumber", "Plumber", "Cleaning & Handyman"),
    ServiceCategory("house-cleaning", "House Cleaning", "Cleaning & Handyman"),
    ServiceCategory("carpenter-service", "Carpenter Service", "Cleaning & Handyman"),
    ServiceCategory("pest-control", "Pest Control", "Cleaning & Handyman"),
    ServiceCategory("painter-service", "Painter Service", "Cleaning & Handyman"),
    ServiceCategory("bike-mechanic", "Bike Mechanic", "Home Repairs & Maintenance"),
    ServiceCategory("car-mechanic", "Car Mechanic", "Home Repairs & Maintenance"),
    ServiceCategory("mobile-servicing", "Mobile Servicing", "Home Repairs & Maintenance"),
    ServiceCategory("electronic-mechanic", "Electronic Mechanic", "Home Repairs & Maintenance"),
    ServiceCategory("electrician", "Electrician", "Home Repairs & Maintenance"),
    ServiceCategory("ac-fridge-service", "AC/Fridge Service", "Home Repairs & Maintenance"),
    ServiceCategory("ro-servicing", "RO Servicing", "Home Repairs & Maintenance"),
    ServiceCategory("battery-servicing", "Battery Servicing", "Home Repairs & Maintenance"),
    ServiceCategory("computer-service", "Computer Service", "Home Repairs & Maintenance"),
    ServiceCategory("gas-stove-service", "Gas Stove Service", "Home Repairs & Maintenance"),
    ServiceCategory("second-hand-device", "Second Hand Device", "Other Services"),
    ServiceCategory("camera-servicing", "Camera Servicing", "Other Services"),
    ServiceCategory("cctv-servicing", "CCTV Servicing", "Other Services"),
    ServiceCategory("printer-servicing", "Printer Servicing", "Other Services"),
    ServiceCategory("e-rickshaw-mechanic", "E-Rickshaw Mechanic", "Other Services"),
    ServiceCategory("water-tank-cleaning", "Water Tank Cleaning", "Other Services"),
    ServiceCategory("laundry-dry-cleaning", "Laundry & Dry Cleaning", "Other Services"),
    ServiceCategory("packers-movers", "Packers & Movers", "Other Services"),
    ServiceCategory("car-bike-wash", "Car/Bike Wash", "Other Services"),
    ServiceCategory("home-tutors", "Home Tutors", "Other Services"),
    ServiceCategory("computer-training", "Computer Training", "Other Services"),
)

CATEGORY_BY_SLUG = {category.slug: category for category in SERVICE_CATEGORIES}


def is_valid_category_slug(slug: str) -> bool:
    return slug in CATEGORY_BY_SLUG
