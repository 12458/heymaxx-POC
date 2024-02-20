# HeyMax POC
> Fuil Stack POC for [HeyMax.ai](https://heymax.ai/)

# Instructions to run

```sh
. .venv/bin/activate # Activate venv
pip3 install -r requirements.txt
python3 app.py # Run flask app
```

# Things to note

Credentials for admin page is `admin` and `admin` for username and password respectively. 

## Database Schema

```sql
CREATE TABLE Users (
    user_id INTEGER PRIMARY KEY,
    username TEXT NOT NULL,
    email TEXT NOT NULL,
    password TEXT NOT NULL
);
CREATE TABLE Items (
    item_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    price REAL NOT NULL
);
CREATE TABLE Admins (
    admin_id INTEGER PRIMARY KEY,
    username TEXT NOT NULL,
    email TEXT NOT NULL,
    password TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS "Cart" (
        "user_id"       INTEGER,
        "item_id"       INTEGER,
        "qty"   INTEGER NOT NULL,
        PRIMARY KEY("user_id","item_id"),
        FOREIGN KEY("user_id") REFERENCES "Users"("user_id"),
        FOREIGN KEY("item_id") REFERENCES "Items"("item_id")
);
CREATE TABLE IF NOT EXISTS "Orders" (
        "order_id"      TEXT,
        "user_id"       TEXT,
        "shipping_address"      TEXT NOT NULL,
        "payment_status"        INTEGER DEFAULT 0,
        "order_date"    TEXT NOT NULL,
        "phone" TEXT,
        FOREIGN KEY("user_id") REFERENCES "Users"("user_id"),
        PRIMARY KEY("order_id")
);
CREATE TABLE IF NOT EXISTS "Order_Items" (
        "order_id"      INTEGER,
        "item_id"       INTEGER,
        "qty"   INTEGER NOT NULL,
        FOREIGN KEY("order_id") REFERENCES "Orders"("order_id"),
        FOREIGN KEY("item_id") REFERENCES "Items"("item_id"),
        PRIMARY KEY("order_id","item_id")
);
CREATE TABLE IF NOT EXISTS "Reviews" (
        "item_id"       INTEGER,
        "user_id"       INTEGER,
        "rating"        INTEGER,
        "review"        TEXT
);
```

# License
All code in this repository is licensed under [AGPL-3.0](https://github.com/12458/heymaxx-POC/blob/master/LICENSE)
