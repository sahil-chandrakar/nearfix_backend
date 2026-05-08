"""add hindi service category labels

Revision ID: 20260430_0007
Revises: 20260430_0006
Create Date: 2026-04-30 22:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260430_0007"
down_revision: str | None = "20260430_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SERVICE_CATEGORY_HINDI = (
    ("mens-grooming", "मेन्स ग्रूमिंग", "पर्सनल केयर"),
    ("spa-massage-at-home", "घर पर स्पा और मसाज", "पर्सनल केयर"),
    ("salon-at-home", "घर पर सैलून", "पर्सनल केयर"),
    ("spa-at-home", "घर पर स्पा", "पर्सनल केयर"),
    ("makeup-services", "मेकअप सेवा", "पर्सनल केयर"),
    ("hair-care", "हेयर केयर", "पर्सनल केयर"),
    ("skincare-advanced-treatments", "स्किन केयर ट्रीटमेंट", "पर्सनल केयर"),
    ("mehndi-services", "मेहंदी सेवा", "पर्सनल केयर"),
    ("plumber", "प्लंबर", "सफाई और मरम्मत"),
    ("house-cleaning", "घर की सफाई", "सफाई और मरम्मत"),
    ("carpenter-service", "कारपेंटर सेवा", "सफाई और मरम्मत"),
    ("pest-control", "पेस्ट कंट्रोल", "सफाई और मरम्मत"),
    ("painter-service", "पेंटर सेवा", "सफाई और मरम्मत"),
    ("bike-mechanic", "बाइक मैकेनिक", "घर की मरम्मत"),
    ("car-mechanic", "कार मैकेनिक", "घर की मरम्मत"),
    ("mobile-servicing", "मोबाइल सर्विसिंग", "घर की मरम्मत"),
    ("electronic-mechanic", "इलेक्ट्रॉनिक मैकेनिक", "घर की मरम्मत"),
    ("electrician", "इलेक्ट्रीशियन", "घर की मरम्मत"),
    ("ac-fridge-service", "AC/फ्रिज सेवा", "घर की मरम्मत"),
    ("ro-servicing", "RO सर्विसिंग", "घर की मरम्मत"),
    ("battery-servicing", "बैटरी सर्विसिंग", "घर की मरम्मत"),
    ("computer-service", "कंप्यूटर सेवा", "घर की मरम्मत"),
    ("gas-stove-service", "गैस स्टोव सेवा", "घर की मरम्मत"),
    ("second-hand-device", "सेकंड हैंड डिवाइस", "अन्य सेवाएं"),
    ("camera-servicing", "कैमरा सर्विसिंग", "अन्य सेवाएं"),
    ("cctv-servicing", "CCTV सर्विसिंग", "अन्य सेवाएं"),
    ("printer-servicing", "प्रिंटर सर्विसिंग", "अन्य सेवाएं"),
    ("e-rickshaw-mechanic", "ई-रिक्शा मैकेनिक", "अन्य सेवाएं"),
    ("water-tank-cleaning", "पानी टंकी सफाई", "अन्य सेवाएं"),
    ("laundry-dry-cleaning", "लॉन्ड्री और ड्राई क्लीनिंग", "अन्य सेवाएं"),
    ("packers-movers", "पैकर्स और मूवर्स", "अन्य सेवाएं"),
    ("car-bike-wash", "कार/बाइक वॉश", "अन्य सेवाएं"),
    ("home-tutors", "होम ट्यूटर", "अन्य सेवाएं"),
    ("computer-training", "कंप्यूटर ट्रेनिंग", "अन्य सेवाएं"),
)


def upgrade() -> None:
    op.add_column(
        "service_categories",
        sa.Column("label_hi", sa.String(length=255), nullable=False, server_default=""),
    )
    op.add_column(
        "service_categories",
        sa.Column("group_hi", sa.String(length=100), nullable=False, server_default=""),
    )

    categories = sa.table(
        "service_categories",
        sa.column("slug", sa.String),
        sa.column("label_hi", sa.String),
        sa.column("group_hi", sa.String),
    )
    for slug, label_hi, group_hi in SERVICE_CATEGORY_HINDI:
        op.execute(
            categories.update()
            .where(categories.c.slug == slug)
            .values(label_hi=label_hi, group_hi=group_hi)
        )

    op.execute("UPDATE service_categories SET label_hi = label, group_hi = 'अन्य सेवाएं' WHERE label_hi = ''")


def downgrade() -> None:
    op.drop_column("service_categories", "group_hi")
    op.drop_column("service_categories", "label_hi")
