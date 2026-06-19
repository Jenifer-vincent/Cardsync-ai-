from pydantic import BaseModel, ConfigDict, Field


class WhatsAppMessageRequest(BaseModel):
    contact_phone: str
    message: str


class WhatsAppTestRequest(BaseModel):
    contact_phone: str
    message: str = "hai"
    mode: str = Field(
        default="auto",
        description=(
            "Send mode: `auto` (text then template fallback), `text`, `template` (hello_world), "
            "or `business-card` (cardsync_contact_saved from WHATSAPP_*_TEMPLATE_NAME env)."
        ),
    )


class ZohoLeadChannels(BaseModel):
    whatsapp: bool = False
    email: bool = False


class ZohoLeadSummary(BaseModel):
    """Lead row returned by GET /api/leads (parsed from Zoho CRM)."""

    id: str | None = None
    name: str = ""
    designation: str = ""
    title: str = ""
    company: str = ""
    address: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    eventName: str = Field(
        default="",
        description="Parsed from Zoho Features line `Event: …`.",
    )
    notes: str = Field(
        default="",
        description="Parsed from Zoho Features line `Notes: …`.",
    )
    status: str = "synced"
    lastSync: str = ""
    channels: ZohoLeadChannels = Field(default_factory=ZohoLeadChannels)


class WhatsAppChatReplyRegisterRequest(BaseModel):
    """Register a scanned contact for auto-reply after they message via wa.me QR."""

    fullName: str = ""
    firstName: str = ""
    lastName: str = ""
    designation: str = ""
    company: str = ""
    phone: str = ""
    secondaryPhone: str = ""
    email: str = ""
    secondaryEmail: str = ""
    website: str = ""
    secondaryWebsite: str = ""
    address: str = ""
    secondaryAddress: str = ""


class EmailMessageRequest(BaseModel):
    contact_email: str
    message: str


class EmailTestRequest(BaseModel):
    contact_email: str = Field(
        ...,
        description="Email parsed from a scanned contact (simulated).",
        examples=["saligantisandeepzzz6@gmail.com"],
    )
    test_override: str = Field(
        default="",
        description=(
            "Optional inbox that receives the mail instead of contact_email. "
            "Leave empty to send to contact_email."
        ),
        examples=[""],
    )


class DuplicateCheckRequest(BaseModel):
    fullName: str = ""
    company: str = ""
    phone: str = ""
    email: str = ""


class ContactUpdateRequest(BaseModel):
    contact: dict


class LocalContactBody(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "fullName": "Sandeep Saliganti",
                    "firstName": "Sandeep",
                    "lastName": "Saliganti",
                    "designation": "Developer",
                    "company": "CardSync Demo",
                    "phone": "+919884993074",
                    "email": "saligantisandeepzzz6@gmail.com",
                    "website": "https://cardsync.ai",
                    "eventName": "Mall Opening",
                    "notes": "Met at booth — follow up next week.",
                    "connectionMode": "online",
                    "skipWhatsApp": True,
                    "skipEmail": False,
                }
            ]
        }
    )

    fullName: str
    firstName: str = ""
    lastName: str = ""
    designation: str = ""
    company: str = ""
    phone: str = ""
    secondaryPhone: str = ""
    email: str = ""
    secondaryEmail: str = ""
    website: str = ""
    secondaryWebsite: str = ""
    address: str = ""
    secondaryAddress: str = ""
    socialLinks: str = ""
    gstNumber: str = ""
    notes: str = Field(
        default="",
        description="User-written notes only (not OCR). Stored in Zoho Features as `Notes: {text}` (max 2000 chars).",
        max_length=2000,
    )
    eventName: str = Field(
        default="",
        description="Event where the card was collected. Stored in Zoho Features as `Event: {name}`.",
    )
    eventId: str | None = None
    cardImageBase64: str | None = None
    syncStatus: str = "local_only"
    zohoLeadId: str | None = None
    connectionMode: str = "online"
    skipWhatsApp: bool = False
    skipEmail: bool = False


class SyncStatusBody(BaseModel):
    syncStatus: str
    zohoLeadId: str | None = None


class SyncOutreachOptions(BaseModel):
    skipWhatsApp: bool = False
    skipEmail: bool = False


class WipeAllDataBody(BaseModel):
    confirm: bool = False
    include_zoho: bool = True


class CreateLeadRequest(BaseModel):
    fullName: str = Field(..., min_length=1)
    designation: str = ""
    company: str = Field(..., min_length=1)
    address: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    eventName: str = Field(
        default="",
        description="Stored in Zoho Features as `Event: {name}`.",
    )
    notes: str = Field(
        default="",
        description="User-written notes. Stored in Zoho Features as `Notes: {text}`.",
        max_length=2000,
    )


class SyncFromLocalRequest(BaseModel):
    """Extracted contact fields from browser OCR — sent by the frontend on save/sync."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "fullName": "Sandeep Saliganti",
                    "firstName": "Sandeep",
                    "lastName": "Saliganti",
                    "designation": "Developer",
                    "company": "CardSync Demo",
                    "phone": "+919884993074",
                    "email": "saligantisandeepzzz6@gmail.com",
                    "website": "https://cardsync.ai",
                    "address": "Hyderabad, India",
                    "eventName": "Mall Opening",
                    "notes": "Interested in enterprise plan.",
                    "connectionMode": "online",
                    "skipWhatsApp": True,
                    "skipEmail": False,
                }
            ]
        }
    )

    fullName: str | None = ""
    firstName: str | None = ""
    lastName: str | None = ""
    name: str | None = ""
    company: str | None = ""
    designation: str | None = ""
    title: str | None = ""
    phone: str | None = ""
    secondaryPhone: str | None = ""
    email: str | None = ""
    emailAddress: str | None = ""
    secondaryEmail: str | None = ""
    secondaryEmailAddress: str | None = ""
    website: str | None = ""
    secondaryWebsite: str | None = ""
    address: str | None = ""
    secondaryAddress: str | None = ""
    notes: str | None = Field(
        default="",
        description="User-written notes only. Stored in Zoho Features as `Notes: {text}`.",
        max_length=2000,
    )
    eventName: str | None = Field(
        default="",
        description="Event name. Stored in Zoho Features as `Event: {name}`.",
    )
    eventId: str | None = None
    zohoLeadId: str | None = None
    connectionMode: str = "online"
    skipWhatsApp: bool = False
    skipEmail: bool = False
