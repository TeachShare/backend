import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.resource_collection_service import ResourceCollectionService
from services.file_service import AppwriteService
from services.interaction_service import InteractionService
from models import ResourceCollection,db

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
             metadata = appwrite_service.upload_file(file_obj)
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
def get_my_resources(current_teacher):
    try:

        filters = {
            "search": request.args.get('search'),
            "subject_id": request.args.get('subject_id', type=int),
            "grade_level_id": request.args.get('grade_level_id', type=int),
            "content_type_id": request.args.get('content_type_id', type=int),
            "status": request.args.get('status')
        }

        resources = ResourceCollectionService.get_my_resources(
            current_teacher.teacher_id,
            filters
        )

        return jsonify({
            "success": True,
            "data": resources,
            "count": len(resources)
        }), 200
    
    except Exception as e:
        traceback.print_exc() 
        return jsonify({"success": False, "error": str(e)}), 500
    

@resource_collection_bp.route('/<int:collection_id>', methods=['GET'])
@verification_required
def get_resource_detail_route(current_teacher,collection_id):
    try:
        resource = ResourceCollectionService.get_resource_by_id(collection_id, current_user_id=current_teacher.teacher_id)
        
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

        original_resource = ResourceCollection.query.get(collection_id)
        
        if not original_resource:
            return jsonify({"success": False, "error": "Original resource not found"}), 404
            
        if original_resource.owner_id != current_teacher_id:
            return jsonify({
                "success": False, 
                "error": "Unauthorized: You can only create versions of your own resources."
            }), 403

        data_string = request.form.get('resource_data')
        if not data_string:
            return jsonify({"success": False, "error": "Missing resource_data payload"}), 400
        
        data = json.loads(data_string)
        
        uploaded_files = request.files.getlist('files')
        new_file_metadata = []
        
        for file_obj in uploaded_files:
            if file_obj.filename != '':
                metadata = appwrite_service.upload_file(file_obj)
                new_file_metadata.append(metadata)

        newly_spawned_resource = ResourceCollectionService.update_resource(
            old_collection_id=collection_id,
            data=data,
            new_files_info=new_file_metadata
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

@resource_collection_bp.route('/compare/<int:v1_id>/<int:v2_id>', methods=['GET'])
@verification_required
def get_comparison_data(current_teacher, v1_id, v2_id):
    try:
        # Fetch any two snapshots from your immutable collection
        version_a = ResourceCollectionService.get_resource_by_id(v1_id)
        version_b = ResourceCollectionService.get_resource_by_id(v2_id)
        
        if not version_a or not version_b:
            return jsonify({"success": False, "error": "Version not found"}), 404

        return jsonify({
            "success": True,
            "v1": version_a, # The historical snapshot
            "v2": version_b  # Usually the latest reference
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@resource_collection_bp.route('/discover', methods=['GET'])
@verification_required
def discover_resources_route(current_teacher):
    current_teacher_id = current_teacher.teacher_id
    resources = ResourceCollectionService.get_discover_resources(current_teacher_id)
    return jsonify({"success": True, "data": resources}), 200


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
        
        if resource.owner_id != current_teacher_id:
            return jsonify({
                "success": False, 
                "error": "Unauthorized: You can only restore your own resources."
            }), 403
        
        result = ResourceCollectionService.restore_resource(collection_id, version_id)

        if "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 400
        
        return jsonify({
            "success": True,
            "message": result["message"]
        }), 200
    
    except Exception as e:
        print(f"Error restoring version {version_id} for collection {collection_id}: {e}")
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