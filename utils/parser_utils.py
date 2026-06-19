import re
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

# Common job titles to help identify designation lines
COMMON_TITLES = [
    "ceo", "cto", "cfo", "coo", "cmo", "founder", "co-founder", "president",
    "director", "manager", "engineer", "developer", "designer", "consultant",
    "architect", "specialist", "coordinator", "administrator", "executive",
    "lead", "head", "vp", "vice president", "partner", "principal", "officer",
    "assistant", "associate", "analyst", "representative", "agent", "broker"
]

# Common company suffixes
COMPANY_SUFFIXES = [
    "inc", "llc", "ltd", "corp", "corporation", "company", "co", "group", 
    "holdings", "gmbh", "solutions", "technologies", "studios", "labs", "partners"
]

# Valid top-level business domain suffixes for website validation
VALID_TLDS = {
    'com', 'org', 'net', 'in', 'co', 'io', 'us', 'uk', 'ca', 'biz', 'info', 
    'ai', 'app', 'edu', 'gov', 'me', 'xyz', 'tech', 'online', 'site', 'fr', 
    'de', 'jp', 'cn', 'br', 'au', 'eu', 'es', 'it', 'nl', 'se', 'no', 'ch'
}

EMAIL_IN_LINE_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
WEBSITE_IN_LINE_REGEX = re.compile(r'(?:https?://|www\.)[^\s]+', re.IGNORECASE)

def is_valid_email(email: str) -> bool:
    """Validate email format, rejecting spacing anomalies and multiple dots."""
    email = email.strip()
    if not email or " " in email or ".." in email:
        return False
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}$', email))

def is_valid_website(url: str) -> bool:
    """Validate website domain structure, rejecting invalid TLDs and random decimals (e.g. 0.00)."""
    temp = url.lower().strip()
    
    # Reject common decimal noise patterns
    if re.search(r'\d+\.\d+', temp):
        return False
        
    temp = re.sub(r'^https?:\/\/', '', temp)
    temp = re.sub(r'^www\.', '', temp)
    temp = temp.split('/')[0] # keep host domain only
    
    parts = temp.split('.')
    if len(parts) < 2:
        return False
        
    # Suffix TLD must be alphabetical and in our whitelist of valid business domains
    tld = parts[-1]
    if tld not in VALID_TLDS:
        return False
        
    # Second-level domain must be alphanumeric and at least 2 chars long
    sld = parts[-2]
    if not sld or (not sld.isalnum() and '-' not in sld):
        return False
    if len(sld) < 2:
        return False
        
    return True

def is_valid_phone(phone: str) -> bool:
    """Validate phone number, enforcing minimum length and rejecting decimals."""
    if not phone or "." in phone:
        return False
    # Reject if it has more than one letter (allows for 'x' at the end for extensions, but rejects typos)
    letters = [c for c in phone if c.isalpha()]
    if len(letters) > 1:
        return False
    digits = "".join(c for c in phone if c.isdigit())
    return 7 <= len(digits) <= 15

def clean_text(text: str) -> List[str]:
    """Clean the raw text, returning a list of normalized non-empty lines."""
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Remove unwanted garbage symbols completely, keep letters, numbers, basic punctuation, '&' and '_'
        line = re.sub(r'[^\w\s\.\,\@\-\+\(\)\:\/\|&_]', '', line)
        line = line.strip()
        
        # Skip empty lines or lines with very few characters (likely noise)
        if len(line) < 3:  # Increased from 2 to 3 to reject garbage short strings
            continue
            
        # Reject decimal fraction garbage lines (e.g. 0.00, 2.990)
        if re.match(r'^\d+\.\d+$', line):
            logger.info(f"[OCR Noise Filter] Discarded decimal garbage line: '{line}'")
            continue
            
        cleaned_lines.append(line)
        
    return cleaned_lines

def extract_emails(lines: List[str]) -> tuple[List[str], List[str]]:
    """Extract emails and return the extracted emails and the remaining lines."""
    emails = []
    remaining_lines = []
    email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    
    for line in lines:
        matches = email_pattern.findall(line)
        if matches:
            for match in matches:
                if is_valid_email(match):
                    emails.append(match.strip())
                else:
                    logger.info(f"[OCR Noise Filter] Rejected invalid email candidate: '{match}'")
            # Remove the emails from the line
            new_line = email_pattern.sub('', line).strip()
            # If line still has useful text after removing email, keep it
            if len(new_line) > 2:
                # Remove prefixes like "Email:" or "E:"
                new_line = re.sub(r'^(e(mail)?|m)\s*[:\-\.]?\s*', '', new_line, flags=re.IGNORECASE).strip()
                if len(new_line) > 2:
                    remaining_lines.append(new_line)
        else:
            remaining_lines.append(line)
            
    # Deduplicate emails (case-insensitive)
    unique_emails = []
    seen = set()
    duplicates_removed = 0
    
    for email in emails:
        norm = email.lower().strip()
        if norm in seen:
            duplicates_removed += 1
        else:
            seen.add(norm)
            unique_emails.append(email)
            
    if duplicates_removed > 0:
        logger.info(f"[Deduplication] Removed {duplicates_removed} duplicate email(s).")
            
    return unique_emails, remaining_lines

def extract_websites(lines: List[str]) -> tuple[List[str], List[str]]:
    """Extract websites and return the extracted websites and the remaining lines."""
    websites = []
    remaining_lines = []
    url_pattern = re.compile(r'(?:https?:\/\/)?(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]{2,}(?:\/[^\s]*)?', re.IGNORECASE)
    
    for line in lines:
        # Avoid matching emails as urls
        if '@' in line:
            remaining_lines.append(line)
            continue
            
        matches = url_pattern.findall(line)
        if matches:
            for match in matches:
                if is_valid_website(match):
                    websites.append(match.strip())
                else:
                    logger.info(f"[OCR Noise Filter] Rejected invalid website candidate: '{match}'")
                    
            new_line = url_pattern.sub('', line).strip()
            if len(new_line) > 2:
                new_line = re.sub(r'^(w(eb(site)?)?)\s*[:\-\.]?\s*', '', new_line, flags=re.IGNORECASE).strip()
                if len(new_line) > 2:
                    remaining_lines.append(new_line)
        else:
            remaining_lines.append(line)
            
    # Normalize and deduplicate websites (remove protocol, www, trailing slashes)
    unique_websites = []
    seen_normalized = set()
    duplicates_removed = 0
    
    for url in websites:
        norm = url.lower().strip()
        norm = re.sub(r'^https?:\/\/', '', norm)
        norm = re.sub(r'^www\.', '', norm)
        norm = norm.rstrip('/')
        
        if norm in seen_normalized:
            duplicates_removed += 1
        else:
            seen_normalized.add(norm)
            unique_websites.append(url)
            
    if duplicates_removed > 0:
        logger.info(f"[Deduplication] Removed {duplicates_removed} duplicate website(s).")
            
    return unique_websites, remaining_lines

def extract_phones(lines: List[str]) -> tuple[List[str], List[str]]:
    """Extract all valid phone numbers and return them along with remaining lines."""
    phones = []
    remaining_lines = []
    
    # A broad international and domestic phone number pattern
    phone_pattern = re.compile(r'(?:(?:\+|00)\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{3,4}(?:[\s.-]?\d{2,4})?')

    for line in lines:
        clean_line = re.sub(r'^(tel|phone|mobile|cell|m|p|t|f|office|direct)\s*[:\-\.]?\s*', '', line, flags=re.IGNORECASE).strip()
        
        matches = phone_pattern.findall(clean_line)
        matched_in_line = False
        for match in matches:
            if is_valid_phone(match):
                phones.append(match.strip())
                matched_in_line = True
                clean_line = clean_line.replace(match, '').strip()
            else:
                logger.info(f"[OCR Noise Filter] Rejected invalid phone candidate: '{match}'")
                
        if matched_in_line:
            clean_line = re.sub(r'^(tel|phone|mobile|cell|m|p|t|f|office|direct)\s*[:\-\.]?\s*', '', clean_line, flags=re.IGNORECASE).strip()
            if len(clean_line) > 2:
                remaining_lines.append(clean_line)
        else:
            remaining_lines.append(line)
            
    # Normalize and deduplicate phone numbers (suffix comparison)
    unique_phones = []
    seen_normalized = set()
    duplicates_removed = 0
    
    for phone in phones:
        norm = "".join(c for c in phone if c.isdigit())
        is_duplicate = False
        for existing in list(seen_normalized):
            # Suffix/prefix matching (e.g. 9876543210 is suffix of +919876543210)
            if norm.endswith(existing) or existing.endswith(norm):
                is_duplicate = True
                duplicates_removed += 1
                if len(norm) > len(existing):
                    # Replace with the more complete number containing country code
                    seen_normalized.remove(existing)
                    seen_normalized.add(norm)
                    for idx, val in enumerate(unique_phones):
                        val_norm = "".join(c for c in val if c.isdigit())
                        if val_norm == existing:
                            unique_phones[idx] = phone
                            break
                break
        if not is_duplicate:
            seen_normalized.add(norm)
            unique_phones.append(phone)
            
    if duplicates_removed > 0:
        logger.info(f"[Deduplication] Removed {duplicates_removed} duplicate phone number(s).")
        
    return unique_phones, remaining_lines

def is_likely_name_line(line: str) -> bool:
    line = line.strip()
    if not line or len(line) < 2 or len(line) > 60:
        return False
    if EMAIL_IN_LINE_REGEX.search(line) or WEBSITE_IN_LINE_REGEX.search(line):
        return False
    if re.search(r"\+?\d[\d\s\-().]{7,}", line):
        return False
    words = line.split()
    if len(words) < 1 or len(words) > 6:
        return False
    alpha_words = sum(1 for w in words if re.match(r"^[A-Za-z][A-Za-z.\-'']*$", w))
    return alpha_words >= max(1, len(words) - 1)


def infer_name_from_email(email: str) -> str:
    if not email or "@" not in email:
        return ""
    local = email.split("@")[0].strip()
    if not local or local.isdigit():
        return ""
    name = re.sub(r"[._+\-]+", " ", local).strip()
    words = [w.capitalize() for w in name.split() if w.isalpha()]
    if 1 <= len(words) <= 5:
        return " ".join(words)
    return ""


def extract_name_and_designation(lines: List[str]) -> tuple[str, str, List[str]]:
    """Identify the person's name and designation using heuristics."""
    name = ""
    designation = ""
    remaining_lines = []
    
    # 1. First, look for a designation line matching COMMON_TITLES
    designation_idx = -1
    for i, line in enumerate(lines):
        lower_line = line.lower()
        for title in COMMON_TITLES:
            if re.search(r'\b' + re.escape(title) + r'\b', lower_line):
                designation = line
                designation_idx = i
                break
        if designation:
            break
            
    # 2. Look for name
    # Heuristic A: If designation is found, name is often the line immediately preceding it
    if designation and designation_idx > 0:
        prev_line = lines[designation_idx - 1]
        # Ensure the previous line is not a company name
        if not any(suffix in prev_line.lower() for suffix in COMPANY_SUFFIXES):
            # And looks like a name (no numbers, reasonable length)
            words = prev_line.split()
            if 1 <= len(words) <= 5 and is_likely_name_line(prev_line):
                name = prev_line

    # Heuristic B: first line that looks like a person name
    if not name:
        for line in lines:
            if line == designation:
                continue
            if is_likely_name_line(line) and not any(
                suffix in line.lower() for suffix in COMPANY_SUFFIXES
            ):
                name = line
                break
                        
    # Re-build remaining lines excluding matched name and designation
    for line in lines:
        if line == name or line == designation:
            continue
        remaining_lines.append(line)
        
    return name, designation, remaining_lines

def extract_address(lines: List[str]) -> tuple[str, List[str]]:
    """Extract address using heuristics (street suffixes, zip codes)."""
    address_parts = []
    remaining_lines = []
    
    address_patterns = re.compile(r'\b(street|st|avenue|ave|boulevard|blvd|road|rd|drive|drv|lane|ln|suite|ste|floor|fl|building|bldg|p\.?o\.?\s*box)\b', re.IGNORECASE)
    zip_pattern = re.compile(r'\b\d{5}(?:-\d{4})?\b')
    
    for line in lines:
        if address_patterns.search(line) or zip_pattern.search(line) or (len(line) > 5 and line[0].isdigit() and ',' in line):
            # Clean up address prefixes
            clean_line = re.sub(r'^(address|add|a|location)\s*[:\-\.]?\s*', '', line, flags=re.IGNORECASE).strip()
            address_parts.append(clean_line)
        else:
            remaining_lines.append(line)
            
    return ", ".join(address_parts), remaining_lines

def extract_company(lines: List[str], emails: List[str], websites: List[str]) -> str:
    """Extract company name using suffixes or domain names from emails/websites."""
    # 1. Look for explicit company suffixes
    for line in lines:
        lower_line = line.lower()
        for suffix in COMPANY_SUFFIXES:
            if re.search(r'\b' + re.escape(suffix) + r'\b', lower_line):
                return line
                
    # 2. Guess from domain name
    domain_hints = []
    for email in emails:
        parts = email.split('@')
        if len(parts) == 2:
            domain = parts[1].split('.')[0]
            if domain not in ['gmail', 'yahoo', 'hotmail', 'outlook', 'icloud']:
                domain_hints.append(domain)
                
    for website in websites:
        match = re.search(r'(?:www\.)?([a-zA-Z0-9-]+)\.', website)
        if match:
            domain_hints.append(match.group(1))
            
    if domain_hints:
        hint = domain_hints[0].lower()
        # Look for a line that contains this hint
        for line in lines:
            if hint in line.lower():
                return line
        # Fallback: humanize domain (pinnacleadvisors -> Pinnacle Advisors)
        spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", hint)
        spaced = re.sub(r"[-_]", " ", spaced)
        if spaced.isalpha() and len(spaced) > 6:
            # Split camelCase-like runs: pinnacleadvisors -> try word split via common suffixes
            for suffix in ("advisors", "solutions", "technologies", "consulting", "group", "labs", "studio"):
                if spaced.endswith(suffix) and len(spaced) > len(suffix):
                    prefix = spaced[: -len(suffix)]
                    return f"{prefix.capitalize()} {suffix.capitalize()}"
        return " ".join(w.capitalize() for w in spaced.split())
        
    # 3. Fallback: Take the first reasonably short remaining line
    for line in lines:
        if len(line.split()) <= 4:
            return line
            
    return ""

def repair_ocr_mistakes(text: str) -> str:
    """Repair typical spacing issues and common OCR typos in emails and websites."""
    if not text:
        return ""
        
    logger.info("Running pre-extraction OCR text repairs and normalization.")
    
    # 1. Clean spacing around '@' and '.' in emails (e.g. 'john . doe @ gmail . com' -> 'john.doe@gmail.com')
    email_space_pattern = re.compile(
        r'([a-zA-Z0-9._%+-]+)\s*@\s*([a-zA-Z0-9.-]+)\s*\.\s*([a-zA-Z]{2,})'
    )
    def fix_email_space(match):
        fixed = f"{match.group(1).replace(' ', '')}@{match.group(2).replace(' ', '')}.{match.group(3).replace(' ', '')}"
        logger.info(f"[OCR Spacing Repair] Restored email: '{match.group(0)}' -> '{fixed}'")
        return fixed
    text = email_space_pattern.sub(fix_email_space, text)
    
    # 2. Clean spacing in websites (e.g. 'www . domain . com' -> 'www.domain.com')
    web_space_pattern = re.compile(
        r'(?:https?:\/\/\s*)?(?:www\s*\.\s*)?[a-zA-Z0-9-]+\s*\.\s*[a-zA-Z0-9-.]{2,}(?:\/[^\s]*)?', re.IGNORECASE
    )
    def fix_web_space(match):
        orig = match.group(0)
        if '@' in orig:
            return orig
        fixed = orig.replace(' ', '')
        fixed = re.sub(r'https?:/+', 'http://' if fixed.startswith('http:') else 'https://', fixed)
        if fixed != orig:
            logger.info(f"[OCR Spacing Repair] Restored website: '{orig}' -> '{fixed}'")
        return fixed
    text = web_space_pattern.sub(fix_web_space, text)
    
    # 3. Typo corrections in domain suffixes
    # Examples: '.c0m' -> '.com', '.0rg' -> '.org', '.n3t' -> '.net'
    typo_suffix_mappings = {
        r'\.c0m\b': '.com',
        r'\.0rg\b': '.org',
        r'\.n3t\b': '.net',
        r'\.c[o0]m\.([a-zA-Z]{2})\b': r'.com.\1',
    }
    for pattern, replacement in typo_suffix_mappings.items():
        orig_text = text
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        if text != orig_text:
            logger.info(f"[OCR Typo Correction] Corrected domain typo using pattern '{pattern}'")
            
    return text

def split_name_parts(name: str) -> tuple[str, str]:
    parts = name.strip().split()
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    if parts:
        return parts[0], ""
    return "", ""


def classify_phones(phones: List[str]) -> tuple[List[str], List[str]]:
    mobile: List[str] = []
    telephone: List[str] = []
    for phone in phones:
        digits = "".join(c for c in phone if c.isdigit())
        lower = phone.lower()
        if any(k in lower for k in ("mobile", "cell", "mob", "whatsapp")):
            mobile.append(phone)
        elif len(digits) == 10 and digits[0] in "6789":
            mobile.append(phone)
        elif phone.strip().startswith("+") and len(digits) >= 11:
            mobile.append(phone)
        else:
            telephone.append(phone)
    return mobile, telephone


SOCIAL_PATTERNS = [
    (re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-./]+", re.I), "LinkedIn"),
    (re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/company/[\w\-./]+", re.I), "LinkedIn"),
    (re.compile(r"(?:https?://)?(?:www\.)?(?:twitter|x)\.com/[\w\-./]+", re.I), "Twitter/X"),
    (re.compile(r"(?:https?://)?(?:www\.)?facebook\.com/[\w\-./]+", re.I), "Facebook"),
    (re.compile(r"(?:https?://)?(?:www\.)?instagram\.com/[\w\-./]+", re.I), "Instagram"),
    (re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/[\w\-./]+", re.I), "YouTube"),
]

GST_PATTERN = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]\b", re.I)
TAX_PATTERN = re.compile(r"\b(?:GST|TIN|PAN|VAT|Tax)\s*[:\-]?\s*([A-Z0-9\-/]{8,20})\b", re.I)


def extract_social_links(text: str) -> List[str]:
    found: List[str] = []
    seen = set()
    for pattern, _label in SOCIAL_PATTERNS:
        for match in pattern.findall(text):
            norm = match.lower().rstrip("/")
            if norm not in seen:
                seen.add(norm)
                found.append(match.strip())
    return found


def extract_tax_numbers(text: str) -> List[str]:
    taxes: List[str] = []
    for match in GST_PATTERN.findall(text):
        taxes.append(match.strip())
    for match in TAX_PATTERN.findall(text):
        if match.strip() and match.strip() not in taxes:
            taxes.append(match.strip())
    return taxes


def extract_all_addresses(lines: List[str]) -> tuple[List[str], List[str]]:
    address_parts: List[str] = []
    remaining_lines: List[str] = []
    address_patterns = re.compile(
        r"\b(street|st|avenue|ave|boulevard|blvd|road|rd|drive|drv|lane|ln|suite|ste|floor|fl|building|bldg|p\.?o\.?\s*box)\b",
        re.IGNORECASE,
    )
    zip_pattern = re.compile(r"\b\d{5}(?:-\d{4})?\b")

    for line in lines:
        if address_patterns.search(line) or zip_pattern.search(line) or (
            len(line) > 5 and line[0].isdigit() and "," in line
        ):
            clean_line = re.sub(r"^(address|add|a|location)\s*[:\-\.]?\s*", "", line, flags=re.IGNORECASE).strip()
            address_parts.append(clean_line)
        else:
            remaining_lines.append(line)

    return address_parts, remaining_lines


def build_confidence(result: Dict[str, Any], raw_text: str) -> Dict[str, float]:
    text_lower = raw_text.lower()

    def score(field_value: str, direct: bool = True) -> float:
        if not field_value:
            return 0.0
        if field_value.lower() in text_lower:
            return 96.0 if direct else 88.0
        return 72.0 if direct else 55.0

    first, last = result.get("firstName", ""), result.get("lastName", "")
    return {
        "fullName": score(result.get("name", "")),
        "firstName": score(first),
        "lastName": score(last),
        "designation": score(result.get("designation", "")),
        "companyName": score(result.get("company", ""), direct=False),
        "phoneNumber": max([score(p) for p in result.get("phones", [])] or [0]),
        "emailAddress": max([score(e) for e in result.get("emails", [])] or [0]),
        "website": max([score(w, False) for w in result.get("websites", [])] or [0]),
        "address": score(result.get("address", ""), False),
        "notes": 50.0 if result.get("notes") else 0.0,
        "gstNumber": max([score(g) for g in result.get("gstNumbers", [])] or [0]),
    }


def parse_business_card(raw_text: str) -> Dict[str, Any]:
    """Parse raw OCR text into structured contact JSON."""
    logger.info("Starting intelligent structured duplicate handling extraction from OCR text")
    
    if not raw_text or not raw_text.strip():
        logger.warning("Empty OCR text passed to parser.")
        return {
            "name": "",
            "firstName": "",
            "lastName": "",
            "designation": "",
            "company": "",
            "phones": [],
            "mobileNumbers": [],
            "telephoneNumbers": [],
            "emails": [],
            "websites": [],
            "addresses": [],
            "socialLinks": [],
            "gstNumbers": [],
            "address": "",
            "phone": "",
            "email": "",
            "notes": "",
            "confidence": {},
        }
    
    # Pre-process raw text to repair spacing anomalies and domain suffix typos
    raw_text = repair_ocr_mistakes(raw_text)
    
    lines = clean_text(raw_text)
    raw_lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    
    # Process and remove distinct fields sequentially to prevent overlaps
    emails, lines = extract_emails(lines)
    websites, lines = extract_websites(lines)
    phones, lines = extract_phones(lines)
    address_list, lines = extract_all_addresses(lines)
    name, designation, lines = extract_name_and_designation(lines)
    company = extract_company(lines, emails, websites)

    # Fallback: first plausible line from raw OCR before field stripping
    if not name:
        for line in raw_lines:
            cleaned = re.sub(r"[^\w\s\.\,\@\-\+\(\)\:\/\|&_]", "", line).strip()
            if is_likely_name_line(cleaned):
                name = cleaned
                break

    if not name and emails:
        name = infer_name_from_email(emails[0])

    first_name, last_name = split_name_parts(name)
    mobile_numbers, telephone_numbers = classify_phones(phones)
    social_links = extract_social_links(raw_text)
    gst_numbers = extract_tax_numbers(raw_text)
    notes = " ".join(lines[:3]).strip() if lines else ""

    address = ", ".join(address_list) if address_list else ""

    result = {
        "name": name.title().strip(),
        "firstName": first_name.title().strip(),
        "lastName": last_name.title().strip(),
        "designation": designation.title().strip(),
        "phone": phones[0] if phones else "",
        "email": emails[0] if emails else "",
        "phones": phones,
        "mobileNumbers": mobile_numbers,
        "telephoneNumbers": telephone_numbers,
        "emails": emails,
        "websites": websites,
        "addresses": address_list,
        "socialLinks": social_links,
        "gstNumbers": gst_numbers,
        "address": address.strip(),
        "company": company.title().strip(),
        "notes": notes,
    }
    result["confidence"] = build_confidence(result, raw_text)
    
    logger.info(f"Structured extraction completed: {len(phones)} phone(s), {len(emails)} email(s), {len(websites)} website(s).")
    return result
