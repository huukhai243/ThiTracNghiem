"""Chạy web thi trắc nghiệm.

    python run.py                          chạy tại cổng 8000; máy khác cùng mạng LAN vào bằng IP của máy này
    python run.py --port 5000              đổi cổng
    python run.py create-teacher TÊN       tạo tài khoản giáo viên (tên đã có thì đặt lại mật khẩu)
"""
import argparse
import getpass
import sys

from waitress import serve
from werkzeug.security import generate_password_hash

from quiz import create_app
from quiz.db import get_db, now_iso
from quiz.teacher import lan_ip


def create_teacher(app, username):
    pw = getpass.getpass('Mật khẩu (ít nhất 6 ký tự): ')
    if len(pw) < 6 or pw != getpass.getpass('Nhập lại mật khẩu: '): sys.exit('Mật khẩu quá ngắn hoặc hai lần nhập không khớp.')
    with app.app_context():
        db = get_db()
        with db:
            db.execute('INSERT INTO teachers(username, password_hash, created_at) VALUES (?,?,?) ON CONFLICT(username) '
                       'DO UPDATE SET password_hash = excluded.password_hash', (username, generate_password_hash(pw), now_iso()))
    print(f'Đã lưu tài khoản giáo viên "{username}".')


def main():
    for st in (sys.stdout, sys.stderr):
        try: st.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError): pass
    p = argparse.ArgumentParser(description='Web thi trắc nghiệm')
    p.add_argument('command', nargs='?', choices=['create-teacher'])
    p.add_argument('username', nargs='?')
    p.add_argument('--host', default='0.0.0.0')
    p.add_argument('--port', type=int, default=8000)
    args = p.parse_args()
    app = create_app()
    if args.command == 'create-teacher':
        if not args.username: sys.exit('Dùng: python run.py create-teacher TÊN_ĐĂNG_NHẬP')
        return create_teacher(app, args.username)
    ip = lan_ip()
    print(f'Giáo viên:  http://localhost:{args.port}/teacher')
    print(f'Sinh viên:  http://{ip or "<IP máy này>"}:{args.port}/   (máy cùng mạng LAN/Wi-Fi)')
    print('Nhấn Ctrl+C để dừng.')
    serve(app, host=args.host, port=args.port, threads=16)


if __name__ == '__main__':
    main()
