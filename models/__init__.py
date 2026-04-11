from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from .teachers import Teacher, UserAuth
from .content_type import ContentType
from .grade_level import GradeLevel
from .resource_collection import ResourceCollection
from .resource_tag import ResourceTag
from .review import Review
from .subject import Subject
from .tag_type import TagType
from .tag import Tag
from .resource_file import ResourceFile
from .resource_version import ResourceVersion