# Python SQLAlchemy EntityBase

Base class for `SQLAlchemy` entities called `EntityMixin` that provides common useful methods, encapsulates session management and provides error handling. The current implementation is for `FastAPI` but can be adapted to other frameworks. Probably the most insanely useful I've ever written.

## Usage

The only requirement is to inherit from `EntityMixin`.

```python
# models.py
from app.database import Base
from entity_base import EntityMixin

class User(Base, EntityMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)
```

## Features

- Common useful methods
- Session management
- Error handling
- Logging

Class methods:

- `findById`
- `findAll`
- `findBy`
- `deleteById`
- `deleteBy`
- `exists`
- `conflict`

Instance methods:

- `save`
- `update`
- `delete`
- `to_dict`
- `__str__`
- `__repr__`

`_error_handler` decorator implements handling for SQLAlchemy errors.

## Examples

There will be some examples later

## Why this?

Instead of this:

```python
@app.put("/product/{product_id}")
async def update_product(product_id, new_product: ProductUpdate):
    product = session.query(Product).filter_by(id=product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    product.title = new_product.title
    product.description = request_body.description
    product.price = request_body.price
    product.stock = request_body.stock

    session.commit()

    return {"message": "Product updated"}
```

Do this:

```python
@app.put("/product/{product_id}")
async def update_product(product_id, new_product: ProductUpdate):
    Product.findById(product_id).update(new_product)
    return {"message": "Product updated"}
```
