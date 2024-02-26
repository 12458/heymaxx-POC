"""
E-commerce CRUD app
Backend API
"""

from flask import Flask, jsonify, request, make_response, abort
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity, get_jwt
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import secrets
import uuid
import datetime
import stripe
import os

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = secrets.token_hex(32)  # Generate a strong secret key
jwt = JWTManager(app)

# JWT blacklist
jwt_blacklisted_tokens = set()

@jwt.token_in_blocklist_loader
def check_if_token_in_blacklist(jwt_header, jwt_payload):
    return jwt_payload['jti'] in jwt_blacklisted_tokens

try:
    stripe.api_key = os.environ['STRIPE_SECRET_KEY']
except:
    stripe.api_key = None

YOUR_DOMAIN = 'http://localhost:5000'

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

# Database connection and error handling
def get_db_connection():
    try:
        conn = sqlite3.connect('db.db')
        conn.row_factory = dict_factory
        return conn
    except sqlite3.Error as e:
        abort(500, f"Database error: {e}")

def close_db_connection(conn):
    if conn:
        conn.close()

@app.route('/')
def index():
    return jsonify({'message': 'Welcome to the E-commerce API'}), 200

@app.route('/view_orders', methods=['GET'])
@jwt_required()
def view_orders():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get user ID from JWT
        user_id = get_jwt_identity()

        # Query DB for user's orders
        cursor.execute('SELECT * FROM Orders WHERE user_id = ?', (user_id,))
        orders = cursor.fetchall()
        close_db_connection(conn)

        # Return JSON response with orders data
        return jsonify({'orders': orders})
    except sqlite3.Error as e:
        close_db_connection(conn)
        return jsonify({'error': f'Failed to retrieve orders: {e}'}), 500

@app.route('/order/<string:order_id>', methods=['GET'])
@jwt_required()
def order(order_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get user ID from JWT
        user_id = get_jwt_identity()

        # Query DB for order items, ensuring user owns the order
        cursor.execute('SELECT i.name, i.price, oi.qty FROM Order_Items oi INNER JOIN Items i ON oi.item_id = i.item_id INNER JOIN Orders o ON o.order_id = oi.order_id WHERE o.order_id = ? AND o.user_id = ?', (order_id, user_id))
        order_items = cursor.fetchall()
        close_db_connection(conn)

        # Return JSON response with order items data
        return jsonify({'order_items': [item for item in order_items]})
    except sqlite3.Error as e:
        close_db_connection(conn)
        return jsonify({'error': f'Failed to retrieve order items: {e}'}), 500
    except ValueError:
        return jsonify({'error': 'Invalid order ID'}), 400

@app.route('/review', methods=['GET'])
@jwt_required()
def review():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get user ID from JWT
        user_id = get_jwt_identity()

        # Query DB to get items user ordered before
        cursor.execute('SELECT DISTINCT i.name, i.item_id FROM Order_Items oi INNER JOIN Items i ON oi.item_id = i.item_id INNER JOIN Orders o ON o.order_id = oi.order_id WHERE o.user_id = ?', (user_id,))
        items = cursor.fetchall()
        close_db_connection(conn)

        # Return JSON response with item data
        return jsonify({'items': [item for item in items]})
    except sqlite3.Error as e:
        close_db_connection(conn)
        return jsonify({'error': f'Failed to retrieve items for review: {e}'}), 500

@app.route('/review/<int:item_id>', methods=['POST'])
@jwt_required()
def review_item(item_id):
    # Get data from JSON request
    try:
        rating = int(request.json.get('rating'))
        review = request.json.get('review')
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid rating or review data'}), 400

    # Validate rating
    if not (1 <= rating <= 5):
        return jsonify({'error': 'Rating must be between 1 and 5'}), 400

    # Add review to database
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO Reviews (item_id, user_id, rating, review) VALUES (?, ?, ?, ?)', (item_id, get_jwt_identity(), rating, review))
        conn.commit()
        close_db_connection(conn)
        return jsonify({'message': 'Review submitted successfully'}), 201
    except sqlite3.Error as e:
        close_db_connection(conn)
        return jsonify({'error': f'Failed to submit review: {e}'}), 500

@app.route('/products', methods=['GET'])
def products():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM Items')
    products_fetch = cursor.fetchall()
    close_db_connection(conn)
    return jsonify({'products': [product for product in products_fetch]})

@app.route('/product/<int:item_id>', methods=['GET'])
def product(item_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM Items WHERE item_id = ?', (item_id,))
    product_fetch = cursor.fetchone()
    if product_fetch:
        cursor.execute('SELECT * FROM Reviews WHERE item_id = ?', (item_id,))
        reviews = cursor.fetchall()
        close_db_connection(conn)
        return jsonify({'product': [product_ for product_ in product_fetch], 'reviews': [review for review in reviews]})
    else:
        close_db_connection(conn)
        return jsonify({'error': f"Product with ID {item_id} not found"}), 404

@app.route('/add_to_cart/<int:item_id>', methods=['PUT'])
@jwt_required()
def add_to_cart(item_id):
    item_id = int(item_id)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if item is already in cart
        cursor.execute('SELECT * FROM Cart WHERE user_id = ? AND item_id = ?', (get_jwt_identity(), item_id))
        cart_item = cursor.fetchone()

        if cart_item:
            cursor.execute('UPDATE Cart SET qty = ? WHERE user_id = ? AND item_id = ?', (cart_item[2] + 1, get_jwt_identity(), item_id))
        else:
            cursor.execute('INSERT INTO Cart (user_id, item_id, qty) VALUES (?, ?, ?)', (get_jwt_identity(), item_id, 1))

        conn.commit()
        close_db_connection(conn)
        return jsonify({'message': 'Item added to cart'}), 200
    except sqlite3.Error as e:
        close_db_connection(conn)
        return jsonify({'error': f'Failed to add item to cart: {e}'}), 500


@app.route('/view_cart', methods=['GET'])
@jwt_required()
def view_cart():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT i.item_id, i.name, i.price, c.qty FROM Cart c INNER JOIN Items i ON c.item_id = i.item_id WHERE user_id = ?', (get_jwt_identity(),))
        cart_items = cursor.fetchall()
        close_db_connection(conn)

        return jsonify({'cart': [item for item in cart_items]})
    except sqlite3.Error as e:
        close_db_connection(conn)
        return jsonify({'error': f'Failed to retrieve cart: {e}'}), 500

@app.route('/remove_from_cart/<int:item_id>', methods=['DELETE'])
@jwt_required()
def remove_from_cart(item_id):
    item_id = int(item_id)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM Cart WHERE user_id = ? AND item_id = ?', (get_jwt_identity(), item_id))
        conn.commit()
        close_db_connection(conn)
        return jsonify({'message': 'Item removed from cart'}), 200
    except sqlite3.Error as e:
        close_db_connection(conn)
        return jsonify({'error': f'Failed to remove item from cart: {e}'}), 500

@app.route('/checkout', methods=['POST'])
@jwt_required()
def checkout():
    try:
        # Get user ID from JWT
        user_id = get_jwt_identity()

        # Get order details from JSON request
        name = request.json.get('name')
        email = request.json.get('email')
        address = request.json.get('address')
        phone = request.json.get('phone')

        # Validate data
        if not all([name, email, address, phone]):
            return jsonify({'error': 'Missing required information'}), 400

        # Connect to database
        conn = get_db_connection()
        cursor = conn.cursor()

        # Generate unique order ID
        order_id = uuid.uuid4().hex

        # Insert order into database
        cursor.execute('INSERT INTO Orders (order_id, user_id, shipping_address, phone, order_date) VALUES (?, ?, ?, ?, ?)', (order_id, user_id, address, phone, datetime.datetime.now()))

        # Get cart items for user
        cursor.execute('SELECT item_id, qty FROM Cart WHERE user_id = ?', (user_id,))
        cart = cursor.fetchall()

        # Add order items to database
        for item in cart:
            cursor.execute('INSERT INTO Order_Items (order_id, item_id, qty) VALUES (?, ?, ?)', (order_id, item[0], item[1]))

        # Calculate total price
        cursor.execute('SELECT c.item_id, i.name, i.price, c.qty FROM Cart c INNER JOIN Items i ON c.item_id = i.item_id WHERE user_id = ?', (user_id,))
        cart_detailed = cursor.fetchall()
        total = sum([item['price'] * item['qty'] for item in cart_detailed])

        # Clear cart
        cursor.execute('DELETE FROM Cart WHERE user_id = ?', (user_id,))
        conn.commit()
        close_db_connection(conn)

        # Create Stripe checkout session
        if stripe.api_key is None:
            return jsonify({'error': 'Stripe API key not set'}), 500

        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    'price_data': {
                        'currency': 'sgd',
                        'product': 'prod_Pb3YILaur4mxxM',  # Replace with your product ID
                        'unit_amount': int(total * 100)
                    },
                    'quantity': 1,
                },
            ],
            mode='payment',
            success_url=YOUR_DOMAIN + '/success',
            cancel_url=YOUR_DOMAIN + '/cancel',
        )

        return jsonify({'checkout_url': checkout_session.url})

    except Exception as e:
        close_db_connection(conn)
        return jsonify({'error': f'Failed to create order: {e}'}), 500

@app.route('/search', methods=['GET'])
@jwt_required()
def search():
    query = request.args.get('query')

    if not query:
        return jsonify({'error': 'Missing query parameter'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM Items WHERE name LIKE ?', ('%' + query + '%',))
        products = cursor.fetchall()
        close_db_connection(conn)
        return jsonify({'products': [product for product in products]})
    except sqlite3.Error as e:
        close_db_connection(conn)
        return jsonify({'error': f'Failed to search for products: {e}'}), 500

@app.route('/admin', methods=['GET'])
@jwt_required()
def admin():
    # Check if user is admin
    current_user = get_jwt_identity()
    if current_user != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM Items')
        products = cursor.fetchall()
        close_db_connection(conn)
        return jsonify({'products': [product for product in products]})
    except sqlite3.Error as e:
        close_db_connection(conn)
        return jsonify({'error': f'Failed to retrieve products: {e}'}), 500

@app.route('/admin/add', methods=['POST'])
@jwt_required()
def add_product():
    # Get JSON data
    name = request.json.get('name')
    price = request.json.get('price')
    description = request.json.get('description')

    # Validate inputs (optional, but recommended)
    if not all([name, price, description]):
        return jsonify({'error': 'Missing required fields'}), 400

    # Add item to database
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO Items (name, price, description) VALUES (?, ?, ?)', (name, price, description))
        conn.commit()
        close_db_connection(conn)
        return jsonify({'message': 'Product added successfully'}), 201
    except sqlite3.Error as e:
        close_db_connection(conn)
        return jsonify({'error': f'Failed to add product: {e}'}), 500

@app.route('/admin/remove/<int:item_id>', methods=['DELETE'])
@jwt_required()
def remove_product(item_id):
    # Check if user is admin
    current_user = get_jwt_identity()
    if current_user != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM Items WHERE item_id = ?', (item_id,))
        conn.commit()
        close_db_connection(conn)
        return jsonify({'message': 'Product removed successfully'}), 200
    except sqlite3.Error as e:
        close_db_connection(conn)
        return jsonify({'error': f'Failed to remove product: {e}'}), 500

@app.route('/admin/modify/<int:item_id>', methods=['GET', 'POST'])
@jwt_required()
def edit_product(item_id):
    # Check if user is admin
    current_user = get_jwt_identity()
    if current_user != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401

    if request.method == 'POST':
        # Get form data
        name = request.json.get('name')
        price = request.json.get('price')
        description = request.json.get('description')

        # Validate inputs (optional, but recommended)
        if not all([name, price, description]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Update item in database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE Items SET name = ?, price = ?, description = ? WHERE item_id = ?', (name, price, description, item_id))
        conn.commit()
        close_db_connection(conn)

        return jsonify({'message': 'Product updated successfully'})
    else:
        # Get specific item from database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM Items WHERE item_id = ?', (item_id,))
        product = cursor.fetchone()
        close_db_connection(conn)

        # Return product data as JSON
        return jsonify({'product': product})

@app.route('/register', methods=['POST'])
def register():
    username = request.json.get('username')
    email = request.json.get('email')
    password = request.json.get('password')
    confirm_password = request.json.get('confirm_password')

    # Validate inputs
    if not all([username, email, password, confirm_password]):
        return jsonify({'error': 'Missing required fields'}), 400
    if password != confirm_password:
        return jsonify({'error': 'Passwords do not match'}), 400

    # Check for existing username
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM Users WHERE username = ?', (username,))
    existing_user = cursor.fetchone()
    close_db_connection(conn)

    if existing_user:
        return jsonify({'error': 'Username already exists'}), 400

    # Hash password and insert user
    hashed_password = generate_password_hash(password)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO Users (username, email, password) VALUES (?, ?, ?)', (username, email, hashed_password))
    conn.commit()
    close_db_connection(conn)

    # Create access token
    access_token = create_access_token(identity=username)

    return jsonify({'message': 'Registration successful', 'token': access_token})

# Authentication routes
@app.route('/login', methods=['POST'])
def login():
    username = request.json.get('username')
    password = request.json.get('password')
    if not username or not password:
        return jsonify({'error': 'Missing username or password'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM Users WHERE username = ?', (username,))
    user = cursor.fetchone()
    close_db_connection(conn)

    if user and check_password_hash(user['password'], password):
        access_token = create_access_token(identity=username)
        return jsonify({'token': access_token})
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    jti = get_jwt()["jti"]
    jwt_blacklisted_tokens.add(jti)
    return jsonify({'message': 'Logged out successfully'}), 200

if __name__ == '__main__':
    app.run(debug=True)