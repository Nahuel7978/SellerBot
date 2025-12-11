CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category varchar(20),
    price_fivety_units DECIMAL(10, 2) NOT NULL,
    price_one_hundred_units DECIMAL(10, 2) NOT NULL,
    price_two_hundred_units DECIMAL(10, 2) NOT NULL,
    stock INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE carts (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE cart_items (
    id SERIAL PRIMARY KEY,
    cart_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    qty INTEGER NOT NULL DEFAULT 1,
    
    CONSTRAINT fk_cart
      FOREIGN KEY(cart_id) 
      REFERENCES carts(id)
      ON DELETE CASCADE, -- Si borras el carrito, se borran sus items
      
    CONSTRAINT fk_product
      FOREIGN KEY(product_id) 
      REFERENCES products(id)
      ON DELETE RESTRICT -- No permite borrar un producto si alguien lo tiene en el carrito
);


select * from products p ;

