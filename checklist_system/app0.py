from flask import Flask, render_template, request, redirect, url_for, session, send_file
import pyodbc
from config import Config
import logging
import matplotlib.pyplot as plt
import io
import base64

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = 'your_secret_key'  # Make sure to set a strong secret key in a real application

logging.basicConfig(level=logging.DEBUG)

AUTHORIZED_USERS = {
    'admin': 'password123'
}

def get_db_connection():
    if app.config.get('USE_WINDOWS_AUTH', False):
        connection_string = (
            f"DRIVER={app.config['SQL_DRIVER']};"
            f"SERVER={app.config['SQL_SERVER']};"
            f"DATABASE={app.config['SQL_DATABASE']};"
            f"Trusted_Connection=yes;"
        )
    else:
        connection_string = (
            f"DRIVER={app.config['SQL_DRIVER']};"
            f"SERVER={app.config['SQL_SERVER']};"
            f"DATABASE={app.config['SQL_DATABASE']};"
        )
    try:
        conn = pyodbc.connect(connection_string)
        return conn
    except pyodbc.Error as e:
        app.logger.error(f"Error connecting to database: {e}")
        return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in AUTHORIZED_USERS and AUTHORIZED_USERS[username] == password:
            session['logged_in'] = True
            return redirect(url_for('set_conditions'))
        else:
            return render_template('login.html', message='Invalid username or password.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

@app.route('/')
def index():
    conn = get_db_connection()
    if conn is None:
        return "Database connection error", 500
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM motors')
    motors = cursor.fetchall()
    conn.close()
    return render_template('index.html', motors=motors)

@app.route('/set_conditions', methods=['GET', 'POST'])
def set_conditions():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        current_threshold = request.form.get('current_threshold')
        temperature_threshold = request.form.get('temperature_threshold')
        vibration_threshold = request.form.get('vibration_threshold')

        if not current_threshold or not temperature_threshold or not vibration_threshold:
            return render_template('set_conditions.html', message='All fields are required.')

        current_threshold = float(current_threshold)
        temperature_threshold = float(temperature_threshold)
        vibration_threshold = float(vibration_threshold)

        conn = get_db_connection()
        if conn is None:
            return "Database connection error", 500
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE conditions
            SET current_threshold = ?, temperature_threshold = ?, vibration_threshold = ?
            WHERE id = 1
        ''', (current_threshold, temperature_threshold, vibration_threshold))
        conn.commit()
        conn.close()

        session.pop('logged_in', None)

        return redirect(url_for('index'))
    else:
        conn = get_db_connection()
        if conn is None:
            return "Database connection error", 500
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM conditions WHERE id = 1')
        conditions = cursor.fetchone()
        conn.close()
        return render_template('set_conditions.html', conditions=conditions)

@app.route('/add_motor', methods=['GET', 'POST'])
def add_motor():
    if request.method == 'POST':
        name = request.form.get('name')
        current = request.form.get('current')
        temperature = request.form.get('temperature')
        vibration = request.form.get('vibration')

        if not name or not current or not temperature or not vibration:
            return render_template('add_motor.html', message='All fields are required.')

        current = float(current)
        temperature = float(temperature)
        vibration = float(vibration)

        conn = get_db_connection()
        if conn is None:
            return "Database connection error", 500
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM conditions WHERE id = 1')
        conditions = cursor.fetchone()

        current_threshold = conditions.current_threshold
        temperature_threshold = conditions.temperature_threshold
        vibration_threshold = conditions.vibration_threshold

        current_status = 'OK' if current < current_threshold else 'NOT OK'
        temperature_status = 'OK' if temperature < temperature_threshold else 'NOT OK'
        vibration_status = 'OK' if vibration < vibration_threshold else 'NOT OK'

        cursor.execute('''
            INSERT INTO motors (name, [current], temperature, vibration, current_status, temperature_status, vibration_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, current, temperature, vibration, current_status, temperature_status, vibration_status))
        conn.commit()
        conn.close()

        return redirect(url_for('index'))
    return render_template('add_motor.html')

@app.route('/analysis')
def analysis():
    conn = get_db_connection()
    if conn is None:
        return "Database connection error", 500
    cursor = conn.cursor()
    cursor.execute('SELECT current_status, temperature_status, vibration_status FROM motors')
    statuses = cursor.fetchall()
    conn.close()

    ok_count = sum(status[0] == 'OK' for status in statuses) + \
               sum(status[1] == 'OK' for status in statuses) + \
               sum(status[2] == 'OK' for status in statuses)

    not_ok_count = sum(status[0] == 'NOT OK' for status in statuses) + \
                   sum(status[1] == 'NOT OK' for status in statuses) + \
                   sum(status[2] == 'NOT OK' for status in statuses)

    labels = ['OK', 'NOT OK']
    sizes = [ok_count, not_ok_count]
    colors = ['#4CAF50', '#F44336']

    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
    ax.axis('equal')

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    img_base64 = base64.b64encode(img.getvalue()).decode()

    return render_template('analysis.html', img_base64=img_base64)

if __name__ == '__main__':
    app.run(debug=True)
