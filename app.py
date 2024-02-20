"""
E-commerce CRUD app
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import secrets
import uuid
import datetime

app = Flask(__name__)
app.secret_key = secrets.token_hex() # Generate a random secret key
auth = HTTPBasicAuth()

def sgd(value):
    """Format value as SGD."""
    return f"${value:,.2f}"

# Custom Jinja filter
app.jinja_env.filters["sgd"] = sgd

users = {
    "admin": generate_password_hash("admin")
}

@auth.verify_password
def verify_password(username, password):
    if username in users and \
            check_password_hash(users.get(username), password):
        return username

@app.route('/')
def index():
    username = session.get('username', None)
    return render_template('index.html', username=username)

@app.route('/view_orders')
def view_orders():
    if 'username' in session:
        with sqlite3.connect('db.db') as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM Orders WHERE user_id = ?', (session['username'],))
            orders = cursor.fetchall()
        return render_template('orders.html', orders=orders)
    else:
        return redirect(url_for('login'))

@app.route('/order/<string:order_id>')
def order(order_id):
    if 'username' in session:
        with sqlite3.connect('db.db') as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT i.name, i.price, oi.qty FROM Order_Items oi INNER JOIN Items i ON oi.item_id = i.item_id WHERE order_id = ?', (order_id,))
            order_items = cursor.fetchall()
        return render_template('order.html', order_items=order_items, order_id=order_id)
    else:
        return redirect(url_for('login'))

@app.route('/review')
def review():
    # Query DB to get items user ordered before
    if 'username' in session:
        with sqlite3.connect('db.db') as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT i.name, i.item_id FROM Order_Items oi INNER JOIN Items i ON oi.item_id = i.item_id INNER JOIN Orders o ON o.order_id = oi.order_id WHERE o.user_id = ?', (session['username'],))
            items = cursor.fetchall()
        return render_template('review.html', items=items)
    else:
        return redirect(url_for('login'))

@app.route('/review/<int:item_id>', methods=['GET', 'POST'])
def review_item(item_id):
    if request.method == 'POST' and 'username' in session:
        # Get form data
        rating = int(request.form['rating'])
        review = request.form['review']
        if not (1 <= rating <= 5):
            flash('Rating must be between 1 and 5', 'error')
            return redirect(url_for('review_item', item_id=item_id))
        # Add review to database
        with sqlite3.connect('db.db') as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO Reviews (item_id, user_id, rating, review) VALUES (?, ?, ?, ?)', (item_id, session['username'], rating, review))
            conn.commit()
        return redirect(url_for('product', id=item_id))
    else:
        return render_template('review_item.html', item_id=item_id)

@app.route('/catalog')
def products():
    # Get items from database
    with sqlite3.connect('db.db') as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM Items')
        products = cursor.fetchall()
    return render_template('catalog.html', products=products)

@app.route('/product/<int:id>')
def product(id):
    # Get specific item from database
    with sqlite3.connect('db.db') as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM Items WHERE item_id = ?', (id,))
        product = cursor.fetchone()
        # Get reviews
        cursor.execute('SELECT * FROM Reviews WHERE item_id = ?', (id,))
        reviews = cursor.fetchall()
    return render_template('product.html', product=product, reviews=reviews)

@app.route('/add_to_cart/<int:item_id>')
def add_to_cart(item_id):
    item_id = int(item_id)

    if 'cart' not in session:
        session['cart'] = {}
    session['cart'][item_id] = session['cart'].get(item_id, 0) + 1

    # Update cart in db if logged in
    if 'username' in session:
        with sqlite3.connect('db.db') as conn:
            cursor = conn.cursor()
            # Check if item is already in cart
            cursor.execute('SELECT * FROM Cart WHERE user_id = ? AND item_id = ?', (session['username'], item_id))
            cart_item = cursor.fetchone()
            if cart_item:
                cursor.execute('UPDATE Cart SET qty = ? WHERE user_id = ? AND item_id = ?', (cart_item[2] + 1, session['username'], item_id))
            else:
                cursor.execute('INSERT INTO Cart (user_id, item_id, qty) VALUES (?, ?, ?)', (session['username'], item_id, 1))
            conn.commit()
        return redirect(url_for('view_cart'))
    else:
        return redirect(url_for('login'))


@app.route('/view_cart')
def view_cart():

    if 'username' in session:
        # load cart from db
        with sqlite3.connect('db.db') as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT i.item_id, i.name, i.price, c.qty FROM Cart c INNER JOIN Items i ON c.item_id = i.item_id WHERE user_id = ?', (session['username'],))
            cart = cursor.fetchall()
            
        return render_template('cart.html', cart=cart)
    else:
        return redirect(url_for('login'))

@app.route('/remove_from_cart/<int:item_id>')
def remove_from_cart(item_id):
    item_id = int(item_id)
    # Remove from db if logged in
    if 'username' in session:
        with sqlite3.connect('db.db') as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM Cart WHERE user_id = ? AND item_id = ?', (session['username'], item_id))
            conn.commit()
    return redirect(url_for('view_cart'))

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if request.method == 'POST':
        # Get form data
        name = request.form['name']
        email = request.form['email']
        address = request.form['address']
        phone = request.form['phone']
        # Add order to database
        with sqlite3.connect('db.db') as conn:
            # Generate Unique Order ID
            ORDER_ID = uuid.uuid4().hex
            cursor = conn.cursor()
            cursor.execute('INSERT INTO Orders (order_id, user_id, shipping_address, phone, order_date) VALUES (?, ?, ?, ?, ?)', (ORDER_ID, session['username'], address, phone, datetime.datetime.now()))
            # Add order items to database
            cursor.execute('SELECT item_id, qty FROM Cart WHERE user_id = ?', (session['username'],))
            cart = cursor.fetchall()
            for item in cart:
                cursor.execute('INSERT INTO Order_Items (order_id, item_id, qty) VALUES (?, ?, ?)', (ORDER_ID, item[0], item[1]))
            # Clear cart
            cursor.execute('DELETE FROM Cart WHERE user_id = ?', (session['username'],))
            conn.commit()
        return redirect(url_for('index'))
    else:
        # Get cart items details from database
        if 'username' in session:
            with sqlite3.connect('db.db') as conn:
                cart = session.get('cart', {})
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT i.item_id, i.name, i.price, c.qty FROM Cart c INNER JOIN Items i ON c.item_id = i.item_id WHERE user_id = ?', (session['username'],))
                cart_detailed = cursor.fetchall()
                total = sum([item['price'] * item['qty'] for item in cart_detailed])
            return render_template('checkout.html', cart=cart_detailed, total=total)
        else:
            return redirect(url_for('login'))

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query')
    with sqlite3.connect('db.db') as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM Items WHERE name LIKE ?', ('%' + query + '%',))
        products = cursor.fetchall()
    return render_template('search.html', products=products)

@app.route('/admin')
@auth.login_required
def admin():
    # Get items from database
    with sqlite3.connect('db.db') as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM Items')
        products = cursor.fetchall()
    return render_template('admin.html', products=products)

@app.route('/admin/add', methods=['GET', 'POST'])
@auth.login_required
def add_product():
    if request.method == 'POST':
        # Get form data
        name = request.form['name']
        price = float(request.form['price'])
        description = request.form['description']
        # Add item to database
        with sqlite3.connect('db.db') as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO Items (name, price, description) VALUES (?, ?, ?)', (name, price, description))
            conn.commit()
        return redirect(url_for('admin'))
    else:
        return render_template('add_product.html')

@app.route('/admin/remove/<int:item_id>')
@auth.login_required
def remove_product(item_id):
    # Remove item from database
    with sqlite3.connect('db.db') as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM Items WHERE item_id = ?', (item_id,))
        conn.commit()
    return redirect(url_for('admin'))

@app.route('/admin/modify/<int:item_id>', methods=['GET', 'POST'])
@auth.login_required
def edit_product(item_id):
    if request.method == 'POST':
        # Get form data
        name = str(request.form['name'])
        price = float(request.form['price'])
        description = str(request.form['description'])
        # Update item in database
        with sqlite3.connect('db.db') as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE Items SET name = ?, price = ?, description = ? WHERE item_id = ?', (name, price, description, item_id))
            conn.commit()
        return redirect(url_for('admin'))
    else:
        # Get specific item from database
        with sqlite3.connect('db.db') as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM Items WHERE item_id = ?', (item_id,))
            product = cursor.fetchone()
        return render_template('edit_product.html', product=product, item_id=item_id)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Get form data
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm = request.form['confirm']
        if password != confirm:
            flash('Passwords do not match', 'error')
            return redirect(url_for('register'))
        # Add user to database
        with sqlite3.connect('db.db') as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO Users (username, email, password) VALUES (?, ?, ?)', (username, email, generate_password_hash(password)))
            conn.commit()
        return redirect(url_for('index'))
    else:
        return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get form data
        username = request.form['username']
        password = request.form['password']
        # Check if user exists
        with sqlite3.connect('db.db') as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM Users WHERE username = ?', (username,))
            user = cursor.fetchone()
        if user and check_password_hash(user['password'], password):
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return 'Invalid credentials'
    else:
        return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)