"""Bakery knowledge corpus for RAG (policies, FAQ, delivery)."""

BAKERY_DOCS: list[dict[str, str]] = [
    {
        "id": "delivery-radius",
        "text": (
            "SweetCrust Bakery delivers within 100 km of Andheri West, Mumbai. "
            "Typical Andheri–Bandra delivery is 45–60 minutes for in-stock items. "
            "Minimum order value applies; free delivery above ₹499."
        ),
    },
    {
        "id": "return-policy",
        "text": (
            "Damaged, melted, wrong, or missing items can be reported within 24 hours of delivery. "
            "Upload clear photos in the app. Customers may choose refund or replacement. "
            "Admin makes the final decision after AI preliminary review."
        ),
    },
    {
        "id": "payment",
        "text": (
            "We accept UPI, Google Pay, PhonePe, Paytm, cards, net banking, wallet, and COD when enabled. "
            "GST invoices are generated automatically with bakery GSTIN."
        ),
    },
    {
        "id": "eggless",
        "text": (
            "SweetCrust offers many eggless cakes and pastries. Filter by Eggless in the app "
            "or ask the assistant for eggless chocolate cakes."
        ),
    },
    {
        "id": "custom-cake",
        "text": (
            "Custom cakes: choose occasion, flavour, weight, shape, cream, theme, upload reference photo, "
            "cake message, delivery date/time and budget. Pay after bakery quotation approval."
        ),
    },
    {
        "id": "hours",
        "text": (
            "SweetCrust bakery hours: Monday–Saturday 9 AM to 10 PM, Sunday 9 AM to 9 PM. "
            "AI chatbot support is available 24/7 inside the app."
        ),
    },
    {
        "id": "allergens",
        "text": (
            "Common allergens: gluten, milk, egg (for non-eggless), soy, nuts in some products. "
            "Check product details. Sugar-free options exist for diabetic-friendly needs."
        ),
    },
    {
        "id": "festivals",
        "text": (
            "Festival specials include Diwali hampers, Holi cookie boxes, and celebration cakes. "
            "Order early for weekends and festivals as peak hours are 5 PM–8 PM."
        ),
    },
]
