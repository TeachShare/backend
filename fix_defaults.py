from app import app
from models import db, ResourceCollection

def fix_db():
    with app.app_context():
        # Update NULLs to defaults
        db.session.execute(db.text("UPDATE resource_collection SET collaboration_mode = 'none' WHERE collaboration_mode IS NULL"))
        db.session.execute(db.text("UPDATE resource_collection SET visibility = 'public' WHERE visibility IS NULL"))
        db.session.execute(db.text("UPDATE resource_collection SET allow_remixing = TRUE WHERE allow_remixing IS NULL"))
        db.session.execute(db.text("UPDATE resource_collection SET is_hidden = FALSE WHERE is_hidden IS NULL"))
        db.session.commit()
        print("Database defaults fixed.")

if __name__ == "__main__":
    fix_db()
