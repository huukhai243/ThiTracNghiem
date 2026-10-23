"""Web thi trắc nghiệm: giáo viên tải ngân hàng câu hỏi bằng file Word, sinh viên vào thi bằng mã phòng thi."""
import os
import secrets
from pathlib import Path

from flask import Flask, abort, render_template, request, session

from . import db


def _secret_key(data_dir):
    f = data_dir / 'secret_key'
    if not f.exists():
        f.write_text(secrets.token_hex(32), encoding='utf-8')
        try: os.chmod(f, 0o600)
        except OSError: pass
    return f.read_text(encoding='utf-8').strip()


def create_app(config=None):
    app = Flask(__name__)
    data_dir = Path(os.environ.get('QUIZ_DATA_DIR') or Path(app.root_path).parent / 'data')
    data_dir.mkdir(parents=True, exist_ok=True)
    app.config.update(DATABASE=str(data_dir / 'quiz.db'), SECRET_KEY=os.environ.get('SECRET_KEY') or _secret_key(data_dir),
                      MAX_CONTENT_LENGTH=10 * 1024 * 1024, SESSION_COOKIE_SAMESITE='Lax',
                      PERMANENT_SESSION_LIFETIME=24 * 3600)
    if config: app.config.update(config)
    db.init_db(app.config['DATABASE'])
    app.teardown_appcontext(db.close_db)

    @app.before_request
    def check_csrf():
        if request.method == 'POST':
            token = request.form.get('csrf') or request.headers.get('X-CSRF-Token') or ''
            if not token or not secrets.compare_digest(token, session.get('csrf', '')):
                abort(400, 'Phiên làm việc đã hết hạn. Hãy tải lại trang rồi thử lại.')

    @app.context_processor
    def inject_csrf():
        if 'csrf' not in session: session['csrf'] = secrets.token_urlsafe(24)
        return {'csrf_token': session['csrf']}

    @app.template_filter('vn')
    def vn_time(value, fmt='%H:%M:%S %d/%m/%Y'):
        """Thời gian UTC trong CSDL -> giờ Việt Nam."""
        return db.local(value).strftime(fmt) if value else ''

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def error(e):
        messages = {403: 'Bạn không có quyền xem trang này.', 404: 'Không tìm thấy trang.',
                    413: 'File quá lớn (tối đa 10 MB).'}
        text = messages.get(e.code) if e.code != 400 or not e.description else e.description
        return render_template('error.html', message=text or 'Yêu cầu không hợp lệ.'), e.code

    from .student import bp as student_bp
    from .teacher import bp as teacher_bp
    app.register_blueprint(student_bp)
    app.register_blueprint(teacher_bp)
    return app
