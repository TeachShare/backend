from models import Teacher, ResourceCollection, ResourceVersion, ResourceFile, ResourceTag, Tag, TagType, Subject, ContentType, GradeLevel, db, ResourceComment, ResourceRating, ResourceLike, ResourceCollaborator, FileSignature
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import joinedload
from sqlalchemy import or_, and_, cast, String
from sqlalchemy.sql import func

class ResourceCollectionService:
    @staticmethod
    def get_file_by_hash(file_hash):
        return FileSignature.query.filter_by(file_hash=file_hash).first()

    @staticmethod
    def has_edit_permission(collection_id, teacher_id):
        collection = ResourceCollection.query.get(collection_id)
        if not collection: return False
        if collection.owner_id == teacher_id: return True
        
        collaborator = ResourceCollaborator.query.filter_by(
            collection_id=collection_id, 
            teacher_id=teacher_id, 
            role='editor'
        ).first()
        return collaborator is not None

    @staticmethod
    def create_resource(data):
        is_published = data.get('is_published', False)
        required_fields = ['title', 'owner_id']

        if is_published:
            required_fields.extend(['subject_id', 'grade_level_id', 'content_type_id'])

        for field in required_fields:
            if not data.get(field):
                raise ValueError(f"Missing required field: '{field}'")
        
        estimate_duration = data.get('estimate_duration')
        if estimate_duration and len(str(estimate_duration)) > 100:
            raise ValueError("Estimate duration must be less than 100 characters")
            
        try:
            # 1. Create the parent Collection
            new_collection = ResourceCollection(
                title = data.get('title'),
                description = data.get('description'),
                is_published = is_published,
                owner_id = data.get('owner_id'),
                subject_id = data.get('subject_id'),
                grade_level_id = data.get('grade_level_id'),
                content_type_id = data.get('content_type_id'),
                estimate_duration = estimate_duration,
                student_summary = data.get('student_summary'),
                allow_remixing = data.get('allow_remixing', True),
                visibility = data.get('visibility', 'public'),
                collaboration_mode = data.get('collaboration_mode', 'none'),
                updated_at = datetime.now(timezone.utc)
            )

            db.session.add(new_collection)
            db.session.flush() # Get the collection_id
            
            # 2. CREATE VERSION 1 IMMEDIATELY
            # We set is_latest=True so pipit is immediately "Discoverable"
            new_version = ResourceVersion(
                collection_id = new_collection.collection_id,
                version_no = 1,
                notes = data.get('version_notes', "Initial upload"),
                is_latest = True,  # CRITICAL: Makes it appear in 'My Resources' and 'Discovery'
                is_remix = False,
                created_by = new_collection.owner_id
            )
            
            db.session.add(new_version)
            db.session.flush()

            # 3. Add Files to this Version
            for file_info in data.get('files', []):
                new_file = ResourceFile(
                    version_id = new_version.version_id,
                    file_url = file_info.get('url'),
                    file_name = file_info.get('name'),
                    file_type = file_info.get('type'),
                    file_size = file_info.get('size'),
                    file_hash = file_info.get('hash')
                )
                db.session.add(new_file)

            # 4. Handle Tags
            for tag_string in data.get('tags', []):
                clean_name = str(tag_string).strip().lower()
                if not clean_name: continue

                existing_tag = Tag.query.filter_by(tag_name=clean_name).first()
                if not existing_tag:
                    default_type = TagType.query.filter_by(type_name='custom').first() or TagType(type_name='custom')
                    if not default_type.tag_type_id:
                        db.session.add(default_type)
                        db.session.flush()
                    
                    existing_tag = Tag(tag_name=clean_name, tag_type_id=default_type.tag_type_id)
                    db.session.add(existing_tag)
                    db.session.flush() 
                
                db.session.add(ResourceTag(collection_id=new_collection.collection_id, tag_id=existing_tag.tag_id))
            
            # 5. Handle Collaborators
            for coll_data in data.get('collaborators', []):
                # Ensure the collaborator is not the owner
                if coll_data.get('teacher_id') == new_collection.owner_id:
                    continue
                
                new_collaborator = ResourceCollaborator(
                    collection_id=new_collection.collection_id,
                    teacher_id=coll_data.get('teacher_id'),
                    role=coll_data.get('role', 'editor')
                )
                db.session.add(new_collaborator)

            db.session.commit()

            # Log Activity
            from services.activity_service import ActivityService
            ActivityService.log_activity(
                user_id=new_collection.owner_id,
                activity_type='post_resource',
                collection_id=new_collection.collection_id
            )

            return new_collection

        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_my_resources(teacher_id, filters=None, page=1, per_page=12, sort_by='newest'):
        # Weekly Deltas (last 7 days)
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        
        # Subqueries for counts
        likes_sub = db.session.query(
            ResourceLike.collection_id, 
            func.count(ResourceLike.like_id).label('total_likes')
        ).group_by(ResourceLike.collection_id).subquery()

        weekly_likes_sub = db.session.query(
            ResourceLike.collection_id, 
            func.count(ResourceLike.like_id).label('weekly_likes')
        ).filter(ResourceLike.created_at >= seven_days_ago).group_by(ResourceLike.collection_id).subquery()

        # Query
        query = db.session.query(
            ResourceCollection,
            func.coalesce(likes_sub.c.total_likes, 0).label('likes'),
            func.coalesce(weekly_likes_sub.c.weekly_likes, 0).label('weekly_likes')
        )\
        .options(joinedload(ResourceCollection.subject), 
                 joinedload(ResourceCollection.grade_level),
                 joinedload(ResourceCollection.content_type),
                 joinedload(ResourceCollection.collaborators))\
        .outerjoin(likes_sub, ResourceCollection.collection_id == likes_sub.c.collection_id)\
        .outerjoin(weekly_likes_sub, ResourceCollection.collection_id == weekly_likes_sub.c.collection_id)\
        .filter(
            or_(
                ResourceCollection.owner_id == teacher_id,
                ResourceCollection.collaborators.any(teacher_id=teacher_id)
            )
        )\
        .filter(ResourceCollection.is_hidden == False)

        if filters:
            if filters.get('search'):
                search_query = f"%{filters['search']}%"
                query = query.filter(
                    or_(
                        ResourceCollection.title.ilike(search_query),
                        cast(ResourceCollection.description, String).ilike(search_query)
                    )
                )

            if filters.get('subject_id'):
                query = query.filter(ResourceCollection.subject_id == filters['subject_id'])
            if filters.get('grade_level_id'):
                query = query.filter(ResourceCollection.grade_level_id == filters['grade_level_id'])
            if filters.get('content_type_id'):
                query = query.filter(ResourceCollection.content_type_id == filters['content_type_id'])

            status = filters.get('status')
            if status == 'published':
                query = query.filter(ResourceCollection.is_published == True)
            elif status == 'draft':
                query = query.filter(ResourceCollection.is_published == False)

        # Sorting
        if sort_by == 'downloads':
            query = query.order_by(ResourceCollection.download_count.desc())
        elif sort_by == 'likes':
            query = query.order_by(db.text('likes DESC'))
        elif sort_by == 'alphabetical':
            query = query.order_by(ResourceCollection.title.asc())
        else: # newest
            query = query.order_by(ResourceCollection.updated_at.desc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        results = []
        for col, total_likes, weekly_likes in pagination.items:
            # Safer tag fetching
            tag_names = [rt.tag.tag_name for rt in col.tags if rt.tag] if hasattr(col, 'tags') else []
            
            results.append({
                "collection_id": col.collection_id,
                "title": col.title or "Untitled",
                "is_published": col.is_published,
                "category": col.subject.subject_name if col.subject else "No Subject",
                "type": col.content_type.type_name if col.content_type else "No Type",
                "grade": col.grade_level.grade_name if col.grade_level else "No Grade",
                "tags": tag_names, 
                "likes": total_likes,
                "weekly_likes": weekly_likes,
                "downloads": col.download_count,      
                "visibility": col.visibility,
                "updated_at": col.updated_at.isoformat() if col.updated_at else datetime.now(timezone.utc).isoformat(),
                "is_collaborator": any(c.teacher_id == teacher_id for c in col.collaborators) if hasattr(col, 'collaborators') else False
            })

        return {
            "resources": results,
            "total_pages": pagination.pages,
            "current_page": pagination.page,
            "has_next": pagination.has_next,
            "total_count": pagination.total
        }
    @staticmethod
    def get_resource_by_id(collection_id, current_user_id=None, version_no=None):
        collection = ResourceCollection.query.get(collection_id)
        if not collection: return None

        # Access Control for Private Resources
        if collection.visibility == 'private':
            if not current_user_id:
                return None # Or raise ValueError("Private resource")
            
            is_owner = collection.owner_id == current_user_id
            is_collab = ResourceCollaborator.query.filter_by(
                collection_id=collection_id, 
                teacher_id=current_user_id
            ).first() is not None
            
            if not is_owner and not is_collab:
                return None

        if version_no:
            # Find the version within the same lineage (matching title and owner)
            target_version = db.session.query(ResourceVersion)\
                .join(ResourceCollection, ResourceVersion.collection_id == ResourceCollection.collection_id)\
                .filter(ResourceCollection.owner_id == collection.owner_id)\
                .filter(ResourceCollection.title == collection.title)\
                .filter(ResourceVersion.version_no == version_no)\
                .first()
        else:
            target_version = ResourceVersion.query.filter_by(collection_id=collection_id, is_latest=True).first()
            if not target_version:
                target_version = ResourceVersion.query.filter_by(collection_id=collection_id)\
                    .order_by(ResourceVersion.version_no.desc()).first()

        files_data = []
        if target_version:
            files = ResourceFile.query.filter_by(version_id=target_version.version_id).all()
            files_data = [{
                "file_id": f.file_id, 
                "name": f.file_name, 
                "url": f.file_url, 
                "type": f.file_type, 
                "size": f.file_size,
                "hash": f.file_hash
            } for f in files]

        tag_names = [t.tag_name for t in db.session.query(Tag.tag_name)\
                    .join(ResourceTag, Tag.tag_id == ResourceTag.tag_id)\
                    .filter(ResourceTag.collection_id == collection_id).all()]

        comments_query = db.session.query(ResourceComment, ResourceRating.score)\
            .outerjoin(ResourceRating, (ResourceRating.teacher_id == ResourceComment.teacher_id) & 
                                    (ResourceRating.collection_id == ResourceComment.collection_id))\
            .filter(ResourceComment.collection_id == collection_id)\
            .filter(ResourceComment.is_hidden == False)\
            .order_by(ResourceComment.created_at.desc()).all()
        
        user_has_liked = False

        if current_user_id:
            user_has_liked = ResourceLike.query.filter_by(
            collection_id=collection_id, 
            teacher_id=current_user_id
        ).first() is not None
            
        formatted_comments = [{
            "id": c.comment_id,
            "user": f"{c.teacher.first_name} {c.teacher.last_name}",
            "avatar": c.teacher.first_name[0],
            "rating": score if score else 0,
            "text": c.content,
            "date": c.created_at.strftime("%b %d, %Y")
        } for c, score in comments_query] if comments_query else []

        raw_avg = db.session.query(func.avg(ResourceRating.score))\
            .filter(ResourceRating.collection_id == collection_id).scalar()
        avg_rating = round(float(raw_avg), 1) if raw_avg is not None else 0.0
        
        likes_count = ResourceLike.query.filter_by(collection_id=collection_id).count()

        download_count = collection.download_count
        remixes_count = getattr(collection, 'remixes_count', 0) or 0
        
        collaborators = [{
            "teacher_id": c.teacher_id,
            "username": c.teacher.username,
            "name": f"{c.teacher.first_name} {c.teacher.last_name}",
            "role": c.role
        } for c in collection.collaborators]

        return {
            "collection_id": collection.collection_id,
            "owner_id": collection.owner_id,
            "owner_name": f"{collection.owner.first_name} {collection.owner.last_name}" if collection.owner else "Unknown",
            "owner_username": collection.owner.username if collection.owner else None,
            "title": collection.title,
            "description": collection.description,
            "subject": collection.subject.subject_name if collection.subject else "General",
            "grade": collection.grade_level.grade_name if collection.grade_level else "All Grades",
            "type": collection.content_type.type_name if collection.content_type else "Resource",
            "subject_id": collection.subject_id,
            "grade_level_id": collection.grade_level_id,
            "content_type_id": collection.content_type_id,
            "tags": tag_names,
            "files": files_data,
            "comments": formatted_comments,
            "avg_rating": avg_rating,
            "likes": likes_count,
            "user_has_liked": user_has_liked,
            "downloads": download_count,
            "remixes": remixes_count,
            "estimate_duration": collection.estimate_duration,
            "student_summary": collection.student_summary,
            "is_published": collection.is_published,
            "version_no": target_version.version_no if target_version else 1,
            "is_latest": target_version.is_latest if target_version else True,
            "version_notes": target_version.notes if target_version else None,
            "version_creator_name": f"{target_version.creator.first_name} {target_version.creator.last_name}" if target_version and target_version.creator else None,
            "updated_at": collection.updated_at.isoformat(),
            # Settings
            "allow_remixing": collection.allow_remixing,
            "visibility": collection.visibility,
            "collaboration_mode": collection.collaboration_mode,
            "collaborators": collaborators
        }
    
    @staticmethod
    def restore_resource(collection_id, target_version_id):
        target_version = ResourceVersion.query.filter_by(
            version_id=target_version_id, 
            collection_id=collection_id
        ).first()

        if not target_version:
            return {"error": "Version not found for this collection"}, 404
        
        collection = ResourceCollection.query.get(collection_id)

        ResourceVersion.query.filter_by(collection_id=collection_id).update({"is_latest": False})
        target_version.is_latest = True

        collection.updated_at = datetime.now(timezone.utc)

        db.session.commit()
        return {"message": f"Successfully restored to version {target_version.version_no}"}

    @staticmethod
    def update_resource(old_collection_id, data, new_files_info=None, updater_id=None):
        collection = ResourceCollection.query.get(old_collection_id)

        if not collection:
            raise ValueError("Collection not found")
        
        # Permission check
        if updater_id and not ResourceCollectionService.has_edit_permission(old_collection_id, updater_id):
            raise ValueError("Unauthorized to update this resource")
        
        is_published = data.get('is_published', collection.is_published)

        # Validation for publishing
        if is_published:
            required_fields = ['title', 'subject_id', 'grade_level_id', 'content_type_id']
            for field in required_fields:
                val = data.get(field)
                if val is None: # Use the existing value if not provided in payload
                    val = getattr(collection, field)
                
                if not val:
                    raise ValueError(f"Missing required field for publishing: '{field}'")

        estimate_duration = data.get('estimate_duration')
        if estimate_duration and len(str(estimate_duration)) > 100:
            raise ValueError("Estimate duration must be less than 100 characters")

        collection.is_published = data.get('is_published', collection.is_published)
        collection.title = data.get('title', collection.title)
        collection.description = data.get('description', collection.description)
        collection.subject_id = data.get('subject_id', collection.subject_id)
        collection.grade_level_id = data.get('grade_level_id', collection.grade_level_id)
        collection.estimate_duration = estimate_duration if estimate_duration is not None else collection.estimate_duration
        collection.student_summary = data.get('student_summary', collection.student_summary)
        
        # Update settings
        collection.allow_remixing = data.get('allow_remixing', collection.allow_remixing)
        
        # OWNER-ONLY SETTINGS
        if updater_id and collection.owner_id == updater_id:
            collection.visibility = data.get('visibility', collection.visibility)
            collection.collaboration_mode = data.get('collaboration_mode', collection.collaboration_mode)
        elif not updater_id:
            # Internal server calls with no updater_id (e.g. initial creation logic if reused)
            collection.visibility = data.get('visibility', collection.visibility)
            collection.collaboration_mode = data.get('collaboration_mode', collection.collaboration_mode)

        collection.updated_at = datetime.now(timezone.utc)
        
        last_v = ResourceVersion.query.filter_by(collection_id=old_collection_id)\
            .order_by(ResourceVersion.version_no.desc()).first()
        
        new_v_no = (last_v.version_no + 1) if last_v else 1

        ResourceVersion.query.filter_by(collection_id=old_collection_id).update({"is_latest": False})

        new_version = ResourceVersion(
            collection_id = old_collection_id,
            version_no = new_v_no,
            notes = data.get('version_notes') or data.get('notes') or 'updated resources',
            is_latest = True,
            is_remix = False,
            parent_version_id = last_v.version_id if last_v else None,
            created_by = updater_id if updater_id else collection.owner_id
        )
        
        db.session.add(new_version)
        db.session.flush()

        # 1. Retain files from the previous version, excluding those marked for removal
        if last_v:
            removed_file_urls = data.get('removed_file_urls', [])
            old_files = ResourceFile.query.filter_by(version_id=last_v.version_id).all()
            for old_f in old_files:
                if old_f.file_url in removed_file_urls:
                    continue
                    
                db.session.add(ResourceFile(
                    version_id=new_version.version_id,
                    file_url=old_f.file_url,
                    file_name=old_f.file_name,
                    file_type=old_f.file_type,
                    file_size=old_f.file_size,
                    file_hash=old_f.file_hash
                ))

        # 2. Append new files if they are provided
        if new_files_info:
            for f in new_files_info:
                db.session.add(ResourceFile(
                    version_id=new_version.version_id,
                    file_url=f.get('url'),
                    file_name=f.get('name'),
                    file_type=f.get('type'),
                    file_size=f.get('size'),
                    file_hash=f.get('hash')
                ))
                
        ResourceTag.query.filter_by(collection_id=old_collection_id).delete()

        for tag_string in data.get('tags', []):
                clean_name = str(tag_string).strip().lower()
                if not clean_name: continue
                
                existing_tag = Tag.query.filter_by(tag_name=clean_name).first()
                if not existing_tag:
                    custom_type = TagType.query.filter_by(type_name='custom').first()
                    existing_tag = Tag(tag_name=clean_name, tag_type_id=custom_type.tag_type_id)
                    db.session.add(existing_tag)
                    db.session.flush()           
                db.session.add(ResourceTag(collection_id=old_collection_id, tag_id=existing_tag.tag_id))

        db.session.commit()

        # Log Activity
        from services.activity_service import ActivityService
        ActivityService.log_activity(
            user_id=collection.owner_id,
            activity_type='update_resource',
            collection_id=collection.collection_id
        )

        return collection

    @staticmethod
    def get_version_history(collection_id):
        versions = db.session.query(ResourceVersion)\
            .filter(ResourceVersion.collection_id == collection_id)\
            .order_by(ResourceVersion.version_no.desc())\
            .all()

        history = []
        for version in versions:
            collection = ResourceCollection.query.get(version.collection_id)
            file_count = ResourceFile.query.filter_by(version_id=version.version_id).count()
            history.append({
                "collection_id": version.collection_id,
                "version_id": version.version_id,
                "version_no": version.version_no,
                "notes": version.notes,
                "is_latest": version.is_latest, 
                "created_at": version.created_at.isoformat(),
                "file_count": file_count,
                "author": f"{version.creator.first_name} {version.creator.last_name}" if version.creator else "Unknown"
            })
        return history


    @staticmethod
    def get_discover_resources(current_teacher_id, filters=None, page=1, per_page=12, include_own=False):
        # Weekly Deltas (last 7 days)
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        
        # Subquery for weekly likes growth
        weekly_likes_sub = db.session.query(
            ResourceLike.collection_id, 
            func.count(ResourceLike.like_id).label('weekly_likes')
        ).filter(ResourceLike.created_at >= seven_days_ago).group_by(ResourceLike.collection_id).subquery()

        # Main query for the collections
        query = db.session.query(
            ResourceCollection,
            func.coalesce(weekly_likes_sub.c.weekly_likes, 0).label('weekly_likes')
        )\
        .join(Teacher, ResourceCollection.owner_id == Teacher.teacher_id)\
        .options(joinedload(ResourceCollection.subject),
                joinedload(ResourceCollection.grade_level),
                joinedload(ResourceCollection.content_type))\
        .outerjoin(weekly_likes_sub, ResourceCollection.collection_id == weekly_likes_sub.c.collection_id)
        
        if include_own:
            # For global search: Own resources (any visibility) OR others' public resources
            query = query.filter(
                or_(
                    ResourceCollection.owner_id == current_teacher_id,
                    and_(
                        ResourceCollection.owner_id != current_teacher_id,
                        ResourceCollection.is_published == True,
                        ResourceCollection.visibility == 'public',
                        ResourceCollection.is_hidden == False
                    )
                )
            )
        else:
            # For discovery: Only others' public resources
            query = query.filter(ResourceCollection.owner_id != current_teacher_id)\
                .filter(ResourceCollection.is_published == True)\
                .filter(ResourceCollection.visibility == 'public')\
                .filter(ResourceCollection.is_hidden == False)
        
        if filters:
            if filters.get('search'):
                search_query = f"%{filters['search']}%"
                query = query.filter(
                    or_(
                        ResourceCollection.title.ilike(search_query),
                        cast(ResourceCollection.description, String).ilike(search_query)
                    )
                )

            if filters.get('subject_id'):
                query = query.filter(ResourceCollection.subject_id == filters['subject_id'])
            if filters.get('grade_level_id'):
                query = query.filter(ResourceCollection.grade_level_id == filters['grade_level_id'])
            if filters.get('content_type_id'):
                query = query.filter(ResourceCollection.content_type_id == filters['content_type_id'])
            
            if filters.get('verified_only'):
                query = query.filter(Teacher.is_verified == True)

        # Sorting
        sort_by = filters.get('sort_by', 'newest') if filters else 'newest'
        if sort_by == 'trending':
            query = query.order_by(db.text('weekly_likes DESC'), ResourceCollection.updated_at.desc())
        else: # newest
            query = query.order_by(ResourceCollection.updated_at.desc())
        
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        results = []
        
        for collection, weekly_likes in pagination.items:
            # Manual fetch for the latest version
            latest_v = ResourceVersion.query.filter_by(
                collection_id=collection.collection_id, 
                is_latest=True
            ).first()

            # Fetch tags manually
            tag_names = [t.tag_name for t in db.session.query(Tag.tag_name)\
                        .join(ResourceTag, Tag.tag_id == ResourceTag.tag_id)\
                        .filter(ResourceTag.collection_id == collection.collection_id).all()]

            file_count = ResourceFile.query.filter_by(version_id=latest_v.version_id).count() if latest_v else 0

            results.append({
                "collection_id": collection.collection_id,
                "owner_id": collection.owner_id,
                "title": collection.title,
                "owner_name": f"{collection.owner.first_name} {collection.owner.last_name}" if collection.owner else "Unknown",
                "owner_username": collection.owner.username if collection.owner else None,
                "owner_is_verified": collection.owner.is_verified if collection.owner else False,
                "description": collection.description if isinstance(collection.description, str) else str(collection.description or ""),
                "subject": collection.subject.subject_name if collection.subject else "General",
                "grade": collection.grade_level.grade_name if collection.grade_level else "All Grades",
                "type": collection.content_type.type_name if collection.content_type else "Resource",
                "tags": tag_names, 
                "file_count": file_count,
                "downloads": collection.download_count,
                "weekly_likes": weekly_likes,
                "estimate_duration": collection.estimate_duration,
                "allow_remixing": collection.allow_remixing,
                "version_no": latest_v.version_no if latest_v else 1,
                "updated_at": collection.updated_at.isoformat()
            })

        return {
            "resources": results,
            "total_pages": pagination.pages,
            "current_page": pagination.page,
            "has_next": pagination.has_next,
            "total_count": pagination.total
        }
    
    @staticmethod
    def remix_resource(original_collection_id, new_owner_id ):
        """
        Clones a resource into a new owner's collection.
        Sets is_remix=True and links to the parent_version_id for citation.
        """
        # 1. Fetch the source collection and its latest version
        original_collection = ResourceCollection.query.get(original_collection_id)
        if not original_collection:
            raise ValueError("Original resource not found")
        
        if not original_collection.allow_remixing:
            raise ValueError("Remixing is disabled for this resource")

        original_versions = ResourceVersion.query.filter_by(
            collection_id=original_collection_id
        ).order_by(ResourceVersion.version_no.asc()).all()

        try:
            # 2. Spawn a BRAND NEW Collection for the new owner
            remixed_collection = ResourceCollection(
                title=f"{original_collection.title} (Remix)",
                description=original_collection.description,
                owner_id=new_owner_id, # The teacher doing the remixing
                subject_id=original_collection.subject_id,
                grade_level_id=original_collection.grade_level_id,
                content_type_id=original_collection.content_type_id,
                estimate_duration=original_collection.estimate_duration,
                student_summary=original_collection.student_summary,
                allow_remixing=original_collection.allow_remixing,
                visibility=original_collection.visibility,
                is_published=False # Remixes start as drafts
            )
            db.session.add(remixed_collection)
            db.session.flush()

            # 3. Clone ALL Versions
            for ov in original_versions:
                new_version = ResourceVersion(
                    collection_id=remixed_collection.collection_id,
                    version_no=ov.version_no,
                    notes=ov.notes,
                    is_latest=ov.is_latest,
                    is_remix=True, # Mark as a remix
                    parent_version_id=ov.version_id, # Cite the original version
                    created_by=new_owner_id,
                    created_at=ov.created_at # Preserve timing
                )
                db.session.add(new_version)
                db.session.flush()

                # 4. Clone Files for each version
                original_files = ResourceFile.query.filter_by(version_id=ov.version_id).all()
                for f in original_files:
                    db.session.add(ResourceFile(
                        version_id=new_version.version_id,
                        file_url=f.file_url,
                        file_name=f.file_name,
                        file_type=f.file_type,
                        file_size=f.file_size,
                        file_hash=f.file_hash
                    ))

            # 5. Clone Tags (Attached to the Collection)
            original_tags = ResourceTag.query.filter_by(collection_id=original_collection_id).all()
            for ot in original_tags:
                db.session.add(ResourceTag(
                    collection_id=remixed_collection.collection_id,
                    tag_id=ot.tag_id
                ))

            db.session.commit()

            # Trigger Notification for remix
            from services.notification_service import NotificationService
            NotificationService.create_notification(
                recipient_id=original_collection.owner_id,
                notification_type='remix',
                sender_id=new_owner_id,
                collection_id=original_collection_id,
                extra_data={"remixed_collection_id": remixed_collection.collection_id}
            )

            # Log Activity
            from services.activity_service import ActivityService
            ActivityService.log_activity(
                user_id=new_owner_id,
                activity_type='remix_resource',
                collection_id=original_collection_id,
                extra_data={"remixed_collection_id": remixed_collection.collection_id}
            )

            return remixed_collection

        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def delete_resource(collection_id, teacher_id):
        return ResourceCollectionService.delete_resource_permanently(collection_id, teacher_id)

    @staticmethod
    def delete_resource_permanently(collection_id, teacher_id):
        # 1. Ensure the teacher actually owns this collection
        collection = ResourceCollection.query.filter_by(
            collection_id=collection_id, 
            owner_id=teacher_id
        ).first()

        if not collection:
            raise ValueError("Resource not found or unauthorized.")

        try:
            # 2. Get all versions associated with this collection
            versions = ResourceVersion.query.filter_by(collection_id=collection_id).all()
            version_ids = [v.version_id for v in versions]

            # 3. DELETE FROM CHILD TABLES FIRST (The Order Matters!)
            from models import ResourceLike, ResourceComment, ResourceRating, ResourceCollaborator, Notification, UserActivity
            
            # Remove Likes, Comments, Ratings, Collaborators
            ResourceLike.query.filter_by(collection_id=collection_id).delete(synchronize_session=False)
            ResourceComment.query.filter_by(collection_id=collection_id).delete(synchronize_session=False)
            ResourceRating.query.filter_by(collection_id=collection_id).delete(synchronize_session=False)
            ResourceCollaborator.query.filter_by(collection_id=collection_id).delete(synchronize_session=False)

            # Handle Notifications and Activities
            Notification.query.filter_by(collection_id=collection_id).delete(synchronize_session=False)
            UserActivity.query.filter_by(collection_id=collection_id).delete(synchronize_session=False)
            
            # Remove Tag Links
            ResourceTag.query.filter_by(collection_id=collection_id).delete(synchronize_session=False)

            # Handle File References and Versions
            if version_ids:
                # Set parent_version_id to NULL for any versions (remixes) pointing to these versions
                ResourceVersion.query.filter(ResourceVersion.parent_version_id.in_(version_ids))\
                    .update({ResourceVersion.parent_version_id: None}, synchronize_session=False)
                
                # Remove files
                ResourceFile.query.filter(ResourceFile.version_id.in_(version_ids)).delete(synchronize_session=False)
                
                # Remove versions
                ResourceVersion.query.filter_by(collection_id=collection_id).delete(synchronize_session=False)

            # 4. FINALLY: Remove the Collection itself
            db.session.delete(collection)
            
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e
    
    @staticmethod
    def add_collaborator(collection_id, teacher_id, role='editor', owner_id=None):
        collection = ResourceCollection.query.get(collection_id)
        if not collection:
            raise ValueError("Resource not found")
        
        if collection.collaboration_mode == 'none':
            raise ValueError("Collaboration is disabled for this resource")
        
        if owner_id and collection.owner_id != owner_id:
            raise ValueError("Only the owner can add collaborators")
        
        if collection.owner_id == teacher_id:
            raise ValueError("Owner cannot be a collaborator")
        
        existing = ResourceCollaborator.query.filter_by(
            collection_id=collection_id, 
            teacher_id=teacher_id
        ).first()
        
        if existing:
            raise ValueError("User is already a collaborator")
        
        new_collab = ResourceCollaborator(
            collection_id=collection_id,
            teacher_id=teacher_id,
            role=role
        )
        db.session.add(new_collab)
        db.session.commit()
        
        # Trigger notification
        from services.notification_service import NotificationService
        NotificationService.create_notification(
            recipient_id=teacher_id,
            notification_type='collaborator_added',
            sender_id=owner_id,
            collection_id=collection_id,
            extra_data={"role": role}
        )
        
        return new_collab

    @staticmethod
    def remove_collaborator(collection_id, teacher_id, owner_id=None):
        collection = ResourceCollection.query.get(collection_id)
        if not collection:
            raise ValueError("Resource not found")
        
        # Only owner can remove others, but a collaborator can remove themselves
        if owner_id and collection.owner_id != owner_id and teacher_id != owner_id:
            raise ValueError("Unauthorized to remove collaborator")
            
        collaborator = ResourceCollaborator.query.filter_by(
            collection_id=collection_id, 
            teacher_id=teacher_id
        ).first()
        
        if not collaborator:
            raise ValueError("Collaborator not found")
            
        db.session.delete(collaborator)
        db.session.commit()
        return True

    @staticmethod
    def update_collaborator_role(collection_id, teacher_id, new_role, owner_id=None):
        collection = ResourceCollection.query.get(collection_id)
        if not collection:
            raise ValueError("Resource not found")
        
        if owner_id and collection.owner_id != owner_id:
            raise ValueError("Only the owner can update roles")
            
        collaborator = ResourceCollaborator.query.filter_by(
            collection_id=collection_id, 
            teacher_id=teacher_id
        ).first()
        
        if not collaborator:
            raise ValueError("Collaborator not found")
            
        collaborator.role = new_role
        db.session.commit()
        return collaborator
        
        