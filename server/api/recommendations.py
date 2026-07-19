from flask import Blueprint, jsonify, request


def create_recommendations_api(recommendation_engine) -> Blueprint:
    recommendations_api = Blueprint('runtime_recommendations_api', __name__)

    @recommendations_api.route('/recommendations', methods=['GET'])
    def recommendations():
        results = recommendation_engine.search(request.args.to_dict(flat=True))
        return jsonify({"count": len(results), "results": results}), 200

    return recommendations_api