import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.resource_collection_service import ResourceCollectionService
from services.file_service import AppwriteService
from services.interaction_service import InteractionService
from models import ResourceCollection, db, FileSignature

from lib import verification_required
import traceback

resource_collection_bp = Blueprint('resource_collection', __name__)
appwrite_service = AppwriteService()

@resource_collection_bp.route('/create_resources', methods=['POST'])
@verification_required
def create_resource_route(current_teacher):
    try:
        current_teacher_id = current_teacher.teacher_id

        data_string = request.form.get('resource_data')
        if not data_string:
            return jsonify({"error": "Missing resource_data payload"}), 400
        
        data = json.loads(data_string)
        
        data['owner_id'] = current_teacher_id

        uploaded_files = request.files.getlist('files')

        file_metadata_list = []
        for file_obj in uploaded_files:
            if file_obj.filename != '':
                # Read file bytes to calculate hash
                file_bytes = file_obj.read()
                file_hash = appwrite_service.calculate_hash(file_bytes)
                
                # Check for duplicate
                existing_file = ResourceCollectionService.get_file_by_hash(file_hash)
                
                if existing_file:
                    # Reuse existing file metadata
                    metadata = {
                        "url": existing_file.file_url,
                        "name": file_obj.filename, # Keep the new filename if desired, or use existing
                        "type": existing_file.file_type,
                        "size": existing_file.file_size,
                        "hash": file_hash
                    }
                else:
                    # Upload new file
                    metadata = appwrite_service.upload_bytes(file_bytes, file_obj.filename, file_obj.content_type)
                    
                    # RETAIN: Register the new signature globally
                    new_signature = FileSignature(
                        file_hash=file_hash,
                        file_url=metadata['url'],
                        file_name=metadata['name'],
                        file_type=metadata['type'],
                        file_size=metadata['size']
                    )
                    db.session.add(new_signature)
                    db.session.flush()
                
                file_metadata_list.append(metadata)

        data['files'] = file_metadata_list

        resource = ResourceCollectionService.create_resource(data)

        is_published = data.get('is_published', False)
        status_message = "Resource successfully published." if is_published else "Draft successfully saved."

        return jsonify({
            "success": True,
            "message": status_message,
            "collection_id" : resource.collection_id
        }), 201
    
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve) }), 400
    
    except Exception as e:
        print(f"Error creating resources: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500
    

@resource_collection_bp.route('/my-resources', methods=['GET'])
@verification_required
def get_my_resources_route(current_teacher):
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 12, type=int)
        sort_by = request.args.get('sort_by', 'newest')

        filters = {
            "search": request.args.get('search'),
            "subject_id": request.args.get('subject_id', type=int),
            "grade_level_id": request.args.get('grade_level_id', type=int),
            "content_type_id": request.args.get('content_type_id', type=int),
            "status": request.args.get('status')
        }

        response_data = ResourceCollectionService.get_my_resources(
            current_teacher.teacher_id,
            filters,
            page=page,
            per_page=per_page,
            sort_by=sort_by
        )

        return jsonify({
            "success": True,
            **response_data
        }), 200
    
    except Exception as e:
        traceback.print_exc() 
        return jsonify({"success": False, "error": str(e)}), 500


@resource_collection_bp.route('/bulk-action', methods=['POST'])
@verification_required
def bulk_action_route(current_teacher):
    try:
        data = request.get_json()
        action = data.get('action') # 'delete', 'make_private', 'make_public'
        collection_ids = data.get('collection_ids', [])

        if not action or not collection_ids:
            return jsonify({"success": False, "error": "Action and collection_ids are required"}), 400

        target_resources = ResourceCollection.query.filter(
            ResourceCollection.collection_id.in_(collection_ids),
            ResourceCollection.owner_id == current_teacher.teacher_id
        ).all()

        if not target_resources:
            return jsonify({"success": False, "error": "No valid resources found."}), 404

        if action == 'delete':
            for r in target_resources:
                ResourceCollectionService.delete_resource(r.collection_id, current_teacher.teacher_id)
        elif action == 'make_private':
            for r in target_resources:
                r.visibility = 'private'
        elif action == 'make_public':
            for r in target_resources:
                r.visibility = 'public'
        
        db.session.commit()
        return jsonify({"success": True, "message": f"Bulk {action} completed."}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    

@resource_collection_bp.route('/<int:collection_id>', methods=['GET'])
@verification_required
def get_resource_detail_route(current_teacher,collection_id):
    try:
        version_no = request.args.get('version_no', type=int)
        resource = ResourceCollectionService.get_resource_by_id(
            collection_id, 
            current_user_id=current_teacher.teacher_id,
            version_no=version_no
        )
        
        if not resource:
            return jsonify({"success": False, "error": "Resource not found"}), 404

        return jsonify({
            "success": True,
            "data": resource
        }), 200

    except Exception as e:
        print(f"Error fetching resource {collection_id}: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500
    
    

@resource_collection_bp.route('/<int:collection_id>', methods=['PUT'])
@verification_required
def update_resource_route(current_teacher, collection_id):
    try:
        current_teacher_id = current_teacher.teacher_id

        if not ResourceCollectionService.has_edit_permission(collection_id, current_teacher_id):
            return jsonify({
                "success": False, 
                "error": "Unauthorized: You do not have permission to edit this resource."
            }), 403

        data_string = request.form.get('resource_data')
        if not data_string:
            return jsonify({"success": False, "error": "Missing resource_data payload"}), 400
        
        data = json.loads(data_string)
        
        uploaded_files = request.files.getlist('files')
        new_file_metadata = []

        for file_obj in uploaded_files:
            if file_obj.filename != '':
                file_bytes = file_obj.read()
                file_hash = appwrite_service.calculate_hash(file_bytes)

                existing_file = ResourceCollectionService.get_file_by_hash(file_hash)

                if existing_file:
                    metadata = {
                        "url": existing_file.file_url,
                        "name": file_obj.filename,
                        "type": existing_file.file_type,
                        "size": existing_file.file_size,
                        "hash": file_hash
                    }
                else:
                    metadata = appwrite_service.upload_bytes(file_bytes, file_obj.filename, file_obj.content_type)
                    
                    # RETAIN: Register the new signature globally
                    new_signature = FileSignature(
                        file_hash=file_hash,
                        file_url=metadata['url'],
                        file_name=metadata['name'],
                        file_type=metadata['type'],
                        file_size=metadata['size']
                    )
                    db.session.add(new_signature)
                    db.session.flush()

                new_file_metadata.append(metadata)

        newly_spawned_resource = ResourceCollectionService.update_resource(            old_collection_id=collection_id,
            data=data,
            new_files_info=new_file_metadata,
            updater_id=current_teacher_id
        )

        return jsonify({
            "success": True,
            "message": "New version collection spawned successfully.",
            "collection_id": newly_spawned_resource.collection_id,
            "version_no": data.get('version_no') 
        }), 201 

    except Exception as e:
        print(f"Error spawning new version for collection {collection_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    
@resource_collection_bp.route('/<int:collection_id>/history', methods=['GET'])
@verification_required
def get_resource_history_route(current_teacher, collection_id):
    """
    Fetches the lineage of versions (all spawned collections) 
    associated with this specific resource.
    """
    try:
        # 1. Fetch the history from the service
        history = ResourceCollectionService.get_version_history(collection_id)
        
        if not history:
            # If the collection exists but has no history (shouldn't happen with your logic)
            # we at least return the current one as V1
            return jsonify({"success": True, "data": []}), 200

        return jsonify({
            "success": True,
            "data": history
        }), 200

    except Exception as e:
        print(f"Error fetching history for collection {collection_id}: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500

@resource_collection_bp.route('/compare/<int:collection_id>', methods=['GET'])
@verification_required
def get_comparison_data(current_teacher, collection_id):
    try:
        v1_no = request.args.get('v1', type=int)
        v2_no = request.args.get('v2', type=int)

        version_a = ResourceCollectionService.get_resource_by_id(
            collection_id, 
            current_user_id=current_teacher.teacher_id,
            version_no=v1_no
        )
        version_b = ResourceCollectionService.get_resource_by_id(
            collection_id, 
            current_user_id=current_teacher.teacher_id,
            version_no=v2_no
        )

        if not version_a or not version_b:
            return jsonify({"success": False, "error": "Version not found"}), 404

        return jsonify({
            "success": True,
            "v1": version_a,
            "v2": version_b
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
@resource_collection_bp.route('/discover', methods=['GET'])
@verification_required
def discover_resources_route(current_teacher):
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 12, type=int)

        filters = {
            "search": request.args.get('search'),
            "subject_id": request.args.get('subject_id', type=int),
            "grade_level_id": request.args.get('grade_level_id', type=int),
            "content_type_id": request.args.get('content_type_id', type=int),
            "sort_by": request.args.get('sort_by', 'newest'),
            "verified_only": request.args.get('verified_only') == 'true'
        }

        response_data = ResourceCollectionService.get_discover_resources(
            current_teacher.teacher_id,
            filters,
            page=page,
            per_page=per_page
        )

        return jsonify({
            "success": True,
            **response_data
        }), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@resource_collection_bp.route('/search', methods=['GET'])
@verification_required
def global_search_route(current_teacher):
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify({"success": True, "resources": [], "users": []}), 200

        # Search Resources
        resource_data = ResourceCollectionService.get_discover_resources(
            current_teacher.teacher_id,
            filters={"search": query},
            page=1,
            per_page=5,
            include_own=True
        )

        # Search Users
        from services.teacher_service import TeacherService
        user_data = TeacherService.get_all_profiles(
            current_teacher.teacher_id,
            page=1,
            per_page=5,
            search=query
        )

        return jsonify({
            "success": True,
            "resources": resource_data.get('resources', []),
            "users": user_data.get('teachers', [])
        }), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@resource_collection_bp.route('/remix/<int:collection_id>', methods=['POST'])
@verification_required
def remix_resource_route(current_teacher, collection_id):
    current_teacher_id = current_teacher.teacher_id
    try:
        new_resource = ResourceCollectionService.remix_resource(collection_id, current_teacher_id)
        return jsonify({
            "success": True, 
            "message": "Resource remixed successfully",
            "collection_id": new_resource.collection_id
        }), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@resource_collection_bp.route('/<int:collection_id>', methods=['DELETE'])
@verification_required
def delete_resource_permanently_route(current_teacher, collection_id):
    current_teacher_id = current_teacher.teacher_id
    try:
        ResourceCollectionService.delete_resource_permanently(collection_id, current_teacher_id)
        return jsonify({
            "success": True, 
            "message": "Resource and all associated data wiped permanently."
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
    

@resource_collection_bp.route('/<int:collection_id>/restore/<int:version_id>', methods=['POST'])
@verification_required
def restore_resource_version_route(current_teacher, collection_id, version_id):
    try:
        current_teacher_id = current_teacher.teacher_id

        resource = ResourceCollection.query.get(collection_id)
        if not resource:
            return jsonify({"success": False, "error": "Resource not found"}), 404
        
        result = ResourceCollectionService.restore_resource(
            collection_id=collection_id, 
            target_version_id=version_id,
            teacher_id=current_teacher_id
        )

        if "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 400
        
        return jsonify({
            "success": True,
            "message": result["message"]
        }), 200
    
    except Exception as e:
        print(f"Error restoring version {version_id} for collection {collection_id}: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500
    

@resource_collection_bp.route('/<int:collection_id>/approve/<int:version_id>', methods=['POST'])
@verification_required
def approve_version_route(current_teacher, collection_id, version_id):
    try:
        result = ResourceCollectionService.approve_version(
            collection_id=collection_id,
            version_id=version_id,
            owner_id=current_teacher.teacher_id
        )
        return jsonify({
            "success": True,
            **result
        }), 200
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        print(f"Error approving version {version_id}: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@resource_collection_bp.route('/<int:collection_id>/reject/<int:version_id>', methods=['POST'])
@verification_required
def reject_version_route(current_teacher, collection_id, version_id):
    try:
        result = ResourceCollectionService.reject_version(
            collection_id=collection_id,
            version_id=version_id,
            owner_id=current_teacher.teacher_id
        )
        return jsonify({
            "success": True,
            **result
        }), 200
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        print(f"Error rejecting version {version_id}: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@resource_collection_bp.route('/<int:id>/review', methods=['POST'])
@verification_required
def post_review(current_teacher, id):
    try:
        data = request.get_json()
        
        result = InteractionService.add_review(
            collection_id=id,
            teacher_id=current_teacher.teacher_id,
            data=data
        )

        return jsonify({
            "success": True,
            "data": result,
            "message": "Review submitted successfully"
        }), 201

    except Exception as e:
        traceback.print_exc() 
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    

@resource_collection_bp.route('/<int:id>/like', methods=['POST'])
@verification_required
def toggle_resource_like(current_teacher, id):
    try:
        # Check if the resource actually exists first
        resource = ResourceCollection.query.get(id)
        if not resource:
            return jsonify({"success": False, "error": "Resource not found"}), 404

        result = InteractionService.toggle_like(
            collection_id=id,
            teacher_id=current_teacher.teacher_id
        )

        return jsonify({
            "success": True,
            "liked": result["liked"],
            "message": result["message"]
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@resource_collection_bp.route('/<int:collection_id>/download', methods=['POST'])
@verification_required
def track_download(current_teacher, collection_id):
    try:
        new_count = InteractionService.increment_download_count(collection_id, downloader_id=current_teacher.teacher_id)
        return jsonify({
            "success": True,
            "download_count": new_count
        }), 200
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": "Internal server error"}), 500

@resource_collection_bp.route('/eligible-for-collab', methods=['GET'])
@verification_required
def get_eligible_for_collab_route(current_teacher):
    try:
        # Fetch all resources owned by the user
        owned_resources = ResourceCollection.query.filter_by(owner_id=current_teacher.teacher_id).all()

        results = []
        for r in owned_resources:
            # Check if collaboration is explicitly enabled
            mode = str(r.collaboration_mode).strip().lower() if r.collaboration_mode else 'none'
            
            results.append({
                "collection_id": r.collection_id,
                "title": r.title,
                "subject": r.subject.subject_name if r.subject else "General",
                "grade": r.grade_level.grade_name if r.grade_level else "All Grades",
                "collaboration_mode": r.collaboration_mode,
                "is_eligible": (mode != 'none' and not r.is_hidden)
            })
        
        return jsonify({
            "success": True, 
            "resources": results
        }), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@resource_collection_bp.route('/<int:collection_id>/collaborators', methods=['POST'])
@verification_required
def add_collaborator_route(current_teacher, collection_id):
    try:
        data = request.get_json()
        target_teacher_id = data.get('teacher_id')
        role = data.get('role', 'editor')
        
        if not target_teacher_id:
            return jsonify({"success": False, "error": "teacher_id is required"}), 400
            
        ResourceCollectionService.add_collaborator(
            collection_id=collection_id,
            teacher_id=target_teacher_id,
            role=role,
            owner_id=current_teacher.teacher_id
        )
        
        return jsonify({"success": True, "message": "Collaborator added successfully"}), 201
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@resource_collection_bp.route('/<int:collection_id>/collaborators/<int:teacher_id>', methods=['DELETE'])
@verification_required
def remove_collaborator_route(current_teacher, collection_id, teacher_id):
    try:
        ResourceCollectionService.remove_collaborator(
            collection_id=collection_id,
            teacher_id=teacher_id,
            owner_id=current_teacher.teacher_id
        )
        return jsonify({"success": True, "message": "Collaborator removed successfully"}), 200
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@resource_collection_bp.route('/<int:collection_id>/collaborators/<int:teacher_id>', methods=['PATCH'])
@verification_required
def update_collaborator_role_route(current_teacher, collection_id, teacher_id):
    try:
        data = request.get_json()
        new_role = data.get('role')
        
        if not new_role:
            return jsonify({"success": False, "error": "role is required"}), 400
            
        ResourceCollectionService.update_collaborator_role(
            collection_id=collection_id,
            teacher_id=teacher_id,
            new_role=new_role,
            owner_id=current_teacher.teacher_id
        )
        return jsonify({"success": True, "message": "Collaborator role updated successfully"}), 200
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500