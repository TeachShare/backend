from models import ResourceCollection, ResourceVersion, ResourceFile, ResourceTag, Tag, TagType, Subject, ContentType, GradeLevel, db

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
                content_type_id = data.get('content_type_id')
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
    def get_my_resources(teacher_id):
        # This now works perfectly because create_resource sets is_latest=True
        my_collections = db.session.query(ResourceCollection)\
            .join(ResourceVersion, ResourceCollection.collection_id == ResourceVersion.collection_id)\
            .filter(ResourceCollection.owner_id == teacher_id)\
            .filter(ResourceVersion.is_latest == True)\
            .order_by(ResourceCollection.updated_at.desc())\
            .all()

        results = []
        for collection in my_collections:
            # Metadata mapping
            subject = Subject.query.get(collection.subject_id)
            c_type = ContentType.query.get(collection.content_type_id)
            grade = GradeLevel.query.get(collection.grade_level_id)

            resource_tags = ResourceTag.query.filter_by(collection_id=collection.collection_id).all()
            tag_names = [Tag.query.get(rt.tag_id).tag_name for rt in resource_tags if Tag.query.get(rt.tag_id)]

            # Get version number for the UI badge
            v_info = ResourceVersion.query.filter_by(collection_id=collection.collection_id).first()

            results.append({
                "collection_id": collection.collection_id,
                "title": collection.title,
                "version_no": v_info.version_no if v_info else 1,
                "is_published": collection.is_published,
                "description": collection.description,
                "category": subject.subject_name if subject else "No Subject",
                "type": c_type.type_name if c_type else "No Type",
                "grade": grade.grade_name if grade else "No Grade",
                "tags": tag_names, 
                "created_at": collection.created_at.isoformat(),
                "updated_at": collection.updated_at.isoformat()
            })
        return results

    @staticmethod
    def get_resource_by_id(collection_id):
        collection = ResourceCollection.query.get(collection_id)
        if not collection: return None

        latest_version = ResourceVersion.query.filter_by(collection_id=collection_id).first()
        files_data = []
        if latest_version:
            files = ResourceFile.query.filter_by(version_id=latest_version.version_id).all()
            files_data = [{"file_id": f.file_id, "name": f.file_name, "url": f.file_url, "type": f.file_type, "size": f.file_size} for f in files]

        # Metadata & Tags
        resource_tags = ResourceTag.query.filter_by(collection_id=collection_id).all()
        tag_names = [Tag.query.get(rt.tag_id).tag_name for rt in resource_tags if Tag.query.get(rt.tag_id)]

        return {
            "collection_id": collection.collection_id,
            "owner_id": collection.owner_id,
            "title": collection.title,
            "description": collection.description,
            "subject": Subject.query.get(collection.subject_id).subject_name if collection.subject_id else "General",
            "grade": GradeLevel.query.get(collection.grade_level_id).grade_name if collection.grade_level_id else "All Grades",
            "type": ContentType.query.get(collection.content_type_id).type_name if collection.content_type_id else "Resource",
            "subject_id": collection.subject_id,
            "grade_level_id": collection.grade_level_id,
            "content_type_id": collection.content_type_id,
            "tags": tag_names,
            "files": files_data,
            "is_published": collection.is_published,
            "version_no": latest_version.version_no if latest_version else 1,
            "updated_at": collection.updated_at.isoformat()
        }

    @staticmethod
    def update_resource(old_collection_id, data, new_files_info=None):
        old_collection = ResourceCollection.query.get(old_collection_id)
        if not old_collection: return None

        try:
            # 1. Spawn New Collection (Immutability)
            new_collection = ResourceCollection(
                title=data.get('title', old_collection.title),
                description=data.get('description', old_collection.description),
                owner_id=old_collection.owner_id,
                subject_id=data.get('subject_id', old_collection.subject_id),
                grade_level_id=data.get('grade_level_id', old_collection.grade_level_id),
                content_type_id=data.get('content_type_id', old_collection.content_type_id),
                is_published=data.get('is_published', old_collection.is_published)
            )
            db.session.add(new_collection)
            db.session.flush()

            # 2. Update lineage: Old versions are no longer "latest"
            # Note: In a deep tree, you'd find all siblings. Here we follow the teacher/title chain.
            ResourceVersion.query.filter(
                ResourceVersion.collection_id == old_collection_id
            ).update({"is_latest": False})

            # 3. Calculate new version number
            last_v = ResourceVersion.query.filter_by(collection_id=old_collection_id).first()
            new_v_no = (last_v.version_no + 1) if last_v else 2

            new_version = ResourceVersion(
                collection_id=new_collection.collection_id,
                version_no=new_v_no,
                notes=data.get('version_notes', f"Revised version {new_v_no}"),
                is_latest=True,
                created_by=new_collection.owner_id
            )
            db.session.add(new_version)
            db.session.flush()

            # 4. Handle Files
            if new_files_info:
                for f in new_files_info:
                    db.session.add(ResourceFile(version_id=new_version.version_id, file_url=f.get('url'), file_name=f.get('name'), file_type=f.get('type'), file_size=f.get('size')))
            elif last_v:
                old_files = ResourceFile.query.filter_by(version_id=last_v.version_id).all()
                for old_f in old_files:
                    db.session.add(ResourceFile(version_id=new_version.version_id, file_url=old_f.file_url, file_name=old_f.file_name, file_type=old_f.file_type, file_size=old_f.file_size))

            # 5. Clone Tags
            for tag_string in data.get('tags', []):
                clean_name = str(tag_string).strip().lower()
                if not clean_name: continue
                existing_tag = Tag.query.filter_by(tag_name=clean_name).first()
                if not existing_tag:
                    existing_tag = Tag(tag_name=clean_name, tag_type_id=(TagType.query.filter_by(type_name='custom').first().tag_type_id))
                    db.session.add(existing_tag)
                    db.session.flush()
                db.session.add(ResourceTag(collection_id=new_collection.collection_id, tag_id=existing_tag.tag_id))

            db.session.commit()
            return new_collection
        except Exception as e:
            db.session.rollback()
            raise e

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
    def get_discover_resources(current_teacher_id):
        try:
            query = db.session.query(ResourceCollection)\
                .join(ResourceVersion, ResourceCollection.collection_id == ResourceVersion.collection_id)\
                .filter(ResourceCollection.owner_id != current_teacher_id)\
                .filter(ResourceCollection.is_published == True)\
                .filter(ResourceVersion.is_latest == True)\
                .order_by(ResourceCollection.updated_at.desc())

            results = []
            for collection in query.all():
                latest_v = ResourceVersion.query.filter_by(collection_id=collection.collection_id).first()
                file_count = ResourceFile.query.filter_by(version_id=latest_v.version_id).count() if latest_v else 0
                resource_tags = ResourceTag.query.filter_by(collection_id=collection.collection_id).all()

                results.append({
                    "collection_id": collection.collection_id,
                    "title": collection.title,
                    "description": collection.description,
                    "owner_name": f"{collection.owner.first_name} {collection.owner.last_name}",
                    "subject": Subject.query.get(collection.subject_id).subject_name if collection.subject_id else "General",
                    "grade": GradeLevel.query.get(collection.grade_level_id).grade_name if collection.grade_level_id else "All Grades",
                    "type": ContentType.query.get(collection.content_type_id).type_name if collection.content_type_id else "Resource",
                    "tags": [Tag.query.get(rt.tag_id).tag_name for rt in resource_tags if Tag.query.get(rt.tag_id)],
                    "file_count": file_count,
                    "version_no": latest_v.version_no if latest_v else 1,
                    "updated_at": collection.updated_at.isoformat()
                })
            return results
        except Exception as e:
            raise e
        
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