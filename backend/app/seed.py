from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.category import Category


INITIAL_CATEGORIES = [
    "Food",
    "EMI",
    "Subscription",
    "Shopping",
    "Travel",
    "Recharge",
    "Investment",
    "Gift",
    "Miscellaneous",
    "Salary",
]


def seed_categories() -> None:
    with SessionLocal() as db:
        existing_names = set(db.scalars(select(Category.name)).all())
        for name in INITIAL_CATEGORIES:
            if name not in existing_names:
                db.add(Category(name=name))
        db.commit()


if __name__ == "__main__":
    seed_categories()
