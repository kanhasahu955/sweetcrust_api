from __future__ import annotations
from sqlmodel import Session
from app.models.catalog import ProductReview
from app.repositories import reviews as review_repo
from package.common.errors import BadRequestError, NotFoundError

def list_product_reviews(session: Session, product_id: int, limit: int = 20):
    if not review_repo.get_product(session, product_id):
        raise NotFoundError("Product not found")
    return review_repo.list_for_product(session, product_id, limit)

def add_product_review(session: Session, user_id: int, product_id: int, rating: int, comment=None, order_id=None) -> ProductReview:
    if rating < 1 or rating > 5:
        raise BadRequestError("rating must be 1-5")
    product = review_repo.get_product(session, product_id)
    if not product:
        raise NotFoundError("Product not found")
    review = ProductReview(user_id=user_id, product_id=product_id, rating=rating, comment=comment, order_id=order_id)
    session.add(review)
    total = product.rating * product.review_count + rating
    product.review_count += 1
    product.rating = round(total / product.review_count, 2)
    session.add(product)
    session.commit()
    session.refresh(review)
    return review
