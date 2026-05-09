from models import Notification, db, Teacher, ResourceCollection
from flask_socketio import emit

class NotificationService:
    @staticmethod
    def create_notification(recipient_id, notification_type, sender_id=None, collection_id=None, extra_data=None):
        try:
            # Don't notify yourself
            if sender_id and sender_id == recipient_id:
                return None

            new_notif = Notification(
                recipient_id=recipient_id,
                sender_id=sender_id,
                notification_type=notification_type,
                collection_id=collection_id,
                extra_data=extra_data
            )
            db.session.add(new_notif)
            db.session.commit()

            # Prepare data for Socket.IO
            notif_data = NotificationService.format_notification(new_notif)
            
            # Emit real-time notification via Socket.IO
            room = f"user_{recipient_id}"
            try:
                from app import socketio
                socketio.emit('new_notification', notif_data, room=room)
            except ImportError:
                print("Could not import socketio from app, real-time notification skipped")

            return new_notif
        except Exception as e:
            db.session.rollback()
            print(f"Error creating notification: {e}")
            return None

    @staticmethod
    def get_user_notifications(user_id, page=1, per_page=20):
        pagination = Notification.query.filter_by(recipient_id=user_id)\
            .order_by(Notification.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        return {
            "notifications": [NotificationService.format_notification(n) for n in pagination.items],
            "total_pages": pagination.pages,
            "current_page": pagination.page,
            "has_next": pagination.has_next,
            "unread_count": Notification.query.filter_by(recipient_id=user_id, is_read=False).count()
        }

    @staticmethod
    def mark_as_read(notification_id, user_id):
        notif = Notification.query.filter_by(notification_id=notification_id, recipient_id=user_id).first()
        if notif:
            notif.is_read = True
            db.session.commit()
            return True
        return False

    @staticmethod
    def mark_all_as_read(user_id):
        Notification.query.filter_by(recipient_id=user_id, is_read=False).update({"is_read": True})
        db.session.commit()
        return True

    @staticmethod
    def format_notification(n):
        sender_name = f"{n.sender.first_name} {n.sender.last_name}" if n.sender else "System"
        return {
            "id": n.notification_id,
            "sender_id": n.sender_id,
            "sender_name": sender_name,
            "sender_avatar": n.sender.first_name[0] if n.sender else "S",
            "type": n.notification_type,
            "collection_id": n.collection_id,
            "collection_title": n.collection.title if n.collection else None,
            "extra_data": n.extra_data,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat(),
            # For frontend compatibility
            "user": sender_name,
            "avatar": n.sender.first_name if n.sender else "System",
            "action": NotificationService.get_action_text(n.notification_type),
            "target": n.collection.title if n.collection else "",
            "time": "Just now" 
        }

    @staticmethod
    def get_action_text(notif_type):
        actions = {
            'like': 'liked your resource',
            'comment': 'commented on your resource',
            'download': 'downloaded your resource',
            'remix': 'remixed your resource',
            'review': 'reviewed your resource',
            'collaborator_added': 'added you as a collaborator on'
        }
        return actions.get(notif_type, 'interacted with your resource')
