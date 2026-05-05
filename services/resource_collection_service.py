from models import ResourceCollection, ResourceVersion, ResourceFile, ResourceTag, Tag, TagType, Subject, ContentType, GradeLevel, db, ResourceComment, ResourceRating, ResourceLike
from datetime import datetime, timezone
from sqlalchemy.orm import joinedload
from sqlalchemy import or_, cast, String
from sqlalchemy.sql import func

class ResourceCollectionService:
    @staticmethod
    def create_resource(data):
        is_published = data.get('is_published', False)
        required_fields = ['title', 'owner_id']

        if is_published:
            required_fields.extend(['subject_id', 'grade_level_id', 'content_type_id'])

        for field in required_fields:
            if not data.get(field):
                raise ValueError(f"Missing required field: '{field}'")
            
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
                updated_at = datetime.now(timezone.utc)
            )

            db.session.add(new_collection)
            db.session.flush() # Get the collection_id
            
            # 2. CREATE VERSION 1 IMMEDIATELY
            # We set is_latest=True so it is immediately "Discoverable"
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
                    file_size = file_info.get('size')
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
            
            db.session.commit()
            return new_collection

        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_my_resources(teacher_id, filters=None, page=1, per_page=12):
        
        query = db.session.query(
            ResourceCollection,
            func.count(ResourceLike.collection_id).label('total_likes')
        )\
        .outerjoin(ResourceLike, ResourceCollection.collection_id == ResourceLike.collection_id)\
        .outerjoin(Subject, ResourceCollection.subject_id == Subject.subject_id)\
        .outerjoin(GradeLevel, ResourceCollection.grade_level_id == GradeLevel.grade_level_id)\
        .outerjoin(ContentType, ResourceCollection.content_type_id == ContentType.content_type_id)\
        .join(ResourceVersion, ResourceCollection.collection_id == ResourceVersion.collection_id)\
        .filter(ResourceCollection.owner_id == teacher_id)\
        .filter(ResourceVersion.is_latest == True)\
        .group_by(ResourceCollection.collection_id)
        
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
                
        query = query.order_by(ResourceCollection.updated_at.desc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        results = []

        for col, total_likes in pagination.items:
            # Safer tag fetching to prevent loop crashes
            tag_names = [rt.tag.tag_name for rt in col.tags if rt.tag] if hasattr(col, 'tags') else []
            
            results.append({
                "collection_id": col.collection_id,
                "title": col.title or "Untitled",
                "description": col.description if isinstance(col.description, str) else str(col.description or ""),
                "is_published": col.is_published,
                "category": col.subject.subject_name if col.subject else "No Subject",
                "type": col.content_type.type_name if col.content_type else "No Type",
                "grade": col.grade_level.grade_name if col.grade_level else "No Grade",
                "tags": tag_names, 
                "likes": total_likes,  
                "downloads": 0,      
                "updated_at": col.updated_at.isoformat() if col.updated_at else datetime.now(timezone.utc).isoformat()
            })
        
        return {
            "resources": results,
            "total_pages": pagination.pages,
            "current_page": pagination.page,
            "has_next": pagination.has_next,
            "total_count": pagination.total
        }
    @staticmethod
    def get_resource_by_id(collection_id, current_user_id=None):
        collection = ResourceCollection.query.get(collection_id)
        if not collection: return None

        latest_version = ResourceVersion.query.filter_by(collection_id=collection_id, is_latest=True).first()
        if not latest_version:
            latest_version = ResourceVersion.query.filter_by(collection_id=collection_id)\
                .order_by(ResourceVersion.version_no.desc()).first()

        files_data = []
        if latest_version:
            files = ResourceFile.query.filter_by(version_id=latest_version.version_id).all()
            files_data = [{
                "file_id": f.file_id, 
                "name": f.file_name, 
                "url": f.file_url, 
                "type": f.file_type, 
                "size": f.file_size
            } for f in files]

        tag_names = [t.tag_name for t in db.session.query(Tag.tag_name)\
                    .join(ResourceTag, Tag.tag_id == ResourceTag.tag_id)\
                    .filter(ResourceTag.collection_id == collection_id).all()]

        comments_query = db.session.query(ResourceComment, ResourceRating.score)\
            .outerjoin(ResourceRating, (ResourceRating.teacher_id == ResourceComment.teacher_id) & 
                                    (ResourceRating.collection_id == ResourceComment.collection_id))\
            .filter(ResourceComment.collection_id == collection_id)\
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

        downloads_count = getattr(collection, 'downloads_count', 0) or 0
        remixes_count = getattr(collection, 'remixes_count', 0) or 0

        return {
            "collection_id": collection.collection_id,
            "owner_id": collection.owner_id,
            "owner_name": f"{collection.owner.first_name} {collection.owner.last_name}" if collection.owner else "Unknown",
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
            "downloads": downloads_count,
            "remixes": remixes_count,
            "is_published": collection.is_published,
            "version_no": latest_version.version_no if latest_version else 1,
            "updated_at": collection.updated_at.isoformat()
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
    def update_resource(old_collection_id, data, new_files_info=None):
        collection = ResourceCollection.query.get(old_collection_id)

        if not collection:
            raise ValueError("Collection not found")
        collection.is_published = data.get('is_published', collection.is_published)
        collection.title = data.get('title', collection.title)
        collection.description = data.get('description', collection.description)
        collection.subject_id = data.get('subject_id', collection.subject_id)
        collection.grade_level_id = data.get('grade_level_id', collection.grade_level_id)

        collection.updated_at = datetime.now(timezone.utc)
        
        last_v = ResourceVersion.query.filter_by(collection_id=old_collection_id)\
            .order_by(ResourceVersion.version_no.desc()).first()
        
        new_v_no = (last_v.version_no + 1) if last_v else 1

        ResourceVersion.query.filter_by(collection_id=old_collection_id).update({"is_latest": False})

        new_version = ResourceVersion(
            collection_id = old_collection_id,
            version_no = new_v_no,
            notes = data.get('notes', 'updated resources'),
            is_latest = True,
            is_remix = False,
            parent_version_id = last_v.version_id if last_v else None,
            created_by = collection.owner_id
        )
        
        db.session.add(new_version)
        db.session.flush()

        # 1. Always retain files from the previous version
        if last_v:
            old_files = ResourceFile.query.filter_by(version_id=last_v.version_id).all()
            for old_f in old_files:
                db.session.add(ResourceFile(
                    version_id=new_version.version_id,
                    file_url=old_f.file_url,
                    file_name=old_f.file_name,
                    file_type=old_f.file_type,
                    file_size=old_f.file_size
                ))

        # 2. Append new files if they are provided
        if new_files_info:
            for f in new_files_info:
                db.session.add(ResourceFile(
                    version_id=new_version.version_id,
                    file_url=f.get('url'),
                    file_name=f.get('name'),
                    file_type=f.get('type'),
                    file_size=f.get('size')
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
        return collection

    @staticmethod
    def get_version_history(collection_id):
        current_resource = ResourceCollection.query.get(collection_id)
        if not current_resource: return []

        versions = db.session.query(ResourceVersion, ResourceCollection)\
            .join(ResourceCollection, ResourceVersion.collection_id == ResourceCollection.collection_id)\
            .filter(ResourceCollection.owner_id == current_resource.owner_id)\
            .filter(ResourceCollection.title == current_resource.title)\
            .order_by(ResourceVersion.version_no.desc())\
            .all()

        history = []
        for version, collection in versions:
            file_count = ResourceFile.query.filter_by(version_id=version.version_id).count()
            history.append({
                "collection_id": collection.collection_id,
                "version_id": version.version_id,
                "version_no": version.version_no,
                "notes": version.notes,
                "is_latest": version.is_latest, 
                "created_at": version.created_at.isoformat(),
                "file_count": file_count,
                "author": f"{current_resource.owner.first_name} {current_resource.owner.last_name}"
            })
        return history


    @staticmethod
    def get_discover_resources(current_teacher_id, filters=None, page=1, per_page=12):
        # Main query for the collections
        query = db.session.query(ResourceCollection)\
            .options(joinedload(ResourceCollection.subject),
                    joinedload(ResourceCollection.grade_level),
                    joinedload(ResourceCollection.content_type))\
            .filter(ResourceCollection.owner_id != current_teacher_id)\
            .filter(ResourceCollection.is_published == True)
        
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

        query = query.order_by(ResourceCollection.updated_at.desc())
        
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        results = []
        
        for collection in pagination.items:
            # Manual fetch for the latest version since 'versions' relationship isn't set
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
                "title": collection.title,
                "owner_name": f"{collection.owner.first_name} {collection.owner.last_name}" if collection.owner else "Unknown",
                "subject": collection.subject.subject_name if collection.subject else "General",
                "grade": collection.grade_level.grade_name if collection.grade_level else "All Grades",
                "type": collection.content_type.type_name if collection.content_type else "Resource",
                "tags": tag_names, 
                "file_count": file_count,
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

        original_version = ResourceVersion.query.filter_by(
            collection_id=original_collection_id, 
            is_latest=True
        ).first()

        try:
            # 2. Spawn a BRAND NEW Collection for the new owner
            # We add " (Remix)" to the title or keep it same based on your UI preference
            remixed_collection = ResourceCollection(
                title=f"{original_collection.title} (Remix)",
                description=original_collection.description,
                owner_id=new_owner_id, # The teacher doing the remixing
                subject_id=original_collection.subject_id,
                grade_level_id=original_collection.grade_level_id,
                content_type_id=original_collection.content_type_id,
                is_published=False # Remixes start as drafts
            )
            db.session.add(remixed_collection)
            db.session.flush()

            # 3. Create Version 1 for this new collection
            # Here we cite the original by setting parent_version_id
            new_version = ResourceVersion(
                collection_id=remixed_collection.collection_id,
                version_no=1,
                notes=f"Remixed from {original_collection.owner.first_name} {original_collection.owner.last_name}",
                is_latest=True,
                is_remix=True, # Mark as a remix
                parent_version_id=original_version.version_id if original_version else None,
                created_by=new_owner_id
            )
            db.session.add(new_version)
            db.session.flush()

            # 4. Clone Files (Reference the same Appwrite URLs)
            if original_version:
                original_files = ResourceFile.query.filter_by(version_id=original_version.version_id).all()
                for f in original_files:
                    db.session.add(ResourceFile(
                        version_id=new_version.version_id,
                        file_url=f.file_url,
                        file_name=f.file_name,
                        file_type=f.file_type,
                        file_size=f.file_size
                    ))

            # 5. Clone Tags
            original_tags = ResourceTag.query.filter_by(collection_id=original_collection_id).all()
            for ot in original_tags:
                db.session.add(ResourceTag(
                    collection_id=remixed_collection.collection_id,
                    tag_id=ot.tag_id
                ))

            db.session.commit()
            return remixed_collection

        except Exception as e:
            db.session.rollback()
            raise e

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
            # 2. Get all versions associated with this collection to find files
            versions = ResourceVersion.query.filter_by(collection_id=collection_id).all()
            version_ids = [v.version_id for v in versions]

            # 3. DELETE FROM CHILD TABLES FIRST (The Order Matters!)
            
            # Remove File References
            if version_ids:
                ResourceFile.query.filter(ResourceFile.version_id.in_(version_ids)).delete(synchronize_session=False)
            
            # Remove Tag Links
            ResourceTag.query.filter_by(collection_id=collection_id).delete(synchronize_session=False)
            
            # Remove Versions
            ResourceVersion.query.filter_by(collection_id=collection_id).delete(synchronize_session=False)

            # 4. FINALLY: Remove the Collection itself
            db.session.delete(collection)
            
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e
        
        