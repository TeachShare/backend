from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from .teachers import Teacher, UserAuth
from .content_type import ContentType
from .grade_level import GradeLevel
from .resource_collection import ResourceCollection
from .resource_collaborator import ResourceCollaborator
from .resource_tag import ResourceTag
from .review import Review
from .subject import Subject
from .tag_type import TagType
from .tag import Tag
from .resource_file import ResourceFile
from .file_signature import FileSignature
from .resource_version import ResourceVersion
from .verification_codes import VerificationCodes
from .resource_rating import ResourceRating
from .resource_like import ResourceLike
from .resource_comment import ResourceComment
from .follower import Follower
from .community import CommunityPost, PostComment, PostLike
from .message import Message
from .ai_generated_content import AIGeneratedContent
from .notification import Notification
from .user_activity import UserActivity
from .report import Report
from .quiz import Quiz, QuizQuestion, QuizAttempt, QuizAnswer