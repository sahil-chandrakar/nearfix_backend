import json

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting
from app.schemas.support import SupportDetailsRead, SupportDetailsUpdate


DEFAULT_SUPPORT_DETAILS = SupportDetailsRead(
    footer_site_name="Nearfix.in",
    admin_phone="7970054811",
    email="nearfix12132550@gmail.com",
    help_heading_en="Help & Support",
    help_heading_hi="मदद और सपोर्ट",
    help_description_en="For any help or support, please contact us using the details below:",
    help_description_hi="किसी भी मदद के लिए नीचे दिए गए नंबर या ईमेल पर संपर्क करें:",
)


class SupportRepository:
    support_details_key = "support_details"

    @staticmethod
    def get_details(db: Session) -> SupportDetailsRead:
        setting = db.get(AppSetting, SupportRepository.support_details_key)
        if setting is None:
            return DEFAULT_SUPPORT_DETAILS

        try:
            stored_details = json.loads(setting.value)
            default_details = DEFAULT_SUPPORT_DETAILS.model_dump(
                by_alias=True,
                mode="json",
            )
            return SupportDetailsRead.model_validate({**default_details, **stored_details})
        except (TypeError, ValueError, ValidationError):
            return DEFAULT_SUPPORT_DETAILS

    @staticmethod
    def set_details(db: Session, *, payload: SupportDetailsUpdate) -> SupportDetailsRead:
        value = json.dumps(
            payload.model_dump(by_alias=True, mode="json"),
            ensure_ascii=False,
        )
        setting = db.get(AppSetting, SupportRepository.support_details_key)
        if setting is None:
            setting = AppSetting(
                key=SupportRepository.support_details_key,
                value=value,
            )
        else:
            setting.value = value

        db.add(setting)
        db.commit()
        return SupportDetailsRead.model_validate(payload.model_dump(mode="json"))
