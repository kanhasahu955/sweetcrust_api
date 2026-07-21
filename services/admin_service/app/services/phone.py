def normalize_phone(phone: str) -> str:
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) == 10:
        return "+91" + digits
    if phone.startswith("+"):
        return phone
    return "+" + digits if digits else phone
