from app import app, db

with app.app_context():
    result = db.session.execute(db.text("PRAGMA table_info(user);"))
    for row in result:
        print(row)
