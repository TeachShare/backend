from app import app
from models import db, Subject, GradeLevel, ContentType, ResourceCollection

def seed_data():
    with app.app_context():
        print("Seeding subjects...")
        subjects = [
            ("Mathematics", "General", 1),
            ("Science", "General", 2),
            ("English Language Arts", "General", 3),
            ("Social Studies", "General", 4),
            ("Art", "Elective", 5),
            ("Music", "Elective", 6),
            ("Physical Education", "General", 7),
            ("Computer Science", "STEM", 8),
            ("Foreign Languages", "Elective", 9),
            ("Special Education", "Special", 10),
            ("Health", "General", 11),
            ("History", "Social Studies", 12),
            ("Geography", "Social Studies", 13),
            ("Physics", "Science", 14),
            ("Chemistry", "Science", 15),
            ("Biology", "Science", 16)
        ]
        
        for name, tier, rank in subjects:
            if not Subject.query.filter_by(subject_name=name).first():
                db.session.add(Subject(subject_name=name, tier=tier, rank=rank))
        
        print("Refactoring grade levels...")
        new_grades = [
            ("Preschool", "Early Childhood", 1),
            ("Kindergarten", "Early Childhood", 2),
            ("Elementary", "Primary", 3),
            ("Secondary", "Junior High", 4),
            ("Senior High School", "Secondary", 5),
            ("College / Higher Education", "Tertiary", 6)
        ]
        
        # 1. Create mapping for existing resources
        # Get all current levels
        old_levels = GradeLevel.query.all()
        level_map = {} # old_id -> new_name
        
        for gl in old_levels:
            name = gl.grade_name
            if "Grade 1" in name or "Grade 2" in name or "Grade 3" in name or "Grade 4" in name or "Grade 5" in name or "Grade 6" in name:
                level_map[gl.grade_level_id] = "Elementary"
            elif "Grade 7" in name or "Grade 8" in name or "Grade 9" in name or "Grade 10" in name:
                level_map[gl.grade_level_id] = "Secondary"
            elif "Grade 11" in name or "Grade 12" in name:
                level_map[gl.grade_level_id] = "Senior High School"
            elif "Higher Ed" in name:
                level_map[gl.grade_level_id] = "College / Higher Education"
            else:
                level_map[gl.grade_level_id] = name # Keep Preschool/Kinder as is

        # 2. Add new levels if they don't exist
        for name, tier, rank in new_grades:
            existing = GradeLevel.query.filter_by(grade_name=name).first()
            if not existing:
                db.session.add(GradeLevel(grade_name=name, tier=tier, rank=rank))
        
        db.session.flush() # Ensure new levels get IDs
        
        # 3. Update existing resources to new level IDs
        for old_id, new_name in level_map.items():
            new_level = GradeLevel.query.filter_by(grade_name=new_name).first()
            if new_level and old_id != new_level.grade_level_id:
                # Update resources using this old_id
                ResourceCollection.query.filter_by(grade_level_id=old_id).update({
                    "grade_level_id": new_level.grade_level_id
                })
        
        db.session.commit()
        
        # 4. Cleanup old orphaned levels
        new_names = [g[0] for g in new_grades]
        GradeLevel.query.filter(~GradeLevel.grade_name.in_(new_names)).delete(synchronize_session='fetch')
        
        print("Seeding content types...")
        content_types = [
            "Lesson Plan",
            "Worksheet",
            "Assessment",
            "Activity",
            "Syllabus",
            "Presentation",
            "Flashcards",
            "Educational Game"
        ]
        
        for name in content_types:
            if not ContentType.query.filter_by(type_name=name).first():
                db.session.add(ContentType(type_name=name))
        
        db.session.commit()
        print("Database seeded and grade levels simplified successfully!")

if __name__ == "__main__":
    seed_data()
