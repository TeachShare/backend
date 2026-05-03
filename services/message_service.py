from models import Message, Teacher, db
from sqlalchemy import or_, and_

class MessageService:
    @staticmethod
    def get_conversations(teacher_id):
        # Subquery to get unique conversation partners
        sent_to = db.session.query(Message.receiver_id).filter_by(sender_id=teacher_id)
        received_from = db.session.query(Message.sender_id).filter_by(receiver_id=teacher_id)
        
        partner_ids = sent_to.union(received_from).all()
        partner_ids = [p[0] for p in partner_ids]

        conversations = []
        for p_id in partner_ids:
            partner = Teacher.query.get(p_id)
            if not partner:
                continue
            
            last_msg = Message.query.filter(
                or_(
                    and_(Message.sender_id == teacher_id, Message.receiver_id == p_id),
                    and_(Message.sender_id == p_id, Message.receiver_id == teacher_id)
                )
            ).order_by(Message.created_at.desc()).first()

            conversations.append({
                "id": partner.teacher_id,
                "name": f"{partner.first_name} {partner.last_name}",
                "avatar": partner.profile_image_url,
                "last_message": last_msg.content if last_msg else "",
                "timestamp": last_msg.created_at.isoformat() if last_msg else None,
                "unread_count": Message.query.filter_by(sender_id=p_id, receiver_id=teacher_id, is_read=False).count()
            })
        
        return sorted(conversations, key=lambda x: x['timestamp'] or '', reverse=True)

    @staticmethod
    def get_messages(teacher_id, partner_id):
        messages = Message.query.filter(
            or_(
                and_(Message.sender_id == teacher_id, Message.receiver_id == partner_id),
                and_(Message.sender_id == partner_id, Message.receiver_id == teacher_id)
            )
        ).order_by(Message.created_at.asc()).all()

        # Mark as read
        Message.query.filter_by(sender_id=partner_id, receiver_id=teacher_id, is_read=False).update({"is_read": True})
        db.session.commit()

        return [m.to_dict() for m in messages]

    @staticmethod
    def save_message(sender_id, receiver_id, content):
        msg = Message(sender_id=sender_id, receiver_id=receiver_id, content=content)
        db.session.add(msg)
        db.session.commit()
        return msg.to_dict()
