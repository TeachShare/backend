import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.resource_collection_service import ResourceCollectionService
from services.file_service import AppwriteService
from models import ResourceCollection

resource_collection_bp = Blueprint('resource_collection', __name__)
appwrite_service = AppwriteService()

@resource_collection_bp.route('/create_resources', methods=['POST'])
@jwt_required()
def create_resource_route():
    try:
        current_teacher_id = get_jwt_identity()

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
    

@resource_collection_bp.route('/my_resources', methods=['GET'])
@jwt_required()
def get_my_resources():
    try:
        curr_teacher_id = int(get_jwt_identity())

        resources = ResourceCollectionService.get_my_resources(curr_teacher_id)

        return jsonify({
            "success": True,
            "data": resources
        }), 200
    
    except Exception as e:
        print(f"Error fetching my resources: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500
    

@resource_collection_bp.route('/<int:collection_id>', methods=['GET'])
@jwt_required()
def get_resource_detail_route(collection_id):
    try:
        resource = ResourceCollectionService.get_resource_by_id(collection_id)
        
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
@jwt_required()
def update_resource_route(collection_id):
    try:
        current_teacher_id = int(get_jwt_identity()) 

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
@jwt_required()
def get_resource_history_route(collection_id):
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
@jwt_required()
def get_comparison_data(v1_id, v2_id):
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
@jwt_required()
def discover_resources_route():
    current_teacher_id = int(get_jwt_identity())
    resources = ResourceCollectionService.get_discover_resources(current_teacher_id)
    return jsonify({"success": True, "data": resources}), 200


@resource_collection_bp.route('/remix/<int:collection_id>', methods=['POST'])
@jwt_required()
def remix_resource_route(collection_id):
    current_teacher_id = int(get_jwt_identity())
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
@jwt_required()
def delete_resource_permanently_route(collection_id):
    current_teacher_id = int(get_jwt_identity())
    try:
        ResourceCollectionService.delete_resource_permanently(collection_id, current_teacher_id)
        return jsonify({
            "success": True, 
            "message": "Resource and all associated data wiped permanently."
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400