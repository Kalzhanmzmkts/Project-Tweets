from flask import url_for, redirect

from app import create_app
from app.extensions import db

app = create_app()


@app.route('/')
def root_redirect():
    return redirect(url_for('main.home'))


if __name__ == '__main__':
    with app.app_context():
        db.drop_all()
        db.create_all()
    app.run(debug=True)
