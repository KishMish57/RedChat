from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import requests
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'secret-key-123'

# Настройка загрузки файлов
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# СОЗДАЕМ ПАПКУ ЕСЛИ ЕЕ НЕТ
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    print(f"📁 Создана папка: {UPLOAD_FOLDER}")

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB лимит

CORS(app, supports_credentials=True, origins='*')

db = SQLAlchemy(app)


# ORM Модели
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    last_active = db.Column(db.String(50), nullable=False)
    avatar = db.Column(db.String(200), default=None)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(80), nullable=False)
    content = db.Column(db.String(500), nullable=False)
    time = db.Column(db.String(10), nullable=False)


# Создаем таблицы
with app.app_context():
    db.create_all()
    print("✅ База данных создана")


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ============= API МАРШРУТЫ =============

@app.route('/api/test', methods=['GET'])
def test():
    return jsonify({'ok': True})


# Регистрация
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    name = data.get('username')
    password = data.get('password')

    if not name or not password:
        return jsonify({'error': 'Заполните поля'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Пароль минимум 6 символов'}), 400

    if User.query.filter_by(name=name).first():
        return jsonify({'error': 'Пользователь уже есть'}), 400

    new_user = User(
        name=name,
        password=generate_password_hash(password),
        last_active=datetime.now().isoformat()
    )
    db.session.add(new_user)
    db.session.commit()

    print(f"✅ Зарегистрирован пользователь: {name}")

    return jsonify({'ok': True})


# Вход
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    name = data.get('username')
    password = data.get('password')

    if not name or not password:
        return jsonify({'error': 'Заполните поля'}), 400

    user = User.query.filter_by(name=name).first()

    if not user or not check_password_hash(user.password, password):
        return jsonify({'error': 'Неверные данные'}), 400

    user.last_active = datetime.now().isoformat()
    db.session.commit()

    print(f"✅ Вход пользователя: {name}")

    return jsonify({'ok': True, 'username': name})


# ЗАГРУЗКА АВАТАРА (ОТДЕЛЬНЫЙ МАРШРУТ)
@app.route('/api/upload_avatar', methods=['POST'])
def upload_avatar():
    print("📸 Получен запрос на загрузку аватара")

    # Получаем username из form-data
    username = request.form.get('username')
    print(f"👤 Имя пользователя: {username}")

    if not username:
        return jsonify({'error': 'Не указан пользователь'}), 401

    if 'file' not in request.files:
        return jsonify({'error': 'Нет файла'}), 400

    file = request.files['file']
    print(f"📁 Имя файла: {file.filename}")

    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400

    if file and allowed_file(file.filename):
        # Создаем безопасное имя файла
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = secure_filename(f"{username}_{int(datetime.now().timestamp())}.{ext}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # СОХРАНЯЕМ ФАЙЛ
        file.save(filepath)
        print(f"💾 Файл сохранен: {filepath}")

        # Обновляем путь к аватару в БД
        user = User.query.filter_by(name=username).first()
        if user:
            avatar_url = f'/uploads/{filename}'
            user.avatar = avatar_url
            db.session.commit()
            print(f"🖼️ Аватар обновлен в БД: {avatar_url}")
            return jsonify({'url': avatar_url})
        else:
            print(f"❌ Пользователь не найден: {username}")
            return jsonify({'error': 'Пользователь не найден'}), 404

    print(f"❌ Неподдерживаемый формат: {file.filename}")
    return jsonify({'error': 'Неподдерживаемый формат. Используйте PNG, JPG, JPEG, GIF'}), 400


# Отправка сообщения
@app.route('/api/messages', methods=['POST'])
def send_message():
    data = request.json
    username = data.get('username')
    content = data.get('content')

    if not username:
        return jsonify({'error': 'нет пользователя'}), 401

    if not content:
        return jsonify({'error': 'пусто'}), 400

    new_msg = Message(
        sender=username,
        content=content,
        time=datetime.now().strftime('%H:%M')
    )
    db.session.add(new_msg)
    db.session.commit()

    return jsonify({'id': new_msg.id, 'sender': username, 'content': content, 'time': new_msg.time})


# Получение сообщений
@app.route('/api/messages', methods=['GET'])
def get_messages():
    username = request.args.get('username')

    if not username:
        return jsonify({'error': 'нет пользователя'}), 401

    messages = Message.query.order_by(Message.id.desc()).limit(50).all()
    messages = messages[::-1]

    return jsonify({'messages': [{'sender': m.sender, 'content': m.content, 'time': m.time} for m in messages]})


# Получение пользователей (с аватарами)
@app.route('/api/users', methods=['GET'])
def get_users():
    username = request.args.get('username')

    if not username:
        return jsonify({'error': 'нет пользователя'}), 401

    users = User.query.filter(User.name != username).all()

    return jsonify({'users': [{'name': u.name, 'last': u.last_active, 'avatar': u.avatar} for u in users]})


# Раздача загруженных файлов
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# Погода
@app.route('/api/weather', methods=['GET'])
def get_weather():
    try:
        response = requests.get(
            'https://api.open-meteo.com/v1/forecast?latitude=55.75&longitude=37.62&current_weather=true')
        weather_data = response.json()
        current = weather_data.get('current_weather', {})
        return jsonify({
            'temperature': current.get('temperature'),
            'wind_speed': current.get('windspeed')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print('\n' + '=' * 50)
    print('=' * 50 + '\n')
    app.run(debug=True, port=5000)