from models import Teacher, ResourceCollection, ResourceVersion, ResourceFile, ResourceTag, Tag, TagType, Subject, ContentType, GradeLevel, db, ResourceComment, ResourceRating, ResourceLike, ResourceCollaborator, FileSignature
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import joinedload
from sqlalchemy import or_, and_, cast, String
from sqlalchemy.sql import func

class ResourceCollectionService:
    @staticmethod
    def _generate_unique_title(base_title, exclude_id=None):
        """
        Ensures a resource title is globally unique.
        Appends an incremental suffix like (1), (2) if the title is taken.
        """
        if not base_title:
            return "Untitled Resource"
            
        new_title = base_title
        counter = 1
        
        while True:
            query = ResourceCollection.query.filter(
                func.lower(ResourceCollection.title) == func.lower(new_title)
            )
            if exclude_id:
                query = query.filter(ResourceCollection.collection_id != exclude_id)
            
            existing = query.first()
            if not existing:
                break
            
            new_title = f"{base_title} ({counter})"
            counter += 1
            
        return new_title

    @staticmethod
    def get_file_by_hash(file_hash):
        return FileSignature.query.filter_by(file_hash=file_hash).first()

    @staticmethod
    def has_edit_permission(collection_id, teacher_id):
        collection = ResourceCollection.query.get(collection_id)
        if not collection: return False
        if collection.owner_id == teacher_id: return True

        # NEW: EVERYONE COLLABORATION MODE
        if collection.collaboration_mode == 'everyone':
            return True

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
            # Check for files if publishing
            if not data.get('files'):
                 raise ValueError("At least one file is required to publish a resource.")

        for field in required_fields:
            if not data.get(field):
                raise ValueError(f"Missing required field: '{field}'")
        
        estimate_duration = data.get('estimate_duration')
        if estimate_duration and len(str(estimate_duration)) > 100:
            raise ValueError("Estimate duration must be less than 100 characters")
            
        try:
            # Generate Unique Title
            unique_title = ResourceCollectionService._generate_unique_title(data.get('title'))

            # 1. Create the parent Collection
            new_collection = ResourceCollection(
                title = unique_title,
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
                title = new_collection.title,
                description = new_collection.description,
                notes = data.get('version_notes', "Initial upload"),
                is_latest = True,  # CRITICAL: Makes it appear in 'My Resources' and 'Discovery'
                is_remix = False,
                is_published = is_published,
                visibility = new_collection.visibility,
                estimate_duration = new_collection.estimate_duration,
                allow_remixing = new_collection.allow_remixing,
                collaboration_mode = new_collection.collaboration_mode,
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

        rating_sub = db.session.query(
            ResourceRating.collection_id,
            func.avg(ResourceRating.score).label('avg_rating')
        ).group_by(ResourceRating.collection_id).subquery()

        # Query
        query = db.session.query(
            ResourceCollection,
            func.coalesce(likes_sub.c.total_likes, 0).label('likes'),
            func.coalesce(weekly_likes_sub.c.weekly_likes, 0).label('weekly_likes'),
            func.coalesce(rating_sub.c.avg_rating, 0).label('avg_rating')
        )\
        .options(joinedload(ResourceCollection.subject), 
                 joinedload(ResourceCollection.grade_level),
                 joinedload(ResourceCollection.content_type),
                 joinedload(ResourceCollection.collaborators))\
        .outerjoin(likes_sub, ResourceCollection.collection_id == likes_sub.c.collection_id)\
        .outerjoin(weekly_likes_sub, ResourceCollection.collection_id == weekly_likes_sub.c.collection_id)\
        .outerjoin(rating_sub, ResourceCollection.collection_id == rating_sub.c.collection_id)\
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
        for col, total_likes, weekly_likes, avg_rating in pagination.items:
            # Safer tag fetching
            tag_names = [rt.tag.tag_name for rt in col.tags if rt.tag] if hasattr(col, 'tags') else []
            
            # Fetch latest version info for citation
            latest_v = ResourceVersion.query.filter_by(collection_id=col.collection_id, is_latest=True).first()
            
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
                "avg_rating": round(float(avg_rating), 1) if avg_rating else 0,
                "downloads": col.download_count,      
                "visibility": col.visibility,
                "updated_at": col.updated_at.isoformat() if col.updated_at else datetime.now(timezone.utc).isoformat(),
                "is_collaborator": any(c.teacher_id == teacher_id for c in col.collaborators) if hasattr(col, 'collaborators') else False,
                
                # Citation
                "is_remix": latest_v.is_remix if latest_v else False,
                "original_author_name": latest_v.original_author_name if latest_v else None,
                "original_resource_title": latest_v.original_resource_title if latest_v else None
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
        
        reviews_count = db.session.query(func.count(ResourceRating.rating_id))\
            .filter(ResourceRating.collection_id == collection_id).scalar()
        
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
            "title": target_version.title if target_version and target_version.title else collection.title,
            "description": target_version.description if target_version and target_version.description else collection.description,
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
            "reviews_count": reviews_count,
            "likes": likes_count,
            "user_has_liked": user_has_liked,
            "downloads": download_count,
            "remixes": remixes_count,
            "version_id": target_version.version_id if target_version else None,
            "estimate_duration": target_version.estimate_duration if target_version and hasattr(target_version, 'estimate_duration') else collection.estimate_duration,
            "student_summary": collection.student_summary,
            "is_published": target_version.is_published if target_version else collection.is_published,
            "is_approved": target_version.is_approved if target_version else True,
            "version_no": target_version.version_no if target_version else 1,
            "is_latest": target_version.is_latest if target_version else True,
            "version_notes": target_version.notes if target_version else None,
            "version_creator_name": f"{target_version.creator.first_name} {target_version.creator.last_name}" if target_version and target_version.creator else None,
            "updated_at": collection.updated_at.isoformat(),
            # Citation (for remixes)
            "is_remix": target_version.is_remix if target_version else False,
            "original_author_name": target_version.original_author_name if target_version else None,
            "original_author_username": target_version.original_author_username if target_version else None,
            "original_resource_title": target_version.original_resource_title if target_version else None,
            "parent_version_id": target_version.parent_version_id if target_version else None,
            # Settings
            "allow_remixing": target_version.allow_remixing if target_version and hasattr(target_version, 'allow_remixing') else collection.allow_remixing,
            "visibility": target_version.visibility if target_version else collection.visibility,
            "collaboration_mode": target_version.collaboration_mode if target_version and hasattr(target_version, 'collaboration_mode') else collection.collaboration_mode,
            "collaborators": collaborators
        }
    
    @staticmethod
    def approve_version(collection_id, version_id, owner_id):
        collection = ResourceCollection.query.get(collection_id)
        if not collection:
            raise ValueError("Resource not found")
        
        if collection.owner_id != owner_id:
            raise ValueError("Only the owner can approve versions")
            
        version = ResourceVersion.query.filter_by(
            version_id=version_id, 
            collection_id=collection_id
        ).first()
        
        if not version:
            raise ValueError("Version not found")
            
        if version.is_approved:
            return {"message": "Version is already approved"}
            
        # 1. Promote to Latest
        ResourceVersion.query.filter_by(collection_id=collection_id).update({"is_latest": False})
        version.is_latest = True
        version.is_approved = True
        version.approved_by = owner_id
        
        # 2. Sync Collection Metadata with Approved Version
        collection.title = version.title
        collection.description = version.description
        collection.is_published = version.is_published
        collection.visibility = version.visibility
        collection.estimate_duration = version.estimate_duration
        collection.allow_remixing = version.allow_remixing
        collection.collaboration_mode = version.collaboration_mode
        collection.updated_at = datetime.now(timezone.utc)
        
        db.session.commit()
        
        # 3. Notify Collaborator
        from services.notification_service import NotificationService
        NotificationService.create_notification(
            recipient_id=version.created_by,
            notification_type='version_approved',
            sender_id=owner_id,
            collection_id=collection_id,
            extra_data={"version_no": version.version_no}
        )
        
        return {"success": True, "message": f"Version {version.version_no} approved and published."}
    
    @staticmethod
    def reject_version(collection_id, version_id, owner_id):
        collection = ResourceCollection.query.get(collection_id)
        if not collection:
            raise ValueError("Resource not found")
            
        if collection.owner_id != owner_id:
            raise ValueError("Only the owner can reject proposed versions")
            
        version = ResourceVersion.query.filter_by(
            version_id=version_id, 
            collection_id=collection_id
        ).first()
        
        if not version:
            raise ValueError("Version not found")
            
        if version.is_approved:
            raise ValueError("Cannot reject an approved version. Use 'restore' to roll back instead.")
            
        # Notify Collaborator
        from services.notification_service import NotificationService
        NotificationService.create_notification(
            recipient_id=version.created_by,
            notification_type='version_rejected',
            sender_id=owner_id,
            collection_id=collection_id,
            extra_data={"version_no": version.version_no}
        )
        
        # Delete the version (it was just a proposal)
        db.session.delete(version)
        db.session.commit()
        
        return {"success": True, "message": f"Version {version.version_no} rejected and deleted."}
    
    @staticmethod
    def restore_resource(collection_id, target_version_id, teacher_id):
        collection = ResourceCollection.query.get(collection_id)
        if not collection:
            raise ValueError("Resource not found")
        
        # OWNER-ONLY RESTORE ENFORCEMENT
        if collection.owner_id != teacher_id:
            raise ValueError("Unauthorized: Only the resource owner can restore previous versions.")

        target_version = ResourceVersion.query.filter_by(
            version_id=target_version_id, 
            collection_id=collection_id
        ).first()

        if not target_version:
            return {"error": "Version not found for this collection"}, 404
        
        collection = ResourceCollection.query.get(collection_id)

        ResourceVersion.query.filter_by(collection_id=collection_id).update({"is_latest": False})
        target_version.is_latest = True

        # Sync collection state with restored version
        collection.is_published = target_version.is_published
        collection.visibility = target_version.visibility
        collection.estimate_duration = target_version.estimate_duration
        collection.allow_remixing = target_version.allow_remixing
        collection.collaboration_mode = target_version.collaboration_mode
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
        
        is_owner = updater_id == collection.owner_id
        is_published = data.get('is_published', collection.is_published)

        # Fetch last version once for entire function
        last_v = ResourceVersion.query.filter_by(collection_id=old_collection_id)\
            .order_by(ResourceVersion.version_no.desc()).first()

        # Validation for publishing (only if owner is updating or it's already published)
        if is_owner and is_published:
            required_fields = ['title', 'subject_id', 'grade_level_id', 'content_type_id']
            for field in required_fields:
                val = data.get(field)
                if val is None: 
                    val = getattr(collection, field)
                if not val:
                    raise ValueError(f"Missing required field for publishing: '{field}'")
            
            # Check for files
            last_files_count = ResourceFile.query.filter_by(version_id=last_v.version_id).count() if last_v else 0
            removed_files_count = len(data.get('removed_file_urls', []))
            new_files_count = len(new_files_info or [])
            
            if (last_files_count - removed_files_count + new_files_count) <= 0:
                raise ValueError("At least one file is required to publish a resource.")

        estimate_duration = data.get('estimate_duration')
        if estimate_duration and len(str(estimate_duration)) > 100:
            raise ValueError("Estimate duration must be less than 100 characters")

        # IF OWNER: Update collection metadata immediately
        if is_owner:
            new_title = data.get('title')
            if new_title:
                unique_title = ResourceCollectionService._generate_unique_title(new_title, exclude_id=old_collection_id)
                collection.title = unique_title
            
            collection.is_published = data.get('is_published', collection.is_published)
            collection.description = data.get('description', collection.description)
            collection.subject_id = data.get('subject_id', collection.subject_id)
            collection.grade_level_id = data.get('grade_level_id', collection.grade_level_id)
            collection.estimate_duration = estimate_duration if estimate_duration is not None else collection.estimate_duration
            collection.student_summary = data.get('student_summary', collection.student_summary)
            collection.allow_remixing = data.get('allow_remixing', collection.allow_remixing)
            collection.visibility = data.get('visibility', collection.visibility)
            collection.collaboration_mode = data.get('collaboration_mode', collection.collaboration_mode)
            collection.updated_at = datetime.now(timezone.utc)
            
            # Mark previous versions as not latest
            ResourceVersion.query.filter_by(collection_id=old_collection_id).update({"is_latest": False})

        new_v_no = (last_v.version_no + 1) if last_v else 1

        # CREATE NEW VERSION (Proposed if collaborator, Live if owner)
        new_version = ResourceVersion(
            collection_id = old_collection_id,
            version_no = new_v_no,
            title = data.get('title') or collection.title,
            description = data.get('description') or collection.description,
            notes = data.get('version_notes') or data.get('notes') or ('proposed update' if not is_owner else 'updated resource'),
            is_latest = is_owner, # Only owner updates are immediately "Latest"
            is_approved = is_owner, # Owner edits are auto-approved
            is_remix = last_v.is_remix if last_v else False,
            is_published = is_published if is_owner else collection.is_published,
            visibility = data.get('visibility') if is_owner else collection.visibility,
            estimate_duration = estimate_duration if is_owner else collection.estimate_duration,
            allow_remixing = data.get('allow_remixing') if is_owner else collection.allow_remixing,
            collaboration_mode = data.get('collaboration_mode') if is_owner else collection.collaboration_mode,
            
            # Propagate Citation
            original_author_name = last_v.original_author_name if last_v else None,
            original_author_username = last_v.original_author_username if last_v else None,
            original_resource_title = last_v.original_resource_title if last_v else None,
            parent_version_id = last_v.parent_version_id if last_v else None,
            
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
        
        # Tags are collection-level metadata; only owners can update them via update_resource for now
        # to prevent collaborator-driven tag spam.
        if is_owner:
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

        # Notifications & Logging
        from services.activity_service import ActivityService
        from services.notification_service import NotificationService
        
        if is_owner:
            ActivityService.log_activity(
                user_id=collection.owner_id,
                activity_type='update_resource',
                collection_id=collection.collection_id
            )
        else:
            # COLLABORATOR: Notify owner of proposed changes
            NotificationService.create_notification(
                recipient_id=collection.owner_id,
                notification_type='proposed_change',
                sender_id=updater_id,
                collection_id=collection.collection_id,
                extra_data={"version_no": new_version.version_no}
            )
            
            ActivityService.log_activity(
                user_id=updater_id,
                activity_type='propose_update',
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
                "owner_id": collection.owner_id,
                "version_id": version.version_id,
                "version_no": version.version_no,
                "notes": version.notes,
                "is_latest": version.is_latest, 
                "is_published": version.is_published,
                "visibility": version.visibility,
                "estimate_duration": version.estimate_duration,
                "allow_remixing": version.allow_remixing,
                "collaboration_mode": version.collaboration_mode,
                "is_approved": version.is_approved,
                "approved_by": f"{version.approved_by_teacher.first_name} {version.approved_by_teacher.last_name}" if hasattr(version, 'approved_by_teacher') and version.approved_by_teacher else None,
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

        rating_sub = db.session.query(
            ResourceRating.collection_id,
            func.avg(ResourceRating.score).label('avg_rating')
        ).group_by(ResourceRating.collection_id).subquery()

        # Main query for the collections
        query = db.session.query(
            ResourceCollection,
            func.coalesce(weekly_likes_sub.c.weekly_likes, 0).label('weekly_likes'),
            func.coalesce(rating_sub.c.avg_rating, 0).label('avg_rating')
        )\
        .join(Teacher, ResourceCollection.owner_id == Teacher.teacher_id)\
        .options(joinedload(ResourceCollection.subject),
                joinedload(ResourceCollection.grade_level),
                joinedload(ResourceCollection.content_type))\
        .outerjoin(weekly_likes_sub, ResourceCollection.collection_id == weekly_likes_sub.c.collection_id)\
        .outerjoin(rating_sub, ResourceCollection.collection_id == rating_sub.c.collection_id)
        
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
        
        for collection, weekly_likes, avg_rating in pagination.items:
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
                "avg_rating": round(float(avg_rating), 1) if avg_rating else 0,
                "estimate_duration": collection.estimate_duration,
                "allow_remixing": collection.allow_remixing,
                "version_no": latest_v.version_no if latest_v else 1,
                "updated_at": collection.updated_at.isoformat(),
                
                # Citation
                "is_remix": latest_v.is_remix if latest_v else False,
                "original_author_name": latest_v.original_author_name if latest_v else None,
                "original_resource_title": latest_v.original_resource_title if latest_v else None
            })

        total_avg_raw = db.session.query(func.avg(ResourceRating.score)).scalar()
        total_avg_rating = round(float(total_avg_raw), 1) if total_avg_raw else 0

        return {
            "resources": results,
            "total_pages": pagination.pages,
            "current_page": pagination.page,
            "has_next": pagination.has_next,
            "total_count": pagination.total,
            "total_avg_rating": total_avg_rating
        }
    
    @staticmethod
    def remix_resource(original_collection_id, new_owner_id):
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

        try:
            # Generate Unique Title for Remix (Truncate if needed to fit 255 chars)
            title_base = original_collection.title
            if len(title_base) > 240:
                title_base = title_base[:240]
            
            base_remix_title = f"{title_base} (Remix)"
            unique_remix_title = ResourceCollectionService._generate_unique_title(base_remix_title)

            # 2. Spawn a BRAND NEW Collection for the new owner
            remixed_collection = ResourceCollection(
                title=unique_remix_title,
                description=original_collection.description,
                owner_id=new_owner_id, 
                subject_id=original_collection.subject_id,
                grade_level_id=original_collection.grade_level_id,
                content_type_id=original_collection.content_type_id,
                estimate_duration=original_collection.estimate_duration,
                student_summary=original_collection.student_summary,
                allow_remixing=bool(original_collection.allow_remixing),
                visibility=original_collection.visibility or 'public',
                is_published=False 
            )
            db.session.add(remixed_collection)
            db.session.flush()

            # 3. Determine source content (latest version with fallbacks)
            latest_v = ResourceVersion.query.filter_by(
                collection_id=original_collection_id, 
                is_latest=True
            ).first()

            # Fallback 1: Highest version number if no "latest" flag
            if not latest_v:
                latest_v = ResourceVersion.query.filter_by(collection_id=original_collection_id)\
                    .order_by(ResourceVersion.version_no.desc()).first()

            original_owner = original_collection.owner
            author_name = f"{original_owner.first_name} {original_owner.last_name}" if original_owner else "Unknown Author"
            author_username = original_owner.username if original_owner else None

            # 4. Spawn New Version Record
            # If we found a version, use it. Otherwise, use collection metadata.
            new_version = ResourceVersion(
                collection_id=remixed_collection.collection_id,
                version_no=1, 
                title=latest_v.title if latest_v else original_collection.title,
                description=latest_v.description if latest_v else original_collection.description,
                notes=f"Remixed from {author_name}'s original",
                is_latest=True,
                is_remix=True,
                is_published=False,
                visibility=(latest_v.visibility if latest_v else original_collection.visibility) or 'public',
                estimate_duration=latest_v.estimate_duration if latest_v else original_collection.estimate_duration,
                allow_remixing=bool(latest_v.allow_remixing if latest_v else original_collection.allow_remixing),
                collaboration_mode=(latest_v.collaboration_mode if latest_v else original_collection.collaboration_mode) or 'none',
                parent_version_id=latest_v.version_id if latest_v else None,
                
                # Snapshot Citation
                original_author_name=author_name,
                original_author_username=author_username,
                original_resource_title=original_collection.title,
                
                created_by=new_owner_id,
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(new_version)
            db.session.flush()

            # 5. Clone Files for this version (if exists)
            if latest_v:
                original_files = ResourceFile.query.filter_by(version_id=latest_v.version_id).all()
                for f in original_files:
                    db.session.add(ResourceFile(
                        version_id=new_version.version_id,
                        file_url=f.file_url,
                        file_name=f.file_name,
                        file_type=f.file_type,
                        file_size=f.file_size,
                        file_hash=f.file_hash
                    ))

            # 6. Clone Tags (Attached to the Collection)
            original_tags = ResourceTag.query.filter_by(collection_id=original_collection_id).all()
            for ot in original_tags:
                db.session.add(ResourceTag(
                    collection_id=remixed_collection.collection_id,
                    tag_id=ot.tag_id
                ))

            db.session.commit()

            # Trigger Notification for remix
            try:
                from services.notification_service import NotificationService
                NotificationService.create_notification(
                    recipient_id=original_collection.owner_id,
                    notification_type='remix',
                    sender_id=new_owner_id,
                    collection_id=original_collection_id,
                    extra_data={"remixed_collection_id": remixed_collection.collection_id}
                )
            except Exception as e:
                print(f"Non-fatal error creating remix notification: {e}")

            # Log Activity
            try:
                from services.activity_service import ActivityService
                ActivityService.log_activity(
                    user_id=new_owner_id,
                    activity_type='remix_resource',
                    collection_id=original_collection_id,
                    extra_data={"remixed_collection_id": remixed_collection.collection_id}
                )
            except Exception as e:
                print(f"Non-fatal error logging remix activity: {e}")

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
        
        # OWNER-ONLY INVITE ENFORCEMENT
        if not owner_id or collection.owner_id != owner_id:
            raise ValueError("Unauthorized: Only the resource owner can invite collaborators.")
            
        if collection.collaboration_mode == 'none':
            raise ValueError("Collaboration is disabled for this resource")
        
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
        
        