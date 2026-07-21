"""Search product queries — thin wrapper over catalog list helpers."""
from __future__ import annotations
# Reuse service layer list; repository documents ownership for future ES index.
from app.services import products as product_ops

def search(session, query):
    return product_ops.list_products(session, query)
