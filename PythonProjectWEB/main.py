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

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    print(f"создана папка: {UPLOAD_FOLDER}")

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Убираем дублирование CORS
CORS(app, supports_credentials=True, origins='*')

db = SQLAlchemy(app)


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


with app.app_context():
    db.create_all()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/api/test', methods=['GET'])
def test():
    return jsonify({'ok': True})


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

    print(f"новый пользователь: {name}")

    return jsonify({'ok': True})


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    name = data.get('username')
    password = data.get('password')

    if not name or not password:
        return jsonify({'error': 'поля пустые'}), 400

    user = User.query.filter_by(name=name).first()

    if not user or not check_password_hash(user.password, password):
        return jsonify({'error': 'неверно'}), 400

    user.last_active = datetime.now().isoformat()
    db.session.commit()

    print(f"вошел пользователь: {name}")

    return jsonify({'ok': True, 'username': name})


@app.route('/api/upload_avatar', methods=['POST'])
def upload_avatar():
    username = request.form.get('username')

    if not username:
        return jsonify({'error': 'нет пользователя'}), 401

    if 'file' not in request.files:
        return jsonify({'error': 'нет файла'}), 400

    file = request.files['file']
    print(f"файл: {file.filename}")

    if file.filename == '':
        return jsonify({'error': 'не выбрал файл'}), 400

    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = secure_filename(f"{username}_{int(datetime.now().timestamp())}.{ext}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        file.save(filepath)
        print(f"сохранен файл: {filepath}")

        user = User.query.filter_by(name=username).first()
        if user:
            avatar_url = f'/uploads/{filename}'
            user.avatar = avatar_url
            db.session.commit()
            print(f"обновлен аватар: {avatar_url}")
            return jsonify({'url': avatar_url})
        else:
            print(f"нет пользователя: {username}")
            return jsonify({'error': 'нет пользователя'}), 404

    print(f"не тот формат: {file.filename}")
    return jsonify({'error': 'не тот формат'}), 400


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


@app.route('/api/messages', methods=['GET'])
def get_messages():
    username = request.args.get('username')

    if not username:
        return jsonify({'error': 'нет пользователя'}), 401

    messages = Message.query.order_by(Message.id.desc()).limit(50).all()
    messages = messages[::-1]

    return jsonify({'messages': [{'sender': m.sender, 'content': m.content, 'time': m.time} for m in messages]})


@app.route('/api/users', methods=['GET'])
def get_users():
    username = request.args.get('username')

    if not username:
        return jsonify({'error': 'нет пользователя'}), 401

    users = User.query.filter(User.name != username).all()

    return jsonify({'users': [{'name': u.name, 'last': u.last_active, 'avatar': u.avatar} for u in users]})


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


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


@app.route('/', methods=['GET'])
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>RedChat</title>
        <!-- Bootstrap CSS -->
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {
                background: #888;
            }

            .custom-container {
                max-width: 500px;
                margin: 0 auto;
                padding: 20px;
            }

            .message-area {
                height: 450px;
                overflow-y: auto;
                background: transparent;
                padding: 10px;
            }

            .msg {
                margin-bottom: 10px;
                padding: 8px;
                max-width: 70%;
                display: flex;
                align-items: flex-start;
                gap: 8px;
            }

            .msg-me {
                background: #dc3545 !important;
                color: white !important;
                margin-left: auto !important;
            }

            .msg-other {
                background: #6c757d !important;
                color: white !important;
            }

            .msg-avatar {
                width: 30px;
                height: 30px;
                border-radius: 0 !important;
                object-fit: cover;
                background: #555;
                flex-shrink: 0;
            }

            .msg-content {
                flex: 1;
            }

            .msg-name {
                font-size: 11px;
                font-weight: bold;
                margin-bottom: 3px;
            }

            .site-title {
                font-size: 32px;
                font-weight: bold;
                text-align: center;
                margin-bottom: 20px;
                color: white;
            }

            .no-messages {
                text-align: center;
                color: #aaa;
                padding: 20px;
            }

            *, *::before, *::after {
                border-radius: 0 !important;
                box-shadow: none !important;
                outline: none !important;
            }

            .card, .card-body {
                border: none !important;
                background: transparent !important;
                padding: 0 !important;
            }

            .form-control {
                border-radius: 0 !important;
                background: #aaa;
                border: 1px solid #777;
                color: black;
            }

            .form-control::placeholder {
                color: #333;
            }

            .form-control:focus {
                box-shadow: none !important;
                border-color: #777 !important;
                background: #999;
            }

            .btn {
                border-radius: 0 !important;
            }

            .weather-btn {
                background: #6c757d;
                color: white;
                border: none;
                padding: 8px;
                margin-bottom: 10px;
                cursor: pointer;
                text-align: center;
                width: 100%;
            }

            .weather-display {
                background: #6c757d;
                color: white;
                padding: 8px;
                margin-bottom: 10px;
                text-align: center;
            }

            h2 {
                color: white;
                margin-bottom: 20px;
            }

            .avatar-preview {
                margin: 5px 0;
                text-align: center;
            }

            .avatar-preview img {
                max-width: 50px;
                max-height: 50px;
                background: #666;
                padding: 2px;
            }

            .hidden {
                display: none;
            }
        </style>
    </head>
    <body>
        <div class="custom-container">
            <div class="site-title">RedChat</div>

            <div id="loginPanel">
                <h2 class="text-center">Вход</h2>
                <input type="text" id="loginName" class="form-control mb-2" placeholder="имя">
                <input type="password" id="loginPass" class="form-control mb-2" placeholder="пароль">
                <button onclick="login()" class="btn btn-danger w-100 mb-2">Войти</button>
                <div class="text-center">
                    <a href="#" onclick="showReg()" class="text-danger">Регистрация</a>
                </div>
                <div id="loginErr" class="alert alert-danger mt-2 d-none"></div>
            </div>

            <div id="regPanel" class="hidden">
                <h2 class="text-center">регистрация</h2>
                <input type="text" id="regName" class="form-control mb-2" placeholder="имя">
                <input type="password" id="regPass" class="form-control mb-2" placeholder="пароль (6+)">
                <input type="file" id="regAvatar" class="form-control mb-2" accept="image/*" onchange="previewAvatar()">
                <div id="avatarPreview" class="avatar-preview"></div>
                <button onclick="register()" class="btn btn-danger w-100 mb-2">Зарегистрироваться</button>
                <div class="text-center">
                    <a href="#" onclick="showLogin()" class="text-danger">вход</a>
                </div>
                <div id="regErr" class="alert alert-danger mt-2 d-none"></div>
            </div>

            <div id="chatPanel" class="hidden">
                <div id="weatherContainer">
                    <button onclick="getWeather()" class="weather-btn">погода в мск</button>
                </div>

                <div class="message-area" id="messagesDiv">
                    <div class="no-messages">пусто</div>
                </div>

                <div class="mt-3">
                    <input type="text" id="msgInput" class="form-control mb-2" placeholder="сообщение" onkeypress="if(event.key==='Enter') send()">
                    <button onclick="send()" class="btn btn-danger w-100">отправить</button>
                </div>
            </div>
        </div>

        <script>
            let currentUser = null;
            let usersData = {};

            async function request(url, method, data) {
                const options = {
                    method: method,
                    headers: {
                        'Content-Type': 'application/json'
                    }
                };

                if (data) {
                    options.body = JSON.stringify(data);
                }

                // ИСПРАВЛЕНО: убираем лишний /api/login
                const response = await fetch('/api' + url, options);
                const result = await response.json();

                if (!response.ok) {
                    throw new Error(result.error || 'Ошибка');
                }

                return result;
            }

            function previewAvatar() {
                const file = document.getElementById('regAvatar').files[0];
                const preview = document.getElementById('avatarPreview');

                if (file) {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        preview.innerHTML = `<img src="${e.target.result}" alt="аватар">`;
                    };
                    reader.readAsDataURL(file);
                } else {
                    preview.innerHTML = '';
                }
            }

            async function uploadAvatar(username, file) {
                const formData = new FormData();
                formData.append('username', username);
                formData.append('file', file);

                const response = await fetch('/api/upload_avatar', {
                    method: 'POST',
                    body: formData  // ИСПРАВЛЕНО: убираем headers, они не нужны для FormData
                });
                const result = await response.json();
                return result.url;
            }

            async function register() {
                const name = document.getElementById('regName').value;
                const pass = document.getElementById('regPass').value;
                const avatarFile = document.getElementById('regAvatar').files[0];
                const errDiv = document.getElementById('regErr');

                if (!name || !pass) {
                    errDiv.textContent = 'поля пустые';
                    errDiv.classList.remove('d-none');
                    return;
                }
                if (pass.length < 6) {
                    errDiv.textContent = 'мало символов';
                    errDiv.classList.remove('d-none');
                    return;
                }

                errDiv.classList.add('d-none');

                try {
                    await request('/register', 'POST', {username: name, password: pass});

                    if (avatarFile) {
                        await uploadAvatar(name, avatarFile);
                    }

                    alert('аккаунт создан, войдите');
                    showLogin();
                    document.getElementById('loginName').value = name;
                    document.getElementById('regAvatar').value = '';
                    document.getElementById('avatarPreview').innerHTML = '';
                } catch(e) {
                    errDiv.textContent = e.message;
                    errDiv.classList.remove('d-none');
                }
            }

            async function login() {
                const name = document.getElementById('loginName').value;
                const pass = document.getElementById('loginPass').value;
                const errDiv = document.getElementById('loginErr');

                if (!name || !pass) {
                    errDiv.textContent = 'поля пустые';
                    errDiv.classList.remove('d-none');
                    return;
                }

                errDiv.classList.add('d-none');

                try {
                    const result = await request('/login', 'POST', {username: name, password: pass});
                    currentUser = result.username;

                    await loadUsers();

                    document.getElementById('loginPanel').classList.add('hidden');
                    document.getElementById('regPanel').classList.add('hidden');
                    document.getElementById('chatPanel').classList.remove('hidden');

                    await loadMessages();

                    if (window.timer) clearInterval(window.timer);
                    window.timer = setInterval(() => {
                        loadMessages();
                        loadUsers();
                    }, 3000);

                } catch(e) {
                    errDiv.textContent = e.message;
                    errDiv.classList.remove('d-none');
                }
            }

            async function loadUsers() {
                try {
                    const data = await request('/users?username=' + currentUser, 'GET');
                    if (data.users) {
                        data.users.forEach(user => {
                            usersData[user.name] = user;
                        });
                    }
                } catch(e) {
                    console.log('ошибка пользователя:', e);
                }
            }

            async function send() {
                const input = document.getElementById('msgInput');
                const text = input.value.trim();
                if (!text) return;

                try {
                    await request('/messages', 'POST', {
                        username: currentUser,
                        content: text
                    });
                    input.value = '';
                    await loadMessages();
                } catch(e) {
                    alert('ошибка: ' + e.message);
                }
            }

            async function loadMessages() {
                try {
                    const data = await request('/messages?username=' + currentUser, 'GET');
                    const container = document.getElementById('messagesDiv');

                    if (!data.messages || data.messages.length === 0) {
                        container.innerHTML = '<div class="no-messages">пусто</div>';
                        return;
                    }

                    container.innerHTML = '';

                    for (const msg of data.messages) {
                        const isMe = msg.sender === currentUser;
                        const div = document.createElement('div');
                        div.className = `msg ${isMe ? 'msg-me' : 'msg-other'} p-2 mb-2`;

                        if (!isMe) {
                            const avatarUrl = usersData[msg.sender]?.avatar || '';
                            const avatarImg = document.createElement('img');
                            avatarImg.className = 'msg-avatar';
                            avatarImg.src = avatarUrl ? avatarUrl : 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%23666"%3E%3Cpath d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/%3E%3C/svg%3E';
                            avatarImg.style.background = '#555';
                            avatarImg.style.padding = '2px';
                            div.appendChild(avatarImg);
                        }

                        const contentDiv = document.createElement('div');
                        contentDiv.className = 'msg-content';

                        if (!isMe) {
                            const nameDiv = document.createElement('div');
                            nameDiv.className = 'msg-name';
                            nameDiv.textContent = msg.sender;
                            contentDiv.appendChild(nameDiv);
                        }

                        const textDiv = document.createElement('div');
                        textDiv.textContent = msg.content;
                        contentDiv.appendChild(textDiv);

                        div.appendChild(contentDiv);
                        container.appendChild(div);
                    }

                    container.scrollTop = container.scrollHeight;
                } catch(e) {
                    console.log(e);
                }
            }

            async function getWeather() {
                const container = document.getElementById('weatherContainer');
                const url = '/api/weather';

                try {
                    const response = await fetch(url);
                    const data = await response.json();

                    if (data.error) {
                        container.innerHTML = '<button onclick="getWeather()" class="weather-btn">погода в мск</button>';
                    } else {
                        container.innerHTML = `
                            <div class="weather-display">
                                ${data.temperature}°C | ветер: ${data.wind_speed} км/ч
                                <button onclick="getWeather()" style="float: right; background: transparent; border: none; color: white; text-decoration: underline; cursor: pointer;">обновить</button>
                            </div>
                        `;
                    }
                } catch(e) {
                    container.innerHTML = '<button onclick="getWeather()" class="weather-btn">погода в мск</button>';
                }
            }

            function showReg() {
                document.getElementById('loginPanel').classList.add('hidden');
                document.getElementById('regPanel').classList.remove('hidden');
                document.getElementById('loginErr').classList.add('d-none');
                document.getElementById('regErr').classList.add('d-none');
            }

            function showLogin() {
                document.getElementById('loginPanel').classList.remove('hidden');
                document.getElementById('regPanel').classList.add('hidden');
                document.getElementById('loginErr').classList.add('d-none');
                document.getElementById('regErr').classList.add('d-none');
            }
        </script>
    </body>
    </html>
    '''


if __name__ == '__main__':
    print('\n' + '=' * 50)
    print('Сервер запущен на http://localhost:5000')
    print('=' * 50 + '\n')
    app.run(debug=True, port=5000)
