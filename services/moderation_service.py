from models import db, Report, ResourceCollection, ResourceComment, CommunityPost, PostComment, Teacher

class ModerationService:
    @staticmethod
    def create_report(reporter_id, target_type, target_id, reason, description=None):
        # 1. Validate Target Exists
        target_exists = False
        if target_type == 'resource':
            target_exists = ResourceCollection.query.get(target_id) is not None
        elif target_type == 'comment':
            target_exists = ResourceComment.query.get(target_id) is not None
        elif target_type == 'post_comment':
            target_exists = PostComment.query.get(target_id) is not None
        elif target_type == 'post':
            target_exists = CommunityPost.query.get(target_id) is not None
        elif target_type == 'teacher':
            target_exists = Teacher.query.get(target_id) is not None
        
        if not target_exists:
            raise ValueError(f"Target {target_type} with ID {target_id} not found.")

        # 2. Check for duplicate pending reports from same user
        existing = Report.query.filter_by(
            reporter_id=reporter_id,
            target_type=target_type,
            target_id=target_id,
            status='pending'
        ).first()
        
        if existing:
            return existing

        # 3. Create Report
        new_report = Report(
            reporter_id=reporter_id,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
            description=description
        )
        
        db.session.add(new_report)
        db.session.commit()
        return new_report

    @staticmethod
    def get_reports(status=None, page=1, per_page=20):
        query = Report.query
        if status:
            query = query.filter_by(status=status)
        
        pagination = query.order_by(Report.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        return {
            "reports": [r.to_dict() for r in pagination.items],
            "total_pages": pagination.pages,
            "current_page": pagination.page
        }

    @staticmethod
    def update_report_status(report_id, status):
        report = Report.query.get(report_id)
        if not report:
            raise ValueError("Report not found")
        
        report.status = status
        db.session.commit()
        return report

    @staticmethod
    def perform_action(report_id, action):
        report = Report.query.get(report_id)
        if not report:
            raise ValueError("Report not found")
        
        target_id = report.target_id
        target_type = report.target_type

        if action == 'hide':
            if target_type == 'resource':
                item = ResourceCollection.query.get(target_id)
                if item: item.is_hidden = True
            elif target_type == 'comment':
                item = ResourceComment.query.get(target_id)
                if item: item.is_hidden = True
            elif target_type == 'post_comment':
                item = PostComment.query.get(target_id)
                if item: item.is_hidden = True
            elif target_type == 'post':
                item = CommunityPost.query.get(target_id)
                if item: item.is_hidden = True
            elif target_type == 'teacher':
                item = Teacher.query.get(target_id)
                if item: item.is_suspended = True
            
            report.status = 'resolved'
        
        elif action == 'dismiss':
            report.status = 'dismissed'
        
        db.session.commit()
        return report
