"""
PII masking utilities for public CV data.

When CVs are shared publicly (visible to non-owners), sensitive personal
information is partially masked to protect candidate privacy while still
allowing meaningful screening and evaluation.

Masking rules:
  - Name:  "Nguyễn Văn An" → "Nguyễn V** A*"
  - Email: "local email" → "masked email"
  - Phone: "local phone" → "masked phone"
"""

# Standard library imports
import re
from copy import deepcopy
from typing import Dict, List, Optional


def mask_name(name: Optional[str]) -> Optional[str]:
    """Mask a person's name, keeping first word and first char of others."""
    if not name:
        return name
    parts = name.strip().split()
    if len(parts) <= 1:
        # Single name: keep first char + stars
        return name[0] + "*" * (len(name) - 1) if len(name) > 1 else name
    # Keep first word fully, mask rest (keep first char + stars)
    masked = [parts[0]]
    for p in parts[1:]:
        if len(p) > 1:
            masked.append(p[0] + "*" * (len(p) - 1))
        else:
            masked.append(p)
    return " ".join(masked)


def mask_email(email: Optional[str]) -> Optional[str]:
    """Mask email: keep first 3 chars of local + domain initial."""
    if not email or "@" not in email:
        return email
    local, domain = email.rsplit("@", 1)
    domain_parts = domain.split(".")
    # Local: keep first 3 chars
    if len(local) > 3:
        masked_local = local[:3] + "*" * min(4, len(local) - 3)
    else:
        masked_local = local[0] + "**"
    # Domain: keep first 2 chars of main part
    if len(domain_parts[0]) > 2:
        masked_domain = domain_parts[0][:2] + "*" * min(3, len(domain_parts[0]) - 2)
    else:
        masked_domain = domain_parts[0]
    rest = ".".join(domain_parts[1:])
    return f"{masked_local}@{masked_domain}.{rest}"


def mask_phone(phone: Optional[str]) -> Optional[str]:
    """Mask phone number: keep first 3 and last 3 digits."""
    if not phone:
        return phone
    digits = re.sub(r"\D", "", phone)
    if len(digits) <= 6:
        return phone  # Too short to mask meaningfully
    return digits[:3] + "*" * (len(digits) - 6) + digits[-3:]


def mask_cv_text(text: Optional[str], metadata: Dict) -> str:
    """Remove PII from raw CV text — replace name/email/phone with masked versions."""
    if not text:
        return text or ""
    result = text
    # Mask email if present
    email = metadata.get("email", "")
    if email and email in result:
        result = result.replace(email, mask_email(email) or "")
    # Mask phone (various formats)
    phone = metadata.get("phone", "")
    if phone:
        # Remove formatting to find in text
        digits = re.sub(r"\D", "", phone)
        # Try original format first
        if phone in result:
            result = result.replace(phone, mask_phone(phone) or "")
        # Try with spaces removed
        for pattern in [digits, f"+{digits}"]:
            if pattern in result:
                result = result.replace(pattern, mask_phone(phone) or "")
    # Mask name (try original casing + uppercase)
    name = metadata.get("name", "")
    if name:
        masked_name = mask_name(name) or ""
        if name in result:
            result = result.replace(name, masked_name)
        if name.upper() in result:
            result = result.replace(name.upper(), masked_name.upper())
        if name.title() in result:
            result = result.replace(name.title(), mask_name(name.title()) or "")
    return result


def mask_cv_metadata(metadata: Dict, is_owner: bool = False) -> Dict:
    """
    Mask PII fields in CV metadata if viewer is not the owner.

    Args:
        metadata: CV metadata dict (may contain name, email, phone)
        is_owner: True if the requesting user owns this CV

    Returns:
        Metadata with PII masked (or original if owner)
    """
    if is_owner:
        return metadata

    masked = deepcopy(metadata)
    if "name" in masked:
        masked["name"] = mask_name(masked["name"])
    if "email" in masked:
        masked["email"] = mask_email(masked["email"])
    if "phone" in masked:
        masked["phone"] = mask_phone(masked["phone"])
    # Also mask file_path which may contain real name
    if "file_path" in masked:
        masked["file_path"] = "cv_document.pdf"
    return masked


def mask_candidate_result(
    candidate: Dict, viewer_user_id: Optional[str] = None
) -> Dict:
    """
    Mask PII in a screening candidate result dict.

    The candidate dict has top-level name/email/phone fields
    plus a nested metadata dict.
    """
    owner = candidate.get("owner_user_id") or candidate.get("metadata", {}).get(
        "owner_user_id", ""
    )
    is_owner = viewer_user_id and owner == viewer_user_id

    if is_owner:
        return candidate

    masked = deepcopy(candidate)
    if "name" in masked:
        masked["name"] = mask_name(masked["name"])
    if "email" in masked:
        masked["email"] = mask_email(masked["email"])
    if "phone" in masked:
        masked["phone"] = mask_phone(masked["phone"])
    if "metadata" in masked and isinstance(masked["metadata"], dict):
        masked["metadata"] = mask_cv_metadata(masked["metadata"], is_owner=False)
    return masked


def mask_cv_list(cvs: List[Dict], viewer_user_id: Optional[str] = None) -> List[Dict]:
    """Mask PII in a list of CV objects for non-owners."""
    result = []
    for cv in cvs:
        meta = cv.get("metadata", {})
        owner = meta.get("owner_user_id", "")
        is_owner = viewer_user_id and owner == viewer_user_id
        if is_owner:
            result.append(cv)
        else:
            masked_cv = deepcopy(cv)
            # Mask text field (contains raw CV with PII)
            if "text" in masked_cv:
                masked_cv["text"] = mask_cv_text(masked_cv["text"], meta)
            masked_cv["metadata"] = mask_cv_metadata(
                masked_cv.get("metadata", {}), is_owner=False
            )
            result.append(masked_cv)
    return result
