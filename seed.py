from app import app
from models import db, Subject, GradeLevel, ContentType, ResourceCollection

def seed_data():
    # Bypass pooler (port 6543) and connect directly (port 5432) for seeding
    direct_url = app.config['SQLALCHEMY_DATABASE_URI'].replace(":6543/", ":5432/")
    app.config['SQLALCHEMY_DATABASE_URI'] = direct_url
    
    with app.app_context():
        print(f"Connecting to: {direct_url}")
        
        print("Seeding subjects...")
        existing_subjects = {s.subject_name: s for s in Subject.query.all()}
        subjects_to_add = [
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
        
        for name, tier, rank in subjects_to_add:
            if name not in existing_subjects:
                db.session.add(Subject(subject_name=name, tier=tier, rank=rank))
        
        db.session.commit()

        print("Refactoring grade levels...")
        existing_grades = {g.grade_name for g in GradeLevel.query.all()}
        new_grades = [
            ("Preschool", "Early Childhood", 1),
            ("Kindergarten", "Early Childhood", 2),
            ("Elementary", "Primary", 3),
            ("Secondary", "Junior High", 4),
            ("Senior High School", "Secondary", 5),
            ("College / Higher Education", "Tertiary", 6)
        ]
        
        # 1. Create mapping for existing resources
        old_levels = GradeLevel.query.all()
        level_map = {} 
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
                level_map[gl.grade_level_id] = name

        # 2. Add new levels
        for name, tier, rank in new_grades:
            if name not in existing_grades:
                db.session.add(GradeLevel(grade_name=name, tier=tier, rank=rank))
        
        db.session.commit()
        
        # 3. Update existing resources
        # Fetch all levels AGAIN to get new IDs
        all_levels_new = {g.grade_name: g.grade_level_id for g in GradeLevel.query.all()}
        
        for old_id, new_name in level_map.items():
            new_id = all_levels_new.get(new_name)
            if new_id and old_id != new_id:
                ResourceCollection.query.filter_by(grade_level_id=old_id).update({
                    "grade_level_id": new_id
                })
        
        db.session.commit()
        
        # 4. Cleanup old orphaned levels
        new_names = [g[0] for g in new_grades]
        GradeLevel.query.filter(~GradeLevel.grade_name.in_(new_names)).delete(synchronize_session='fetch')
        db.session.commit()
        
        print("Seeding content types...")
        existing_types = {t.type_name for t in ContentType.query.all()}
        content_types = [
            "Lesson Plan", "Worksheet", "Assessment", "Activity", 
            "Syllabus", "Presentation", "Flashcards", "Educational Game"
        ]
        
        for name in content_types:
            if name not in existing_types:
                db.session.add(ContentType(type_name=name))
        
        db.session.commit()

        print("Seeding demo teachers and resources...")
        from werkzeug.security import generate_password_hash
        from models import Teacher, UserAuth, Quiz, QuizQuestion
        import secrets

        # 1. Create a Demo Teacher
        demo_email = "sarah.smith@teachshare.com"
        if not Teacher.query.filter_by(email=demo_email).first():
            sarah = Teacher(
                username="sarah_smith",
                first_name="Sarah",
                last_name="Smith",
                email=demo_email,
                is_verified=True,
                role="Science Lead",
                institution="Greenwood Academy",
                bio="Passionate about bringing hands-on science to middle schoolers. I love biology and environmental science!"
            )
            db.session.add(sarah)
            db.session.flush()

            db.session.add(UserAuth(
                teacher_id=sarah.teacher_id,
                hashed_password=generate_password_hash("SarahPassword123!"),
                auth_provider="local",
                is_active=True
            ))

            # 2. Add a realistic Resource Collection
            science_subj = Subject.query.filter_by(subject_name="Science").first()
            elem_grade = GradeLevel.query.filter_by(grade_name="Elementary").first()
            lp_type = ContentType.query.filter_by(type_name="Lesson Plan").first()

            lesson = ResourceCollection(
                title="Introduction to Photosynthesis & Plant Growth",
                description={"blocks": [{"text": "A comprehensive 45-minute lesson plan for grade 4 students to understand how plants make food using sunlight, water, and air."}]},
                owner_id=sarah.teacher_id,
                subject_id=science_subj.subject_id if science_subj else None,
                grade_level_id=elem_grade.grade_level_id if elem_grade else None,
                content_type_id=lp_type.content_type_id if lp_type else None,
                is_published=True,
                visibility="public"
            )
            db.session.add(lesson)

            # 3. Add an Interactive Quiz
            quiz = Quiz(
                teacher_id=sarah.teacher_id,
                title="Photosynthesis Quick Check",
                description="Test your knowledge about the basic process of plant nutrition.",
                time_limit=10,
                access_code="DEMO_PLANTS",
                is_active=True
            )
            db.session.add(quiz)
            db.session.flush()

            db.session.add(QuizQuestion(
                quiz_id=quiz.quiz_id,
                question_text="What do plants need for photosynthesis besides water and carbon dioxide?",
                question_type="multiple_choice",
                options=["Sunlight", "Soil", "Oxygen", "Sugar"],
                correct_answer="Sunlight",
                points=1,
                order=0
            ))
            db.session.add(QuizQuestion(
                quiz_id=quiz.quiz_id,
                question_text="True or False: Photosynthesis occurs during the night.",
                question_type="true_false",
                options=["True", "False"],
                correct_answer="False",
                points=1,
                order=1
            ))

        db.session.commit()
        print("Database seeded and demo data added successfully!")

if __name__ == "__main__":
    seed_data()
