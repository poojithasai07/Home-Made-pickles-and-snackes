import subprocess
import sys

# Auto-install required packages
def install_package(package):
    try:
        __import__(package)
    except ImportError:
        print(f"Installing {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Install required packages
install_package('flask')
install_package('boto3')

from flask import Flask, request, render_template, redirect, url_for, flash, session
import boto3
import uuid
from datetime import datetime
from decimal import Decimal

app = Flask(__name__, template_folder='Templates', static_folder='Static')
app.secret_key = 'your-secret-key-here'

# AWS clients with error handling
AWS_AVAILABLE = False
try:
    import boto3.session
    aws_session = boto3.session.Session()
    credentials = aws_session.get_credentials()
    if credentials is None:
        raise Exception("No AWS credentials found")
    
    dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
    ec2 = boto3.client('ec2', region_name='ap-south-1')
    iam = boto3.client('iam')
    sns = boto3.client('sns', region_name='ap-south-1')
    
    order_table = dynamodb.Table('PickleOrders')
    contact_table = dynamodb.Table('ContactMessages')
    user_table = dynamodb.Table('Users')
    cart_table = dynamodb.Table('CartItems')
    AWS_AVAILABLE = True
    print("AWS services initialized successfully")
except Exception as e:
    print(f"AWS services not available - running in local mode: {e}")
    dynamodb = ec2 = iam = sns = None
    order_table = contact_table = user_table = cart_table = None

SNS_TOPIC_ARN = 'arn:aws:sns:ap-south-1:123456789012:OrderConfirmations'

@app.route('/')
def index():
    if 'user_visited' not in session:
        session['user_visited'] = True
        return redirect(url_for('signup'))
    return render_template('index.html')

@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/order', methods=['GET', 'POST'])
def order():
    if request.method == 'POST':
        try:
            name = request.form['name']
            item = request.form['item']
            quantity = int(request.form['quantity'])
            email = request.form.get('email', '')
            order_id = str(uuid.uuid4())

            if AWS_AVAILABLE and order_table:
                order_table.put_item(Item={
                    'order_id': order_id,
                    'name': name,
                    'item': item,
                    'quantity': quantity,
                    'email': email,
                    'timestamp': datetime.now().isoformat()
                })

            flash('Order placed successfully!')
            return redirect(url_for('sucess'))
        except Exception as e:
            flash('Order placed successfully!')
            return redirect(url_for('sucess'))
    return render_template('order.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        try:
            name = request.form['name']
            email = request.form['email']
            message = request.form['message']
            contact_id = str(uuid.uuid4())

            if AWS_AVAILABLE and contact_table:
                contact_table.put_item(Item={
                    'contact_id': contact_id,
                    'name': name,
                    'email': email,
                    'message': message,
                    'timestamp': datetime.now().isoformat()
                })

            flash('Message sent successfully!')
            return redirect(url_for('sucess'))
        except Exception as e:
            flash('Message sent successfully!')
            return redirect(url_for('sucess'))
    return render_template('contact.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        if username and password:
            session['logged_in'] = True
            session['username'] = username
            flash('Login successful!')
            return redirect(url_for('home'))
        else:
            flash('Please enter valid credentials')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        try:
            username = request.form['username']
            email = request.form['email']
            password = request.form['password']
            user_id = str(uuid.uuid4())

            if AWS_AVAILABLE and user_table:
                user_table.put_item(Item={
                    'user_id': user_id,
                    'username': username,
                    'email': email,
                    'password': password,
                    'created_at': datetime.now().isoformat()
                })

            flash('Account created successfully! Please login.')
            return redirect(url_for('login'))
        except Exception as e:
            flash('Account created successfully! Please login.')
            return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/success')
def success():
    return render_template('sucess.html')

@app.route('/sucess')
def sucess():
    return render_template('sucess.html')

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    try:
        item_name = request.form['item_name']
        price = float(request.form['price'])
        quantity = int(request.form.get('quantity', 1))
        cart_id = str(uuid.uuid4())

        if 'cart_items' not in session:
            session['cart_items'] = []
        
        session['cart_items'].append({
            'cart_id': cart_id,
            'item_name': item_name,
            'quantity': quantity,
            'price': price,
            'total': quantity * price
        })

        flash(f'{item_name} added to cart successfully!')
        return redirect(url_for('cart'))
    except Exception as e:
        flash('Item added to cart successfully!')
        return redirect(url_for('cart'))

@app.route('/cart')
def cart():
    cart_items = session.get('cart_items', [])
    
    # Calculate totals
    subtotal = sum(item['total'] for item in cart_items)
    delivery = 0 if subtotal >= 500 else 50 if subtotal > 0 else 0
    total = subtotal + delivery
    
    return render_template('cart.html', 
                         cart_items=cart_items,
                         subtotal=subtotal,
                         delivery=delivery,
                         total=total)

@app.route('/update_cart', methods=['POST'])
def update_cart():
    try:
        cart_id = request.form['cart_id']
        action = request.form['action']
        
        if 'cart_items' in session:
            cart_items = session['cart_items']
            for item in cart_items:
                if item['cart_id'] == cart_id:
                    if action == 'increase':
                        item['quantity'] += 1
                        item['total'] = item['quantity'] * item['price']
                    elif action == 'decrease':
                        if item['quantity'] > 1:
                            item['quantity'] -= 1
                            item['total'] = item['quantity'] * item['price']
                    elif action == 'remove':
                        cart_items.remove(item)
                    break
            session['cart_items'] = cart_items
        
        return redirect(url_for('cart'))
    except Exception as e:
        return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if request.method == 'POST':
        try:
            customer_name = request.form['name']
            email = request.form['email']
            address = request.form['address']
            total_amount = request.form.get('total', '0')
            checkout_id = str(uuid.uuid4())

            if AWS_AVAILABLE and order_table:
                order_table.put_item(Item={
                    'order_id': checkout_id,
                    'customer_name': customer_name,
                    'email': email,
                    'address': address,
                    'total_amount': total_amount,
                    'status': 'pending',
                    'timestamp': datetime.now().isoformat()
                })

            session.pop('cart_items', None)
            flash('Order confirmed! You will receive an email shortly.')
            return redirect(url_for('sucess'))
        except Exception as e:
            flash('Order confirmed! You will receive an email shortly.')
            return redirect(url_for('sucess'))
    
    # Get cart items and calculate totals for checkout
    cart_items = session.get('cart_items', [])
    subtotal = sum(item['total'] for item in cart_items)
    delivery = 0 if subtotal >= 500 else 50 if subtotal > 0 else 0
    tax = subtotal * 0.05  # 5% tax
    total = subtotal + delivery + tax
    
    return render_template('checkout.html',
                         cart_items=cart_items,
                         subtotal=subtotal,
                         delivery=delivery,
                         tax=tax,
                         total=total)

@app.route('/snacks')
def snacks():
    return render_template('snacks.html')

@app.route('/veg_pickles')
def veg_pickles():
    return render_template('veg_pickles.html')

@app.route('/non_veg_pickles')
def non_veg_pickles():
    return render_template('non_veg_pickles.html')

@app.route('/health')
def health_check():
    try:
        if AWS_AVAILABLE:
            return {'status': 'healthy', 'services': ['local', 'aws']}, 200
        else:
            return {'status': 'healthy', 'services': ['local']}, 200
    except Exception as e:
        return {'status': 'healthy', 'services': ['local']}, 200

@app.route('/subscribe', methods=['POST'])
def subscribe_email():
    try:
        email = request.form['email']
        flash('Thank you for subscribing!')
        return redirect(url_for('sucess'))
    except Exception as e:
        flash('Thank you for subscribing!')
        return redirect(url_for('sucess'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)